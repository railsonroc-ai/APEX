/**
 * apex-api.js
 *
 * Camada de comunicação entre o frontend
 * e o backend Flask do APEX.
 *
 * Responsabilidades:
 * - requisições HTTP;
 * - salvamento de notas;
 * - leitura do stream SSE do tutor.
 */
(function () {
  'use strict';

  // ==========================================================
  // HTTP
  // ==========================================================

  function getHeaders() {
    return {
      'Content-Type':
        'application/json'
    };
  }


  async function fetchApi(
    url,
    options = {}
  ) {
    return fetch(
      url,
      {
        ...options,

        headers: {
          ...(options.headers || {}),
          ...getHeaders(),
        },
      }
    );
  }


  // ==========================================================
  // NOTAS
  // ==========================================================

  async function saveNote(
    text,
    area
  ) {
    const response =
      await fetchApi(
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
  // SESSÃO DE APRENDIZAGEM
  // ==========================================================

  async function readJsonResponse(response) {
    let data = {};

    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      const error = new Error(
        data.error
        || `HTTP ${response.status}`
      );

      error.status = response.status;
      error.code = data.code || null;
      throw error;
    }

    return data;
  }


  async function getSession(area) {
    const query = new URLSearchParams({
      area: String(area || 'ads'),
    });

    const response = await fetchApi(
      `/api/session?${query.toString()}`,
      {
        method: 'GET',
      }
    );

    return readJsonResponse(response);
  }


  async function pauseSession(area) {
    const response = await fetchApi(
      '/api/session/pause',
      {
        method: 'POST',
        body: JSON.stringify({
          area: String(area || 'ads'),
        }),
      }
    );

    return readJsonResponse(response);
  }


  async function resumeSession(
    area,
    mode
  ) {
    const response = await fetchApi(
      '/api/session/resume',
      {
        method: 'POST',
        body: JSON.stringify({
          area: String(area || 'ads'),
          mode: String(mode || 'direct'),
        }),
      }
    );

    return readJsonResponse(response);
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
      await fetchApi(
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
    getHeaders,
    saveNote,
    getSession,
    pauseSession,
    resumeSession,
    streamChat,
  };

}());