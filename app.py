"""
AegisCore — Password Vault Engine
Motor Criptográfico: Argon2id (KDF 64MB) + AES-256-GCM (AEAD)
Persistência Atômica com Backup e Higienização de Memória
"""

import os
import sys
import uuid
import threading
import webbrowser
from datetime import datetime
import pyperclip
import webview
from cryptography.exceptions import InvalidTag

import vault_core


class VaultApi:
    """API exposta para a interface Web HUD via pywebview."""

    def __init__(self):
        # Variáveis internas privadas prefixadas com '_' para não serem inspecionadas pelo JS bridge
        self._cofre: list[dict] = []
        self._chave: bytes = b""
        self._salt: bytes = b""
        self._clipboard_timer: threading.Timer | None = None
        self._last_copied_sensitive: str = ""
        self._window = None

    def set_window(self, window):
        """Define a referência para a janela ativa do pywebview para diálogos do sistema."""
        self._window = window

    def check_vault_status(self) -> dict:
        """Verifica se o cofre local já foi criado no disco."""
        exists = os.path.exists(vault_core.VAULT_FILE)
        return {
            "exists": exists,
            "unlocked": len(self._chave) > 0,
        }

    def unlock_vault(self, senha_mestra: str) -> dict:
        """Descriptografa o cofre usando a senha mestra."""
        if not senha_mestra:
            return {"success": False, "error": "Senha mestra não pode ser vazia."}

        try:
            cofre, chave, salt = vault_core.carregar_cofre(senha_mestra)
            self._cofre = cofre
            self._chave = chave
            self._salt = salt
            return {"success": True, "entries": self._cofre}
        except InvalidTag:
            return {
                "success": False,
                "error": "Senha incorreta ou integridade do cofre violada.",
            }
        except FileNotFoundError:
            return {"success": False, "error": "Arquivo de cofre não encontrado."}
        except Exception as e:
            return {"success": False, "error": f"Erro ao descriptografar: {str(e)}"}

    def create_vault(self, senha_mestra: str) -> dict:
        """Inicializa um novo cofre com senha mestra confirmada."""
        if not senha_mestra:
            return {"success": False, "error": "A senha mestra não pode ser vazia."}

        try:
            cofre, chave, salt = vault_core.inicializar_novo_cofre(senha_mestra)
            self._cofre = cofre
            self._chave = chave
            self._salt = salt
            return {"success": True, "entries": self._cofre}
        except Exception as e:
            return {"success": False, "error": f"Erro ao criar cofre: {str(e)}"}

    def lock_vault(self) -> dict:
        """Higieniza dados sensíveis da memória RAM e bloqueia a sessão."""
        self._cofre = []
        self._chave = b""
        self._salt = b""
        if self._clipboard_timer:
            self._clipboard_timer.cancel()
            self._clipboard_timer = None
        return {"success": True}

    def save_entry(self, entry_data: dict) -> dict:
        """Adiciona ou atualiza uma credencial de forma atômica."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}

        entry_id = entry_data.get("id")
        servico = str(entry_data.get("servico") or "").strip()
        usuario = str(entry_data.get("usuario") or "").strip()
        senha = str(entry_data.get("senha") or "")
        url = str(entry_data.get("url") or "").strip()
        notas = str(entry_data.get("notas") or "").strip()
        totp_secret = str(entry_data.get("totp_secret") or "").strip()

        if not servico or not senha:
            return {"success": False, "error": "Serviço e Senha são obrigatórios."}

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        if entry_id:
            # Atualização de registro existente
            encontrado = False
            for item in self._cofre:
                if item["id"] == entry_id:
                    item["servico"] = servico
                    item["usuario"] = usuario
                    item["senha"] = senha
                    item["url"] = url
                    item["notas"] = notas
                    item["totp_secret"] = totp_secret
                    if "favorito" in entry_data:
                        item["favorito"] = bool(entry_data["favorito"])
                    item["atualizado_em"] = agora
                    encontrado = True
                    break
            if not encontrado:
                return {"success": False, "error": "Registro não encontrado."}
        else:
            # Novo registro
            novo = {
                "id": uuid.uuid4().hex[:12],
                "servico": servico,
                "usuario": usuario,
                "senha": senha,
                "url": url,
                "notas": notas,
                "totp_secret": totp_secret,
                "favorito": bool(entry_data.get("favorito", False)),
                "criado_em": agora,
                "atualizado_em": agora,
            }
            self._cofre.append(novo)

        # Salva atomicamente no disco
        try:
            vault_core.salvar_cofre(self._cofre, self._chave, self._salt)
            return {"success": True, "entries": self._cofre}
        except Exception as e:
            return {"success": False, "error": f"Falha ao persistir cofre: {str(e)}"}

    def open_url(self, url: str) -> dict:
        """Abre uma URL no navegador padrão do sistema operacional com segurança."""
        if not url:
            return {"success": False, "error": "URL não informada."}
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        try:
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def toggle_favorite(self, entry_id: str) -> dict:
        """Alterna o status de favorito de uma credencial e salva atomicamente."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}

        encontrado = False
        for item in self._cofre:
            if item["id"] == entry_id:
                item["favorito"] = not item.get("favorito", False)
                encontrado = True
                break

        if not encontrado:
            return {"success": False, "error": "Credencial não encontrada."}

        try:
            vault_core.salvar_cofre(self._cofre, self._chave, self._salt)
            return {"success": True, "entries": self._cofre}
        except Exception as e:
            return {"success": False, "error": f"Falha ao persistir favorito: {str(e)}"}

    def reorder_entries(self, ordered_ids: list[str]) -> dict:
        """Reordena o cofre conforme a ordem manual do drag-and-drop e salva atomicamente."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}

        id_map = {item["id"]: item for item in self._cofre}
        nova_ordem = []
        for eid in ordered_ids:
            if eid in id_map:
                nova_ordem.append(id_map[eid])

        # Adiciona por segurança qualquer item que não estava na lista recebida
        for item in self._cofre:
            if item["id"] not in ordered_ids:
                nova_ordem.append(item)

        self._cofre = nova_ordem

        try:
            vault_core.salvar_cofre(self._cofre, self._chave, self._salt)
            return {"success": True, "entries": self._cofre}
        except Exception as e:
            return {"success": False, "error": f"Falha ao persistir nova ordem: {str(e)}"}

    def delete_entry(self, entry_id: str) -> dict:
        """Remove uma credencial por ID e persiste atomicamente."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}

        self._cofre = [item for item in self._cofre if item["id"] != entry_id]

        try:
            vault_core.salvar_cofre(self._cofre, self._chave, self._salt)
            return {"success": True, "entries": self._cofre}
        except Exception as e:
            return {"success": False, "error": f"Falha ao persistir cofre: {str(e)}"}

    def generate_password(
        self,
        length: int = 24,
        upper: bool = True,
        lower: bool = True,
        digits: bool = True,
        symbols: bool = True,
    ) -> dict:
        """Gera uma senha forte e calcula sua entropia em tempo real."""
        pwd = vault_core.gerar_senha_forte(
            tamanho=length,
            usar_maiusculas=upper,
            usar_minusculas=lower,
            usar_numeros=digits,
            usar_simbolos=symbols,
        )
        entropy = vault_core.calcular_entropia(pwd)
        return {"password": pwd, "entropy": entropy}

    def calculate_entropy(self, pwd: str) -> dict:
        """Calcula a entropia da string informada."""
        return vault_core.calcular_entropia(pwd)

    def copy_to_clipboard(self, text: str, is_sensitive: bool = True) -> dict:
        """Copia para o clipboard e inicia timer de higienização de 15 segundos se for sensível."""
        try:
            pyperclip.copy(text)
        except Exception as e:
            return {"success": False, "error": str(e)}

        if is_sensitive:
            self._last_copied_sensitive = text
            if self._clipboard_timer:
                self._clipboard_timer.cancel()

            def limpar():
                try:
                    if pyperclip.paste() == self._last_copied_sensitive:
                        pyperclip.copy("")
                except Exception:
                    pass

            self._clipboard_timer = threading.Timer(15.0, limpar)
            self._clipboard_timer.daemon = True
            self._clipboard_timer.start()

        return {"success": True, "timeout": 15}

    def get_totp_token(self, secret: str) -> dict:
        """Gera código TOTP para um segredo individual."""
        return vault_core.gerar_totp(secret)

    def get_vault_totp_tokens(self) -> dict:
        """Retorna os códigos TOTP ativos de todos os registros que possuem chave 2FA configurada."""
        tokens = {}
        for item in self._cofre:
            sec = str(item.get("totp_secret") or "").strip()
            if sec:
                tokens[item["id"]] = vault_core.gerar_totp(sec)
        return tokens

    def get_vault_health(self) -> dict:
        """Executa a auditoria de saúde e cálculo de pontuação do cofre."""
        try:
            return vault_core.analisar_saude_cofre(self._cofre)
        except Exception as e:
            return {
                "score": 100,
                "total": len(self._cofre) if self._cofre else 0,
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
                "status_seguranca": "Status: Indisponível",
                "nivel_blindagem": "Status: Indisponível",
                "cor_status": "#f43f5e",
                "cor_blindagem": "#f43f5e",
                "resumo": "Não foi possível concluir a auditoria no momento.",
                "error": str(e),
            }

    def import_csv_data(self, csv_text: str) -> dict:
        """Importa credenciais a partir de uma string CSV e persiste atomicamente."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}

        novos_itens, count = vault_core.importar_csv(csv_text)
        if count == 0:
            return {"success": False, "error": "Nenhuma credencial válida encontrada no arquivo CSV."}

        self._cofre.extend(novos_itens)
        try:
            vault_core.salvar_cofre(self._cofre, self._chave, self._salt)
            return {"success": True, "count": count, "entries": self._cofre}
        except Exception as e:
            return {"success": False, "error": f"Falha ao persistir dados importados: {str(e)}"}

    def export_csv_data(self) -> dict:
        """Exporta o cofre atual em formato CSV RFC 4180."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}
        try:
            csv_content = vault_core.exportar_csv(self._cofre)
            return {"success": True, "csv_content": csv_content, "count": len(self._cofre)}
        except Exception as e:
            return {"success": False, "error": f"Erro ao exportar CSV: {str(e)}"}

    def select_and_import_csv(self) -> dict:
        """Abre o diálogo nativo do Windows para selecionar e importar arquivo CSV."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}
        if not self._window:
            return {"success": False, "error": "Janela indisponível."}

        file_types = ("Arquivos CSV (*.csv)", "Todos os arquivos (*.*)")
        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=file_types,
            )
            if not result:
                return {"cancelled": True}
            file_path = result[0] if isinstance(result, (list, tuple)) else result
            with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
            return self.import_csv_data(content)
        except Exception as e:
            return {"success": False, "error": f"Falha ao abrir arquivo: {str(e)}"}

    def export_csv_to_file(self) -> dict:
        """Abre o diálogo nativo do Windows para salvar o arquivo de backup CSV."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}
        if not self._window:
            return {"success": False, "error": "Janela indisponível."}

        default_name = f"AegisCore-Backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
        file_types = ("Arquivos CSV (*.csv)", "Todos os arquivos (*.*)")
        try:
            save_path = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_name,
                file_types=file_types,
            )
            if not save_path:
                return {"cancelled": True}
            if isinstance(save_path, (list, tuple)):
                save_path = save_path[0]
            csv_str = vault_core.exportar_csv(self._cofre)
            with open(save_path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_str)
            return {"success": True, "path": save_path, "count": len(self._cofre)}
        except Exception as e:
            return {"success": False, "error": f"Erro ao salvar arquivo: {str(e)}"}


def get_resource_path(relative_path: str) -> str:
    """Obtém o caminho absoluto para recursos, funcionando em dev e empacotado pelo PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aegiscore.vault.app.1.1")
        except Exception:
            pass

    ui_index = get_resource_path(os.path.join("ui", "index.html"))
    icon_path = get_resource_path("aegiscore.ico")

    api = VaultApi()

    window = webview.create_window(
        title="AegisCore",
        url=ui_index,
        js_api=api,
        width=1060,
        height=700,
        min_size=(900, 580),
        background_color="#0c0b08",
        text_select=False,
    )
    api.set_window(window)

    webview.start(debug=False, icon=icon_path if os.path.exists(icon_path) else None)


if __name__ == "__main__":
    main()