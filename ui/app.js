// Estado Global do AegisCore
let state = {
  entries: [],
  filter: '',
  categoryFilter: 'all',
  clipboardTimer: null,
  pendingDeleteId: null,
  draggedId: null,
};

// Comunicação com API Python
async function callApi(fnName, ...args) {
  if (!window.pywebview || !window.pywebview.api) {
    console.error('API AegisCore indisponível.');
    return null;
  }
  try {
    return await window.pywebview.api[fnName](...args);
  } catch (err) {
    console.error(`Erro ao chamar ${fnName}:`, err);
    throw err;
  }
}

// Inicialização da Aplicação
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  if (window.pywebview && window.pywebview.api) {
    initApp();
  } else {
    window.addEventListener('pywebviewready', initApp);
  }
});

async function initApp() {
  const status = await callApi('check_vault_status');
  if (!status) return;

  const panelUnlock = document.getElementById('panel-unlock');
  const panelSetup = document.getElementById('panel-setup');

  if (status.exists) {
    panelUnlock.style.display = 'block';
    panelSetup.style.display = 'none';
    document.getElementById('input-unlock-pass').focus();
  } else {
    panelUnlock.style.display = 'none';
    panelSetup.style.display = 'block';
    document.getElementById('input-setup-pass').focus();
  }
}

function setupEventListeners() {
  // Desbloqueio
  document.getElementById('unlock-form').addEventListener('submit', handleUnlock);
  document.getElementById('btn-submit-unlock').addEventListener('click', handleUnlock);

  // Alternar senha no unlock
  document.getElementById('btn-toggle-unlock-pass').addEventListener('click', () => {
    const input = document.getElementById('input-unlock-pass');
    input.type = input.type === 'password' ? 'text' : 'password';
  });

  // Configuração inicial
  document.getElementById('setup-form').addEventListener('submit', handleSetup);
  document.getElementById('btn-submit-setup').addEventListener('click', handleSetup);
  document.getElementById('input-setup-pass').addEventListener('input', (e) => {
    updateEntropyMeter(e.target.value, 'setup-meter-fill', 'setup-meter-label', 'setup-meter-bits');
  });

  // Ações da Sidebar
  document.getElementById('btn-sidebar-gen').addEventListener('click', openGenModal);
  document.getElementById('btn-sidebar-lock').addEventListener('click', handleLock);

  // Sincronização e alternância de categoria (Sidebar e Pílulas)
  function setCategory(cat) {
    state.categoryFilter = cat;
    document.querySelectorAll('.nav-item[data-category]').forEach((i) => {
      if (i.getAttribute('data-category') === cat) {
        i.classList.add('active');
      } else {
        i.classList.remove('active');
      }
    });
    document.querySelectorAll('.filter-pill').forEach((p) => {
      if (p.getAttribute('data-filter') === cat) {
        p.classList.add('active');
      } else {
        p.classList.remove('active');
      }
    });
    renderCards();
  }

  // Navegação na Sidebar
  document.querySelectorAll('.nav-item[data-category]').forEach((item) => {
    item.addEventListener('click', () => {
      setCategory(item.getAttribute('data-category'));
    });
  });

  // Pílulas de Filtro
  document.querySelectorAll('.filter-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      setCategory(pill.getAttribute('data-filter'));
    });
  });

  // Busca rápida (com atalho Ctrl+K ou Ctrl+F)
  const searchInput = document.getElementById('input-search');
  searchInput.addEventListener('input', (e) => {
    state.filter = e.target.value.trim().toLowerCase();
    renderCards();
  });

  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'k' || e.key.toLowerCase() === 'f')) {
      e.preventDefault();
      if (document.getElementById('dashboard-wrapper').style.display !== 'none') {
        searchInput.focus();
        searchInput.select();
      }
    }
  });

  // Modais de Credencial
  document.getElementById('btn-add-credential').addEventListener('click', () => openEntryModal());
  document.getElementById('btn-empty-add').addEventListener('click', () => openEntryModal());
  document.getElementById('btn-close-entry-modal').addEventListener('click', closeEntryModal);
  document.getElementById('btn-cancel-entry').addEventListener('click', closeEntryModal);
  document.getElementById('entry-form').addEventListener('submit', handleSaveEntry);

  document.getElementById('btn-toggle-entry-pass').addEventListener('click', () => {
    const input = document.getElementById('entry-password');
    input.type = input.type === 'password' ? 'text' : 'password';
  });

  document.getElementById('entry-password').addEventListener('input', (e) => {
    updateEntropyMeter(e.target.value, 'entry-meter-fill', 'entry-meter-label', 'entry-meter-bits');
  });

  // Gerador rápido no modal
  document.getElementById('btn-modal-quick-gen').addEventListener('click', async () => {
    const res = await callApi('generate_password', 24, true, true, true, true);
    if (res && res.password) {
      const input = document.getElementById('entry-password');
      input.value = res.password;
      input.type = 'text';
      updateEntropyMeter(res.password, 'entry-meter-fill', 'entry-meter-label', 'entry-meter-bits');
    }
  });

  // Gerador Completo
  document.getElementById('btn-close-gen-modal').addEventListener('click', closeGenModal);
  document.getElementById('gen-slider').addEventListener('input', (e) => {
    document.getElementById('gen-length-val').innerText = e.target.value;
    refreshGeneratorDisplay();
  });
  ['gen-upper', 'gen-lower', 'gen-digits', 'gen-symbols'].forEach((id) => {
    document.getElementById(id).addEventListener('change', refreshGeneratorDisplay);
  });
  document.getElementById('btn-regen').addEventListener('click', refreshGeneratorDisplay);
  document.getElementById('btn-copy-generated').addEventListener('click', copyGeneratedPassword);
  document.getElementById('btn-use-generated').addEventListener('click', () => {
    copyGeneratedPassword();
    closeGenModal();
  });

  // Exclusão
  document.getElementById('btn-cancel-delete').addEventListener('click', closeDeleteModal);
  document.getElementById('btn-confirm-delete').addEventListener('click', handleConfirmDelete);
}

