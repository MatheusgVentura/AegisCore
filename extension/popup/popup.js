/**
 * AegisCore Companion — Popup Script
 * Controla a interface HUD do popup da extensão, comunicação com o background worker,
 * busca de credenciais da aba atual, TOTP em tempo real e injeção de auto-preenchimento.
 */

let currentTab = null;
let currentDomain = '';
let currentPairCode = null;
let totpInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await refreshPopupState();
});

function setupEventListeners() {
  document.getElementById('btn-retry-offline')?.addEventListener('click', refreshPopupState);
  document.getElementById('btn-check-unlocked')?.addEventListener('click', refreshPopupState);

  // Pareamento
  document.getElementById('btn-start-pairing')?.addEventListener('click', handleStartPairing);
  document.getElementById('btn-check-pair-confirm')?.addEventListener('click', handleCheckPairConfirm);

  // Rodapé
  document.getElementById('btn-unpair')?.addEventListener('click', handleUnpair);
  document.getElementById('btn-toggle-gen-footer')?.addEventListener('click', toggleGeneratorPanel);
  document.getElementById('btn-close-gen')?.addEventListener('click', () => {
    document.getElementById('generator-panel').style.display = 'none';
  });
  document.getElementById('btn-refresh-gen')?.addEventListener('click', handleGeneratePassword);
  document.getElementById('btn-copy-gen')?.addEventListener('click', copyGeneratedPassword);
  document.getElementById('btn-open-generator-view')?.addEventListener('click', () => {
    toggleGeneratorPanel();
  });
}

function showToast(text, duration = 2000) {
  const toast = document.getElementById('popup-toast');
  const toastText = document.getElementById('toast-text');
  if (!toast || !toastText) return;
  toastText.innerText = text;
  toast.style.display = 'block';
  setTimeout(() => {
    toast.style.display = 'none';
  }, duration);
}

function setHeaderStatus(type, text) {
  const badge = document.getElementById('header-status-badge');
  if (!badge) return;
  badge.className = `status-indicator ${type}`;
  const textEl = badge.querySelector('.status-text');
  if (textEl) textEl.innerText = text;
}

function switchView(viewId) {
  const views = ['view-offline', 'view-unpaired', 'view-locked', 'view-connected'];
  views.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === viewId ? 'flex' : 'none';
  });
}

async function refreshPopupState() {
  // Obtém aba ativa
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentTab = tab;
    if (tab && tab.url && !tab.url.startsWith('chrome://') && !tab.url.startsWith('about:')) {
      try {
        const u = new URL(tab.url);
        currentDomain = u.hostname.replace(/^www\./, '');
      } catch (e) {
        currentDomain = '';
      }
    } else {
      currentDomain = 'Página do Sistema';
    }
  } catch (e) {
    currentDomain = '';
  }

  const domainEl = document.getElementById('current-domain-text');
  if (domainEl) domainEl.innerText = currentDomain || 'Guia Atual';

  // Consulta status do background service worker
  chrome.runtime.sendMessage({ action: 'GET_STATUS' }, (res) => {
    if (chrome.runtime.lastError || !res || !res.success) {
      setHeaderStatus('offline', 'Offline');
      switchView('view-offline');
      return;
    }

    const { status, isPaired } = res;

    if (!status.online) {
      setHeaderStatus('offline', 'Desktop Inativo');
      switchView('view-offline');
      return;
    }

    if (!isPaired) {
      setHeaderStatus('offline', 'Não Conectado');
      switchView('view-unpaired');
      return;
    }

    if (!status.unlocked) {
      setHeaderStatus('locked', 'Cofre Bloqueado');
      switchView('view-locked');
      return;
    }

    // Conectado e Desbloqueado!
    setHeaderStatus('online', 'Conectado');
    switchView('view-connected');
    loadCredentialsForTab();
  });
}

// Início do pareamento com o Desktop
function handleStartPairing() {
  let clientName = 'Google Chrome';
  if (navigator.userAgent.includes('Edg')) clientName = 'Microsoft Edge';
  else if (navigator.userAgent.includes('Brave')) clientName = 'Brave Browser';
  else if (navigator.userAgent.includes('Firefox')) clientName = 'Mozilla Firefox';

  chrome.runtime.sendMessage({ action: 'REQUEST_PAIR', clientName }, (res) => {
    if (res && res.success && res.code) {
      currentPairCode = res.code;
      document.getElementById('display-pair-code').innerText = res.code;
      document.getElementById('unpaired-step-request').style.display = 'none';
      document.getElementById('unpaired-step-code').style.display = 'block';
    } else {
      showToast(res?.error || 'Erro ao iniciar pareamento.');
    }
  });
}

function handleCheckPairConfirm() {
  if (!currentPairCode) return;
  chrome.runtime.sendMessage({ action: 'CONFIRM_PAIR', code: currentPairCode }, (res) => {
    if (res && res.success) {
      showToast('Extensão conectada com sucesso!');
      setTimeout(refreshPopupState, 400);
    } else {
      showToast(res?.error || 'Aguardando autorização no Desktop.');
    }
  });
}

function handleUnpair() {
  if (!confirm('Deseja desconectar a extensão do AegisCore Desktop?')) return;
  chrome.runtime.sendMessage({ action: 'UNPAIR' }, () => {
    showToast('Extensão desconectada.');
    refreshPopupState();
  });
}

