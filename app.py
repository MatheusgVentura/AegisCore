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
        servico = entry_data.get("servico", "").strip()
        usuario = entry_data.get("usuario", "").strip()
        senha = entry_data.get("senha", "")
        url = entry_data.get("url", "").strip()
        notas = entry_data.get("notas", "").strip()

        if not servico or not senha:
            return {"success": False, "error": "Serviço e Senha são obrigatórios."}

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
                    if "favorito" in entry_data:
                        item["favorito"] = bool(entry_data["favorito"])
                    item["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
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
                "favorito": bool(entry_data.get("favorito", False)),
                "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
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


def get_resource_path(relative_path: str) -> str:
    """Obtém o caminho absoluto para recursos, funcionando em dev e empacotado pelo PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aegiscore.vault.app.1.0")
        except Exception:
            pass

    ui_index = get_resource_path(os.path.join("ui", "index.html"))
    icon_path = get_resource_path("aegiscore.ico")

    api = VaultApi()

    webview.create_window(
        title="AegisCore",
        url=ui_index,
        js_api=api,
        width=1060,
        height=700,
        min_size=(900, 580),
        background_color="#0c0b08",
        text_select=False,
    )

    webview.start(debug=False, icon=icon_path if os.path.exists(icon_path) else None)


if __name__ == "__main__":
    main()