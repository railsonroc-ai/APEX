/**
 * chat-engine.js — Lógica compartilhada do Chat APEX com DOMPurify (fail-safe), Auth Key e Retry isolado
 */
(function () {
  'use strict';

  const { area: AREA, lang: LANG, label: LABEL } = window.APEX_CHAT_CONFIG || { area: 'ads', lang: 'pt-BR', label: 'ADS' };

  let historico = [];
  let ttsAudio  = null;

  const input = document.getElementById('user-input');

  if (input) {
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { 
        e.preventDefault(); 
        sendMessage(); 
      }
    });
  }

  function getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const key = localStorage.getItem('apex_key');
    if (key) headers['X-Apex-Key'] = key;
    return headers;
  }

  function handleAuthError() {
    const key = prompt("Acesso protegido. Digite a sua chave APEX_ACCESS_KEY:");
    if (key) {
      localStorage.setItem('apex_key', key);
      return true;
    }
    return false;
  }

  function ask(msg) { 
    if (input) {
      input.value = msg; 
      sendMessage(); 
    }
  }

  function toast(msg) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2200);
  }

  function escHtml(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function cleanText(r) {
    return (r || '').replace(/\[\s*[^\]]{0,40}\s*\]/g, '').replace(/\\n/g, '\n');
  }

  function removeWelcome() { 
    const w = document.getElementById('welcome'); 
    if (w) w.remove(); 
  }
  
  function scrollBottom() { 
    const c = document.getElementById('messages'); 
    if (c) c.scrollTop = c.scrollHeight; 
  }

  function appendUserMsg(text) {
    removeWelcome();
    const msgs = document.getElementById('messages');
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = 'msg user';
    div.innerHTML = `<div class="avatar">R</div><div class="bubble">${escHtml(text).replace(/\n/g, '<br>')}</div>`;
    msgs.appendChild(div);
    scrollBottom();
  }

  function createBotMsg() {
    removeWelcome();
    const msgs = document.getElementById('messages');
    const div = document.createElement('div'); 
    div.className = 'msg bot';
    
    const avatar = document.createElement('div'); 
    avatar.className = 'avatar'; 
    avatar.textContent = 'A';
    
    const bubble = document.createElement('div'); 
    bubble.className = 'bubble';
    
    const tag = document.createElement('div'); 
    tag.className = 'area-tag'; 
    tag.textContent = LABEL;
    
    const content = document.createElement('div'); 
    content.className = 'md stream-cursor';
    
    bubble.appendChild(tag);
    bubble.appendChild(content);
    div.appendChild(avatar);
    div.appendChild(bubble);
    msgs.appendChild(div);
    scrollBottom();
    
    return { content, bubble };
  }

  function stripForTTS(text) {
    return (text || '')
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`[^`]+`/g, '')
      .replace(/#{1,6}\s/g, '')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/^\s*[-*+]\s/gm, '')
      .replace(/\n{2,}/g, '. ')
      .replace(/\n/g, ' ')
      .trim()
      .slice(0, 600);
  }

  async function speakText(text, ttsBtn) {
    if (ttsAudio) { 
      ttsAudio.pause(); 
      ttsAudio = null; 
    }
    const plain = stripForTTS(text);
    if (!plain) return;
    
    if (ttsBtn) ttsBtn.classList.add('speaking');
    
    try {
      const res = await fetch('/tts', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ texto: plain, lang: LANG }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      ttsAudio = new Audio(url);
      
      ttsAudio.onended = () => { 
        if (ttsBtn) ttsBtn.classList.remove('speaking'); 
        URL.revokeObjectURL(url); 
        ttsAudio = null; 
      };
      ttsAudio.onerror = () => { 
        if (ttsBtn) ttsBtn.classList.remove('speaking'); 
        ttsAudio = null; 
      };
      
      await ttsAudio.play().catch(() => {
        if (ttsBtn) ttsBtn.classList.remove('speaking');
      });
    } catch { 
      if (ttsBtn) ttsBtn.classList.remove('speaking'); 
    }
  }

  function finalizeBotMsg(content, bubble, fullText) {
    content.classList.remove('stream-cursor');
    
    if (typeof window.marked !== 'undefined' && typeof window.DOMPurify !== 'undefined') {
      content.innerHTML = window.DOMPurify.sanitize(window.marked.parse(cleanText(fullText)));
    } else {
      content.textContent = cleanText(fullText);
    }

    if (typeof window.hljs !== 'undefined') {
      content.querySelectorAll('pre code').forEach(el => window.hljs.highlightElement(el));
    }

    const saveBtn = document.createElement('button');
    saveBtn.className = 'save-btn';
    saveBtn.textContent = '📌 Salvar nota';
    saveBtn.onclick = () => saveNote(fullText, saveBtn);
    bubble.appendChild(saveBtn);

    const ttsBtn = document.createElement('button');
    ttsBtn.className = 'tts-btn';
    ttsBtn.title = 'Ouvir';
    ttsBtn.textContent = '🔊';
    ttsBtn.onclick = () => speakText(fullText, ttsBtn);
    bubble.appendChild(ttsBtn);

    scrollBottom();
  }

  async function saveNote(text, btn) {
    try {
      const res = await fetch('/api/notes', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ text: text.slice(0, 400), area: AREA }),
      });

      if (res.status === 401 && handleAuthError()) {
        return saveNote(text, btn);
      }

      const data = await res.json();
      if (data.ok) {
        btn.textContent = '✅ Salvo!';
        btn.classList.add('saved');
        toast('Nota salva com sucesso!');
        setTimeout(() => { 
          btn.textContent = '📌 Salvar nota'; 
          btn.classList.remove('saved'); 
        }, 2000);
      }
    } catch { 
      toast('Erro ao salvar nota.'); 
    }
  }

  function _updateBadge() {
    const b = document.getElementById('memory-badge');
    if (!b) return;
    const n = parseInt(b.dataset.count || '0', 10) + 2;
    b.dataset.count = n;
    b.textContent = `🧠 ${n} msgs`;
  }

  async function _streamChat(text, btn) {
    const { content, bubble } = createBotMsg();
    let fullText = '';

    try {
      const res = await fetch('/chat/stream', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ message: text, area: AREA }),
      });

      if (res.status === 401) {
        if (handleAuthError()) {
          return _streamChat(text, btn);
        }
        throw new Error("Acesso não autorizado.");
      }

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n');
        buffer = parts.pop();

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data: ')) continue;
          
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.token) {
              fullText += evt.token;
              content.textContent = fullText;
              scrollBottom();
            } else if (evt.done) {
              finalizeBotMsg(content, bubble, fullText);
              historico.push({ role: 'assistant', content: fullText });
              if (historico.length > 20) historico = historico.slice(-20);
              _updateBadge();
            } else if (evt.error) {
              content.classList.remove('stream-cursor');
              content.innerHTML = `<span style="color:#ff6b6b">⚠️ ${escHtml(evt.error)}</span>`;
            }
          } catch {}
        }
      }

      if (fullText && content.classList.contains('stream-cursor')) {
        finalizeBotMsg(content, bubble, fullText);
        historico.push({ role: 'assistant', content: fullText });
        if (historico.length > 20) historico = historico.slice(-20);
        _updateBadge();
      }
    } catch (err) {
      content.classList.remove('stream-cursor');
      content.innerHTML = `<span style="color:#ff6b6b">⚠️ Sem conexão com o servidor.<br><small>${escHtml(err.message)}</small></span>`;
    }

    if (btn) btn.disabled = false;
    if (input) input.focus();
  }

  async function sendMessage() {
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    const btn = document.getElementById('send-btn');
    if (btn) btn.disabled = true;
    input.value = '';
    input.style.height = 'auto';

    appendUserMsg(text);
    historico.push({ role: 'user', content: text });

    await _streamChat(text, btn);
  }

  function clearChat() {
    historico = [];
    const msgs = document.getElementById('messages');
    if (msgs) {
      msgs.innerHTML = `<div class="welcome" id="welcome"><h2>Pronto!</h2><p>Conversa limpa. Faça sua pergunta sobre ADS.</p></div>`;
    }
  }

  window.ask = ask;
  window.sendMessage = sendMessage;
  window.clearChat = clearChat;
  window.toast = toast;
}());