// Busca credenciais para a aba ativa
function loadCredentialsForTab() {
  if (!currentTab || !currentTab.url) return;

  chrome.runtime.sendMessage(
    { action: 'QUERY_CREDENTIALS', url: currentTab.url },
    (res) => {
      const container = document.getElementById('entries-list');
      const emptyMsg = document.getElementById('no-credentials-msg');
      if (!container) return;

      container.innerHTML = '';

      if (!res || !res.success || !res.entries || res.entries.length === 0) {
        if (emptyMsg) emptyMsg.style.display = 'block';
        return;
      }

      if (emptyMsg) emptyMsg.style.display = 'none';

      res.entries.forEach((entry) => {
        const card = createEntryCard(entry);
        container.appendChild(card);
      });
    }
  );
}

function createEntryCard(entry) {
  const card = document.createElement('div');
  card.className = 'entry-card';

  card.innerHTML = `
    <div class="entry-header">
      <span class="entry-service">${escapeHtml(entry.servico || 'Sem Nome')}</span>
      ${entry.tem_totp ? `<span style="font-size: 10px; background: rgba(184, 145, 83, 0.2); color: var(--gold-primary); padding: 2px 6px; border-radius: 4px; font-weight: 600;">2FA Ativo</span>` : ''}
    </div>
    <div class="entry-user">${escapeHtml(entry.usuario || 'Sem usuário')}</div>

    ${
      entry.tem_totp
        ? `<div class="entry-totp-box" id="totp-box-${entry.id}">
             <span class="totp-code" id="totp-val-${entry.id}">------</span>
             <span class="totp-timer" id="totp-timer-${entry.id}">30s</span>
           </div>`
        : ''
    }

    <div class="entry-actions">
      <button type="button" class="btn-fill" data-action="fill" data-id="${entry.id}">
        Preencher Login
      </button>
      <button type="button" class="btn-ghost-sm" data-action="copy-user" data-user="${escapeAttr(entry.usuario)}" title="Copiar Usuário">
        Usuário
      </button>
      <button type="button" class="btn-ghost-sm" data-action="copy-pass" data-id="${entry.id}" title="Copiar Senha">
        Senha
      </button>
    </div>
  `;

  // Event Listeners dos botões do Card
  card.querySelector('[data-action="fill"]').addEventListener('click', () => fillLogin(entry.id));
  card.querySelector('[data-action="copy-user"]').addEventListener('click', (e) => {
    const user = e.target.getAttribute('data-user');
    if (user) {
      navigator.clipboard.writeText(user);
      showToast('Usuário copiado!');
    }
  });
  card.querySelector('[data-action="copy-pass"]').addEventListener('click', () => copyPassword(entry.id));

  // Carrega TOTP se aplicável
  if (entry.tem_totp) {
    fetchAndDisplayTotp(entry.id);
  }

  return card;
}

// Preenchimento de login com 1 clique na página web
async function fillLogin(entryId) {
  chrome.runtime.sendMessage({ action: 'GET_FILL', id: entryId }, async (res) => {
    if (!res || !res.success || !res.entry) {
      showToast(res?.error || 'Erro ao carregar dados de preenchimento.');
      return;
    }

    const { usuario, senha } = res.entry;

    if (!currentTab || !currentTab.id) return;

    // Envia dados para o content script injetado na página
    chrome.tabs.sendMessage(
      currentTab.id,
      {
        action: 'AUTOFILL_CREDENTIALS',
        username: usuario,
        password: senha,
      },
      (contentRes) => {
        if (chrome.runtime.lastError || !contentRes || !contentRes.success) {
          showToast('Credenciais copiadas (campos não detectados na aba).');
          navigator.clipboard.writeText(senha);
        } else {
          showToast('Campos preenchidos com sucesso!');
          setTimeout(() => window.close(), 600);
        }
      }
    );
  });
}

// Cópia de senha
function copyPassword(entryId) {
  chrome.runtime.sendMessage({ action: 'GET_FILL', id: entryId }, (res) => {
    if (res && res.success && res.entry && res.entry.senha) {
      navigator.clipboard.writeText(res.entry.senha);
      showToast('Senha copiada com segurança!');
    } else {
      showToast(res?.error || 'Erro ao copiar senha.');
    }
  });
}

// Exibição e atualização de TOTP
function fetchAndDisplayTotp(entryId) {
  chrome.runtime.sendMessage({ action: 'GET_FILL', id: entryId }, (res) => {
    if (res && res.success && res.entry && res.entry.totp) {
      const codeEl = document.getElementById(`totp-val-${entryId}`);
      const timerEl = document.getElementById(`totp-timer-${entryId}`);
      if (codeEl) codeEl.innerText = res.entry.totp;

      const remaining = 30 - (Math.floor(Date.now() / 1000) % 30);
      if (timerEl) timerEl.innerText = `${remaining}s`;
    }
  });
}

// Gerador de senhas rápido
function toggleGeneratorPanel() {
  const panel = document.getElementById('generator-panel');
  if (!panel) return;
  const isHidden = panel.style.display === 'none';
  panel.style.display = isHidden ? 'block' : 'none';
  if (isHidden) handleGeneratePassword();
}

function handleGeneratePassword() {
  chrome.runtime.sendMessage(
    {
      action: 'GENERATE_PASSWORD',
      options: { tamanho: 18, usar_simbolos: true },
    },
    (res) => {
      const out = document.getElementById('gen-output-text');
      if (out && res && res.success && res.password) {
        out.innerText = res.password;
      }
    }
  );
}

function copyGeneratedPassword() {
  const out = document.getElementById('gen-output-text');
  if (out && out.innerText && out.innerText !== '••••••••••••••••') {
    navigator.clipboard.writeText(out.innerText);
    showToast('Senha forte copiada!');
  }
}

// Escapes utilitários
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/'/g, '&#39;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
