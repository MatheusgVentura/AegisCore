/**
 * AegisCore Companion — Content Script (In-Page Injection & Autofill)
 * Detecta formulários de autenticação, injeta o badge tático Desert Gold e preenche
 * credenciais com eventos DOM sintéticos compatíveis com React, Vue, Angular e formulários padrão.
 */

(() => {
  // Evita injeção dupla
  if (window.__aegisCoreLoaded) return;
  window.__aegisCoreLoaded = true;

  let activeDropdown = null;
  const attachedBadges = new Map(); // inputEl -> badgeEl

  // Escuta comandos vindos do Popup ou Background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.action === 'AUTOFILL_CREDENTIALS') {
      const result = autofillPageCredentials(message.username, message.password);
      sendResponse(result);
      return true;
    }
  });

  // Função universal de preenchimento com disparo sintético de eventos
  function fillInputValue(inputEl, value) {
    if (!inputEl || value === undefined || value === null) return false;

    try {
      inputEl.focus();

      // Suporte para frameworks reativos (React / Angular / Vue) usando descritor de propriedade nativo
      const proto = Object.getPrototypeOf(inputEl);
      const setDescriptor = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      if (setDescriptor) {
        setDescriptor.call(inputEl, value);
      } else {
        inputEl.value = value;
      }

      // Dispara eventos em cadeia para atualizar o estado do formulário web
      inputEl.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
      inputEl.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
      inputEl.dispatchEvent(new Event('blur', { bubbles: true, cancelable: true }));
      return true;
    } catch (e) {
      console.warn('AegisCore: falha ao preencher input', e);
      return false;
    }
  }

  function findUsernameInputForPassword(passInput) {
    // 1. Tenta achar no mesmo formulário
    const form = passInput.closest('form');
    if (form) {
      const candidates = form.querySelectorAll(
        'input[type="email"], input[type="text"], input[autocomplete*="user"], input[autocomplete*="email"], input[name*="user"], input[name*="login"], input[name*="email"], input[id*="user"], input[id*="login"], input[id*="email"]'
      );
      for (const input of candidates) {
        if (input !== passInput && isElementVisible(input)) {
          return input;
        }
      }
    }

    // 2. Tenta achar o input imediatamente anterior no DOM
    const allInputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="password"])'));
    const visibleInputs = allInputs.filter(isElementVisible);
    const passIndex = visibleInputs.findIndex((el) => el.compareDocumentPosition(passInput) & Node.DOCUMENT_POSITION_FOLLOWING);
    if (passIndex !== -1 && visibleInputs[passIndex]) {
      return visibleInputs[passIndex];
    }

    return null;
  }

  function autofillPageCredentials(username, password) {
    const passwordInputs = Array.from(document.querySelectorAll('input[type="password"]')).filter(isElementVisible);

    if (passwordInputs.length === 0) {
      // Se não houver campo de senha visível (ex: login de duas etapas, etapa 1 de e-mail)
      const usernameInput = document.querySelector('input[type="email"], input[type="text"][autocomplete*="user"], input[name*="user"], input[name*="login"]');
      if (usernameInput && username) {
        fillInputValue(usernameInput, username);
        return { success: true, count: 1 };
      }
      return { success: false, error: 'Nenhum campo de senha detectado.' };
    }

    let filledCount = 0;
    const targetPassword = passwordInputs[0];
    const targetUser = findUsernameInputForPassword(targetPassword);

    if (targetUser && username) {
      if (fillInputValue(targetUser, username)) filledCount++;
    }

    if (targetPassword && password) {
      if (fillInputValue(targetPassword, password)) filledCount++;
    }

    return { success: filledCount > 0, count: filledCount };
  }

  function isElementVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return (
      rect.width > 20 &&
      rect.height > 15 &&
      style.visibility !== 'hidden' &&
      style.display !== 'none' &&
      style.opacity !== '0'
    );
  }

  // Posicionamento do badge flutuante à direita do campo de senha
  function updateBadgePosition(inputEl, badgeEl) {
    if (!isElementVisible(inputEl)) {
      badgeEl.style.display = 'none';
      return;
    }

    const rect = inputEl.getBoundingClientRect();
    const scrollX = window.scrollX || document.documentElement.scrollLeft;
    const scrollY = window.scrollY || document.documentElement.scrollTop;

    badgeEl.style.display = 'flex';
    badgeEl.style.left = `${rect.right + scrollX - 28}px`;
    badgeEl.style.top = `${rect.top + scrollY + (rect.height / 2) - 11}px`;
  }

  // Injeção do Badge Desert Gold nos inputs de senha
  function scanAndInjectBadges() {
    const passwordInputs = document.querySelectorAll('input[type="password"]');

    passwordInputs.forEach((input) => {
      if (attachedBadges.has(input)) return;
      if (!isElementVisible(input)) return;

      const badge = document.createElement('div');
      badge.className = 'aegis-companion-badge';
      badge.setAttribute('title', 'AegisCore — Preenchimento Seguro');
      badge.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="#b89153" stroke-width="2.2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
      `;

      badge.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleDropdownForInput(input, badge);
      });

      document.body.appendChild(badge);
      attachedBadges.set(input, badge);
      updateBadgePosition(input, badge);
    });
  }

  // Dropdown Tático Inline Flutuante
  function toggleDropdownForInput(inputEl, badgeEl) {
    if (activeDropdown) {
      activeDropdown.remove();
      activeDropdown = null;
      return;
    }

    const dropdown = document.createElement('div');
    dropdown.className = 'aegis-companion-dropdown';

    const rect = inputEl.getBoundingClientRect();
    const scrollX = window.scrollX || document.documentElement.scrollLeft;
    const scrollY = window.scrollY || document.documentElement.scrollTop;

    dropdown.style.left = `${rect.left + scrollX}px`;
    dropdown.style.top = `${rect.bottom + scrollY + 4}px`;

    dropdown.innerHTML = `
      <div class="aegis-dropdown-header">
        <span class="aegis-dropdown-title">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#b89153" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          AegisCore Vault
        </span>
        <button type="button" class="aegis-dropdown-close">&times;</button>
      </div>
      <div class="aegis-dropdown-list" id="aegis-dropdown-items">
        <div style="color: #8e8677; font-size: 11px; padding: 8px; text-align: center;">Carregando credenciais...</div>
      </div>
      <div class="aegis-dropdown-footer">
        <span>100% Offline</span>
        <span>AegisCore v2.0</span>
      </div>
    `;

    dropdown.querySelector('.aegis-dropdown-close').addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.remove();
      activeDropdown = null;
    });

    document.body.appendChild(dropdown);
    activeDropdown = dropdown;

    // Carrega credenciais do servidor local
    chrome.runtime.sendMessage(
      { action: 'QUERY_CREDENTIALS', url: window.location.href },
      (res) => {
        const itemsContainer = dropdown.querySelector('#aegis-dropdown-items');
        if (!itemsContainer) return;

        if (!res || !res.success || !res.entries || res.entries.length === 0) {
          itemsContainer.innerHTML = `
            <div style="color: #8e8677; font-size: 11px; padding: 8px; text-align: center;">
              ${res?.locked ? '🔒 Cofre local bloqueado. Desbloqueie no AegisCore Desktop.' : 'Nenhuma credencial encontrada para este site.'}
            </div>
          `;
          return;
        }

        itemsContainer.innerHTML = '';
        res.entries.forEach((entry) => {
          const itemEl = document.createElement('div');
          itemEl.className = 'aegis-dropdown-item';
          itemEl.innerHTML = `
            <span class="aegis-item-service">${escapeHtml(entry.servico || 'Credencial')}</span>
            <span class="aegis-item-user">${escapeHtml(entry.usuario || 'Sem usuário')}</span>
          `;

          itemEl.addEventListener('click', () => {
            chrome.runtime.sendMessage({ action: 'GET_FILL', id: entry.id }, (fillRes) => {
              if (fillRes && fillRes.success && fillRes.entry) {
                autofillPageCredentials(fillRes.entry.usuario, fillRes.entry.senha);
              }
              dropdown.remove();
              activeDropdown = null;
            });
          });

          itemsContainer.appendChild(itemEl);
        });
      }
    );
  }

  // Fechamento de dropdown ao clicar fora
  document.addEventListener('click', (e) => {
    if (activeDropdown && !activeDropdown.contains(e.target) && !e.target.closest('.aegis-companion-badge')) {
      activeDropdown.remove();
      activeDropdown = null;
    }
  });

  // Reposiciona badges ao rolar ou redimensionar a janela
  const repositionAll = () => {
    attachedBadges.forEach((badge, input) => {
      updateBadgePosition(input, badge);
    });
  };
  window.addEventListener('scroll', repositionAll, { passive: true });
  window.addEventListener('resize', repositionAll, { passive: true });

  // Observer para detecção dinâmica em SPAs
  let debounceTimeout = null;
  const observer = new MutationObserver(() => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(scanAndInjectBadges, 300);
  });

  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
  });

  // Escaneamento inicial
  scanAndInjectBadges();

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
})();
