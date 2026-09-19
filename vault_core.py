import os
import json
import math
import uuid
import secrets
import string
import shutil
import sys
import time
import hmac
import hashlib
import struct
import base64
import re
import csv
import io
from datetime import datetime
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


def get_data_dir() -> str:
    """
    Retorna o diretório de persistência dos dados do cofre.
    Prioridades:
    1. Se houver um arquivo 'portable.dat' na pasta do executável, força modo 100% portátil local.
    2. Utiliza %APPDATA%/AegisCore como padrão seguro no Windows (evita perdas em rebuilds ou limpezas).
    3. Se ainda não houver cofre no APPDATA mas houver na pasta do app, migra/copia automaticamente.
    """
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    # Modo portátil explícito (ex: pendrive ou pasta isolada)
    if os.path.exists(os.path.join(app_dir, "portable.dat")):
        return app_dir

    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    vault_dir = os.path.join(appdata, "AegisCore")
    os.makedirs(vault_dir, exist_ok=True)

    appdata_vault = os.path.join(vault_dir, "vault.enc")
    local_vault = os.path.join(app_dir, "vault.enc")

    # Migração automática e transparente de cofre legado local se ainda não existir no APPDATA
    if not os.path.exists(appdata_vault) and os.path.exists(local_vault):
        try:
            shutil.copy2(local_vault, appdata_vault)
            bak = os.path.join(app_dir, "vault.enc.bak")
            if os.path.exists(bak):
                shutil.copy2(bak, os.path.join(vault_dir, "vault.enc.bak"))
        except Exception:
            return app_dir

    return vault_dir


BASE_DIR = get_data_dir()
VAULT_FILE = os.path.join(BASE_DIR, "vault.enc")
BACKUP_FILE = os.path.join(BASE_DIR, "vault.enc.bak")


def derivar_chave(senha_mestra: str, salt: bytes) -> bytes:
    """Deriva uma chave AES-256 de 32 bytes usando Argon2id."""
    kdf = Argon2id(
        salt=salt,
        length=32,
        iterations=4,
        lanes=4,
        memory_cost=64 * 1024,  # 64 MB RAM
    )
    return kdf.derive(senha_mestra.encode("utf-8"))


