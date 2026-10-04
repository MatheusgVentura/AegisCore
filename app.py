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
import pystray
from PIL import Image

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
        self._last_selected_entry_id: str | None = None
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
        if self._last_copied_sensitive:
            try:
                if pyperclip.paste() == self._last_copied_sensitive:
                    pyperclip.copy("")
            except Exception:
                pass
            self._last_copied_sensitive = ""
        self._last_selected_entry_id = None
        return {"success": True}

    def set_active_entry(self, entry_id: str) -> dict:
        """Define a credencial ativa para atalhos rápidos como Auto-Type."""
        self._last_selected_entry_id = entry_id
        return {"success": True}

    def perform_autotype(self, entry_id: str | None = None) -> dict:
        """
        Executa a sequência de auto-digitação (usuário -> TAB -> senha -> ENTER)
        após minimizar a janela para retornar o foco à aplicação ativa.
        """
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}

        target_id = entry_id or self._last_selected_entry_id
        if not target_id:
            return {"success": False, "error": "Nenhuma credencial selecionada para Auto-Type."}

        entry = next((item for item in self._cofre if item.get("id") == target_id), None)
        if not entry:
            return {"success": False, "error": "Credencial não encontrada no cofre."}

        self._last_selected_entry_id = target_id

        settings = vault_core.carregar_configuracoes()
        press_enter = settings.get("autotype_press_enter", True)
        delay_ms = settings.get("autotype_delay_ms", 500)

        # Minimiza a janela para que o foco volte ao navegador/aplicativo anterior
        if self._window:
            try:
                self._window.minimize()
            except Exception:
                pass

        # Dispara thread com a sequência de digitação
        usuario = str(entry.get("usuario") or "")
        senha = str(entry.get("senha") or "")

        def worker():
            vault_core.executar_autotype(
                usuario=usuario,
                senha=senha,
                press_enter=press_enter,
                delay_ms=delay_ms,
            )

        threading.Thread(target=worker, daemon=True).start()
        return {
            "success": True,
            "servico": entry.get("servico", ""),
            "delay_ms": delay_ms,
        }

    def save_entry(self, entry_data: dict) -> dict:
        """Adiciona ou atualiza uma credencial de forma atômica."""
        if not self._chave:
            return {"success": False, "error": "Cofre bloqueado."}

        if not isinstance(entry_data, dict):
            return {"success": False, "error": "Dados inválidos."}

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

        if not isinstance(ordered_ids, (list, tuple)):
            return {"success": False, "error": "Lista de IDs inválida."}

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
        if self._last_selected_entry_id == entry_id:
            self._last_selected_entry_id = None

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

    def generate_passphrase(
        self,
        words_count: int = 4,
        separator: str = "-",
        capitalize: str = "title",
        include_number: bool = True,
    ) -> dict:
        """Gera uma frase-senha memorável (Diceware) e calcula sua entropia."""
        passphrase = vault_core.gerar_passphrase(
            palavras_count=words_count,
            separador=separator,
            capitalizacao=capitalize,
            incluir_numero=include_number,
        )
        entropy = vault_core.calcular_entropia_passphrase(words_count, include_number)
        return {"passphrase": passphrase, "entropy": entropy}

    def calculate_entropy(self, pwd: str) -> dict:
        """Calcula a entropia da string informada."""
        return vault_core.calcular_entropia(pwd)

    def copy_to_clipboard(self, text: str, is_sensitive: bool = True) -> dict:
        """Copia para o clipboard e inicia timer de higienização configurável se for sensível."""
        try:
            pyperclip.copy(text)
        except Exception as e:
            return {"success": False, "error": str(e)}

        if is_sensitive:
            self._last_copied_sensitive = text
            if self._clipboard_timer:
                self._clipboard_timer.cancel()

            cfg = vault_core.carregar_configuracoes()
            timeout_sec = float(cfg.get("clipboard_clear_seconds", 15))

            def limpar():
                try:
                    if pyperclip.paste() == self._last_copied_sensitive:
                        pyperclip.copy("")
                except Exception:
                    pass
                self._last_copied_sensitive = ""

            self._clipboard_timer = threading.Timer(timeout_sec, limpar)
            self._clipboard_timer.daemon = True
            self._clipboard_timer.start()

            return {"success": True, "timeout": int(timeout_sec)}

        return {"success": True, "timeout": 0}

    def get_settings(self) -> dict:
        """Retorna as preferências configuradas no aplicativo."""
        return vault_core.carregar_configuracoes()

    def update_settings(self, settings: dict) -> dict:
        """Atualiza e persiste as preferências do usuário no disco."""
        try:
            saved = vault_core.salvar_configuracoes(settings)
            return {"success": True, "settings": saved}
        except Exception as e:
            return {"success": False, "error": str(e)}

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



