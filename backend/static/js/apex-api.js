/**
 * apex-api.js
 *
 * Camada de comunicação entre o frontend
 * e o backend Flask do APEX.
 *
 * Responsabilidades:
 * - autenticação X-Apex-Key;
 * - requisições HTTP;
 * - salvamento de notas;
 * - leitura do stream SSE do tutor.
 */
(function () {
  'use strict';

  const ACCESS_KEY_STORAGE = 'apex_key';


  // ==========================================================
  // AUTENTICAÇÃO
  // ==========================================================

  function getAccessKey() {
    return (
      localStorage.getItem(
        ACCESS_KEY_STORAGE
      )
      || ''
    );
  }


  function setAccessKey(key) {
    const normalized = String(
      key || ''
    ).trim();

    if (!normalized) {
      return;
    }

    localStorage.setItem(
      ACCESS_KEY_STORAGE,
      normalized
    );
  }


  function clearAccessKey() {
    localStorage.removeItem(
      ACCESS_KEY_STORAGE
    );
  }


  function getHeaders() {
    const headers = {
      'Content-Type':
        'application/json'
    };

    const key = getAccessKey();

    if (key) {
      headers['X-Apex-Key'] = key;
    }

    return headers;
  }


  function isAuthError(status) {
    return (
      status === 401
      || status === 403
    );
  }


  function requestAccessKey() {
    clearAccessKey();

    const key = window.prompt(
      'Acesso protegido. Digite a sua chave APEX_ACCESS_KEY:'
    );

    if (!key) {
      return false;
    }

    setAccessKey(key);

    return true;
  }


  // ==========================================================
  // FETCH COM RETENTATIVA DE AUTENTICAÇÃO
  // ==========================================================

  async function fetchWithAuth(
    url,
    options = {},
    allowRetry = true
  ) {
    const response = await fetch(
      url,
      {
        ...options,

        headers: {
          ...(options.headers || {}),
          ...getHeaders(),
        },
      }
    );

    if (
      isAuthError(response.status)
      && allowRetry
      && requestAccessKey()
    ) {
      return fetchWithAuth(
        url,
        options,
        false
      );
    }

    return response;
  }


  // ==========================================================
  // NOTAS
  // ==========================================================

  async function saveNote(
    text,
    area
  ) {
    const response =
      await fetchWithAuth(
        '/api/notes',
        {
          method: 'POST',

          body: JSON.stringify({
            text,
            area,
          }),
        }
      );

    let data = {};

    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(
        data.error
        || `HTTP ${response.status}`
      );
    }

    return data;
  }


  // ==========================================================
  // SSE
  // ==========================================================

  function processSseLine(
    line,
    handlers
  ) {
    const normalized =
      String(line || '').trim();

    if (
      !normalized.startsWith(
        'data: '
      )
    ) {
      return;
    }

    let event;

    try {
      event = JSON.parse(
        normalized.slice(6)
      );
    } catch {
      return;
    }

    if (
      event.token
      && typeof handlers.onToken
        === 'function'
    ) {
      handlers.onToken(
        event.token
      );

      return;
    }

    if (
      event.done
      && typeof handlers.onDone
        === 'function'
    ) {
      handlers.onDone();

      return;
    }

    if (
      event.error
      && typeof handlers.onError
        === 'function'
    ) {
      handlers.onError(
        event.error
      );
    }
  }


  async function streamChat(
    payload,
    handlers = {}
  ) {
    const response =
      await fetchWithAuth(
        '/chat/stream',
        {
          method: 'POST',

          body:
            JSON.stringify(
              payload
            ),
        }
      );


    if (!response.ok) {
      let message =
        `HTTP ${response.status}`;

      try {
        const data =
          await response.json();

        if (data.error) {
          message = data.error;
        }
      } catch {
        // Mantém a mensagem HTTP.
      }

      throw new Error(
        message
      );
    }


    if (!response.body) {
      throw new Error(
        'Servidor não forneceu stream de resposta.'
      );
    }


    const reader =
      response.body.getReader();

    const decoder =
      new TextDecoder();

    let buffer = '';


    while (true) {
      const {
        value,
        done
      } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(
        value,
        {
          stream: true,
        }
      );

      const lines =
        buffer.split('\n');

      buffer =
        lines.pop() || '';

      for (
        const line
        of lines
      ) {
        processSseLine(
          line,
          handlers
        );
      }
    }


    buffer += decoder.decode();


    if (buffer.trim()) {
      const remainingLines =
        buffer.split('\n');

      for (
        const line
        of remainingLines
      ) {
        processSseLine(
          line,
          handlers
        );
      }
    }
  }


  // ==========================================================
  // API PÚBLICA
  // ==========================================================

  window.ApexApi = {
    getAccessKey,
    setAccessKey,
    clearAccessKey,
    getHeaders,
    isAuthError,
    requestAccessKey,
    saveNote,
    streamChat,
  };

}());