def normalizar_cofre(dados_descriptografados: any) -> list[dict]:
    """
    Garante que o cofre seja sempre uma lista de objetos padronizados,
    mantendo compatibilidade retroativa com a versão anterior baseada em dicionário.
    """
    if isinstance(dados_descriptografados, list):
        for item in dados_descriptografados:
            if "id" not in item or not item.get("id"):
                item["id"] = uuid.uuid4().hex[:12]
            if "url" not in item or item.get("url") is None:
                item["url"] = ""
            if "notas" not in item or item.get("notas") is None:
                item["notas"] = ""
            if "favorito" not in item or item.get("favorito") is None:
                item["favorito"] = False
            if "totp_secret" not in item or item.get("totp_secret") is None:
                item["totp_secret"] = ""
            if "criado_em" not in item or not item.get("criado_em"):
                item["criado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            if "atualizado_em" not in item or not item.get("atualizado_em"):
                item["atualizado_em"] = item.get("criado_em", "")
        return dados_descriptografados

    if isinstance(dados_descriptografados, dict):
        lista_migrada = []
        for servico, info in dados_descriptografados.items():
            lista_migrada.append({
                "id": uuid.uuid4().hex[:12],
                "servico": servico,
                "usuario": info.get("usuario", ""),
                "senha": info.get("senha", ""),
                "url": info.get("url", ""),
                "notas": info.get("notas", ""),
                "totp_secret": info.get("totp_secret", ""),
                "favorito": info.get("favorito", False),
                "criado_em": info.get("criado_em", datetime.now().strftime("%d/%m/%Y %H:%M")),
                "atualizado_em": info.get("atualizado_em", datetime.now().strftime("%d/%m/%Y %H:%M")),
            })
        return lista_migrada

    return []


def carregar_cofre(senha_mestra: str, vault_path: str | None = None) -> tuple[list[dict], bytes, bytes]:
    """
    Carrega e descriptografa o cofre de senhas existente.
    Retorna (lista_de_entradas, chave_derivada, salt).
    Lança FileNotFoundError se não existir o arquivo, ou InvalidTag se senha incorreta.
    """
    if vault_path is None:
        vault_path = VAULT_FILE

    if not os.path.exists(vault_path):
        raise FileNotFoundError(f"Arquivo '{vault_path}' não encontrado.")

    with open(vault_path, "rb") as f:
        dados = f.read()

    # Cabeçalho mínimo: Salt (16) + Nonce (12) + Tag GCM (16) = 44 bytes
    if len(dados) < 44:
        raise ValueError("Arquivo de cofre corrompido ou incompleto (menos de 44 bytes).")

    salt = dados[:16]
    nonce = dados[16:28]
    ciphertext = dados[28:]

    chave = derivar_chave(senha_mestra, salt)
    aesgcm = AESGCM(chave)

    conteudo_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    dados_json = json.loads(conteudo_bytes.decode("utf-8"))
    cofre = normalizar_cofre(dados_json)

    return cofre, chave, salt


def inicializar_novo_cofre(senha_mestra: str, vault_path: str | None = None) -> tuple[list[dict], bytes, bytes]:
    """Inicializa um novo arquivo de cofre criptografado com a senha mestra fornecida."""
    if vault_path is None:
        vault_path = VAULT_FILE

    salt = os.urandom(16)
    chave = derivar_chave(senha_mestra, salt)
    cofre: list[dict] = []
    salvar_cofre(cofre, chave, salt, vault_path=vault_path)
    return cofre, chave, salt


def salvar_cofre(cofre: list[dict], chave: bytes, salt: bytes, vault_path: str | None = None) -> None:
    """
    Salva o cofre de forma 100% atômica e segura contra quedas de energia e falhas.
    Cria automaticamente um backup prévio (vault.enc.bak).
    """
    if vault_path is None:
        vault_path = VAULT_FILE

    aesgcm = AESGCM(chave)
    nonce = os.urandom(12)
    conteudo_bytes = json.dumps(cofre, ensure_ascii=False, indent=2).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, conteudo_bytes, None)

    pacote_completo = salt + nonce + ciphertext
    temp_path = f"{vault_path}.tmp"

    # 1. Escreve primeiro no arquivo temporário com flush e fsync
    with open(temp_path, "wb") as f:
        f.write(pacote_completo)
        f.flush()
        os.fsync(f.fileno())

    # 2. Faz backup automático do cofre anterior, se existir
    if os.path.exists(vault_path):
        shutil.copy2(vault_path, f"{vault_path}.bak")

    # 3. Substituição atômica no sistema de arquivos
    os.replace(temp_path, vault_path)


def gerar_senha_forte(
    tamanho: int = 24,
    usar_maiusculas: bool = True,
    usar_minusculas: bool = True,
    usar_numeros: bool = True,
    usar_simbolos: bool = True,
) -> str:
    """Gera uma senha com entropia criptograficamente segura via secrets."""
    pools = []
    if usar_maiusculas:
        pools.append(string.ascii_uppercase)
    if usar_minusculas:
        pools.append(string.ascii_lowercase)
    if usar_numeros:
        pools.append(string.digits)
    if usar_simbolos:
        pools.append("!@#$%^&*()_+-=[]{}|;:,.<>?")

    if not pools:
        pools.append(string.ascii_letters + string.digits)

    # Garante pelo menos um caractere de cada pool selecionado
    senha_chars = [secrets.choice(p) for p in pools]

    # Preenche o restante aleatoriamente
    alfabeto_completo = "".join(pools)
    while len(senha_chars) < tamanho:
        senha_chars.append(secrets.choice(alfabeto_completo))

    # Embaralha com CSPRNG
    rng = secrets.SystemRandom()
    rng.shuffle(senha_chars)
    return "".join(senha_chars)


