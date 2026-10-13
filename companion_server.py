"""
AegisCore — Local Companion Server
Servidor HTTP seguro em loopback (127.0.0.1) para integração com a Extensão de Navegador (Manifest V3).
100% Offline, Zero Telemetria, Pareamento por Token com Confirmação e Validação de Origem.
"""

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
import vault_core

VERSION = "2.0.0"


class CompanionRequestHandler(BaseHTTPRequestHandler):
    """Manipulador de requisições HTTP da API local da extensão."""

    # Suprime logs automáticos de console para manter a saída limpa
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Aegis-Token")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")

    def _send_json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len <= 0 or content_len > 65536:  # Limite defensivo de 64KB
            return {}
        try:
            body = self.rfile.read(content_len).decode("utf-8")
            return json.loads(body)
        except Exception:
            return {}

    def _verify_loopback(self) -> bool:
        client_ip = self.client_address[0]
        return client_ip in ("127.0.0.1", "::1", "localhost")

    def _check_auth(self) -> bool:
        token = self.headers.get("X-Aegis-Token", "").strip()
        if not token:
            return False
        server: CompanionServer = self.server.companion_instance
        return server.validate_token(token)

    def do_OPTIONS(self) -> None:
        if not self._verify_loopback():
            self.send_error(403, "Acesso externo não permitido.")
            return

        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if not self._verify_loopback():
            self.send_error(403, "Acesso externo não permitido.")
            return

        server: CompanionServer = self.server.companion_instance

        if self.path == "/api/status":
            unlocked = server.vault_provider.is_vault_unlocked() if server.vault_provider else False
            self._send_json({
                "online": True,
                "unlocked": unlocked,
                "version": VERSION,
            })
            return

        self._send_json({"error": "Endpoint não encontrado."}, 404)

    def do_POST(self) -> None:
        if not self._verify_loopback():
            self.send_error(403, "Acesso externo não permitido.")
            return

        server: CompanionServer = self.server.companion_instance
        data = self._read_json()

        # 1. Solicitação de Pareamento
        if self.path == "/api/pair":
            client_name = str(data.get("client_name") or "Navegador Web").strip()
            code = server.create_pairing_request(client_name)
            self._send_json({
                "success": True,
                "status": "pending",
                "code": code,
            })
            return

        # 2. Confirmação do Pareamento (consulta/resgate de token pela extensão)
        if self.path == "/api/confirm-pair":
            code = str(data.get("code") or "").strip()
            status_info = server.get_pairing_status(code)
            if status_info.get("success"):
                self._send_json({
                    "success": True,
                    "token": status_info.get("token"),
                })
            elif status_info.get("waiting"):
                self._send_json({
                    "success": False,
                    "waiting": True,
                    "error": status_info.get("error"),
                }, 200)
            else:
                self._send_json({
                    "success": False,
                    "waiting": False,
                    "error": status_info.get("error", "Código de pareamento inválido ou expirado."),
                }, 400)
            return

        # Daqui em diante, todas as rotas exigem X-Aegis-Token
        if not self._check_auth():
            self._send_json({
                "success": False,
                "error": "Token de autenticação inválido ou ausente.",
            }, 401)
            return

        provider = server.vault_provider
        is_unlocked = provider.is_vault_unlocked() if provider else False

        # 3. Consulta de Credenciais por Domínio/URL
        if self.path == "/api/query":
            if not is_unlocked:
                self._send_json({"success": False, "locked": True})
                return

            url = str(data.get("url") or "").strip()
            entries = provider.get_entries() if provider else []
            matching_entries = []

            for item in entries:
                if vault_core.casar_dominio(url, item.get("url"), item.get("servico", "")):
                    # Higienização: NUNCA expor senha na consulta simples de listagem
                    matching_entries.append({
                        "id": item.get("id"),
                        "servico": item.get("servico", ""),
                        "usuario": item.get("usuario", ""),
                        "url": item.get("url", ""),
                        "tem_totp": bool(item.get("totp_secret")),
                    })

            self._send_json({
                "success": True,
                "entries": matching_entries,
            })
            return

        # 4. Obtenção Segura para Preenchimento de Campo (Fill)
        if self.path == "/api/get-fill":
            if not is_unlocked:
                self._send_json({"success": False, "locked": True})
                return

            entry_id = str(data.get("id") or "").strip()
            entry = provider.get_entry_by_id(entry_id) if provider else None

            if not entry:
                self._send_json({"success": False, "error": "Credencial não encontrada."}, 404)
                return

            totp_code = ""
            totp_secret = entry.get("totp_secret")
            if totp_secret:
                try:
                    totp_info = vault_core.gerar_totp(totp_secret)
                    if totp_info.get("valid"):
                        totp_code = totp_info.get("code", "")
                except Exception:
                    totp_code = ""

            self._send_json({
                "success": True,
                "entry": {
                    "id": entry.get("id"),
                    "servico": entry.get("servico", ""),
                    "usuario": entry.get("usuario", ""),
                    "senha": entry.get("senha", ""),
                    "totp": totp_code,
                },
            })
            return

        # 5. Geração de Senha Forte via Motor Criptográfico
        if self.path == "/api/generate-password":
            tamanho = int(data.get("tamanho", 18))
            usar_maiusculas = bool(data.get("usar_maiusculas", True))
            usar_minusculas = bool(data.get("usar_minusculas", True))
            usar_numeros = bool(data.get("usar_numeros", True))
            usar_simbolos = bool(data.get("usar_simbolos", True))

            senha = vault_core.gerar_senha_forte(
                tamanho=tamanho,
                usar_maiusculas=usar_maiusculas,
                usar_minusculas=usar_minusculas,
                usar_numeros=usar_numeros,
                usar_simbolos=usar_simbolos,
            )
            self._send_json({
                "success": True,
                "password": senha,
            })
            return

        self._send_json({"error": "Endpoint não encontrado."}, 404)


