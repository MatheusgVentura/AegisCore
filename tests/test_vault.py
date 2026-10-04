import os
import tempfile
from unittest.mock import MagicMock
import pytest
import vault_core
from app import VaultApi, TrayIconManager


@pytest.fixture(autouse=True)
def isolate_vault_for_tests(monkeypatch, tmp_path):
    """Garante 100% que nenhum teste leia ou escreva no cofre real do usuário."""
    temp_dir = tmp_path / "sandbox"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_vault = temp_dir / "vault.enc"
    monkeypatch.setattr(vault_core, "BASE_DIR", str(temp_dir))
    monkeypatch.setattr(vault_core, "VAULT_FILE", str(temp_vault))
    monkeypatch.setattr(vault_core, "BACKUP_FILE", str(temp_vault) + ".bak")
    monkeypatch.setattr(vault_core, "SETTINGS_FILE", str(temp_dir / "settings.json"))


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


def test_settings_load_save(tmp_path):
    # Padrões quando não existe arquivo
    settings_file = str(tmp_path / "custom_settings.json")
    cfg = vault_core.carregar_configuracoes(settings_file)
    assert cfg["auto_lock_minutes"] == 5
    assert cfg["clipboard_clear_seconds"] == 15

    # Salva novas configurações
    salvo = vault_core.salvar_configuracoes(
        {"auto_lock_minutes": 15, "clipboard_clear_seconds": 30},
        settings_path=settings_file,
    )
    assert salvo["auto_lock_minutes"] == 15
    assert salvo["clipboard_clear_seconds"] == 30

    # Recarrega do disco para confirmar persistência atômica
    recarregado = vault_core.carregar_configuracoes(settings_file)
    assert recarregado["auto_lock_minutes"] == 15
    assert recarregado["clipboard_clear_seconds"] == 30


def test_vault_api_settings_and_lock_clears_clipboard(monkeypatch):
    import pyperclip

    api = VaultApi()
    # Verifica leitura e atualização de settings via API
    settings = api.get_settings()
    assert "auto_lock_minutes" in settings

    res = api.update_settings({"auto_lock_minutes": 1, "clipboard_clear_seconds": 10})
    assert res["success"] is True
    assert res["settings"]["auto_lock_minutes"] == 1

    # Testa cópia sensível e limpeza na tranca do cofre
    copy_res = api.copy_to_clipboard("SensitivePasswordToWipe!", is_sensitive=True)
    assert copy_res["success"] is True
    assert copy_res["timeout"] == 10
    assert pyperclip.paste() == "SensitivePasswordToWipe!"

    # Ao bloquear o cofre, o clipboard e os buffers de RAM devem ser higienizados
    lock_res = api.lock_vault()
    assert lock_res["success"] is True
    assert pyperclip.paste() == ""
    assert api._chave == b""
    assert api._cofre == []


def test_gerar_passphrase_diceware():
    # 4 palavras com hífen, título e número
    p1 = vault_core.gerar_passphrase(4, separador="-", capitalizacao="title", incluir_numero=True)
    partes1 = p1.split("-")
    assert len(partes1) == 5  # 4 palavras + 1 número no final
    assert partes1[-1].isdigit()
    for w in partes1[:-1]:
        assert w.istitle()
        assert w.lower() in vault_core.DICEWARE_WORDS

    # 3 palavras minúsculas com ponto e sem número
    p2 = vault_core.gerar_passphrase(3, separador=".", capitalizacao="lower", incluir_numero=False)
    partes2 = p2.split(".")
    assert len(partes2) == 3
    for w in partes2:
        assert w.islower()
        assert w in vault_core.DICEWARE_WORDS

    # 5 palavras maiúsculas com sublinhado e com número
    p3 = vault_core.gerar_passphrase(5, separador="_", capitalizacao="upper", incluir_numero=True)
    partes3 = p3.split("_")
    assert len(partes3) == 6
    assert partes3[-1].isdigit()
    for w in partes3[:-1]:
        assert w.isupper()
        assert w.lower() in vault_core.DICEWARE_WORDS

    # Limites mínimo e máximo de palavras
    p_min = vault_core.gerar_passphrase(1, incluir_numero=False)  # deve restringir a 3
    assert len(p_min.split("-")) == 3

    p_max = vault_core.gerar_passphrase(20, incluir_numero=False)  # deve restringir a 8
    assert len(p_max.split("-")) == 8

    # Entropia calculada para passphrase
    ent = vault_core.calcular_entropia_passphrase(4, incluir_numero=True)
    assert ent["bits"] >= 40
    assert ent["nivel"] in ["Forte", "Impenetrável"]


def test_vault_api_generate_passphrase():
    api = VaultApi()
    res = api.generate_passphrase(words_count=4, separator="-", capitalize="title", include_number=True)
    assert "passphrase" in res
    assert "entropy" in res
    assert len(res["passphrase"].split("-")) == 5
    assert res["entropy"]["bits"] > 40


def test_settings_minimize_to_tray_persistence():
    cfg = vault_core.carregar_configuracoes()
    assert cfg["minimize_to_tray"] is True

    salvo = vault_core.salvar_configuracoes({"minimize_to_tray": False})
    assert salvo["minimize_to_tray"] is False

    reloaded = vault_core.carregar_configuracoes()
    assert reloaded["minimize_to_tray"] is False