// Autenticação
async function handleUnlock(e) {
  if (e) e.preventDefault();
  const input = document.getElementById('input-unlock-pass');
  const errorBox = document.getElementById('unlock-error');
  const pass = input.value;

  if (!pass) {
    showError(errorBox, 'Digite a senha mestra para desbloquear.');
    return;
  }

  errorBox.style.display = 'none';
  const res = await callApi('unlock_vault', pass);

  if (res && res.success) {
    state.entries = res.entries || [];
    input.value = '';
    showDashboard();
  } else {
    showError(errorBox, res?.error || 'Senha incorreta ou integridade violada.');
  }
}

async function handleSetup(e) {
  if (e) e.preventDefault();
  const pass = document.getElementById('input-setup-pass').value;
  const confirm = document.getElementById('input-setup-confirm').value;
  const errorBox = document.getElementById('setup-error');

  if (!pass) {
    showError(errorBox, 'A senha mestra não pode ser vazia.');
    return;
  }
  if (pass !== confirm) {
    showError(errorBox, 'As senhas digitadas não conferem.');
    return;
  }

  const res = await callApi('create_vault', pass);
  if (res && res.success) {
    state.entries = res.entries || [];
    showDashboard();
  } else {
    showError(errorBox, res?.error || 'Falha ao inicializar o cofre AegisCore.');
  }
}

async function handleLock() {
  await callApi('lock_vault');
  state.entries = [];
  state.filter = '';
  document.getElementById('dashboard-wrapper').style.display = 'none';
  document.getElementById('app-sidebar').style.display = 'none';
  document.getElementById('auth-view').style.display = 'flex';
  document.getElementById('panel-unlock').style.display = 'block';
  document.getElementById('panel-setup').style.display = 'none';
  document.getElementById('input-unlock-pass').value = '';
  document.getElementById('unlock-error').style.display = 'none';
  document.getElementById('input-unlock-pass').focus();
}

function showDashboard() {
  document.getElementById('auth-view').style.display = 'none';
  document.getElementById('app-sidebar').style.display = 'flex';
  document.getElementById('dashboard-wrapper').style.display = 'flex';
  renderCards();
}

function showError(element, msg) {
  element.innerText = msg;
  element.style.display = 'block';
}