def calcular_entropia(senha: str) -> dict:
    """Calcula a entropia em bits e classificação da senha."""
    if not senha:
        return {"bits": 0, "nivel": "Vazia", "cor": "#64748b", "percentual": 0}

    pool_size = 0
    if any(c in string.ascii_lowercase for c in senha):
        pool_size += 26
    if any(c in string.ascii_uppercase for c in senha):
        pool_size += 26
    if any(c in string.digits for c in senha):
        pool_size += 10
    if any(c not in string.ascii_letters and c not in string.digits for c in senha):
        pool_size += 32

    if pool_size == 0:
        pool_size = 1

    bits = len(senha) * math.log2(pool_size)

    if bits < 40:
        return {"bits": round(bits, 1), "nivel": "Vulnerável", "cor": "#f43f5e", "percentual": 25}
    elif bits < 60:
        return {"bits": round(bits, 1), "nivel": "Moderada", "cor": "#f59e0b", "percentual": 50}
    elif bits < 80:
        return {"bits": round(bits, 1), "nivel": "Forte", "cor": "#10b981", "percentual": 75}
    else:
        return {"bits": round(bits, 1), "nivel": "Impenetrável", "cor": "#06b6d4", "percentual": 100}


def gerar_totp(secret: str, timestamp: int | None = None) -> dict:
    """
    Gera token TOTP (RFC 6238 / RFC 4226) de 6 dígitos sem dependências externas.
    Suporta segredos Base32 puros ou URLs no formato otpauth://totp/...
    """
    if not secret:
        return {"code": "", "remaining": 0, "valid": False}

    # Se for uma URL otpauth, extrai o parâmetro secret
    m = re.search(r"[?&]secret=([A-Za-z2-7=]+)", secret, re.IGNORECASE)
    clean_secret = m.group(1) if m else secret
    clean_secret = clean_secret.strip().replace(" ", "").replace("-", "").upper()

    if not clean_secret:
        return {"code": "", "remaining": 0, "valid": False}

    try:
        # Preenche com padding Base32 '=' se faltar
        padding = (8 - len(clean_secret) % 8) % 8
        clean_secret += "=" * padding
        key = base64.b32decode(clean_secret, casefold=True)

        t = int(time.time()) if timestamp is None else timestamp
        remaining = 30 - (t % 30)
        counter = t // 30
        counter_bytes = struct.pack(">Q", counter)

        digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        code = (
            (digest[offset] & 0x7F) << 24
            | (digest[offset + 1] & 0xFF) << 16
            | (digest[offset + 2] & 0xFF) << 8
            | (digest[offset + 3] & 0xFF)
        ) % 1_000_000

        return {
            "code": f"{code:06d}",
            "remaining": remaining,
            "valid": True,
        }
    except Exception:
        return {"code": "INVÁLIDO", "remaining": 0, "valid": False}


