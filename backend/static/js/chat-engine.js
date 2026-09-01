/**
 * chat-engine.js — Lógica compartilhada do Chat APEX
 * com DOMPurify, autenticação, histórico, SSE e TTS nativo.
 */
(function () {
  'use strict';

  const {
    area: AREA,
    lang: LANG,
    label: LABEL
  } = window.APEX_CHAT_CONFIG || {
    area: 'ads',
    lang: 'pt-BR',
    label: 'ADS'
  };

  let historico = [];
  let currentUtterance = null;

  const input = document.getElementById('user-input');

  if (input) {
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height =
        Math.min(input.scrollHeight, 120) + 'px';
    });

    input.addEventListener('keydown', e => {
      if (
        e.key === 'Enter'
        && !e.shiftKey
      ) {
        e.preventDefault();
        sendMessage();
      }
    });
  }


  // ==========================================================
  // AUTENTICAÇÃO
  // ==========================================================

  function getHeaders() {
    const headers = {
      'Content-Type': 'application/json'
    };

    const key = localStorage.getItem(
      'apex_key'
    );

    if (key) {
      headers['X-Apex-Key'] = key;
    }

    return headers;
  }


  function handleAuthError() {
    localStorage.removeItem(
      'apex_key'
    );

    const key = prompt(
      'Acesso protegido. Digite a sua chave APEX_ACCESS_KEY:'
    );

    if (key) {
      localStorage.setItem(
        'apex_key',
        key
      );

      return true;
    }

    return false;
  }


  function isAuthError(status) {
    return (
      status === 401
      || status === 403
    );
  }


  // ==========================================================
  // INTERFACE
  // ==========================================================

  function ask(msg) {
    if (!input) {
      return;
    }

    input.value = msg;
    sendMessage();
  }


  function toast(msg) {
    const el = document.getElementById(
      'toast'
    );

    if (!el) {
      return;
    }

    el.textContent = msg;
    el.classList.add('show');

    setTimeout(() => {
      el.classList.remove('show');
    }, 2200);
  }


  function escHtml(s) {
    return (s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }


  function cleanText(r) {
    return (r || '')
      .replace(
        /\[\s*[^\]]{0,40}\s*\]/g,
        ''
      )
      .replace(/\\n/g, '\n');
  }


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

    if (container) {
      container.scrollTop =
        container.scrollHeight;
    }
  }


  // ==========================================================
  // CONTADOR DO HISTÓRICO
  // ==========================================================

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


  // ==========================================================
  // MENSAGEM DO USUÁRIO
  // ==========================================================

  function appendUserMsg(text) {
    removeWelcome();

    const msgs =
      document.getElementById(
        'messages'
      );

    if (!msgs) {
      return;
    }

    const div =
      document.createElement(
        'div'
      );

    div.className = 'msg user';

    div.innerHTML =
      `<div class="avatar">R</div>`
      + `<div class="bubble">`
      + `${escHtml(text).replace(/\n/g, '<br>')}`
      + `</div>`;

    msgs.appendChild(div);

    scrollBottom();
  }


  // ==========================================================
  // MENSAGEM DO APEX
  // ==========================================================

  function createBotMsg() {
    removeWelcome();

    const msgs =
      document.getElementById(
        'messages'
      );

    if (!msgs) {
      throw new Error(
        'Área de mensagens não encontrada.'
      );
    }

    const div =
      document.createElement(
        'div'
      );

    div.className = 'msg bot';


    const avatar =
      document.createElement(
        'div'
      );

    avatar.className = 'avatar';
    avatar.textContent = 'A';


    const bubble =
      document.createElement(
        'div'
      );

    bubble.className = 'bubble';


    const tag =
      document.createElement(
        'div'
      );

    tag.className = 'area-tag';
    tag.textContent = LABEL;


    const content =
      document.createElement(
        'div'
      );

    content.className =
      'md stream-cursor';


    bubble.appendChild(tag);
    bubble.appendChild(content);

    div.appendChild(avatar);
    div.appendChild(bubble);

    msgs.appendChild(div);

    scrollBottom();

    return {
      content,
      bubble
    };
  }


  // ==========================================================
  // TTS NATIVO DO NAVEGADOR
  // ==========================================================

  function stripForTTS(text) {
    return (text || '')
      .replace(
        /```[\s\S]*?```/g,
        ''
      )
      .replace(
        /`[^`]+`/g,
        ''
      )
      .replace(
        /#{1,6}\s/g,
        ''
      )
      .replace(
        /\*\*([^*]+)\*\*/g,
        '$1'
      )
      .replace(
        /\*([^*]+)\*/g,
        '$1'
      )
      .replace(
        /\[([^\]]+)\]\([^)]+\)/g,
        '$1'
      )
      .replace(
        /^\s*[-*+]\s/gm,
        ''
      )
      .replace(
        /\n{2,}/g,
        '. '
      )
      .replace(
        /\n/g,
        ' '
      )
      .trim()
      .slice(
        0,
        4000
      );
  }


  function resetTTSButton(btn) {
    if (!btn) {
      return;
    }

    btn.classList.remove(
      'speaking'
    );

    btn.textContent = '🔊';
    btn.title = 'Ouvir';
  }


  function stopSpeech() {
    if (
      'speechSynthesis'
      in window
    ) {
      window.speechSynthesis.cancel();
    }

    currentUtterance = null;
  }


  function speakText(text, ttsBtn) {
    if (
      !(
        'speechSynthesis'
        in window
      )
      || !(
        'SpeechSynthesisUtterance'
        in window
      )
    ) {
      toast(
        'Seu navegador não oferece síntese de voz.'
      );

      return;
    }

    if (
      ttsBtn
      && ttsBtn.classList.contains(
        'speaking'
      )
    ) {
      stopSpeech();
      resetTTSButton(ttsBtn);

      return;
    }

    stopSpeech();

    document
      .querySelectorAll(
        '.tts-btn.speaking'
      )
      .forEach(button => {
        resetTTSButton(button);
      });


    const plain =
      stripForTTS(text);

    if (!plain) {
      toast(
        'Não há texto para ler.'
      );

      return;
    }


    const utterance =
      new SpeechSynthesisUtterance(
        plain
      );

    utterance.lang =
      LANG || 'pt-BR';

    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;


    const voices =
      window
        .speechSynthesis
        .getVoices();

    const preferredVoice =
      voices.find(
        voice =>
          voice.lang
          && voice.lang
            .toLowerCase()
            .startsWith(
              utterance.lang
                .toLowerCase()
                .split('-')[0]
            )
      );

    if (preferredVoice) {
      utterance.voice =
        preferredVoice;
    }


    utterance.onstart = () => {
      if (ttsBtn) {
        ttsBtn.classList.add(
          'speaking'
        );

        ttsBtn.textContent = '⏹';
        ttsBtn.title = 'Parar leitura';
      }
    };


    utterance.onend = () => {
      resetTTSButton(
        ttsBtn
      );

      if (
        currentUtterance
        === utterance
      ) {
        currentUtterance = null;
      }
    };


    utterance.onerror = event => {
      resetTTSButton(
        ttsBtn
      );

      if (
        currentUtterance
        === utterance
      ) {
        currentUtterance = null;
      }

      if (
        event.error
        && event.error !== 'canceled'
        && event.error !== 'interrupted'
      ) {
        toast(
          'Não foi possível reproduzir o áudio.'
        );
      }
    };


    currentUtterance =
      utterance;

    window
      .speechSynthesis
      .speak(
        utterance
      );
  }


  // ==========================================================
  // FINALIZA RESPOSTA
  // ==========================================================

  function finalizeBotMsg(
    content,
    bubble,
    fullText
  ) {
    content.classList.remove(
      'stream-cursor'
    );

    if (
      typeof window.marked
      !== 'undefined'
      && typeof window.DOMPurify
      !== 'undefined'
    ) {
      content.innerHTML =
        window.DOMPurify.sanitize(
          window.marked.parse(
            cleanText(fullText)
          )
        );
    } else {
      content.textContent =
        cleanText(fullText);
    }


    if (
      typeof window.hljs
      !== 'undefined'
    ) {
      content
        .querySelectorAll(
          'pre code'
        )
        .forEach(
          el =>
            window.hljs.highlightElement(
              el
            )
        );
    }


    const saveBtn =
      document.createElement(
        'button'
      );

    saveBtn.className =
      'save-btn';

    saveBtn.textContent =
      '📌 Salvar nota';

    saveBtn.onclick = () =>
      saveNote(
        fullText,
        saveBtn
      );

    bubble.appendChild(
      saveBtn
    );


    const ttsBtn =
      document.createElement(
        'button'
      );

    ttsBtn.className =
      'tts-btn';

    ttsBtn.title =
      'Ouvir';

    ttsBtn.textContent =
      '🔊';

    ttsBtn.onclick = () =>
      speakText(
        fullText,
        ttsBtn
      );

    bubble.appendChild(
      ttsBtn
    );

    scrollBottom();
  }


  // ==========================================================
  // SALVAR NOTA
  // ==========================================================

  async function saveNote(
    text,
    btn
  ) {
    try {
      const res =
        await fetch(
          '/api/notes',
          {
            method: 'POST',

            headers:
              getHeaders(),

            body:
              JSON.stringify({
                text:
                  text.slice(
                    0,
                    400
                  ),

                area:
                  AREA
              })
          }
        );


      if (
        isAuthError(
          res.status
        )
      ) {
        if (
          handleAuthError()
        ) {
          return saveNote(
            text,
            btn
          );
        }

        throw new Error(
          'Acesso não autorizado.'
        );
      }


      const data =
        await res.json();


      if (!res.ok) {
        throw new Error(
          data.error
          || `HTTP ${res.status}`
        );
      }


      if (data.ok) {
        btn.textContent =
          '✅ Salvo!';

        btn.classList.add(
          'saved'
        );

        toast(
          'Nota salva com sucesso!'
        );

        setTimeout(() => {
          btn.textContent =
            '📌 Salvar nota';

          btn.classList.remove(
            'saved'
          );
        }, 2000);
      }

    } catch {
      toast(
        'Erro ao salvar nota.'
      );
    }
  }


  // ==========================================================
  // STREAMING
  // ==========================================================

  async function _streamChat(
    text,
    btn,
    historyForRequest
  ) {
    const {
      content,
      bubble
    } = createBotMsg();

    let fullText = '';
    let finalized = false;


    try {
      const res =
        await fetch(
          '/chat/stream',
          {
            method: 'POST',

            headers:
              getHeaders(),

            body:
              JSON.stringify({
                message:
                  text,

                area:
                  AREA,

                history:
                  historyForRequest
              })
          }
        );


      if (
        isAuthError(
          res.status
        )
      ) {
        content
          .closest(
            '.msg'
          )
          ?.remove();

        if (
          handleAuthError()
        ) {
          return _streamChat(
            text,
            btn,
            historyForRequest
          );
        }

        throw new Error(
          'Acesso não autorizado.'
        );
      }


      if (
        !res.ok
        || !res.body
      ) {
        throw new Error(
          `HTTP ${res.status}`
        );
      }


      const reader =
        res.body.getReader();

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

        buffer +=
          decoder.decode(
            value,
            {
              stream: true
            }
          );

        const parts =
          buffer.split(
            '\n'
          );

        buffer =
          parts.pop();


        for (
          const part
          of parts
        ) {
          const line =
            part.trim();

          if (
            !line.startsWith(
              'data: '
            )
          ) {
            continue;
          }


          try {
            const evt =
              JSON.parse(
                line.slice(6)
              );


            if (evt.token) {
              fullText +=
                evt.token;

              content.textContent =
                fullText;

              scrollBottom();

            } else if (
              evt.done
            ) {
              finalizeBotMsg(
                content,
                bubble,
                fullText
              );

              finalized = true;

              historico.push({
                role:
                  'assistant',

                content:
                  fullText
              });

              if (
                historico.length
                > 20
              ) {
                historico =
                  historico.slice(
                    -20
                  );
              }

              updateBadge();

            } else if (
              evt.error
            ) {
              content.classList.remove(
                'stream-cursor'
              );

              content.innerHTML =
                `<span style="color:#ff6b6b">`
                + `⚠️ ${escHtml(evt.error)}`
                + `</span>`;
            }

          } catch {
            /*
             * Ignora apenas um evento
             * SSE isolado inválido.
             */
          }
        }
      }


      if (
        fullText
        && !finalized
      ) {
        finalizeBotMsg(
          content,
          bubble,
          fullText
        );

        historico.push({
          role:
            'assistant',

          content:
            fullText
        });

        if (
          historico.length
          > 20
        ) {
          historico =
            historico.slice(
              -20
            );
        }

        updateBadge();
      }

    } catch (err) {
      if (
        content.isConnected
      ) {
        content.classList.remove(
          'stream-cursor'
        );

        content.innerHTML =
          `<span style="color:#ff6b6b">`
          + `⚠️ Sem conexão com o servidor.<br>`
          + `<small>${escHtml(err.message)}</small>`
          + `</span>`;
      }

    } finally {
      if (btn) {
        btn.disabled = false;
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

    const text =
      input.value.trim();

    if (!text) {
      return;
    }


    const btn =
      document.getElementById(
        'send-btn'
      );

    if (btn) {
      btn.disabled = true;
    }


    input.value = '';
    input.style.height = 'auto';

    appendUserMsg(
      text
    );


    /*
     * O histórico usado na requisição é
     * capturado ANTES de adicionar a
     * pergunta atual.
     *
     * O TutorCore adiciona a pergunta
     * atual uma única vez no backend.
     */
    const historyForRequest =
      historico.slice();


    historico.push({
      role: 'user',
      content: text
    });

    if (
      historico.length
      > 20
    ) {
      historico =
        historico.slice(
          -20
        );
    }

    updateBadge();


    await _streamChat(
      text,
      btn,
      historyForRequest
    );
  }


  // ==========================================================
  // LIMPAR CONVERSA
  // ==========================================================

  function clearChat() {
    stopSpeech();

    historico = [];

    updateBadge();

    const msgs =
      document.getElementById(
        'messages'
      );

    if (msgs) {
      msgs.innerHTML =
        `<div class="welcome" id="welcome">`
        + `<h2>Pronto!</h2>`
        + `<p>Conversa limpa. Faça sua pergunta sobre ADS.</p>`
        + `</div>`;
    }
  }


  // ==========================================================
  // API GLOBAL
  // ==========================================================

  updateBadge();

  window.ask =
    ask;

  window.sendMessage =
    sendMessage;

  window.clearChat =
    clearChat;

  window.toast =
    toast;

}());