// Descoberta Inteligente de Logo por Serviço
function getServiceLogoUrl(servico) {
  if (!servico) return '';
  const clean = servico.toLowerCase().trim();

  const map = {
    gmail: 'gmail.com',
    google: 'google.com',
    hackerone: 'hackerone.com',
    github: 'github.com',
    gitlab: 'gitlab.com',
    bitbucket: 'bitbucket.org',
    discord: 'discord.com',
    slack: 'slack.com',
    telegram: 'telegram.org',
    whatsapp: 'whatsapp.com',
    microsoft: 'microsoft.com',
    outlook: 'outlook.com',
    hotmail: 'outlook.com',
    office: 'office.com',
    azure: 'azure.microsoft.com',
    aws: 'aws.amazon.com',
    amazon: 'amazon.com',
    netflix: 'netflix.com',
    spotify: 'spotify.com',
    steam: 'steampowered.com',
    epic: 'epicgames.com',
    twitter: 'x.com',
    x: 'x.com',
    instagram: 'instagram.com',
    facebook: 'facebook.com',
    linkedin: 'linkedin.com',
    reddit: 'reddit.com',
    chatgpt: 'openai.com',
    openai: 'openai.com',
    anthropic: 'anthropic.com',
    claude: 'claude.ai',
    cloudflare: 'cloudflare.com',
    apple: 'apple.com',
    icloud: 'apple.com',
    uber: 'uber.com',
    paypal: 'paypal.com',
    twitch: 'twitch.tv',
    dropbox: 'dropbox.com',
    notion: 'notion.so',
    figma: 'figma.com',
    trello: 'trello.com',
    jira: 'atlassian.com',
    atlassian: 'atlassian.com',
    binance: 'binance.com',
    coinbase: 'coinbase.com',
    mercado: 'mercadolivre.com.br',
    mercadolivre: 'mercadolivre.com.br',
    mercadopago: 'mercadopago.com.br',
    nubank: 'nubank.com.br',
    inter: 'bancointer.com.br',
    itau: 'itau.com.br',
    bradesco: 'bradesco.com.br',
    santander: 'santander.com.br',
    caixa: 'caixa.gov.br',
    proton: 'proton.me',
    protonmail: 'proton.me',
    tuta: 'tuta.com',
    tutanota: 'tuta.com',
    docker: 'docker.com',
    digitalocean: 'digitalocean.com',
    heroku: 'heroku.com',
    vercel: 'vercel.com',
    render: 'render.com',
    tryhackme: 'tryhackme.com',
    hackthebox: 'hackthebox.com',
    shodan: 'shodan.io',
    virustotal: 'virustotal.com',
    crowdstrike: 'crowdstrike.com',
    bugcrowd: 'bugcrowd.com',
    intigriti: 'intigriti.com',
    cisco: 'cisco.com',
    oracle: 'oracle.com',
    adobe: 'adobe.com',
    canva: 'canva.com',
    pinterest: 'pinterest.com',
    tiktok: 'tiktok.com',
    youtube: 'youtube.com'
  };

  for (const [key, domain] of Object.entries(map)) {
    if (clean.includes(key)) {
      return `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
    }
  }

  const urlMatch = clean.match(/(?:https?:\/\/)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
  if (urlMatch) {
    return `https://www.google.com/s2/favicons?domain=${urlMatch[1]}&sz=64`;
  }

  const single = clean.replace(/[^a-z0-9]/g, '');
  if (single.length >= 3) {
    return `https://www.google.com/s2/favicons?domain=${single}.com&sz=64`;
  }

  return '';
}

// Descoberta Inteligente de URL de Acesso por Serviço
function getServiceUrl(entry) {
  if (entry.url && entry.url.trim()) {
    let u = entry.url.trim();
    if (!u.startsWith('http://') && !u.startsWith('https://')) {
      u = 'https://' + u;
    }
    return u;
  }

  const clean = (entry.servico || '').toLowerCase().trim();
  if (!clean) return '';

  const urlMap = {
    gmail: 'https://mail.google.com',
    google: 'https://accounts.google.com',
    hackerone: 'https://hackerone.com',
    github: 'https://github.com/login',
    gitlab: 'https://gitlab.com/users/sign_in',
    bitbucket: 'https://bitbucket.org',
    discord: 'https://discord.com/login',
    slack: 'https://slack.com/signin',
    telegram: 'https://web.telegram.org',
    whatsapp: 'https://web.whatsapp.com',
    microsoft: 'https://login.live.com',
    outlook: 'https://outlook.live.com',
    hotmail: 'https://outlook.live.com',
    office: 'https://office.com',
    azure: 'https://portal.azure.com',
    aws: 'https://aws.amazon.com/console/',
    amazon: 'https://amazon.com.br',
    netflix: 'https://netflix.com/login',
    spotify: 'https://open.spotify.com',
    steam: 'https://store.steampowered.com/login/',
    epic: 'https://store.epicgames.com',
    twitter: 'https://x.com',
    x: 'https://x.com',
    instagram: 'https://instagram.com',
    facebook: 'https://facebook.com',
    linkedin: 'https://linkedin.com/login',
    reddit: 'https://reddit.com/login',
    chatgpt: 'https://chatgpt.com',
    openai: 'https://platform.openai.com',
    anthropic: 'https://claude.ai',
    claude: 'https://claude.ai',
    cloudflare: 'https://dash.cloudflare.com',
    apple: 'https://appleid.apple.com',
    icloud: 'https://icloud.com',
    uber: 'https://uber.com',
    paypal: 'https://paypal.com/signin',
    twitch: 'https://twitch.tv/login',
    dropbox: 'https://dropbox.com/login',
    notion: 'https://notion.so/login',
    figma: 'https://figma.com/login',
    trello: 'https://trello.com/login',
    jira: 'https://id.atlassian.com/login',
    binance: 'https://binance.com',
    coinbase: 'https://coinbase.com',
    mercadolivre: 'https://mercadolivre.com.br',
    mercado: 'https://mercadolivre.com.br',
    mercadopago: 'https://mercadopago.com.br',
    nubank: 'https://nubank.com.br',
    inter: 'https://bancointer.com.br',
    itau: 'https://itau.com.br',
    bradesco: 'https://banco.bradesco',
    santander: 'https://santander.com.br',
    caixa: 'https://caixa.gov.br',
    proton: 'https://account.proton.me',
    protonmail: 'https://account.proton.me',
    tuta: 'https://app.tuta.com',
    tutanota: 'https://app.tuta.com',
    docker: 'https://hub.docker.com',
    digitalocean: 'https://cloud.digitalocean.com/login',
    heroku: 'https://dashboard.heroku.com',
    vercel: 'https://vercel.com/login',
    render: 'https://dashboard.render.com',
    tryhackme: 'https://tryhackme.com/login',
    hackthebox: 'https://app.hackthebox.com/login',
    shodan: 'https://account.shodan.io/login',
    virustotal: 'https://virustotal.com/gui/sign-in',
    crowdstrike: 'https://falcon.crowdstrike.com',
    bugcrowd: 'https://identity.bugcrowd.com/login',
    intigriti: 'https://app.intigriti.com/login',
    canva: 'https://canva.com/login',
    tiktok: 'https://tiktok.com',
    youtube: 'https://youtube.com'
  };

  for (const [key, url] of Object.entries(urlMap)) {
    if (clean.includes(key)) {
      return url;
    }
  }

  const urlMatch = clean.match(/(?:https?:\/\/)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
  if (urlMatch) {
    return 'https://' + urlMatch[1];
  }

  const single = clean.replace(/[^a-z0-9]/g, '');
  if (single.length >= 3) {
    return `https://${single}.com`;
  }

  return '';
}

// Renderização dos Cards AegisCore
function renderCards() {
  const container = document.getElementById('cards-container');
  const emptyState = document.getElementById('empty-state');
  container.innerHTML = '';

  const filtered = state.entries.filter((item) => {
    if (state.filter) {
      const q = state.filter;
      const match =
        item.servico.toLowerCase().includes(q) ||
        (item.usuario && item.usuario.toLowerCase().includes(q)) ||
        (item.notas && item.notas.toLowerCase().includes(q));
      if (!match) return false;
    }

    if (state.categoryFilter === 'favorites') {
      return Boolean(item.favorito);
    }

    return true;
  });

  const totalCount = state.entries.length;
  const favCount = state.entries.filter((item) => Boolean(item.favorito)).length;
  const totalBadge = document.getElementById('nav-count-total');
  if (totalBadge) totalBadge.innerText = totalCount;
  const favBadge = document.getElementById('nav-count-fav');
  if (favBadge) favBadge.innerText = favCount;

  if (filtered.length === 0) {
    emptyState.style.display = 'flex';
    return;
  }
  emptyState.style.display = 'none';

  filtered.forEach((entry) => {
    const card = document.createElement('div');
    card.className = 'credential-card';
    card.setAttribute('draggable', 'true');
    card.dataset.id = entry.id;

    const initials = (entry.servico || 'AC')
      .split(' ')
      .map((s) => s[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();

    const logoUrl = getServiceLogoUrl(entry.servico);
    const siteUrl = getServiceUrl(entry);
    const isFav = Boolean(entry.favorito);

    card.innerHTML = `
      <div>
        <div class="card-header">
          <div class="card-service">
            <div class="service-badge">
              ${logoUrl ? `<img class="service-logo" src="${logoUrl}" alt="${escapeAttr(entry.servico)}" loading="lazy" onerror="this.remove()" />` : ''}
              <span class="service-initials">${initials}</span>
            </div>
            <div class="service-info">
              <div class="service-name" title="${escapeHtml(entry.servico)}">${escapeHtml(entry.servico)}</div>
              <div class="service-sub">${entry.criado_em ? entry.criado_em : 'Protegido'}</div>
            </div>
          </div>
          <div class="card-header-actions">
            ${
              siteUrl
                ? `<button type="button" class="btn-launch-site" title="Abrir site no navegador (${siteUrl})" onclick="openServiceUrl('${escapeAttr(siteUrl)}', event)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                      <polyline points="15 3 21 3 21 9"/>
                      <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </button>`
                : ''
            }
            <button type="button" class="btn-star ${isFav ? 'active' : ''}" title="${isFav ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}" onclick="toggleFavorite('${entry.id}', event)">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="${isFav ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
            </button>
            <span class="card-tag">Aegis Vault</span>
          </div>
        </div>

        <div class="card-data-section">
          <div class="card-data-row">
            <svg class="data-row-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <span class="data-row-text">${escapeHtml(entry.usuario || 'Não informado')}</span>
          </div>

          <div class="card-data-row">
            <svg class="data-row-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            <span class="data-row-text mono" id="pass-val-${entry.id}">••••••••••••</span>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--gold-primary)" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
          </div>
        </div>

        ${
          entry.notas
            ? `<div class="card-notes" title="${escapeHtml(entry.notas)}">${escapeHtml(entry.notas)}</div>`
            : ''
        }
      </div>

      <div class="card-action-bar">
        <div class="card-action-btns-left">
          <button class="btn-primary" onclick="copyPassword('${escapeAttr(entry.senha)}')">
            Copiar Senha
          </button>
          <button class="btn-secondary" onclick="copyUser('${escapeAttr(entry.usuario)}')">
            Usuário
          </button>
          <button class="btn-icon-btn" title="Mostrar/Ocultar" onclick="toggleCardPassword('${entry.id}', '${escapeAttr(entry.senha)}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>

        <div class="card-action-btns-right">
          <button class="btn-icon-btn" title="Editar" onclick="editEntry('${entry.id}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn-danger-ghost" title="Excluir" onclick="promptDelete('${entry.id}', '${escapeAttr(entry.servico)}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
    `;

    // Listeners de Drag and Drop
    card.addEventListener('dragstart', (e) => {
      if (e.target.closest('button, input, textarea, a')) {
        e.preventDefault();
        return;
      }
      state.draggedId = entry.id;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', entry.id);
    });

    card.addEventListener('dragend', () => {
      state.draggedId = null;
      card.classList.remove('dragging');
      document.querySelectorAll('.credential-card').forEach((c) => c.classList.remove('drag-over'));
    });

    card.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (!state.draggedId || state.draggedId === entry.id) return;
      e.dataTransfer.dropEffect = 'move';
      card.classList.add('drag-over');
    });

    card.addEventListener('dragleave', (e) => {
      if (!card.contains(e.relatedTarget)) {
        card.classList.remove('drag-over');
      }
    });

    card.addEventListener('drop', async (e) => {
      e.preventDefault();
      card.classList.remove('drag-over');
      const targetId = entry.id;
      const sourceId = state.draggedId;
      if (!sourceId || sourceId === targetId) return;

      const fromIndex = state.entries.findIndex((i) => i.id === sourceId);
      const toIndex = state.entries.findIndex((i) => i.id === targetId);

      if (fromIndex !== -1 && toIndex !== -1 && fromIndex !== toIndex) {
        const [movedItem] = state.entries.splice(fromIndex, 1);
        state.entries.splice(toIndex, 0, movedItem);
        renderCards();

        const orderedIds = state.entries.map((i) => i.id);
        const res = await callApi('reorder_entries', orderedIds);
        if (res && res.success) {
          state.entries = res.entries;
          triggerToast('Ordem das credenciais salva ✨', 2);
        }
      }
    });

    container.appendChild(card);
  });
}

// Ações do Usuário
window.toggleCardPassword = function (id, rawPassword) {
  const el = document.getElementById(`pass-val-${id}`);
  if (!el) return;
  if (el.innerText === '••••••••••••') {
    el.innerText = rawPassword;
    el.style.color = '#ffffff';
  } else {
    el.innerText = '••••••••••••';
    el.style.color = 'var(--text-primary)';
  }
};

window.copyUser = async function (user) {
  if (!user) return;
  await callApi('copy_to_clipboard', user, false);
  triggerToast('Usuário copiado para a área de transferência', 3);
};

window.copyPassword = async function (pass) {
  if (!pass) return;
  await callApi('copy_to_clipboard', pass, true);
  triggerToast('Senha copiada com segurança • Limpeza em', 15);
};

// Alternar Favorito AegisCore
window.toggleFavorite = async function (id, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  // Atualização otimista na interface
  const item = state.entries.find((e) => e.id === id);
  if (item) {
    item.favorito = !item.favorito;
    renderCards();
  }

  const res = await callApi('toggle_favorite', id);
  if (res && res.success) {
    state.entries = res.entries;
    renderCards();
    const isFav = state.entries.find((e) => e.id === id)?.favorito;
    triggerToast(isFav ? 'Marcado como favorito ⭐' : 'Removido dos favoritos', 2);
  } else {
    // Reverte se falhou
    if (item) {
      item.favorito = !item.favorito;
      renderCards();
    }
    alert(res?.error || 'Falha ao alterar favorito.');
  }
};

// Abrir Site Externo no Navegador Padrão
window.openServiceUrl = async function (url, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  if (!url) return;
  await callApi('open_url', url);
  triggerToast('Abrindo site no navegador 🌐', 2);
};

// Toast AegisCore
function triggerToast(msg, durationSec) {
  const toast = document.getElementById('clipboard-toast');
  const msgEl = document.getElementById('toast-message');
  const timerEl = document.getElementById('toast-timer');

  msgEl.innerText = msg;
  timerEl.innerText = `${durationSec}s`;
  toast.classList.add('show');

  if (state.clipboardTimer) clearInterval(state.clipboardTimer);

  let remaining = durationSec;
  state.clipboardTimer = setInterval(() => {
    remaining--;
    timerEl.innerText = `${remaining}s`;

    if (remaining <= 0) {
      clearInterval(state.clipboardTimer);
      toast.classList.remove('show');
    }
  }, 1000);
}

// Modal Adicionar / Editar
function openEntryModal(entry = null) {
  const modal = document.getElementById('modal-entry');
  const title = document.getElementById('modal-entry-title');
  const idInput = document.getElementById('entry-id');
  const servInput = document.getElementById('entry-service');
  const userInput = document.getElementById('entry-username');
  const urlInput = document.getElementById('entry-url');
  const passInput = document.getElementById('entry-password');
  const notesInput = document.getElementById('entry-notes');

  if (entry) {
    title.innerText = 'Editar credencial';
    idInput.value = entry.id;
    servInput.value = entry.servico;
    userInput.value = entry.usuario || '';
    urlInput.value = entry.url || '';
    passInput.value = entry.senha || '';
    passInput.type = 'password';
    notesInput.value = entry.notas || '';
    updateEntropyMeter(entry.senha, 'entry-meter-fill', 'entry-meter-label', 'entry-meter-bits');
  } else {
    title.innerText = 'Nova credencial AegisCore';
    idInput.value = '';
    servInput.value = '';
    userInput.value = '';
    urlInput.value = '';
    passInput.value = '';
    passInput.type = 'password';
    notesInput.value = '';
    updateEntropyMeter('', 'entry-meter-fill', 'entry-meter-label', 'entry-meter-bits');
  }

  modal.classList.add('active');
  servInput.focus();
}

function closeEntryModal() {
  document.getElementById('modal-entry').classList.remove('active');
}

window.editEntry = function (id) {
  const entry = state.entries.find((e) => e.id === id);
  if (entry) openEntryModal(entry);
};

async function handleSaveEntry(e) {
  if (e) e.preventDefault();
  const id = document.getElementById('entry-id').value;
  const servico = document.getElementById('entry-service').value.trim();
  const usuario = document.getElementById('entry-username').value.trim();
  const url = document.getElementById('entry-url').value.trim();
  const senha = document.getElementById('entry-password').value;
  const notas = document.getElementById('entry-notes').value.trim();

  if (!servico || !senha) {
    alert('Serviço e senha são obrigatórios.');
    return;
  }

  const existing = id ? state.entries.find((e) => e.id === id) : null;
  const payload = {
    id: id || undefined,
    servico,
    usuario,
    senha,
    url,
    notas,
    favorito: existing ? Boolean(existing.favorito) : false,
  };

  const res = await callApi('save_entry', payload);
  if (res && res.success) {
    state.entries = res.entries;
    closeEntryModal();
    renderCards();
    triggerToast('Credencial protegida no AegisCore', 3);
  } else {
    alert('Erro ao salvar credencial.');
  }
}

// Modal Exclusão
window.promptDelete = function (id, serviceName) {
  state.pendingDeleteId = id;
  document.getElementById('delete-service-name').innerText = serviceName;
  document.getElementById('modal-delete').classList.add('active');
};

function closeDeleteModal() {
  document.getElementById('modal-delete').classList.remove('active');
  state.pendingDeleteId = null;
}

async function handleConfirmDelete() {
  if (!state.pendingDeleteId) return;
  const res = await callApi('delete_entry', state.pendingDeleteId);
  if (res && res.success) {
    state.entries = res.entries;
    closeDeleteModal();
    renderCards();
    triggerToast('Credencial excluída', 3);
  }
}

// Gerador de Senhas
async function openGenModal() {
  document.getElementById('modal-gen').classList.add('active');
  await refreshGeneratorDisplay();
}

function closeGenModal() {
  document.getElementById('modal-gen').classList.remove('active');
}

async function refreshGeneratorDisplay() {
  const len = parseInt(document.getElementById('gen-slider').value, 10);
  const upper = document.getElementById('gen-upper').checked;
  const lower = document.getElementById('gen-lower').checked;
  const digits = document.getElementById('gen-digits').checked;
  const symbols = document.getElementById('gen-symbols').checked;

  const res = await callApi('generate_password', len, upper, lower, digits, symbols);
  if (res && res.password) {
    document.getElementById('gen-display').value = res.password;
    updateEntropyMeter(res.password, 'gen-meter-fill', 'gen-meter-label', 'gen-meter-bits');
  }
}

async function copyGeneratedPassword() {
  const pass = document.getElementById('gen-display').value;
  if (!pass) return;
  await callApi('copy_to_clipboard', pass, true);
  triggerToast('Senha gerada copiada com segurança', 15);
}

// Medidor de Entropia
async function updateEntropyMeter(pwd, fillId, labelId, bitsId) {
  const res = await callApi('calculate_entropy', pwd);
  if (!res) return;

  const fill = document.getElementById(fillId);
  const label = document.getElementById(labelId);
  const bits = document.getElementById(bitsId);

  if (fill) {
    fill.style.width = `${res.percentual}%`;
    fill.style.background = res.cor;
  }
  if (label) {
    label.innerText = `Força: ${res.nivel}`;
  }
  if (bits) {
    bits.innerText = `${res.bits} bits`;
  }
}

// Escape de strings
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeAttr(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