def analisar_saude_cofre(cofre: list[dict]) -> dict:
    """
    Executa auditoria de segurança e calcula a pontuação de resiliência do cofre (0 a 100).
    Critérios com pesos calibrados de segurança:
    - Senhas fracas / baixa entropia (< 60 bits): penalidade proporcional de até 35 pontos.
    - Senhas reutilizadas: penalidade proporcional de até 35 pontos.
    - Ausência de segundo fator (2FA / TOTP): penalidade proporcional de até 25 pontos.
    """
    total = len(cofre) if cofre else 0
    if total == 0:
        return {
            "score": 100,
            "total": 0,
            "fracas_count": 0,
            "fracas_ids": [],
            "reutilizadas_count": 0,
            "reutilizadas_ids": [],
            "com_totp_count": 0,
            "com_totp_ids": [],
            "sem_totp_count": 0,
            "sem_totp_ids": [],
            "fortes_count": 0,
            "fortes_ids": [],
            "status_seguranca": "Status: Sem Credenciais",
            "nivel_blindagem": "Status: Sem Credenciais",
            "cor_status": "#10b981",
            "cor_blindagem": "#10b981",
            "resumo": "Nenhuma credencial cadastrada no cofre no momento.",
        }

    fracas_ids = []
    fortes_ids = []
    passwords_map: dict[str, list[str]] = {}
    com_totp_ids = []
    sem_totp_ids = []

    for item in cofre:
        eid = str(item.get("id") or "")
        pwd = str(item.get("senha") or "")
        totp = str(item.get("totp_secret") or "").strip()

        # Análise de entropia (limiar seguro da indústria: 60 bits)
        entropy = calcular_entropia(pwd)
        if entropy["bits"] < 60:
            fracas_ids.append(eid)
        else:
            fortes_ids.append(eid)

        # Segundo fator (2FA / TOTP)
        if totp:
            com_totp_ids.append(eid)
        else:
            sem_totp_ids.append(eid)

        # Mapeamento para detecção de reuso
        if pwd.strip():
            if pwd not in passwords_map:
                passwords_map[pwd] = []
            passwords_map[pwd].append(eid)

    reutilizadas_ids = []
    for pwd, eids in passwords_map.items():
        if len(eids) > 1:
            reutilizadas_ids.extend(eids)
    reutilizadas_ids = list(set(reutilizadas_ids))

    # Cálculo da pontuação calibrada de resiliência (0 a 100)
    fracas_ratio = len(fracas_ids) / total
    reutilizadas_ratio = len(reutilizadas_ids) / total
    totp_ratio = len(com_totp_ids) / total

    # Pesos dos pilares de segurança:
    penalidade_fracas = fracas_ratio * 35.0
    penalidade_reuso = reutilizadas_ratio * 35.0
    penalidade_sem_totp = (1.0 - totp_ratio) * 25.0

    score = round(100.0 - penalidade_fracas - penalidade_reuso - penalidade_sem_totp)
    score = max(5, min(100, score))

    if score >= 90:
        status_seguranca = "Status: Excelente (Alta Resiliência)"
        cor_status = "#10b981"
        resumo = "Seu cofre apresenta alta resiliência criptográfica, senhas exclusivas e ampla cobertura de autenticação multifator."
    elif score >= 75:
        status_seguranca = "Status: Forte (Boa Resiliência)"
        cor_status = "#06b6d4"
        resumo = "Seu cofre possui boa segurança geral, com oportunidades pontuais de melhoria em 2FA ou complexidade."
    elif score >= 50:
        status_seguranca = "Status: Atenção Requerida (Resiliência Moderada)"
        cor_status = "#b89153"
        resumo = "Foram identificadas vulnerabilidades como senhas fracas, reutilizadas ou baixa adoção de autenticação em duas etapas."
    else:
        status_seguranca = "Status: Crítico (Vulnerável)"
        cor_status = "#f43f5e"
        resumo = "Ação imediata recomendada. Existem senhas de baixa entropia ou reutilizadas expondo suas contas a risco de comprometimento."

    return {
        "score": score,
        "total": total,
        "fracas_count": len(fracas_ids),
        "fracas_ids": fracas_ids,
        "reutilizadas_count": len(reutilizadas_ids),
        "reutilizadas_ids": reutilizadas_ids,
        "com_totp_count": len(com_totp_ids),
        "com_totp_ids": com_totp_ids,
        "sem_totp_count": len(sem_totp_ids),
        "sem_totp_ids": sem_totp_ids,
        "fortes_count": len(fortes_ids),
        "fortes_ids": fortes_ids,
        "status_seguranca": status_seguranca,
        "nivel_blindagem": status_seguranca,
        "cor_status": cor_status,
        "cor_blindagem": cor_status,
        "resumo": resumo,
    }