def test_tray_icon_manager_actions_and_closing():
    api = VaultApi()
    api.lock_vault = MagicMock(return_value={"success": True})
    api.copy_to_clipboard = MagicMock(return_value={"success": True, "timeout": 15})

    mock_window = MagicMock()
    tray = TrayIconManager(api=api, window=mock_window, icon_path="aegiscore.ico")
    tray.notify = MagicMock()

    # 1. Testar restauração de janela
    tray.show_window()
    mock_window.show.assert_called_once()
    mock_window.restore.assert_called_once()

    # 2. Testar bloqueio tático via tray
    tray.lock_vault()
    api.lock_vault.assert_called_once()
    mock_window.evaluate_js.assert_called_once()

    # 3. Testar geração rápida de senha
    tray.quick_password()
    api.copy_to_clipboard.assert_called_once()

    # 4. Testar on_closing com minimize_to_tray=True (deve esconder janela e retornar False para não fechar processo)
    vault_core.salvar_configuracoes({"minimize_to_tray": True})
    mock_window.hide.reset_mock()
    res_closing_true = tray.on_closing()
    assert res_closing_true is False
    mock_window.hide.assert_called_once()

    # 5. Testar on_closing com minimize_to_tray=False (deve fechar aplicação e retornar True)
    vault_core.salvar_configuracoes({"minimize_to_tray": False})
    res_closing_false = tray.on_closing()
    assert res_closing_false is True
    assert tray.is_exiting is True
    mock_window.destroy.assert_called_once()


def test_autotype_settings_persistence():
    cfg = vault_core.carregar_configuracoes()
    assert cfg["autotype_press_enter"] is True
    assert cfg["autotype_delay_ms"] == 500

    salvo = vault_core.salvar_configuracoes({
        "autotype_press_enter": False,
        "autotype_delay_ms": 1000,
    })
    assert salvo["autotype_press_enter"] is False
    assert salvo["autotype_delay_ms"] == 1000

    reloaded = vault_core.carregar_configuracoes()
    assert reloaded["autotype_press_enter"] is False
    assert reloaded["autotype_delay_ms"] == 1000


def test_executar_autotype_simulated():
    from pynput.keyboard import Key
    mock_kb = MagicMock()

    # Cenário com usuário, senha e enter
    res = vault_core.executar_autotype(
        usuario="operador@aegis.corp",
        senha="TacticalVaultPassword123!",
        press_enter=True,
        delay_ms=0,
        keyboard_controller=mock_kb,
    )
    assert res is True
    assert mock_kb.type.call_count == 2
    mock_kb.tap.assert_any_call(Key.tab)
    mock_kb.tap.assert_any_call(Key.enter)

    # Cenário sem enter e apenas senha
    mock_kb.reset_mock()
    res2 = vault_core.executar_autotype(
        usuario="",
        senha="OnlyPassword456!",
        press_enter=False,
        delay_ms=0,
        keyboard_controller=mock_kb,
    )
    assert res2 is True
    assert mock_kb.type.call_count == 1
    mock_kb.type.assert_called_with("OnlyPassword456!")
    assert mock_kb.tap.call_count == 0


def test_vault_api_autotype_workflow():
    api = VaultApi()
    mock_window = MagicMock()
    api.set_window(mock_window)

    # 1. Com cofre bloqueado, deve falhar
    assert api.perform_autotype("entry-1")["success"] is False

    # 2. Desbloqueia cofre em memória
    salt = os.urandom(16)
    api._chave = vault_core.derivar_chave("MasterPass123!", salt)
    api._salt = salt
    api._cofre = [
        {"id": "entry-alpha", "servico": "ProtonMail", "usuario": "sec@pm.me", "senha": "SecretPassword!"}
    ]

    # 3. Credencial não encontrada
    assert api.perform_autotype("entry-inexistente")["success"] is False

    # 4. Credencial válida
    api.set_active_entry("entry-alpha")
    assert api._last_selected_entry_id == "entry-alpha"

    res = api.perform_autotype("entry-alpha")
    assert res["success"] is True
    assert res["servico"] == "ProtonMail"
    mock_window.minimize.assert_called_once()

    # 5. Lock vault higieniza _last_selected_entry_id
    api.lock_vault()
    assert api._last_selected_entry_id is None
    assert len(api._chave) == 0


def test_tray_icon_manager_autotype_actions():
    api = VaultApi()
    mock_window = MagicMock()
    tray = TrayIconManager(api=api, window=mock_window, icon_path="aegiscore.ico")
    tray.notify = MagicMock()

    # 1. Cofre bloqueado -> restaura janela e avisa
    tray.trigger_autotype()
    mock_window.show.assert_called()
    mock_window.restore.assert_called()

    # 2. Cofre desbloqueado sem credencial ativa -> restaura janela e foca busca
    api._chave = b"mock-key"
    mock_window.reset_mock()
    tray.trigger_autotype()
    mock_window.show.assert_called()
    mock_window.evaluate_js.assert_called_with("if (window.focusSearch) window.focusSearch();")

    # 3. Cofre desbloqueado com credencial ativa -> chama perform_autotype
    api._last_selected_entry_id = "cred-1"
    api.perform_autotype = MagicMock(return_value={"success": True, "servico": "AWS Cloud"})
    tray.trigger_autotype()
    api.perform_autotype.assert_called_with("cred-1")




