(function () {
  'use strict';

  const SpeechRecognitionImpl =
    (typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition))
      ? (window.SpeechRecognition || window.webkitSpeechRecognition)
      : null;

  class ApexVoice extends EventTarget {
    constructor(options = {}) {
      super();

      this.options = {
        lang: 'pt-BR',
        continuous: true,
        interimResults: true,
        maxAlternatives: 1,
        ...options
      };

      this.recognition = null;
      this.isListening = false;

      // Mapeamento solicitado para comandos por voz do APEX.
      this.COMMANDS = {
        'abrir ensino': () => { window.location.href = '/ensino'; },
        tutor: () => {
          const tutorInput = document.querySelector('.tutor-input');
          if (tutorInput && typeof tutorInput.focus === 'function') {
            tutorInput.focus();
            return;
          }

          // Fallback: abre Ensino já com foco solicitado.
          window.location.href = '/ensino?focusTutor=1';
        },
        'automação': () => { window.location.href = '/automacao'; },
        github: () => { window.open('https://github.com/railsonroc-ai/APEX'); },
        parar: () => {
          if (this.recognition && typeof this.recognition.stop === 'function') {
            this.recognition.stop();
          }
        },
        'apenas confirme': () => { this.speak('APEX ativo e funcionando perfeitamente!'); }
      };

      this._setupRecognition();
    }

    _normalizeCommand(text) {
      return String(text || '')
        .trim()
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/\s+/g, ' ');
    }

    executeVoiceCommand(rawText) {
      const normalizedText = this._normalizeCommand(rawText);

      const commandEntries = Object.entries(this.COMMANDS).map(([key, action]) => ({
        key,
        normalizedKey: this._normalizeCommand(key),
        action
      }));

      const matched = commandEntries.find((item) => item.normalizedKey === normalizedText);

      if (matched) {
        try {
          matched.action();
          this._emit('voice:command', {
            recognized: true,
            command: matched.key,
            transcript: String(rawText || '').trim()
          });
          return { recognized: true, command: matched.key };
        } catch (error) {
          this._emit('voice:error', {
            code: 'VOICE_COMMAND_EXECUTION_FAILED',
            message: error?.message || String(error),
            command: matched.key
          });
          return { recognized: false, command: matched.key, error: error?.message || String(error) };
        }
      }

      this.speak('Comando não reconhecido');
      this._emit('voice:command', {
        recognized: false,
        command: null,
        transcript: String(rawText || '').trim()
      });
      return { recognized: false, command: null };
    }

    async requestMicrophonePermission() {
      if (typeof navigator === 'undefined' || !navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
        this._emit('voice:error', {
          code: 'MIC_PERMISSION_API_UNAVAILABLE',
          message: 'mediaDevices.getUserMedia não disponível neste navegador.'
        });
        return false;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this._emit('voice:mic-permission-granted', {});
        // Libera o microfone imediatamente; SpeechRecognition abrirá novamente quando iniciar.
        stream.getTracks().forEach((track) => track.stop());
        return true;
      } catch (error) {
        this._emit('voice:error', {
          code: 'MIC_PERMISSION_DENIED',
          message: error?.message || String(error)
        });
        return false;
      }
    }

    _emit(type, detail = {}) {
      this.dispatchEvent(new CustomEvent(type, { detail }));
    }

    _setupRecognition() {
      if (!SpeechRecognitionImpl) {
        this._emit('voice:error', {
          code: 'SPEECH_RECOGNITION_UNAVAILABLE',
          message: 'SpeechRecognition API não disponível neste navegador.'
        });
        return;
      }

      this.recognition = new SpeechRecognitionImpl();
      this.recognition.lang = this.options.lang;
      this.recognition.continuous = Boolean(this.options.continuous);
      this.recognition.interimResults = Boolean(this.options.interimResults);
      this.recognition.maxAlternatives = Number(this.options.maxAlternatives || 1);

      this.recognition.onstart = () => {
        this.isListening = true;
        this._emit('voice:listening-start', { lang: this.recognition.lang });
      };

      this.recognition.onend = () => {
        this.isListening = false;
        this._emit('voice:listening-stop', {});
      };

      this.recognition.onerror = (event) => {
        this._emit('voice:error', {
          code: event?.error || 'SPEECH_RECOGNITION_ERROR',
          message: event?.message || 'Erro no reconhecimento de voz.'
        });
      };

      this.recognition.onresult = (event) => {
        let finalText = '';
        let interimText = '';

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const transcript = result[0]?.transcript || '';
          if (result.isFinal) {
            finalText += transcript;
          } else {
            interimText += transcript;
          }
        }

        let commandResult = null;
        if (finalText.trim()) {
          commandResult = this.executeVoiceCommand(finalText.trim());
        }

        this._emit('voice:result', {
          finalText: finalText.trim(),
          interimText: interimText.trim(),
          commandMatched: Boolean(commandResult?.recognized),
          commandName: commandResult?.command || null,
          rawEvent: event
        });
      };
    }

    startListening() {
      if (!this.recognition) {
        this._emit('voice:error', {
          code: 'SPEECH_RECOGNITION_UNAVAILABLE',
          message: 'SpeechRecognition API indisponível.'
        });
        return false;
      }

      if (this.isListening) {
        return true;
      }

      try {
        this.recognition.start();
        return true;
      } catch (error) {
        this._emit('voice:error', {
          code: 'SPEECH_RECOGNITION_START_FAILED',
          message: error?.message || String(error)
        });
        return false;
      }
    }

    stopListening() {
      if (!this.recognition) {
        return false;
      }

      if (!this.isListening) {
        return true;
      }

      try {
        this.recognition.stop();
        return true;
      } catch (error) {
        this._emit('voice:error', {
          code: 'SPEECH_RECOGNITION_STOP_FAILED',
          message: error?.message || String(error)
        });
        return false;
      }
    }

    speak(text) {
      const content = String(text || '').trim();
      if (!content) {
        return false;
      }

      if (typeof window === 'undefined' || !window.speechSynthesis || typeof window.SpeechSynthesisUtterance !== 'function') {
        this._emit('voice:error', {
          code: 'SPEECH_SYNTHESIS_UNAVAILABLE',
          message: 'SpeechSynthesis API não disponível neste navegador.'
        });
        return false;
      }

      try {
        const utterance = new window.SpeechSynthesisUtterance(content);
        utterance.lang = this.options.lang;

        utterance.onstart = () => {
          this._emit('voice:speak-start', { text: content });
        };

        utterance.onend = () => {
          this._emit('voice:speak-end', { text: content });
        };

        utterance.onerror = (event) => {
          this._emit('voice:error', {
            code: event?.error || 'SPEECH_SYNTHESIS_ERROR',
            message: event?.message || 'Erro ao sintetizar fala.'
          });
        };

        window.speechSynthesis.speak(utterance);
        return true;
      } catch (error) {
        this._emit('voice:error', {
          code: 'SPEECH_SYNTHESIS_FAILED',
          message: error?.message || String(error)
        });
        return false;
      }
    }
  }

  const apexVoice = new ApexVoice();

  apexVoice.addEventListener('voice:listening-start', () => console.log('[ApexVoice] Ouvindo...'));
  apexVoice.addEventListener('voice:listening-stop', () => console.log('[ApexVoice] Escuta encerrada.'));
  apexVoice.addEventListener('voice:mic-permission-granted', () => console.log('[ApexVoice] Permissão de microfone concedida.'));
  apexVoice.addEventListener('voice:result', (event) => {
    console.log('[ApexVoice] Capturado', {
      finalText: event?.detail?.finalText || '',
      interimText: event?.detail?.interimText || ''
    });
  });
  apexVoice.addEventListener('voice:speak-start', (event) => console.log('[ApexVoice] Falando', event?.detail?.text || ''));
  apexVoice.addEventListener('voice:speak-end', (event) => console.log('[ApexVoice] Fala concluída', event?.detail?.text || ''));
  apexVoice.addEventListener('voice:error', (event) => console.error('[ApexVoice] Erro', event?.detail || {}));

  const exported = {
    requestMicrophonePermission: () => apexVoice.requestMicrophonePermission(),
    startListening: () => apexVoice.startListening(),
    stopListening: () => apexVoice.stopListening(),
    speak: (text) => apexVoice.speak(text),
    on: (eventName, handler) => apexVoice.addEventListener(eventName, handler),
    off: (eventName, handler) => apexVoice.removeEventListener(eventName, handler),
    instance: apexVoice
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exported;
  }

  if (typeof window !== 'undefined') {
    window.ApexVoice = exported;
  }
})();
