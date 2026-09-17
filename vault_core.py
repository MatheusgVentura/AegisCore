import os
import json
import math
import uuid
import secrets
import string
import shutil
import sys
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
            if "id" not in item:
                item["id"] = uuid.uuid4().hex[:12]
            if "url" not in item:
                item["url"] = ""
            if "notas" not in item:
                item["notas"] = ""
            if "favorito" not in item:
                item["favorito"] = False
            if "criado_em" not in item:
                item["criado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
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
                "favorito": info.get("favorito", False),
                "criado_em": info.get("criado_em", datetime.now().strftime("%d/%m/%Y %H:%M")),
            })
        return lista_migrada

    return []


def carregar_cofre(senha_mestra: str, vault_path: str = VAULT_FILE) -> tuple[list[dict], bytes, bytes]:
    """
    Carrega e descriptografa o cofre de senhas existente.
    Retorna (lista_de_entradas, chave_derivada, salt).
    Lança FileNotFoundError se não existir o arquivo, ou InvalidTag se senha incorreta.
    """
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


def inicializar_novo_cofre(senha_mestra: str, vault_path: str = VAULT_FILE) -> tuple[list[dict], bytes, bytes]:
    """Inicializa um novo arquivo de cofre criptografado com a senha mestra fornecida."""
    salt = os.urandom(16)
    chave = derivar_chave(senha_mestra, salt)
    cofre: list[dict] = []
    salvar_cofre(cofre, chave, salt, vault_path=vault_path)
    return cofre, chave, salt


def salvar_cofre(cofre: list[dict], chave: bytes, salt: bytes, vault_path: str = VAULT_FILE) -> None:
    """
    Salva o cofre de forma 100% atômica e segura contra quedas de energia e falhas.
    Cria automaticamente um backup prévio (vault.enc.bak).
    """
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