class CompanionServer:
    """Gerenciador do Mini-Servidor Local em Loopback para Navegadores."""

    def __init__(
        self,
        vault_provider: Any = None,
        host: str = "127.0.0.1",
        port: int = 18291,
        on_pair_request: Callable[[str, str], None] | None = None,
    ):
        self.vault_provider = vault_provider
        self.host = host
        self.port = port
        self.on_pair_request = on_pair_request
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.is_running: bool = False
        self._lock = threading.Lock()

        # { token: { "client_name": str, "created_at": float } }
        self.authorized_tokens: dict[str, dict] = {}
        # { code: { "client_name": str, "created_at": float, "token": str } }
        self.pending_pairs: dict[str, dict] = {}

    def start(self, daemon: bool = True) -> None:
        """Inicia o servidor HTTP em background."""
        with self._lock:
            if self.is_running:
                return

            server_address = (self.host, self.port)
            self.server = ThreadingHTTPServer(server_address, CompanionRequestHandler)
            self.server.companion_instance = self
            self.is_running = True

            self.thread = threading.Thread(target=self.server.serve_forever, daemon=daemon)
            self.thread.start()

    def stop(self) -> None:
        """Encerra o servidor graciosamente."""
        with self._lock:
            if not self.is_running or not self.server:
                return
            self.server.shutdown()
            self.server.server_close()
            self.is_running = False
            self.server = None
            if self.thread:
                self.thread.join(timeout=2)
                self.thread = None

    def get_bound_port(self) -> int:
        """Retorna a porta na qual o servidor está rodando."""
        if self.server:
            return self.server.server_address[1]
        return self.port

    def _cleanup_expired_pairs(self) -> None:
        """Remove solicitações de pareamento expiradas (>120s)."""
        now = time.time()
        expired = [c for c, p in self.pending_pairs.items() if now - p.get("created_at", 0) > 120]
        for c in expired:
            del self.pending_pairs[c]

    def create_pairing_request(self, client_name: str) -> str:
        """Gera um código de 6 dígitos para confirmação de pareamento."""
        with self._lock:
            self._cleanup_expired_pairs()
            code = f"{secrets.randbelow(900000) + 100000:06d}"
            token = secrets.token_hex(32)
            self.pending_pairs[code] = {
                "client_name": client_name,
                "created_at": time.time(),
                "token": token,
                "approved": False,
            }

            if self.on_pair_request:
                try:
                    self.on_pair_request(code, client_name)
                except Exception:
                    pass

            return code

    def approve_pairing(self, code: str) -> str | None:
        """Aprova o pareamento solicitado pelo navegador (chamado pelo AegisCore Desktop)."""
        with self._lock:
            self._cleanup_expired_pairs()
            pair = self.pending_pairs.get(code)
            if not pair:
                return None

            pair["approved"] = True
            token = pair["token"]
            self.authorized_tokens[token] = {
                "client_name": pair["client_name"],
                "created_at": time.time(),
            }
            # Mantém em pending_pairs para que a extensão capture via /api/confirm-pair
            return token

    def get_pairing_status(self, code: str) -> dict:
        """Verifica o status de aprovação de um código de pareamento para a extensão."""
        with self._lock:
            self._cleanup_expired_pairs()
            pair = self.pending_pairs.get(code)
            if not pair:
                return {
                    "success": False,
                    "waiting": False,
                    "error": "Código de pareamento inválido ou expirado.",
                }

            if not pair.get("approved"):
                return {
                    "success": False,
                    "waiting": True,
                    "error": "Aguardando autorização no AegisCore Desktop.",
                }

            token = pair["token"]
            return {
                "success": True,
                "token": token,
            }

    def confirm_pairing(self, code: str) -> str | None:
        """Confirma e efetiva o pareamento (aprovação direta ou compatibilidade retroativa)."""
        with self._lock:
            self._cleanup_expired_pairs()
            pair = self.pending_pairs.get(code)
            if not pair:
                return None

            pair["approved"] = True
            token = pair["token"]
            self.authorized_tokens[token] = {
                "client_name": pair["client_name"],
                "created_at": time.time(),
            }
            return token

    def generate_and_register_token(self, client_name: str) -> str:
        """Gera e registra um token diretamente (para testes ou autorização prévia)."""
        with self._lock:
            token = secrets.token_hex(32)
            self.authorized_tokens[token] = {
                "client_name": client_name,
                "created_at": time.time(),
            }
            return token

    def validate_token(self, token: str) -> bool:
        """Valida se o token foi autorizado."""
        with self._lock:
            return token in self.authorized_tokens

    def revoke_token(self, token: str) -> bool:
        """Revoga o acesso de uma extensão."""
        with self._lock:
            if token in self.authorized_tokens:
                del self.authorized_tokens[token]
                return True
            return False

    def list_paired_clients(self) -> list[dict]:
        """Lista as extensões autorizadas com token mascarado."""
        with self._lock:
            result = []
            for token, info in self.authorized_tokens.items():
                result.append({
                    "token_preview": f"{token[:8]}...{token[-4:]}",
                    "token": token,
                    "client_name": info.get("client_name", "Desconhecido"),
                    "created_at": info.get("created_at", 0),
                })
            return result

    def load_paired_tokens(self, tokens_data: list[dict]) -> None:
        """Carrega tokens persistidos anteriormente."""
        with self._lock:
            for item in tokens_data:
                token = item.get("token")
                if token:
                    self.authorized_tokens[token] = {
                        "client_name": item.get("client_name", "Navegador Web"),
                        "created_at": item.get("created_at", time.time()),
                    }
