/**
 * chat-engine.js
 *
 * Motor de conversa e interface do APEX.
 *
 * Responsabilidades:
 * - estado local da conversa;
 * - renderização das mensagens;
 * - contador de histórico;
 * - integração com Markdown;
 * - ações de salvar nota e ouvir resposta;
 * - coordenação do streaming.
 *
 * Comunicação HTTP/SSE:
 * - window.ApexApi
 *
 * Síntese de voz:
 * - window.ApexTTS
 */
(function () {
  'use strict';


  // ==========================================================
  // CONFIGURAÇÃO
  // ==========================================================

  const {
    area: AREA,
    lang: LANG,
    label: LABEL,
    maxHistoryMessages
  } = window.APEX_CHAT_CONFIG || {
    area: 'ads',
    lang: 'pt-BR',
    label: 'ADS',
    maxHistoryMessages: 8
  };


  const MAX_HISTORY_MESSAGES =
    Number.isInteger(
      Number(maxHistoryMessages)
    )
    && Number(maxHistoryMessages) > 0
      ? Number(maxHistoryMessages)
      : 8;


  const Api = window.ApexApi;
  const TTS = window.ApexTTS;

  let historico = [];


  // ==========================================================
  // ELEMENTOS PRINCIPAIS
  // ==========================================================

  const input =
    document.getElementById(
      'user-input'
    );

  const sendButton =
    document.getElementById(
      'send-btn'
    );

  const pauseButton =
    document.getElementById(
      'pause-btn'
    );

  const resumeDirectButton =
    document.getElementById(
      'resume-direct-btn'
    );

  const resumeReviewButton =
    document.getElementById(
      'resume-review-btn'
    );

  const sessionStatusBadge =
    document.getElementById(
      'session-status-badge'
    );

  const sessionPanel =
    document.getElementById(
      'session-panel'
    );

  const sessionPanelTitle =
    document.getElementById(
      'session-panel-title'
    );

  const sessionPanelDetail =
    document.getElementById(
      'session-panel-detail'
    );

  const sessionPanelActions =
    document.getElementById(
      'session-panel-actions'
    );

  const learningFocus =
    document.getElementById(
      'learning-focus'
    );

  const learningFocusTitle =
    document.getElementById(
      'learning-focus-title'
    );

  const learningFocusDetail =
    document.getElementById(
      'learning-focus-detail'
    );

  let sessionRuntime = {
    status: 'loading'
  };

  let sessionControlBusy = false;


  // ==========================================================
  // VALIDAÇÃO DOS MÓDULOS
  // ==========================================================

  function modulesReady() {
    return Boolean(
      Api
      && typeof Api.streamChat
        === 'function'
      && typeof Api.saveNote
        === 'function'
      && typeof Api.getSession
        === 'function'
      && typeof Api.pauseSession
        === 'function'
      && typeof Api.resumeSession
        === 'function'
      && TTS
      && typeof TTS.speak
        === 'function'
      && typeof TTS.stop
        === 'function'
    );
  }


  // ==========================================================
  // INPUT
  // ==========================================================

  if (input) {
    input.addEventListener(
      'input',
      () => {
        input.style.height =
          'auto';

        input.style.height =
          Math.min(
            input.scrollHeight,
            120
          )
          + 'px';
      }
    );


    input.addEventListener(
      'keydown',
      event => {
        if (
          event.key === 'Enter'
          && !event.shiftKey
        ) {
          event.preventDefault();

          sendMessage();
        }
      }
    );
  }


  // ==========================================================
  // CICLO DA SESSÃO
  // ==========================================================

  function sessionStatus() {
    return String(
      sessionRuntime
      && sessionRuntime.status
      || 'unknown'
    );
  }


  function chatBlockedBySession() {
    return sessionStatus() === 'paused';
  }


  function syncInputAvailability() {
    const blocked =
      chatBlockedBySession();

    const loading =
      sessionStatus() === 'loading';

    const busy =
      sendingMessage
      || sessionControlBusy
      || loading;

    if (input) {
      input.disabled =
        blocked || loading;

      if (blocked) {
        input.placeholder =
          'Sessão pausada. Escolha como deseja retomar.';
      } else if (sessionStatus() === 'reviewing') {
        input.placeholder =
          'Responda à revisão de retomada...';
      } else if (
        sessionRuntime.learning_focus
        && sessionRuntime.learning_focus.concept
      ) {
        input.placeholder =
          'Responda à tarefa atual ou peça ajuda...';
      } else {
        input.placeholder =
          'Diga o que você quer aprender...';
      }
    }

    if (sendButton) {
      sendButton.disabled =
        blocked || busy;
    }

    if (pauseButton) {
      pauseButton.disabled =
        sessionStatus() !== 'studying'
        || busy;
    }

    if (learningFocus) {
      const focus =
        sessionRuntime.learning_focus
        && typeof sessionRuntime.learning_focus === 'object'
          ? sessionRuntime.learning_focus
          : null;
      const showFocus = Boolean(
        sessionStatus() === 'studying'
        && focus
        && focus.concept
      );
      learningFocus.hidden = !showFocus;

      if (showFocus) {
        if (learningFocusTitle) {
          learningFocusTitle.textContent =
            `Agora: ${focus.concept}. `;
        }
        if (learningFocusDetail) {
          learningFocusDetail.textContent =
            focus.next_step || '';
        }
      }
    }

    if (resumeDirectButton) {
      resumeDirectButton.disabled =
        sessionStatus() !== 'paused'
        || busy;
    }

    if (resumeReviewButton) {
      resumeReviewButton.disabled =
        sessionStatus() !== 'paused'
        || busy;
    }
  }


  function renderSessionRuntime(
    runtime
  ) {
    sessionRuntime =
      runtime
      && typeof runtime === 'object'
        ? runtime
        : { status: 'unknown' };

    const status =
      sessionStatus();

    if (sessionStatusBadge) {
      sessionStatusBadge.dataset.status =
        status;

      const labels = {
        studying: 'Sessão: estudando',
        paused: 'Sessão: pausada',
        reviewing: 'Sessão: revisão',
        loading: 'Sessão: carregando',
        unknown: 'Sessão: indisponível'
      };

      sessionStatusBadge.textContent =
        labels[status]
        || labels.unknown;
    }

    if (pauseButton) {
      pauseButton.hidden =
        status !== 'studying';
    }

    if (sessionPanel) {
      const showPanel =
        status === 'paused'
        || status === 'reviewing';

      sessionPanel.hidden =
        !showPanel;

      if (showPanel) {
        const concept =
          String(
            sessionRuntime.resume_concept
            || ''
          ).trim();

        if (status === 'paused') {
          if (sessionPanelTitle) {
            sessionPanelTitle.textContent =
              'Estudo pausado';
          }

          if (sessionPanelDetail) {
            sessionPanelDetail.textContent =
              concept
                ? `Você pausou em ${concept}. Retome direto ou faça uma revisão curta antes de continuar.`
                : 'Retome direto ou faça uma revisão curta antes de continuar.';
          }

          if (sessionPanelActions) {
            sessionPanelActions.hidden = false;
          }
        } else {
          if (sessionPanelTitle) {
            sessionPanelTitle.textContent =
              'Revisão antes de retomar';
          }

          if (sessionPanelDetail) {
            sessionPanelDetail.textContent =
              'Conclua esta revisão curta. Quando a evidência for suficiente, o APEX restaura automaticamente o ponto em que você parou.';
          }

          if (sessionPanelActions) {
            sessionPanelActions.hidden = true;
          }
        }
      }
    }

    syncInputAvailability();

    if (
      typeof document.dispatchEvent === 'function'
      && typeof window.CustomEvent === 'function'
    ) {
      document.dispatchEvent(
        new window.CustomEvent(
          'apex:session-updated',
          {
            detail: {
              session: { ...sessionRuntime }
            }
          }
        )
      );
    }
  }


  async function refreshSessionRuntime(
    { quiet = false } = {}
  ) {
    if (
      !Api
      || typeof Api.getSession !== 'function'
    ) {
      renderSessionRuntime({
        status: 'unknown'
      });
      return null;
    }

    try {
      const result =
        await Api.getSession(AREA);

      if (
        !result
        || !result.ok
        || !result.session
      ) {
        throw new Error(
          'Estado de sessão inválido.'
        );
      }

      renderSessionRuntime(
        result.session
      );

      return result.session;
    } catch (error) {
      renderSessionRuntime({
        status: 'unknown'
      });

      if (!quiet) {
        toast(
          error.message
          || 'Não foi possível consultar a sessão.'
        );
      }

      return null;
    }
  }


  async function pauseLearningSession() {
    if (
      sendingMessage
      || sessionControlBusy
    ) {
      toast(
        'Aguarde o turno atual terminar antes de pausar.'
      );
      return;
    }

    sessionControlBusy = true;
    syncInputAvailability();

    try {
      const result =
        await Api.pauseSession(AREA);

      renderSessionRuntime(
        result.session
      );

      toast('Estudo pausado.');
      return result.session;
    } catch (error) {
      toast(
        error.message
        || 'Não foi possível pausar.'
      );

      await refreshSessionRuntime({
        quiet: true
      });
      return null;
    } finally {
      sessionControlBusy = false;
      syncInputAvailability();
    }
  }


  async function resumeLearningSession(
    mode
  ) {
    if (sessionControlBusy) {
      return;
    }

    sessionControlBusy = true;
    syncInputAvailability();

    try {
      const result =
        await Api.resumeSession(
          AREA,
          mode
        );

      renderSessionRuntime(
        result.session
      );

      if (mode === 'review') {
        toast(
          'Revisão de retomada iniciada.'
        );

        if (input) {
          input.value =
            'Quero revisar antes de retomar.';
        }

        await sendMessage();
      } else {
        toast(
          'Estudo retomado do ponto em que você parou.'
        );

        if (input) {
          input.focus();
        }
      }

      return result.session;
    } catch (error) {
      toast(
        error.message
        || 'Não foi possível retomar.'
      );

      await refreshSessionRuntime({
        quiet: true
      });
      return null;
    } finally {
      sessionControlBusy = false;
      syncInputAvailability();
    }
  }


  if (pauseButton) {
    pauseButton.addEventListener(
      'click',
      pauseLearningSession
    );
  }

  if (resumeDirectButton) {
    resumeDirectButton.addEventListener(
      'click',
      () => resumeLearningSession('direct')
    );
  }

  if (resumeReviewButton) {
    resumeReviewButton.addEventListener(
      'click',
      () => resumeLearningSession('review')
    );
  }


  // ==========================================================
  // AÇÕES RÁPIDAS
  // ==========================================================

  function ask(message) {
    if (!input) {
      return;
    }

    input.value =
      String(message || '');

    sendMessage();
  }


  // ==========================================================
  // TOAST
  // ==========================================================

  function toast(message) {
    const element =
      document.getElementById(
        'toast'
      );

    if (!element) {
      return;
    }

    element.textContent =
      String(message || '');

    element.classList.add(
      'show'
    );

    window.setTimeout(
      () => {
        element.classList.remove(
          'show'
        );
      },
      2200
    );
  }


  // ==========================================================
  // TEXTO / HTML
  // ==========================================================

  function escapeHtml(text) {
    return String(text || '')
      .replace(
        /&/g,
        '&amp;'
      )
      .replace(
        /</g,
        '&lt;'
      )
      .replace(
        />/g,
        '&gt;'
      );
  }


  function cleanText(text) {
    return String(text || '');
  }


  // ==========================================================
  // INTERFACE
  // ==========================================================

  function removeWelcome() {
    const welcome =
      document.getElementById(
        'welcome'
      );

    if (welcome) {
      welcome.remove();
    }
  }


  function scrollBottom() {
    const container =
      document.getElementById(
        'messages'
      );

    if (!container) {
      return;
    }

    container.scrollTop =
      container.scrollHeight;
  }


  // ==========================================================
  // HISTÓRICO / BADGE
  // ==========================================================

  function trimHistory() {
    if (
      historico.length
      > MAX_HISTORY_MESSAGES
    ) {
      historico =
        historico.slice(
          -MAX_HISTORY_MESSAGES
        );
    }
  }


  function updateBadge() {
    const badge =
      document.getElementById(
        'memory-badge'
      );

    if (!badge) {
      return;
    }

    const total =
      historico.length;

    badge.dataset.count =
      String(total);

    badge.textContent =
      `🧠 ${total} msgs`;
  }


  function addToHistory(
    role,
    content
  ) {
    historico.push({
      role,
      content
    });

    trimHistory();

    updateBadge();
  }


  // ==========================================================
  // MENSAGEM DO USUÁRIO
  // ==========================================================

  function appendUserMessage(
    text
  ) {
    removeWelcome();

    const messages =
      document.getElementById(
        'messages'
      );

    if (!messages) {
      return;
    }


    const wrapper =
      document.createElement(
        'div'
      );

    wrapper.className =
      'msg user';


    const avatar =
      document.createElement(
        'div'
      );

    avatar.className =
      'avatar';

    avatar.textContent =
      'R';


    const bubble =
      document.createElement(
        'div'
      );

    bubble.className =
      'bubble';

    bubble.innerHTML =
      escapeHtml(text)
        .replace(
          /\n/g,
          '<br>'
        );


    wrapper.appendChild(
      avatar
    );

    wrapper.appendChild(
      bubble
    );

    messages.appendChild(
      wrapper
    );

    scrollBottom();
  }


  // ==========================================================
  // MENSAGEM DO APEX
  // ==========================================================

  function createBotMessage() {
    removeWelcome();

    const messages =
      document.getElementById(
        'messages'
      );

    if (!messages) {
      throw new Error(
        'Área de mensagens não encontrada.'
      );
    }


    const wrapper =
      document.createElement(
        'div'
      );

    wrapper.className =
      'msg bot';


    const avatar =
      document.createElement(
        'div'
      );

    avatar.className =
      'avatar';

    avatar.textContent =
      'A';


    const bubble =
      document.createElement(
        'div'
      );

    bubble.className =
      'bubble';


    const tag =
      document.createElement(
        'div'
      );

    tag.className =
      'area-tag';

    tag.textContent =
      LABEL;


    const content =
      document.createElement(
        'div'
      );

    content.className =
      'md stream-cursor';


    bubble.appendChild(
      tag
    );

    bubble.appendChild(
      content
    );

    wrapper.appendChild(
      avatar
    );

    wrapper.appendChild(
      bubble
    );

    messages.appendChild(
      wrapper
    );

    scrollBottom();


    return {
      wrapper,
      bubble,
      content
    };
  }


  // ==========================================================
  // MARKDOWN
  // ==========================================================

  function renderMarkdown(
    element,
    text
  ) {
    const cleaned =
      cleanText(text);


    if (
      typeof window.marked
        !== 'undefined'
      && typeof window.DOMPurify
        !== 'undefined'
    ) {
      element.innerHTML =
        window.DOMPurify.sanitize(
          window.marked.parse(
            cleaned
          )
        );

    } else {
      element.textContent =
        cleaned;
    }


    if (
      typeof window.hljs
        !== 'undefined'
    ) {
      element
        .querySelectorAll(
          'pre code'
        )
        .forEach(
          code => {
            window.hljs
              .highlightElement(
                code
              );
          }
        );
    }
  }


  // ==========================================================
  // TTS
  // ==========================================================

  function speakText(
    text,
    button
  ) {
    if (!TTS) {
      toast(
        'Módulo de voz indisponível.'
      );

      return;
    }


    TTS.speak(
      text,
      {
        button,
        lang: LANG,

        onUnsupported: () => {
          toast(
            'Seu navegador não oferece síntese de voz.'
          );
        },

        onEmpty: () => {
          toast(
            'Não há texto para ler.'
          );
        },

        onError: () => {
          toast(
            'Não foi possível reproduzir o áudio.'
          );
        }
      }
    );
  }


  // ==========================================================
  // SALVAR NOTA
  // ==========================================================

  async function saveNote(
    text,
    button
  ) {
    if (!Api) {
      toast(
        'Comunicação com o servidor indisponível.'
      );

      return;
    }


    try {
      const result =
        await Api.saveNote(
          String(text || ''),
          AREA
        );


      if (
        !result
        || !result.ok
      ) {
        throw new Error(
          'Resposta inválida do servidor.'
        );
      }


      button.textContent =
        '✅ Salvo!';

      button.classList.add(
        'saved'
      );

      toast(
        'Nota salva com sucesso!'
      );


      window.setTimeout(
        () => {
          button.textContent =
            '📌 Salvar nota';

          button.classList.remove(
            'saved'
          );
        },
        2000
      );

    } catch (error) {
      toast(
        error.message
        || 'Erro ao salvar nota.'
      );
    }
  }


  // ==========================================================
  // FINALIZA RESPOSTA
  // ==========================================================

  function finalizeBotMessage(
    content,
    bubble,
    fullText
  ) {
    content.classList.remove(
      'stream-cursor'
    );


    renderMarkdown(
      content,
      fullText
    );


    const saveButton =
      document.createElement(
        'button'
      );

    saveButton.className =
      'save-btn';

    saveButton.textContent =
      '📌 Salvar nota';

    saveButton.addEventListener(
      'click',
      () => {
        saveNote(
          fullText,
          saveButton
        );
      }
    );


    const ttsButton =
      document.createElement(
        'button'
      );

    ttsButton.className =
      'tts-btn';

    ttsButton.title =
      'Ouvir';

    ttsButton.textContent =
      '🔊';

    ttsButton.addEventListener(
      'click',
      () => {
        speakText(
          fullText,
          ttsButton
        );
      }
    );


    bubble.appendChild(
      saveButton
    );

    bubble.appendChild(
      ttsButton
    );

    scrollBottom();
  }


  // ==========================================================
  // ERROS NO BALÃO
  // ==========================================================

  function showBotError(
    content,
    message
  ) {
    content.classList.remove(
      'stream-cursor'
    );

    content.innerHTML =
      '<span style="color:#ff6b6b">'
      + '⚠️ '
      + escapeHtml(
        message
        || 'Erro inesperado.'
      )
      + '</span>';

    scrollBottom();
  }


  // ==========================================================
  // STREAM DO CHAT
  // ==========================================================

  function createTurnId() {
    if (
      globalThis.crypto
      && typeof globalThis.crypto.randomUUID
        === 'function'
    ) {
      return globalThis.crypto.randomUUID();
    }

    return [
      'turn',
      Date.now().toString(36),
      Math.random().toString(36).slice(2)
    ].join('-');
  }


  async function streamChat(
    text,
    button,
    turnId
  ) {
    const {
      content,
      bubble
    } = createBotMessage();


    let fullText = '';
    let finalized = false;
    let streamError = false;


    try {
      if (!Api) {
        throw new Error(
          'Módulo de comunicação indisponível.'
        );
      }


      await Api.streamChat(
        {
          message: text,
          area: AREA,
          turn_id: turnId
        },
        {
          onToken: token => {
            if (streamError) {
              return;
            }

            fullText +=
              token;

            content.textContent =
              fullText;

            scrollBottom();
          },


          onDone: () => {
            if (
              finalized
              || streamError
            ) {
              return;
            }

            finalizeBotMessage(
              content,
              bubble,
              fullText
            );

            finalized = true;
          },


          onError: message => {
            streamError = true;

            showBotError(
              content,
              message
            );
          }
        }
      );


      /*
       * O backend só confirma um turno concluído
       * quando envia explicitamente {"done": true}.
       *
       * EOF sem confirmação significa que o turno
       * pode ter sofrido rollback no servidor.
       */
      if (
        !finalized
        && !streamError
      ) {
        streamError = true;

        showBotError(
          content,
          'Resposta interrompida antes da confirmação do servidor.'
        );
      }

      if (
        finalized
        && !streamError
      ) {
        return fullText;
      }

      return null;

    } catch (error) {
      streamError = true;

      showBotError(
        content,
        error.message
        || 'Sem conexão com o servidor.'
      );

      return null;

    } finally {
      syncInputAvailability();

      if (
        input
        && !input.disabled
      ) {
        input.focus();
      }
    }
  }


  // ==========================================================
  // ENVIAR MENSAGEM
  // ==========================================================

  let sendingMessage = false;


  async function sendMessage() {
    if (!input) {
      return;
    }


    if (sendingMessage) {
      return;
    }


    if (chatBlockedBySession()) {
      toast(
        'A sessão está pausada. Escolha como deseja retomar.'
      );
      return;
    }


    if (!modulesReady()) {
      toast(
        'Os módulos do APEX não foram carregados corretamente.'
      );

      return;
    }


    const text =
      input.value.trim();

    if (!text) {
      return;
    }


    if (sendButton) {
      sendButton.disabled =
        true;
    }


    input.value = '';

    input.style.height =
      'auto';


    appendUserMessage(
      text
    );


    sendingMessage = true;

    try {
      const turnId =
        createTurnId();

      const assistantText =
        await streamChat(
          text,
          sendButton,
          turnId
        );

      if (assistantText !== null) {
        addToHistory(
          'user',
          text
        );

        addToHistory(
          'assistant',
          assistantText
        );

        await refreshSessionRuntime({
          quiet: true
        });
      }
    } finally {
      sendingMessage = false;
      syncInputAvailability();
    }
  }


  // ==========================================================
  // LIMPAR CONVERSA
  // ==========================================================

  function clearChat() {
    if (
      TTS
      && typeof TTS.stop
        === 'function'
    ) {
      TTS.stop();
    }


    historico = [];

    updateBadge();


    const messages =
      document.getElementById(
        'messages'
      );


    if (messages) {
      messages.innerHTML =
        '<div class="welcome" id="welcome">'
        + '<h2>Pronto!</h2>'
        + '<p>'
        + 'Conversa limpa. '
        + 'Faça sua pergunta sobre ADS.'
        + '</p>'
        + '</div>';
    }


    if (input) {
      input.focus();
    }
  }


  // ==========================================================
  // INICIALIZAÇÃO
  // ==========================================================

  updateBadge();
  renderSessionRuntime({
    status: 'loading'
  });


  if (!modulesReady()) {
    console.error(
      'APEX: apex-api.js ou apex-tts.js não foi carregado corretamente.'
    );
  } else {
    refreshSessionRuntime();
  }


  // ==========================================================
  // API GLOBAL DA INTERFACE
  // ==========================================================

  window.ask =
    ask;

  window.sendMessage =
    sendMessage;

  window.clearChat =
    clearChat;

  window.toast =
    toast;

  window.ApexChat = Object.freeze({
    ask,
    pauseLearningSession,
    resumeLearningSession,
    refreshSessionRuntime,
    getSessionRuntime() {
      return { ...sessionRuntime };
    },
    focusInput() {
      if (input) {
        input.focus();
      }
    }
  });

}());
