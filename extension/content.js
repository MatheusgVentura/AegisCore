/**
 * AegisCore Companion — Content Script (In-Page Injection & Autofill)
 * Detecta formulários de autenticação, injeta o badge tático Desert Gold e preenche
 * credenciais com eventos DOM sintéticos compatíveis com React, Vue, Angular e formulários padrão.
 */

(() => {
  // Limpeza preventiva de quaisquer badges ou dropdowns residuais no DOM
  document.querySelectorAll('.aegis-companion-badge, .aegis-companion-dropdown').forEach((el) => el.remove());

  // Evita injeção dupla no mesmo contexto
  if (window.__aegisCoreLoaded) return;
  window.__aegisCoreLoaded = true;

  let activeDropdown = null;
  const attachedBadges = new Map(); // inputEl -> badgeEl

  // Escuta comandos vindos do Popup ou Background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.action === 'AUTOFILL_CREDENTIALS') {
      const result = autofillPageCredentials(message.username, message.password, message.totp);
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

  // Verificação rigorosa de visibilidade real do elemento na tela
  function isElementVisible(el) {
    if (!el || !(el instanceof HTMLElement)) return false;
    if (el.type === 'hidden') return false;

    // 1. Verificação nativa moderna de visibilidade (Chrome 105+)
    if (typeof el.checkVisibility === 'function') {
      if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) {
        return false;
      }
    }

    // 2. offsetParent é null quando o elemento ou algum pai tem display: none
    const style = window.getComputedStyle(el);
    if (el.offsetParent === null && style.position !== 'fixed') {
      return false;
    }

    // 3. Estilos de invisibilidade
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0' || parseFloat(style.opacity) < 0.1) {
      return false;
    }

    // 4. Dimensões reais do retângulo visível
    const rect = el.getBoundingClientRect();
    if (rect.width < 40 || rect.height < 18) {
      return false;
    }

    // 5. Atributos de elemento desabilitado/oculto
    if (el.getAttribute('aria-hidden') === 'true' || el.disabled || el.readOnly) {
      return false;
    }

    return true;
  }

  function findUsernameInputForPassword(passInput) {
    const form = passInput.closest('form');
    const container = form || passInput.parentElement?.parentElement || document;

    const candidates = Array.from(
      container.querySelectorAll('input[type="email"], input[type="text"], input[type="tel"]')
    ).filter((input) => input !== passInput && isElementVisible(input));

    // Prioridade 1: Campos com autocomplete explícito de identificação
    for (const input of candidates) {
      const auto = (input.getAttribute('autocomplete') || '').toLowerCase();
      if (auto.includes('username') || auto.includes('email')) {
        return input;
      }
    }

    // Prioridade 2: Campos com name ou id sugestivo, excluindo expressamente campos de código/busca/backup
    const userPatterns = /user|email|login|account|ident/i;
    for (const input of candidates) {
      const nameOrId = `${input.name} ${input.id} ${input.placeholder}`;
      if (userPatterns.test(nameOrId) && !/search|otp|totp|code|backup|pin|captcha/i.test(nameOrId)) {
        return input;
      }
    }

    // Prioridade 3: Se estiver no mesmo form, o input imediatamente anterior que não seja código/busca
    if (form) {
      const formTextInputs = candidates.filter((el) => {
        const nameOrId = `${el.name} ${el.id}`;
        return !/search|otp|totp|code|backup|pin|captcha/i.test(nameOrId);
      });
      const beforeInputs = formTextInputs.filter(
        (el) => el.compareDocumentPosition(passInput) & Node.DOCUMENT_POSITION_FOLLOWING
      );
      if (beforeInputs.length > 0) {
        return beforeInputs[beforeInputs.length - 1];
      }
    }

    return null;
  }

  function autofillPageCredentials(username, password, totp) {
    const passwordInputs = Array.from(document.querySelectorAll('input[type="password"]')).filter(isElementVisible);

    // Se for tela de 2FA / TOTP (sem senha)
    const totpInput = document.querySelector('input[autocomplete="one-time-code"], input[name="app_totp"], input[id="app_totp"]');
    if (totpInput && isElementVisible(totpInput) && totp) {
      fillInputValue(totpInput, totp);
      return { success: true, count: 1 };
    }

    if (passwordInputs.length === 0) {
      // Se não houver campo de senha visível (ex: login de duas etapas, etapa 1 de e-mail)
      const usernameInput = document.querySelector(
        'input[type="email"], input[type="text"][autocomplete*="user"], input[name*="user"], input[name*="login"]'
      );
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

  // Injeção do Badge Desert Gold nos inputs com proteção anti-duplicação
  function scanAndInjectBadges() {
    // 1. Limpeza de badges órfãos ou desconectados
    for (const [input, badge] of attachedBadges.entries()) {
      if (!input.isConnected || !isElementVisible(input)) {
        badge.remove();
        attachedBadges.delete(input);
        delete input.dataset.aegisBadgeAttached;
      }
    }

    // 2. Remoção de elementos residuais no DOM não rastreados
    const domBadges = document.querySelectorAll('.aegis-companion-badge');
    domBadges.forEach((domBadge) => {
      let isTracked = false;
      for (const badge of attachedBadges.values()) {
        if (badge === domBadge) {
          isTracked = true;
          break;
        }
      }
      if (!isTracked) {
        domBadge.remove();
      }
    });

    // 3. Coleta de candidatos estritamente válidos
    const passwordInputs = Array.from(document.querySelectorAll('input[type="password"]')).filter(isElementVisible);
    const candidateInputs = new Set(passwordInputs);

    // Para cada campo de senha encontrado, busca o campo de usuário correspondente
    passwordInputs.forEach((passInput) => {
      const userInput = findUsernameInputForPassword(passInput);
      if (userInput) {
        candidateInputs.add(userInput);
      }
    });

    // Inputs com autocomplete explícito de identificação
    const explicitAuthInputs = Array.from(
      document.querySelectorAll('input[autocomplete="username"], input[autocomplete="email"]')
    ).filter(isElementVisible);
    explicitAuthInputs.forEach((input) => candidateInputs.add(input));

    // Inputs de TOTP em telas de 2FA (apenas o principal)
    const totpInputs = Array.from(
      document.querySelectorAll('input[autocomplete="one-time-code"], input[name="app_totp"], input[id="app_totp"]')
    ).filter(isElementVisible);
    if (totpInputs.length > 0) {
      candidateInputs.add(totpInputs[0]); // Apenas o primeiro, NUNCA backup code!
    }

    // 4. Injeção com deduplicação espacial
    candidateInputs.forEach((input) => {
      if (!isElementVisible(input)) return;

      // Se já está anexado, apenas atualiza posição
      if (attachedBadges.has(input) || input.dataset.aegisBadgeAttached === 'true') {
        const existingBadge = attachedBadges.get(input);
        if (existingBadge) {
          updateBadgePosition(input, existingBadge);
        }
        return;
      }

      // Prevenção de colisão espacial com outros badges já posicionados
      const rect = input.getBoundingClientRect();
      for (const [existingInput] of attachedBadges.entries()) {
        const existingRect = existingInput.getBoundingClientRect();
        const dX = Math.abs(rect.left - existingRect.left);
        const dY = Math.abs(rect.top - existingRect.top);
        if (dX < 15 && dY < 15) {
          return; // Já existe um badge cobrindo a mesma área visual
        }
      }

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
      input.dataset.aegisBadgeAttached = 'true';
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
                autofillPageCredentials(fillRes.entry.usuario, fillRes.entry.senha, fillRes.entry.totp);
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
    debounceTimeout = setTimeout(scanAndInjectBadges, 250);
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
