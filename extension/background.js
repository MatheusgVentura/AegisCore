/**
 * AegisCore Companion — Background Service Worker (Manifest V3)
 * Responsável pela comunicação segura em loopback com o servidor local Desktop (127.0.0.1:18291),
 * gerenciamento de tokens de sessão, monitoramento de status do cofre e barramento de mensagens.
 */

const DEFAULT_HOST = '127.0.0.1';
const DEFAULT_PORT = 18291;

// Obter configurações persistidas em chrome.storage.local
async function getStorageData(keys) {
  return new Promise((resolve) => {
    chrome.storage.local.get(keys, (result) => resolve(result || {}));
  });
}

async function setStorageData(data) {
  return new Promise((resolve) => {
    chrome.storage.local.set(data, () => resolve());
  });
}

async function getServerBaseUrl() {
  const data = await getStorageData(['serverHost', 'serverPort']);
  const host = data.serverHost || DEFAULT_HOST;
  const port = data.serverPort || DEFAULT_PORT;
  return `http://${host}:${port}`;
}

async function getAuthToken() {
  const data = await getStorageData(['aegisToken']);
  return data.aegisToken || null;
}

// Wrapper seguro de Fetch com timeout
async function fetchLocalApi(endpoint, options = {}) {
  const baseUrl = await getServerBaseUrl();
  const token = await getAuthToken();
  const url = `${baseUrl}${endpoint}`;

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers['X-Aegis-Token'] = token;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3500);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    const contentType = response.headers.get('content-type') || '';
    let body = {};
    if (contentType.includes('application/json')) {
      body = await response.json();
    }

    return {
      ok: response.ok,
      status: response.status,
      data: body,
    };
  } catch (err) {
    clearTimeout(timeoutId);
    return {
      ok: false,
      status: 0,
      error: err.name === 'AbortError' ? 'Timeout de conexão' : 'AegisCore Desktop não acessível',
    };
  }
}

// Atualização visual do Badge do ícone da extensão
async function updateBadgeStatus(status) {
  try {
    if (!status || !status.online) {
      await chrome.action.setBadgeText({ text: 'OFF' });
      await chrome.action.setBadgeBackgroundColor({ color: '#4b5563' }); // Cinza
      await chrome.action.setTitle({ title: 'AegisCore: Desktop Inativo' });
      return;
    }

    if (!status.unlocked) {
      await chrome.action.setBadgeText({ text: 'LOCK' });
      await chrome.action.setBadgeBackgroundColor({ color: '#d97706' }); // Âmbar
      await chrome.action.setTitle({ title: 'AegisCore: Cofre Bloqueado' });
      return;
    }

    // Conectado e Desbloqueado
    await chrome.action.setBadgeText({ text: '' });
    await chrome.action.setTitle({ title: 'AegisCore: Conectado e Ativo' });
  } catch (e) {
    // Ignora erros caso o contexto de ação não esteja pronto
  }
}

// Checagem de status de conexão com o AegisCore Desktop
async function checkServerStatus() {
  const res = await fetchLocalApi('/api/status', { method: 'GET' });
  let status = { online: false, unlocked: false, version: '' };

  if (res.ok && res.data) {
    status = {
      online: true,
      unlocked: !!res.data.unlocked,
      version: res.data.version || '2.0.0',
    };
  }

  await setStorageData({ lastStatus: status });
  await updateBadgeStatus(status);
  return status;
}

let pairingPollingTimer = null;

function stopPairingPolling() {
  if (pairingPollingTimer) {
    clearInterval(pairingPollingTimer);
    pairingPollingTimer = null;
  }
}

function startPairingPolling(code) {
  stopPairingPolling();
  const startTime = Date.now();

  pairingPollingTimer = setInterval(async () => {
    // Se passou de 120s, encerra o polling
    if (Date.now() - startTime > 120000) {
      stopPairingPolling();
      await setStorageData({ pendingPair: null });
      return;
    }

    // Se já foi pareado, para
    const currentToken = await getAuthToken();
    if (currentToken) {
      stopPairingPolling();
      await setStorageData({ pendingPair: null });
      return;
    }

    const res = await fetchLocalApi('/api/confirm-pair', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });

    if (res.ok && res.data && res.data.success && res.data.token) {
      // Pareamento aprovado com sucesso no Desktop!
      stopPairingPolling();
      await setStorageData({
        aegisToken: res.data.token,
        pendingPair: null,
      });
      await checkServerStatus();
      return;
    }

    // Se o código expirou ou falhou fatalmente
    if (!res.ok && res.status === 400) {
      stopPairingPolling();
      await setStorageData({ pendingPair: null });
    }
  }, 1200);
}

// Início do pareamento com o Desktop
async function requestPairing(clientName) {
  const name = clientName || 'Navegador Web';
  const res = await fetchLocalApi('/api/pair', {
    method: 'POST',
    body: JSON.stringify({ client_name: name }),
  });

  if (res.ok && res.data && res.data.success) {
    const code = res.data.code;
    await setStorageData({
      pendingPair: {
        code,
        clientName: name,
        createdAt: Date.now(),
      },
    });
    startPairingPolling(code);
    return {
      success: true,
      code,
      status: 'pending',
    };
  }

  return {
    success: false,
    error: res.error || res.data?.error || 'Falha ao solicitar pareamento.',
  };
}

