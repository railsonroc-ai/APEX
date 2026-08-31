(function () {
  'use strict';

  function getElement(id) {
    return document.getElementById(id);
  }

  async function handleSend() {
    const panel = window.ApexPanel;
    const input = getElement('inputBox');

    if (!panel || !input) {
      return;
    }

    const message = String(panel.getInputValue() || '').trim();
    if (!message || panel.getLoadingState()) {
      return;
    }

    await panel.sendToApex(message);
    panel.clearInput();
    panel.focusInput();
  }

  function bindEvents() {
    const sendButton = getElement('sendButton');
    const input = getElement('inputBox');

    if (!sendButton || !input || sendButton.dataset.apexBound === 'true') {
      return;
    }

    sendButton.addEventListener('click', () => {
      handleSend();
    });

    input.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') {
        return;
      }

      event.preventDefault();
      handleSend();
    });

    sendButton.dataset.apexBound = 'true';
  }

  function loadInitialHistory() {
    if (!window.ApexHistory || typeof window.ApexHistory.configure !== 'function') {
      return;
    }

    window.ApexHistory.configure({
      containerId: 'historyContainer',
      inputId: 'inputBox',
      persist: true
    });
  }

  function focusInput() {
    const panel = window.ApexPanel;
    if (panel && typeof panel.focusInput === 'function') {
      panel.focusInput();
      return;
    }

    const input = getElement('inputBox');
    if (input) {
      input.focus();
    }
  }

  function initApexDashboard() {
    loadInitialHistory();
    bindEvents();
    focusInput();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApexDashboard);
  } else {
    initApexDashboard();
  }

  window.initApexDashboard = initApexDashboard;
})();
