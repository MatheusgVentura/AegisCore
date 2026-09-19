import os
import tempfile
import pytest
import vault_core
from app import VaultApi


@pytest.fixture(autouse=True)
def isolate_vault_for_tests(monkeypatch, tmp_path):
    """Garante 100% que nenhum teste leia ou escreva no cofre real do usuário."""
    temp_dir = tmp_path / "sandbox"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_vault = temp_dir / "vault.enc"
    monkeypatch.setattr(vault_core, "BASE_DIR", str(temp_dir))
    monkeypatch.setattr(vault_core, "VAULT_FILE", str(temp_vault))
    monkeypatch.setattr(vault_core, "BACKUP_FILE", str(temp_vault) + ".bak")


def test_derivar_chave_argon2id():
    salt = os.urandom(16)
    k1 = vault_core.derivar_chave("SenhaForte123!", salt)
    k2 = vault_core.derivar_chave("SenhaForte123!", salt)
    assert len(k1) == 32
    assert k1 == k2


def test_totp_rfc6238_vector():
    # RFC 6238 / 4226 test vector
    res = vault_core.gerar_totp("JBSWY3DPEHPK3PXP", 1234567890)
    assert res["valid"] is True
    assert res["code"] == "742275"
    assert 1 <= res["remaining"] <= 30


def test_totp_otpauth_uri_and_formatting():
    uri = "otpauth://totp/AegisVault:user@test.com?secret=jbswy3dpehpk3pxp&issuer=AegisVault"
    res = vault_core.gerar_totp(uri, 1234567890)
    assert res["valid"] is True
    assert res["code"] == "742275"


def test_totp_invalid():
    res = vault_core.gerar_totp("INVALID!*#1923")
    assert res["valid"] is False
    assert res["code"] == "INVÁLIDO"


def test_analisar_saude_cofre():
    vault = [
        {"id": "1", "servico": "GitHub", "usuario": "octo", "senha": "123", "totp_secret": ""},
        {"id": "2", "servico": "GitLab", "usuario": "octo", "senha": "123", "totp_secret": ""},
        {"id": "3", "servico": "AWS", "usuario": "root", "senha": "X9#mK$2!pL0@zQ8&vW4*bN1^", "totp_secret": "JBSWY3DPEHPK3PXP"},
    ]
    health = vault_core.analisar_saude_cofre(vault)
    assert health["total"] == 3
    assert health["fracas_count"] == 2
    assert health["reutilizadas_count"] == 2
    assert health["com_totp_count"] == 1
    assert health["score"] < 70


def test_csv_import_chrome_and_bitwarden():
    chrome_sample = """name,url,username,password,note
Google,https://google.com,test@gmail.com,secret123,my note
"""
    items, count = vault_core.importar_csv(chrome_sample)
    assert count == 1
    assert items[0]["servico"] == "Google"
    assert items[0]["usuario"] == "test@gmail.com"
    assert items[0]["senha"] == "secret123"

    bw_sample = """folder,favorite,type,name,notes,fields,reprompt,login_uri,login_username,login_password,login_totp
,1,login,Cloudflare,cf note,,0,https://cloudflare.com,cf_user,cf_pass,JBSWY3DPEHPK3PXP
"""
    items_bw, count_bw = vault_core.importar_csv(bw_sample)
    assert count_bw == 1
    assert items_bw[0]["servico"] == "Cloudflare"
    assert items_bw[0]["totp_secret"] == "JBSWY3DPEHPK3PXP"


def test_csv_export_roundtrip():
    original = [
        {
            "id": "abc",
            "servico": "ProtonMail",
            "usuario": "sec@pm.me",
            "senha": "super-secure-pass",
            "url": "https://proton.me",
            "notas": "offline",
            "totp_secret": "JBSWY3DPEHPK3PXP",
            "favorito": True,
            "criado_em": "19/09/2026 02:00",
        }
    ]
    csv_str = vault_core.exportar_csv(original)
    reimported, count = vault_core.importar_csv(csv_str)
    assert count == 1
    assert reimported[0]["servico"] == "ProtonMail"
    assert reimported[0]["usuario"] == "sec@pm.me"
    assert reimported[0]["senha"] == "super-secure-pass"
    assert reimported[0]["totp_secret"] == "JBSWY3DPEHPK3PXP"


