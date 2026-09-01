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
    return String(text || '')
      .replace(
        /\[\s*[^\]]{0,40}\s*\]/g,
        ''
      )
      .replace(
        /\\n/g,
        '\n'
      );
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

  async function streamChat(
    text,
    button,
    historyForRequest
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
          history:
            historyForRequest
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

            addToHistory(
              'assistant',
              fullText
            );
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
       * Proteção para streams que terminam
       * sem enviar explicitamente {"done": true}.
       */
      if (
        fullText
        && !finalized
        && !streamError
      ) {
        finalizeBotMessage(
          content,
          bubble,
          fullText
        );

        finalized = true;

        addToHistory(
          'assistant',
          fullText
        );
      }

    } catch (error) {
      streamError = true;

      showBotError(
        content,
        error.message
        || 'Sem conexão com o servidor.'
      );

    } finally {
      if (button) {
        button.disabled =
          false;
      }

      if (input) {
        input.focus();
      }
    }
  }


  // ==========================================================
  // ENVIAR MENSAGEM
  // ==========================================================

  async function sendMessage() {
    if (!input) {
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


    const sendButton =
      document.getElementById(
        'send-btn'
      );


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


    /*
     * A pergunta atual NÃO deve estar
     * no histórico enviado ao backend.
     *
     * O TutorCore adiciona essa pergunta
     * uma única vez.
     *
     * O frontend envia somente a quantidade
     * de mensagens de contexto definida
     * pelo backend.
     */
    const historyForRequest =
      historico.slice(
        -MAX_HISTORY_MESSAGES
      );


    addToHistory(
      'user',
      text
    );


    await streamChat(
      text,
      sendButton,
      historyForRequest
    );
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


  if (!modulesReady()) {
    console.error(
      'APEX: apex-api.js ou apex-tts.js não foi carregado corretamente.'
    );
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

}());