// Confirmação do código de 6 dígitos
async function confirmPairing(code) {
  const res = await fetchLocalApi('/api/confirm-pair', {
    method: 'POST',
    body: JSON.stringify({ code }),
  });

  if (res.ok && res.data && res.data.success && res.data.token) {
    stopPairingPolling();
    await setStorageData({
      aegisToken: res.data.token,
      pendingPair: null,
    });
    await checkServerStatus();
    return { success: true };
  }

  if (res.ok && res.data && res.data.waiting) {
    return {
      success: false,
      waiting: true,
      error: res.data.error || 'Aguardando autorização no AegisCore Desktop.',
    };
  }

  stopPairingPolling();
  await setStorageData({ pendingPair: null });
  return {
    success: false,
    waiting: false,
    error: res.data?.error || 'Código de confirmação incorreto ou expirado.',
  };
}

// Cancelar solicitação de pareamento
async function cancelPairing() {
  stopPairingPolling();
  await setStorageData({ pendingPair: null });
  return { success: true };
}

// Consulta de credenciais para a URL ativa
async function queryCredentialsForUrl(url) {
  const token = await getAuthToken();
  if (!token) {
    return { success: false, notPaired: true };
  }

  const res = await fetchLocalApi('/api/query', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });

  if (res.status === 401) {
    // Token revogado ou inválido
    await setStorageData({ aegisToken: null });
    await updateBadgeStatus({ online: true, unlocked: false });
    return { success: false, notPaired: true };
  }

  if (res.ok && res.data) {
    return res.data;
  }

  return {
    success: false,
    error: res.error || res.data?.error || 'Erro ao consultar credenciais.',
  };
}

// Obtenção segura dos dados de login (usuário, senha, totp) para preenchimento
async function getFillCredentials(entryId) {
  const token = await getAuthToken();
  if (!token) {
    return { success: false, notPaired: true };
  }

  const res = await fetchLocalApi('/api/get-fill', {
    method: 'POST',
    body: JSON.stringify({ id: entryId }),
  });

  if (res.ok && res.data) {
    return res.data;
  }

  return {
    success: false,
    error: res.error || res.data?.error || 'Falha ao obter credenciais.',
  };
}

// Geração de senha forte via motor do cofre
async function generatePassword(options = {}) {
  const res = await fetchLocalApi('/api/generate-password', {
    method: 'POST',
    body: JSON.stringify(options),
  });

  if (res.ok && res.data) {
    return res.data;
  }

  return {
    success: false,
    error: res.error || 'Falha ao gerar senha.',
  };
}

// Desconectar pareamento
async function unpairClient() {
  await setStorageData({ aegisToken: null });
  await checkServerStatus();
  return { success: true };
}

// Barramento de Mensagens da Extensão
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const action = message?.action;

  (async () => {
    try {
      switch (action) {
        case 'GET_STATUS': {
          const status = await checkServerStatus();
          const token = await getAuthToken();
          const storage = await getStorageData(['pendingPair']);
          let validPending = null;
          if (storage.pendingPair && (Date.now() - (storage.pendingPair.createdAt || 0)) <= 120000) {
            validPending = storage.pendingPair;
            if (!token && !pairingPollingTimer) {
              startPairingPolling(validPending.code);
            }
          } else if (storage.pendingPair) {
            await setStorageData({ pendingPair: null });
            stopPairingPolling();
          }
          sendResponse({
            success: true,
            status,
            isPaired: !!token,
            pendingPair: validPending,
          });
          break;
        }

        case 'REQUEST_PAIR': {
          const result = await requestPairing(message.clientName);
          sendResponse(result);
          break;
        }

        case 'CONFIRM_PAIR': {
          const result = await confirmPairing(message.code);
          sendResponse(result);
          break;
        }

        case 'CANCEL_PAIR': {
          const result = await cancelPairing();
          sendResponse(result);
          break;
        }

        case 'QUERY_CREDENTIALS': {
          const result = await queryCredentialsForUrl(message.url);
          sendResponse(result);
          break;
        }

        case 'GET_FILL': {
          const result = await getFillCredentials(message.id);
          sendResponse(result);
          break;
        }

        case 'GENERATE_PASSWORD': {
          const result = await generatePassword(message.options || {});
          sendResponse(result);
          break;
        }

        case 'UNPAIR': {
          const result = await unpairClient();
          sendResponse(result);
          break;
        }

        default:
          sendResponse({ success: false, error: 'Ação desconhecida.' });
          break;
      }
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
  })();

  return true; // Mantém o canal sendResponse aberto assincronamente
});

// Checagem periódica inicial e de heartbeat
chrome.alarms?.create('statusHeartbeat', { periodInMinutes: 0.5 });
chrome.alarms?.onAlarm.addListener((alarm) => {
  if (alarm.name === 'statusHeartbeat') {
    checkServerStatus();
  }
});

// Checa status e restaura polling na inicialização se houver pareamento pendente
(async () => {
  await checkServerStatus();
  const token = await getAuthToken();
  if (!token) {
    const storage = await getStorageData(['pendingPair']);
    if (storage.pendingPair && (Date.now() - (storage.pendingPair.createdAt || 0)) <= 120000) {
      startPairingPolling(storage.pendingPair.code);
    }
  }
})();
