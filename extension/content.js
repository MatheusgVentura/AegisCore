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

  const AEGIS_SHIELD_SVG = `
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" shape-rendering="geometricPrecision">
      <defs>
        <linearGradient id="aegisGoldGrad" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#fae7b9" />
          <stop offset="35%" stop-color="#d1a868" />
          <stop offset="70%" stop-color="#b89153" />
          <stop offset="100%" stop-color="#735222" />
        </linearGradient>
        <linearGradient id="aegisCoreGrad" x1="12" y1="7" x2="12" y2="16" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="35%" stop-color="#fae7b9" />
          <stop offset="100%" stop-color="#b89153" />
        </linearGradient>
        <radialGradient id="aegisCoreBg" cx="12" cy="11" r="10" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#242017" />
          <stop offset="100%" stop-color="#0e0d09" />
        </radialGradient>
      </defs>
      <!-- Base do Escudo Blindado Aegis -->
      <path d="M12 2L4 5.5V11.5C4 16.8 7.5 21.4 12 22.5C16.5 21.4 20 16.8 20 11.5V5.5L12 2Z" 
            fill="url(#aegisCoreBg)" stroke="url(#aegisGoldGrad)" stroke-width="1.6" stroke-linejoin="round" />
      <!-- Faceta Interna Tática Chanfrada -->
      <path d="M12 3.8L5.5 6.6V11.5C5.5 15.9 8.2 19.8 12 20.8C15.8 19.8 18.5 15.9 18.5 11.5V6.6L12 3.8Z" 
            fill="url(#aegisGoldGrad)" fill-opacity="0.16" />
      <!-- Monograma Tático 'A' do AegisCore -->
      <path d="M12 7.2L8.6 15H10.3L11 13.1H13L13.7 15H15.4L12 7.2ZM11.6 11.6L12 9.4L12.4 11.6H11.6Z" 
            fill="url(#aegisCoreGrad)" />
    </svg>
  `;

  // Posicionamento do badge flutuante à direita do campo de senha ou login
  function updateBadgePosition(inputEl, badgeEl) {
    if (!isElementVisible(inputEl)) {
      badgeEl.style.display = 'none';
      return;
    }

    const rect = inputEl.getBoundingClientRect();
    const scrollX = window.scrollX || document.documentElement.scrollLeft;
    const scrollY = window.scrollY || document.documentElement.scrollTop;

    badgeEl.style.display = 'flex';
    badgeEl.style.left = `${rect.right + scrollX - 30}px`;
    badgeEl.style.top = `${rect.top + scrollY + (rect.height / 2) - 12}px`;
  }

  // Injeção do Badge Desert Gold nos inputs de login e senha
  function scanAndInjectBadges() {
    const passwordInputs = Array.from(document.querySelectorAll('input[type="password"]'));
    const candidateInputs = new Set(passwordInputs);

    // Para cada campo de senha encontrado, busca também o campo de usuário correspondente
    passwordInputs.forEach((passInput) => {
      const userInput = findUsernameInputForPassword(passInput);
      if (userInput) {
        candidateInputs.add(userInput);
      }
    });

    // Inputs com semântica explícita de autenticação
    const explicitAuthInputs = document.querySelectorAll(
      'input[autocomplete="username"], input[autocomplete="email"], input[autocomplete="webauthn"]'
    );
    explicitAuthInputs.forEach((input) => candidateInputs.add(input));

    candidateInputs.forEach((input) => {
      if (attachedBadges.has(input)) return;
      if (!isElementVisible(input)) return;

      const badge = document.createElement('div');
      badge.className = 'aegis-companion-badge';
      badge.setAttribute('title', 'AegisCore — Preenchimento Seguro');
      badge.innerHTML = AEGIS_SHIELD_SVG;

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
          <span style="width: 14px; height: 14px; display: inline-flex;">${AEGIS_SHIELD_SVG}</span>
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
