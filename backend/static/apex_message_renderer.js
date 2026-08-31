(function () {
  'use strict';

  const STYLE_ID = 'apex-message-renderer-style';

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function injectStyles() {
    if (typeof document === 'undefined') {
      return;
    }

    if (document.getElementById(STYLE_ID)) {
      return;
    }

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .apx-rendered-message {
        position: relative;
        border-radius: 12px;
        border: 1px solid rgba(94, 242, 255, 0.35);
        background: linear-gradient(140deg, rgba(12, 20, 38, 0.96), rgba(22, 33, 58, 0.92));
        padding: 12px 14px;
        color: #d9ecff;
        box-shadow: 0 0 0 1px rgba(94, 242, 255, 0.1), 0 8px 26px rgba(6, 14, 31, 0.55);
        backdrop-filter: blur(2px);
      }

      .apx-rendered-message::before {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: inherit;
        pointer-events: none;
        box-shadow: inset 0 0 0 1px rgba(94, 242, 255, 0.12);
      }

      .apx-rendered-message.message-user {
        border-color: rgba(70, 165, 255, 0.55);
        background: linear-gradient(140deg, rgba(17, 32, 56, 0.96), rgba(28, 47, 79, 0.92));
      }

      .apx-rendered-message.message-apex {
        border-color: rgba(131, 109, 255, 0.55);
        background: linear-gradient(140deg, rgba(24, 21, 48, 0.96), rgba(38, 30, 66, 0.92));
      }

      .apx-rendered-message .message-content {
        line-height: 1.5;
        font-size: 14px;
      }

      .apx-rendered-message p {
        margin: 0 0 8px 0;
      }

      .apx-rendered-message p:last-child {
        margin-bottom: 0;
      }

      .apx-rendered-message ul {
        margin: 0 0 8px 0;
        padding-left: 20px;
      }

      .apx-rendered-message li {
        margin-bottom: 4px;
      }

      .apx-rendered-message code {
        font-family: Consolas, 'SFMono-Regular', Menlo, Monaco, monospace;
        background: rgba(94, 242, 255, 0.12);
        border: 1px solid rgba(94, 242, 255, 0.28);
        color: #95f8ff;
        border-radius: 6px;
        padding: 1px 5px;
      }

      .apx-rendered-message pre {
        margin: 8px 0;
        padding: 12px;
        border-radius: 10px;
        border: 1px solid rgba(94, 242, 255, 0.28);
        background: rgba(8, 14, 28, 0.92);
        overflow-x: auto;
      }

      .apx-rendered-message pre code {
        border: none;
        background: transparent;
        padding: 0;
        color: #b8d8ff;
      }

      .apx-rendered-message .code-lang {
        display: inline-block;
        font-size: 11px;
        color: #8db9ff;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
      }

      .apx-rendered-message a {
        color: #79e6ff;
        text-decoration: underline;
      }
    `;

    document.head.appendChild(style);
  }

  function renderInlineMarkdown(text) {
    let html = escapeHtml(text);

    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    return html;
  }

  function renderTextBlocks(text) {
    const blocks = String(text || '').split(/\n\n+/);

    return blocks.map((block) => {
      const trimmed = block.trim();
      if (!trimmed) {
        return '';
      }

      const lines = trimmed.split('\n');
      const isList = lines.every((line) => /^\s*[-*]\s+/.test(line));

      if (isList) {
        const items = lines
          .map((line) => line.replace(/^\s*[-*]\s+/, ''))
          .map((line) => `<li>${renderInlineMarkdown(line)}</li>`)
          .join('');

        return `<ul>${items}</ul>`;
      }

      const paragraph = lines.map((line) => renderInlineMarkdown(line)).join('<br>');
      return `<p>${paragraph}</p>`;
    }).join('');
  }

  function renderMarkdown(text) {
    const source = String(text || '');
    const codeRegex = /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g;

    let result = '';
    let lastIndex = 0;
    let match;

    while ((match = codeRegex.exec(source)) !== null) {
      const [fullMatch, language, code] = match;
      const textBefore = source.slice(lastIndex, match.index);

      if (textBefore.trim()) {
        result += renderTextBlocks(textBefore);
      }

      const langTag = language ? `<div class="code-lang">${escapeHtml(language)}</div>` : '';
      result += `<pre>${langTag}<code>${escapeHtml(code)}</code></pre>`;

      lastIndex = match.index + fullMatch.length;
    }

    const tail = source.slice(lastIndex);
    if (tail.trim()) {
      result += renderTextBlocks(tail);
    }

    if (!result.trim()) {
      return '<p></p>';
    }

    return result;
  }

  function renderMessage(text, roleClass) {
    injectStyles();
    const body = renderMarkdown(text);
    return `<div class="apx-rendered-message ${roleClass}"><div class="message-content">${body}</div></div>`;
  }

  function renderUserMessage(text) {
    return renderMessage(text, 'message-user');
  }

  function renderApexMessage(text) {
    return renderMessage(text, 'message-apex');
  }

  const exported = {
    renderUserMessage,
    renderApexMessage
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exported;
  }

  if (typeof window !== 'undefined') {
    window.ApexMessageRenderer = exported;
  }
})();