def importar_csv(conteudo_csv: str) -> tuple[list[dict], int]:
    """
    Importa credenciais de um texto CSV, detectando automaticamente formatos comuns:
    - Google Chrome / Edge / Brave (name, url, username, password, note)
    - Bitwarden (folder, favorite, type, name, notes, login_uri, login_username, login_password, login_totp)
    - KeePassXC (Group, Title, Username, Password, URL, Notes, TOTP)
    - Formatos genéricos compatíveis.
    Retorna (lista_de_novos_registros, quantidade_importada).
    """
    if not conteudo_csv or not conteudo_csv.strip():
        return [], 0

    f = io.StringIO(conteudo_csv.strip())
    # Usa Sniffer para detectar delimitador (vírgula ou ponto-e-vírgula)
    try:
        sample = conteudo_csv[:2048]
        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
    except Exception:
        dialect = "excel"

    f.seek(0)
    reader = csv.DictReader(f, dialect=dialect)
    if not reader.fieldnames:
        return [], 0

    novos_itens = []
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    for row in reader:
        # Cria mapa normalizado de colunas em minúsculas
        cols = {k.lower().strip(): (v.strip() if v else "") for k, v in row.items() if k}

        # Reconhecimento do Serviço / Nome
        servico = (
            cols.get("name")
            or cols.get("title")
            or cols.get("serviço")
            or cols.get("servico")
            or cols.get("service")
            or cols.get("group")
            or ""
        )

        # Reconhecimento do Usuário
        usuario = (
            cols.get("login_username")
            or cols.get("username")
            or cols.get("usuário")
            or cols.get("usuario")
            or cols.get("user")
            or cols.get("email")
            or cols.get("login")
            or ""
        )

        # Reconhecimento da Senha
        senha = (
            cols.get("login_password")
            or cols.get("password")
            or cols.get("senha")
            or cols.get("pass")
            or ""
        )

        # Reconhecimento da URL
        url = (
            cols.get("login_uri")
            or cols.get("url")
            or cols.get("website")
            or cols.get("link")
            or ""
        )

        # Reconhecimento de Notas
        notas = (
            cols.get("notes")
            or cols.get("note")
            or cols.get("notas")
            or cols.get("observações")
            or cols.get("observacoes")
            or ""
        )

        # Reconhecimento de TOTP
        totp_secret = (
            cols.get("login_totp")
            or cols.get("totp")
            or cols.get("totp_secret")
            or cols.get("2fa")
            or cols.get("otp")
            or ""
        )

        # Se não tiver serviço nem senha, ignora a linha
        if not servico and not senha:
            continue

        if not servico:
            servico = url or usuario or "Credencial Importada"

        novos_itens.append({
            "id": uuid.uuid4().hex[:12],
            "servico": servico,
            "usuario": usuario,
            "senha": senha,
            "url": url,
            "notas": notas,
            "totp_secret": totp_secret,
            "favorito": False,
            "criado_em": agora,
            "atualizado_em": agora,
        })

    return novos_itens, len(novos_itens)


def exportar_csv(cofre: list[dict]) -> str:
    """
    Gera uma exportação no padrão CSV universal RFC 4180 de todas as credenciais do cofre.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Cabeçalho
    writer.writerow(["Servico", "Usuario", "Senha", "URL", "Notas", "TOTP_Secret", "Favorito", "Criado_Em"])

    for item in cofre:
        writer.writerow([
            str(item.get("servico") or ""),
            str(item.get("usuario") or ""),
            str(item.get("senha") or ""),
            str(item.get("url") or ""),
            str(item.get("notas") or ""),
            str(item.get("totp_secret") or ""),
            "1" if item.get("favorito") else "0",
            str(item.get("criado_em") or ""),
        ])

    return output.getvalue()

