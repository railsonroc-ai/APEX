/**
 * apex-tts.js
 *
 * Síntese de voz nativa do APEX.
 *
 * Responsabilidades:
 * - limpar o texto para leitura;
 * - iniciar a síntese de voz;
 * - interromper a leitura;
 * - controlar o estado visual do botão.
 */
(function () {
  'use strict';

  let currentUtterance = null;


  // ==========================================================
  // PREPARAÇÃO DO TEXTO
  // ==========================================================

  function stripText(text) {
    return String(text || '')
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


  // ==========================================================
  // SUPORTE
  // ==========================================================

  function isSupported() {
    return (
      'speechSynthesis' in window
      && 'SpeechSynthesisUtterance' in window
    );
  }


  // ==========================================================
  // BOTÃO
  // ==========================================================

  function resetButton(button) {
    if (!button) {
      return;
    }

    button.classList.remove(
      'speaking'
    );

    button.textContent = '🔊';
    button.title = 'Ouvir';
  }


  function resetAllButtons() {
    document
      .querySelectorAll(
        '.tts-btn.speaking'
      )
      .forEach(
        resetButton
      );
  }


  // ==========================================================
  // PARAR
  // ==========================================================

  function stop() {
    if (isSupported()) {
      window
        .speechSynthesis
        .cancel();
    }

    currentUtterance = null;

    resetAllButtons();
  }


  // ==========================================================
  // ESCOLHA DE VOZ
  // ==========================================================

  function findPreferredVoice(
    language
  ) {
    if (!isSupported()) {
      return null;
    }

    const languagePrefix =
      String(
        language || 'pt-BR'
      )
        .toLowerCase()
        .split('-')[0];

    const voices =
      window
        .speechSynthesis
        .getVoices();

    return (
      voices.find(
        voice =>
          voice.lang
          && voice.lang
            .toLowerCase()
            .startsWith(
              languagePrefix
            )
      )
      || null
    );
  }


  // ==========================================================
  // FALAR
  // ==========================================================

  function speak(
    text,
    options = {}
  ) {
    const {
      button = null,
      lang = 'pt-BR',
      onUnsupported = null,
      onEmpty = null,
      onError = null,
    } = options;


    if (!isSupported()) {
      if (
        typeof onUnsupported
        === 'function'
      ) {
        onUnsupported();
      }

      return false;
    }


    /*
     * Segundo toque no botão atual:
     * interrompe a leitura.
     */
    if (
      button
      && button.classList.contains(
        'speaking'
      )
    ) {
      stop();

      return false;
    }


    stop();


    const plain =
      stripText(text);

    if (!plain) {
      if (
        typeof onEmpty
        === 'function'
      ) {
        onEmpty();
      }

      return false;
    }


    const utterance =
      new SpeechSynthesisUtterance(
        plain
      );

    utterance.lang =
      lang || 'pt-BR';

    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;


    const preferredVoice =
      findPreferredVoice(
        utterance.lang
      );

    if (preferredVoice) {
      utterance.voice =
        preferredVoice;
    }


    utterance.onstart = () => {
      if (!button) {
        return;
      }

      button.classList.add(
        'speaking'
      );

      button.textContent = '⏹';
      button.title =
        'Parar leitura';
    };


    utterance.onend = () => {
      resetButton(
        button
      );

      if (
        currentUtterance
        === utterance
      ) {
        currentUtterance = null;
      }
    };


    utterance.onerror = event => {
      resetButton(
        button
      );

      if (
        currentUtterance
        === utterance
      ) {
        currentUtterance = null;
      }

      if (
        event.error === 'canceled'
        || event.error === 'interrupted'
      ) {
        return;
      }

      if (
        typeof onError
        === 'function'
      ) {
        onError(
          event.error || 'unknown'
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

    return true;
  }


  // ==========================================================
  // API PÚBLICA
  // ==========================================================

  window.ApexTTS = {
    isSupported,
    stripText,
    speak,
    stop,
  };

}());