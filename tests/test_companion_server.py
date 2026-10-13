import json
import urllib.request
import urllib.error
import pytest
import vault_core
from companion_server import CompanionServer


class MockVaultProvider:
    """Mock do provedor de cofre (compatível com a interface do VaultApi)."""

    def __init__(self, unlocked: bool = True):
        self.unlocked = unlocked
        self.entries = [
            {
                "id": "entry-1",
                "servico": "GitHub",
                "usuario": "dev@aegiscore.local",
                "senha": "superSecretPassword123!",
                "url": "https://github.com",
                "totp_secret": "JBSWY3DPEHPK3PXP",
            },
            {
                "id": "entry-2",
                "servico": "Google",
                "usuario": "user@gmail.com",
                "senha": "googlePassword456!",
                "url": "https://accounts.google.com",
                "totp_secret": "",
            },
            {
                "id": "entry-3",
                "servico": "Slack",
                "usuario": "dev@company.slack.com",
                "senha": "slackPassword789!",
                "url": "",
                "totp_secret": "",
            },
        ]

    def is_vault_unlocked(self) -> bool:
        return self.unlocked

    def get_entries(self) -> list[dict]:
        return self.entries if self.unlocked else []

    def get_entry_by_id(self, entry_id: str) -> dict | None:
        if not self.unlocked:
            return None
        for item in self.entries:
            if item["id"] == entry_id:
                return item
        return None