class TrayIconManager:
    """Gerencia o ícone da bandeja do sistema (System Tray) e menu de acesso tático rápido."""

    def __init__(self, api: VaultApi, window: webview.Window, icon_path: str):
        self.api = api
        self.window = window
        self.icon_path = icon_path
        self.icon: pystray.Icon | None = None
        self.hotkeys = None
        self.is_exiting = False

    def _create_image(self) -> Image.Image:
        """Carrega o ícone oficial ou cria fallback na memória se não encontrado."""
        if os.path.exists(self.icon_path):
            try:
                return Image.open(self.icon_path)
            except Exception:
                pass
        return Image.new("RGBA", (64, 64), color=(12, 11, 8, 255))

    def notify(self, message: str, title: str = "AegisCore"):
        """Dispara uma notificação do sistema via bandeja."""
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    def show_window(self, icon=None, item=None):
        """Restaura e traz para o primeiro plano a janela do AegisCore."""
        try:
            self.window.show()
            self.window.restore()
        except Exception:
            pass

    def trigger_autotype(self, icon=None, item=None):
        """Dispara a rotina de preenchimento automático para a credencial ativa."""
        if not self.api._chave:
            self.show_window()
            self.notify(
                "Cofre bloqueado. Desbloqueie sua sessão para utilizar o Auto-Type.",
                "AegisCore — Auto-Type",
            )
            return

        if self.api._last_selected_entry_id:
            res = self.api.perform_autotype(self.api._last_selected_entry_id)
            if res.get("success"):
                self.notify(
                    f"Digitando credenciais de '{res.get('servico', 'Serviço')}'...",
                    "AegisCore — Auto-Type",
                )
        else:
            self.show_window()
            try:
                self.window.evaluate_js("if (window.focusSearch) window.focusSearch();")
            except Exception:
                pass
            self.notify(
                "Selecione uma credencial ou clique no botão de Auto-Type.",
                "AegisCore — Auto-Type",
            )

    def lock_vault(self, icon=None, item=None):
        """Tranca o cofre imediatamente, higieniza a RAM e reflete na interface visual."""
        try:
            self.api.lock_vault()
            self.window.evaluate_js("if (window.handleLock) window.handleLock();")
            self.notify(
                "Cofre trancado e credenciais higienizadas da memória.",
                "AegisCore — Bloqueado",
            )
        except Exception:
            pass

    def quick_password(self, icon=None, item=None):
        """Gera uma senha forte e copia diretamente com expiração de clipboard."""
        try:
            pwd = vault_core.gerar_senha_forte(
                tamanho=18,
                usar_maiusculas=True,
                usar_minusculas=True,
                usar_numeros=True,
                usar_simbolos=True,
            )
            self.api.copy_to_clipboard(pwd, is_sensitive=True)
            self.notify(
                "Senha tática de 18 caracteres gerada e copiada para a área de transferência.",
                "AegisCore — Senha Rápida",
            )
        except Exception:
            pass

    def exit_app(self, icon=None, item=None):
        """Finaliza a aplicação, higieniza a sessão e encerra a bandeja e a janela."""
        self.is_exiting = True
        try:
            self.api.lock_vault()
        except Exception:
            pass
        if self.hotkeys:
            try:
                self.hotkeys.stop()
            except Exception:
                pass
            self.hotkeys = None
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        try:
            self.window.destroy()
        except Exception:
            pass

    def on_closing(self, *args, **kwargs) -> bool:
        """
        Intercepta o evento de fechamento da janela.
        Se minimize_to_tray estiver ativado, esconde a janela e cancela o encerramento do processo.
        """
        if self.is_exiting:
            return True

        settings = vault_core.carregar_configuracoes()
        if settings.get("minimize_to_tray", True):
            try:
                self.window.hide()
                self.notify(
                    "AegisCore continua protegido em segundo plano na bandeja do sistema.",
                    "AegisCore Minimizado",
                )
            except Exception:
                pass
            return False

        self.exit_app()
        return True

    def start(self):
        """Inicia o ícone da bandeja e o listener de atalhos globais em segundo plano."""
        image = self._create_image()
        menu = pystray.Menu(
            pystray.MenuItem("Abrir AegisCore", self.show_window, default=True),
            pystray.MenuItem("Auto-Type (Ctrl+Alt+V)", self.trigger_autotype),
            pystray.MenuItem("Bloquear Cofre", self.lock_vault),
            pystray.MenuItem("Gerar Senha Rápida", self.quick_password),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair do AegisCore", self.exit_app),
        )
        self.icon = pystray.Icon("AegisCore", image, "AegisCore — Password Vault", menu=menu)
        self.icon.run_detached()

        # Inicia o atalho global Ctrl+Alt+V
        try:
            from pynput import keyboard
            self.hotkeys = keyboard.GlobalHotKeys({
                '<ctrl>+<alt>+v': self.trigger_autotype,
            })
            self.hotkeys.start()
        except Exception:
            self.hotkeys = None

    def stop(self):
        """Para o ícone da bandeja e o listener de atalhos."""
        if self.hotkeys:
            try:
                self.hotkeys.stop()
            except Exception:
                pass
            self.hotkeys = None
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass


class SingleInstanceManager:
    """Garante que apenas uma única instância do AegisCore execute por sessão do usuário."""

    def __init__(self, app_id: str = "AegisCore_SingleInstance"):
        self.app_id = app_id
        self.mutex_name = f"Local\\{app_id}_Mutex"
        self.event_name = f"Local\\{app_id}_WakeupEvent"
        self._mutex = None
        self._event = None
        self._stop_listening = False
        self._listener_thread = None

    def acquire(self) -> bool:
        """
        Tenta obter o lock de instância única no Windows via Mutex do Kernel32.
        Se já existir outra instância em execução, sinaliza para ela restaurar a janela e retorna False.
        """
        if sys.platform != "win32":
            return True

        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            ERROR_ALREADY_EXISTS = 183

            self._mutex = k32.CreateMutexW(None, False, self.mutex_name)
            last_error = k32.GetLastError()

            if last_error == ERROR_ALREADY_EXISTS:
                # Já existe uma instância ativa! Sinaliza para ela acordar e restaurar a janela.
                wakeup_event = k32.OpenEventW(0x0002, False, self.event_name)  # EVENT_MODIFY_STATE
                if wakeup_event:
                    k32.SetEvent(wakeup_event)
                    k32.CloseHandle(wakeup_event)
                if self._mutex:
                    k32.CloseHandle(self._mutex)
                    self._mutex = None
                return False

            # Primeira instância: cria o evento para escutar futuras tentativas
            self._event = k32.CreateEventW(None, False, False, self.event_name)
            return True
        except Exception:
            return True

    def start_listener(self, on_wakeup_callback):
        """Inicia uma thread em segundo plano aguardando sinais de novas instâncias para restaurar a janela."""
        if sys.platform != "win32" or not self._event:
            return

        def listener():
            import ctypes
            k32 = ctypes.windll.kernel32
            while not self._stop_listening:
                wait_result = k32.WaitForSingleObject(self._event, 500)
                if wait_result == 0:  # WAIT_OBJECT_0
                    try:
                        on_wakeup_callback()
                    except Exception:
                        pass

        self._listener_thread = threading.Thread(target=listener, daemon=True)
        self._listener_thread.start()

    def release(self):
        """Libera os handles do mutex e evento do Windows."""
        self._stop_listening = True
        if sys.platform != "win32":
            return

        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            if self._event:
                k32.CloseHandle(self._event)
                self._event = None
            if self._mutex:
                k32.CloseHandle(self._mutex)
                self._mutex = None
        except Exception:
            pass


def get_resource_path(relative_path: str) -> str:
    """Obtém o caminho absoluto para recursos, funcionando em dev e empacotado pelo PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def main():
    single_instance = SingleInstanceManager()
    if not single_instance.acquire():
        sys.exit(0)

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aegiscore.vault.app.1.2")
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

    tray_mgr = TrayIconManager(api, window, icon_path)
    window.events.closing += tray_mgr.on_closing
    tray_mgr.start()

    single_instance.start_listener(tray_mgr.show_window)

    try:
        webview.start(debug=False, icon=icon_path if os.path.exists(icon_path) else None)
    finally:
        single_instance.release()
        tray_mgr.stop()


if __name__ == "__main__":
    main()