def test_vault_api_in_memory(monkeypatch, tmp_path):
    temp_vault = tmp_path / "vault.enc"
    monkeypatch.setattr(vault_core, "VAULT_FILE", str(temp_vault))
    monkeypatch.setattr(vault_core, "BACKUP_FILE", str(temp_vault) + ".bak")

    api = VaultApi()
    salt = os.urandom(16)
    api._chave = vault_core.derivar_chave("MasterPass!", salt)
    api._salt = salt
    api._cofre = []

    # Salva entrada com TOTP em arquivo temporário isolado
    res = api.save_entry({
        "servico": "TestService",
        "usuario": "user1",
        "senha": "MyPassword123!",
        "totp_secret": "JBSWY3DPEHPK3PXP",
    })
    assert res["success"] is True

    tokens = api.get_vault_totp_tokens()
    assert len(tokens) == 1
    eid = list(tokens.keys())[0]
    assert tokens[eid]["valid"] is True

    health = api.get_vault_health()
    assert health["total"] == 1


def test_analisar_saude_cofre_edge_cases():
    # Testa cofre vazio
    h_vazio = vault_core.analisar_saude_cofre([])
    assert h_vazio["total"] == 0
    assert h_vazio["score"] == 100
    assert "cor_blindagem" in h_vazio

    # Testa itens com valores None
    vault_com_nulos = [
        {"id": "1", "servico": "Nulo1", "usuario": None, "senha": None, "totp_secret": None, "notas": None},
        {"id": "2", "servico": "Nulo2", "usuario": "", "senha": "", "totp_secret": None},
        {"id": "3", "servico": "Bom", "usuario": "u", "senha": "X9#mK$2!pL0@zQ8&vW4*bN1^", "totp_secret": "JBSWY3DPEHPK3PXP"},
    ]
    h_nulos = vault_core.analisar_saude_cofre(vault_com_nulos)
    assert h_nulos["total"] == 3
    assert h_nulos["com_totp_count"] == 1
    assert "cor_blindagem" in h_nulos


def test_analisar_saude_cofre_calibragem_cenario_usuario():
    # Cenário especificado pelo usuário:
    # 8 contas no total, 1 fraca, 0 reutilizadas, 0/8 com 2FA ativo.
    # Score esperado: entre 65% e 75% (devido ao peso da falta de 2FA).
    vault = [
        {"id": "1", "servico": "S1", "usuario": "u1", "senha": "123", "totp_secret": ""}, # fraca
        {"id": "2", "servico": "S2", "usuario": "u2", "senha": "StrongPass#2026!Alpha", "totp_secret": ""},
        {"id": "3", "servico": "S3", "usuario": "u3", "senha": "StrongPass#2026!Beta", "totp_secret": ""},
        {"id": "4", "servico": "S4", "usuario": "u4", "senha": "StrongPass#2026!Gamma", "totp_secret": ""},
        {"id": "5", "servico": "S5", "usuario": "u5", "senha": "StrongPass#2026!Delta", "totp_secret": ""},
        {"id": "6", "servico": "S6", "usuario": "u6", "senha": "StrongPass#2026!Epsilon", "totp_secret": ""},
        {"id": "7", "servico": "S7", "usuario": "u7", "senha": "StrongPass#2026!Zeta", "totp_secret": ""},
        {"id": "8", "servico": "S8", "usuario": "u8", "senha": "StrongPass#2026!Eta", "totp_secret": ""},
    ]
    h = vault_core.analisar_saude_cofre(vault)
    assert h["total"] == 8
    assert h["fracas_count"] == 1
    assert h["reutilizadas_count"] == 0
    assert h["com_totp_count"] == 0
    assert h["sem_totp_count"] == 8
    assert h["fortes_count"] == 7
    # Verifica calibração entre 65 e 75
    assert 65 <= h["score"] <= 75
    assert "Status:" in h["status_seguranca"]