def _make_request(url: str, method: str = "GET", data: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    headers = headers or {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            return status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return e.code, parsed


@pytest.fixture
def companion_server():
    provider = MockVaultProvider(unlocked=True)
    server = CompanionServer(vault_provider=provider, host="127.0.0.1", port=0)
    server.start()
    port = server.get_bound_port()
    base_url = f"http://127.0.0.1:{port}"

    yield server, base_url, provider

    server.stop()


def test_companion_server_cors_options(companion_server):
    _, base_url, _ = companion_server
    req = urllib.request.Request(f"{base_url}/api/status", method="OPTIONS")
    with urllib.request.urlopen(req, timeout=2) as resp:
        assert resp.status in (200, 204)
        headers = dict(resp.headers)
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert "X-Aegis-Token" in headers.get("Access-Control-Allow-Headers", "")


def test_companion_server_status_endpoint(companion_server):
    _, base_url, provider = companion_server

    # Desbloqueado
    provider.unlocked = True
    status, body = _make_request(f"{base_url}/api/status")
    assert status == 200
    assert body["online"] is True
    assert body["unlocked"] is True
    assert body["version"] == "2.0.0"

    # Bloqueado
    provider.unlocked = False
    status, body = _make_request(f"{base_url}/api/status")
    assert status == 200
    assert body["unlocked"] is False


def test_companion_server_pairing_flow(companion_server):
    server, base_url, _ = companion_server

    # 1. Solicita pareamento
    status, pair_resp = _make_request(
        f"{base_url}/api/pair",
        method="POST",
        data={"client_name": "Chrome Extension"},
    )
    assert status == 200
    assert pair_resp["success"] is True
    code = pair_resp["code"]
    assert len(code) == 6

    # 2. Tentativa com código incorreto
    status, err_resp = _make_request(
        f"{base_url}/api/confirm-pair",
        method="POST",
        data={"code": "000000"},
    )
    assert status == 400
    assert err_resp["success"] is False

    # 3. Consulta da extensão antes da aprovação do Desktop (deve aguardar)
    status, waiting_resp = _make_request(
        f"{base_url}/api/confirm-pair",
        method="POST",
        data={"code": code},
    )
    assert status == 200
    assert waiting_resp["success"] is False
    assert waiting_resp["waiting"] is True

    # 4. Aprovação pelo AegisCore Desktop
    approved_token = server.approve_pairing(code)
    assert approved_token is not None
    assert len(approved_token) >= 32

    # 5. Consulta da extensão após aprovação do Desktop (deve receber token com sucesso)
    status, confirm_resp = _make_request(
        f"{base_url}/api/confirm-pair",
        method="POST",
        data={"code": code},
    )
    assert status == 200
    assert confirm_resp["success"] is True
    token = confirm_resp["token"]
    assert token == approved_token
    assert server.validate_token(token) is True


def test_companion_server_query_credentials_protection(companion_server):
    server, base_url, provider = companion_server
    token = server.generate_and_register_token("Test Browser")

    # Sem token -> 401
    status, body = _make_request(
        f"{base_url}/api/query",
        method="POST",
        data={"url": "https://github.com/login"},
    )
    assert status == 401

    # Com cofre bloqueado
    provider.unlocked = False
    status, body = _make_request(
        f"{base_url}/api/query",
        method="POST",
        data={"url": "https://github.com/login"},
        headers={"X-Aegis-Token": token},
    )
    assert status == 200
    assert body["success"] is False
    assert body["locked"] is True

    # Com cofre desbloqueado e URL do GitHub
    provider.unlocked = True
    status, body = _make_request(
        f"{base_url}/api/query",
        method="POST",
        data={"url": "https://github.com/login"},
        headers={"X-Aegis-Token": token},
    )
    assert status == 200
    assert body["success"] is True
    assert len(body["entries"]) == 1
    assert body["entries"][0]["servico"] == "GitHub"
    assert body["entries"][0]["usuario"] == "dev@aegiscore.local"
    # Senha NUNCA deve ser vazada na consulta de listagem!
    assert "senha" not in body["entries"][0]
    assert body["entries"][0]["tem_totp"] is True


def test_companion_server_get_fill_with_totp(companion_server):
    server, base_url, provider = companion_server
    token = server.generate_and_register_token("Test Browser")

    # Solicita preenchimento seguro de credencial específica
    status, body = _make_request(
        f"{base_url}/api/get-fill",
        method="POST",
        data={"id": "entry-1"},
        headers={"X-Aegis-Token": token},
    )
    assert status == 200
    assert body["success"] is True
    entry = body["entry"]
    assert entry["id"] == "entry-1"
    assert entry["usuario"] == "dev@aegiscore.local"
    assert entry["senha"] == "superSecretPassword123!"
    assert len(entry["totp"]) == 6  # Código TOTP gerado em tempo real!


def test_companion_server_generate_password(companion_server):
    server, base_url, _ = companion_server
    token = server.generate_and_register_token("Test Browser")

    status, body = _make_request(
        f"{base_url}/api/generate-password",
        method="POST",
        data={"tamanho": 20, "usar_simbolos": True},
        headers={"X-Aegis-Token": token},
    )
    assert status == 200
    assert body["success"] is True
    assert len(body["password"]) == 20


def test_companion_server_token_revocation_and_persistence(companion_server):
    server, base_url, _ = companion_server
    token = server.generate_and_register_token("Firefox")

    # Lista clientes pareados
    clients = server.list_paired_clients()
    assert len(clients) == 1
    assert clients[0]["client_name"] == "Firefox"
    assert "..." in clients[0]["token_preview"]

    # Revoga token
    assert server.revoke_token(token) is True
    assert server.validate_token(token) is False

    # Tentativa de requisição com token revogado deve falhar com 401
    status, _ = _make_request(
        f"{base_url}/api/query",
        method="POST",
        data={"url": "https://github.com"},
        headers={"X-Aegis-Token": token},
    )
    assert status == 401

    # Carrega tokens pré-existentes
    persisted = [{"token": "persisted-token-123", "client_name": "Brave", "created_at": 1000.0}]
    server.load_paired_tokens(persisted)
    assert server.validate_token("persisted-token-123") is True
    clients_now = server.list_paired_clients()
    assert len(clients_now) == 1
    assert clients_now[0]["client_name"] == "Brave"


def test_companion_server_edge_cases(companion_server):
    server, base_url, provider = companion_server
    token = server.generate_and_register_token("Edge")

    # get-fill com ID inexistente -> 404
    status, body = _make_request(
        f"{base_url}/api/get-fill",
        method="POST",
        data={"id": "id-que-nao-existe"},
        headers={"X-Aegis-Token": token},
    )
    assert status == 404
    assert body["success"] is False

    # query para domínio sem credenciais cadastradas
    status, body = _make_request(
        f"{base_url}/api/query",
        method="POST",
        data={"url": "https://site-sem-conta.org/login"},
        headers={"X-Aegis-Token": token},
    )
    assert status == 200
    assert body["success"] is True
    assert len(body["entries"]) == 0

