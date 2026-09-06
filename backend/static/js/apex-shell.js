/**
 * apex-shell.js
 *
 * Navegação da tela inicial futurista e ligação com o tutor existente.
 * O servidor continua autoritativo para sessão, progresso e revisões.
 */
(function () {
  'use strict';

  const config = window.APEX_CHAT_CONFIG || {};
  const AREA = String(config.area || 'ads');
  const LABEL = String(config.label || 'ADS');
  const Api = window.ApexApi;
  const Chat = window.ApexChat;

  const homeScreen = document.getElementById('home-screen');
  const studyScreen = document.getElementById('study-screen');
  const homeCanvas = document.getElementById('home-canvas');
  const panel = document.getElementById('home-panel');
  const panelKicker = document.getElementById('home-panel-kicker');
  const panelTitle = document.getElementById('home-panel-title');
  const panelBody = document.getElementById('home-panel-body');
  const panelClose = document.getElementById('home-panel-close');
  const liveStatus = document.getElementById('home-live-status');
  const progressValue = document.getElementById('home-progress-value');
  const progressDetail = document.getElementById('home-progress-detail');
  const notificationCount = document.getElementById('notification-count');
  const input = document.getElementById('user-input');

  let dashboard = null;
  let panelTrigger = null;
  let dashboardLoading = null;
  let activePanel = null;
  let actionBusy = false;

  function makeElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function clearExpanded() {
    document.querySelectorAll('[aria-controls="home-panel"]')
      .forEach(button => button.setAttribute('aria-expanded', 'false'));
  }

  function closePanel({ restoreFocus = true } = {}) {
    panel.hidden = true;
    homeCanvas.classList.remove('panel-open');
    clearExpanded();
    activePanel = null;
    if (restoreFocus && panelTrigger) {
      panelTrigger.focus();
    }
  }

  function setPanelHeading(kicker, title) {
    panelKicker.textContent = kicker;
    panelTitle.textContent = title;
    liveStatus.textContent = title;
  }

  function openPanel(trigger, name, render) {
    if (activePanel === name && !panel.hidden) {
      closePanel();
      return;
    }

    clearExpanded();
    panelTrigger = trigger;
    activePanel = name;
    trigger.setAttribute('aria-expanded', 'true');
    panel.hidden = false;
    homeCanvas.classList.add('panel-open');
    panelBody.replaceChildren();
    render();
    panelClose.focus({ preventScroll: true });
    panel.scrollIntoView({ block: 'nearest' });
  }

  function addParagraph(text, className) {
    const paragraph = makeElement('p', className || '', text);
    panelBody.appendChild(paragraph);
    return paragraph;
  }

  function choice(label, detail, onClick, { disabled = false } = {}) {
    const button = makeElement('button', 'home-choice');
    button.type = 'button';
    button.disabled = disabled;
    const strong = makeElement('strong', '', label);
    const small = makeElement('small', '', detail);
    button.append(strong, small);
    if (typeof onClick === 'function') {
      button.addEventListener('click', onClick);
    }
    return button;
  }

  function choiceGrid(items, { three = false } = {}) {
    const grid = makeElement(
      'div',
      three ? 'home-choice-grid three-columns' : 'home-choice-grid'
    );
    items.forEach(item => grid.appendChild(item));
    panelBody.appendChild(grid);
    return grid;
  }

  function backButton(label, onClick) {
    const button = makeElement('button', 'home-back', `← ${label}`);
    button.type = 'button';
    button.addEventListener('click', onClick);
    panelBody.appendChild(button);
    return button;
  }

  function sessionRuntime() {
    if (dashboard && dashboard.session) {
      return dashboard.session;
    }
    if (Chat && typeof Chat.getSessionRuntime === 'function') {
      return Chat.getSessionRuntime();
    }
    return { status: 'unknown' };
  }

  function showStudy() {
    closePanel({ restoreFocus: false });
    homeScreen.hidden = true;
    studyScreen.hidden = false;
    document.title = `APEX — Estudo de ${LABEL}`;
    if (Chat && typeof Chat.focusInput === 'function') {
      Chat.focusInput();
    }
  }

  async function showHome() {
    studyScreen.hidden = true;
    homeScreen.hidden = false;
    document.title = 'APEX — Tutor Inteligente';
    await refreshDashboard({ quiet: true });
  }

  function showBusyMessage(message) {
    panelBody.replaceChildren();
    const box = makeElement('div', 'panel-message');
    box.appendChild(makeElement('p', '', message));
    panelBody.appendChild(box);
  }

  async function withBusy(action) {
    if (actionBusy) {
      return null;
    }
    actionBusy = true;
    try {
      return await action();
    } finally {
      actionBusy = false;
    }
  }

  async function resumeDirect() {
    return withBusy(async () => {
      const runtime = sessionRuntime();
      if (runtime.status === 'paused') {
        showBusyMessage('Retomando seu estudo…');
        const resumed = await Chat.resumeLearningSession('direct');
        if (!resumed) {
          return null;
        }
      }
      showStudy();
      return true;
    });
  }

  async function reviewBeforeResume() {
    return withBusy(async () => {
      let runtime = sessionRuntime();
      if (runtime.status === 'reviewing') {
        showStudy();
        return true;
      }
      if (runtime.status === 'studying') {
        showBusyMessage('Preparando uma revisão curta…');
        const paused = await Chat.pauseLearningSession();
        if (!paused) {
          return null;
        }
        runtime = paused;
      }
      if (runtime.status !== 'paused') {
        window.toast('Não há um estudo ativo para revisar antes.');
        return null;
      }
      showStudy();
      return Chat.resumeLearningSession('review');
    });
  }

  async function ensureStudying() {
    const runtime = sessionRuntime();
    if (runtime.status === 'reviewing') {
      window.toast('Conclua a revisão de retomada antes de iniciar outra ação.');
      showStudy();
      return false;
    }
    if (runtime.status === 'paused') {
      const resumed = await Chat.resumeLearningSession('direct');
      return Boolean(resumed);
    }
    return runtime.status === 'studying';
  }

  async function sendControlMessage(message) {
    return withBusy(async () => {
      showBusyMessage('Abrindo o tutor…');
      if (!await ensureStudying()) {
        return null;
      }
      showStudy();
      Chat.ask(message);
      return true;
    });
  }

  async function startStudy(concept, restart) {
    return withBusy(async () => {
      showBusyMessage('Preparando o conteúdo…');
      if (!await ensureStudying()) {
        return null;
      }
      try {
        const result = await Api.startStudy(
          AREA,
          concept.concept_id,
          restart === true
        );
        if (dashboard) {
          dashboard.session = result.session;
        }
        await Chat.refreshSessionRuntime({ quiet: true });
        showStudy();
        Chat.ask('Começar este estudo.');
        return result;
      } catch (error) {
        window.toast(error.message || 'Não foi possível iniciar o conteúdo.');
        await refreshDashboard({ quiet: true });
        return null;
      }
    });
  }

  async function startReview(conceptId = null) {
    return withBusy(async () => {
      showBusyMessage('Preparando a revisão…');
      if (!await ensureStudying()) {
        return null;
      }
      try {
        const result = await Api.startReview(AREA, conceptId);
        if (dashboard) {
          dashboard.session = result.session;
        }
        await Chat.refreshSessionRuntime({ quiet: true });
        showStudy();
        Chat.ask('Começar esta revisão.');
        return result;
      } catch (error) {
        window.toast(error.message || 'Não foi possível iniciar a revisão.');
        await refreshDashboard({ quiet: true });
        return null;
      }
    });
  }

  function renderContinue() {
    const runtime = sessionRuntime();
    const focus = runtime.learning_focus || {};
    setPanelHeading('CONTINUAR ESTUDOS', 'Como deseja continuar?');

    if (runtime.status === 'loading' || runtime.status === 'unknown') {
      addParagraph('O estado do estudo ainda não pôde ser carregado.');
      return;
    }

    if (runtime.status === 'reviewing') {
      addParagraph('Sua revisão de retomada está em andamento.');
      choiceGrid([
        choice('Continuar revisão', 'Voltar para a tarefa atual.', showStudy)
      ]);
      return;
    }

    const hasConcept = Boolean(focus.concept_id || focus.concept);
    if (hasConcept) {
      const detail = makeElement('div', 'panel-message');
      detail.appendChild(makeElement('h2', '', focus.concept || 'Estudo atual'));
      detail.appendChild(makeElement('p', '', focus.next_step || 'Continue do ponto em que parou.'));
      panelBody.appendChild(detail);
    } else {
      addParagraph('Você ainda não iniciou um conteúdo nesta área.');
    }

    choiceGrid([
      choice(
        runtime.status === 'paused' ? 'Retomar direto' : 'Abrir estudo',
        hasConcept ? 'Voltar ao ponto exato.' : 'Entrar na tela do tutor.',
        resumeDirect
      ),
      choice(
        'Revisar antes',
        hasConcept ? 'Relembrar e depois continuar.' : 'Disponível após iniciar um conteúdo.',
        reviewBeforeResume,
        { disabled: !hasConcept }
      )
    ]);
  }

  function renderReview() {
    const due = dashboard ? dashboard.due_reviews || [] : [];
    const difficult = dashboard ? dashboard.difficulties || [] : [];
    const concepts = dashboard
      ? (dashboard.progress || []).filter(item => item.updated_at)
      : [];
    setPanelHeading('REVISAR CONTEÚDO', 'O que deseja revisar?');
    choiceGrid([
      choice(
        'Revisões de hoje',
        due.length ? `${due.length} revisão(ões) disponível(is).` : 'Nenhuma revisão programada agora.',
        () => startReview(),
        { disabled: due.length === 0 }
      ),
      choice(
        'Conteúdos com dificuldade',
        difficult.length ? `${difficult.length} conteúdo(s) registrado(s).` : 'Nenhuma dificuldade registrada.',
        renderDifficulties,
        { disabled: difficult.length === 0 }
      ),
      choice(
        'Escolher conteúdo',
        'Selecionar um tema para reforçar.',
        () => renderReviewConcepts(concepts),
        { disabled: concepts.length === 0 }
      )
    ], { three: true });
  }

  function renderDifficulties() {
    const items = dashboard ? dashboard.difficulties || [] : [];
    setPanelHeading('REVISAR CONTEÚDO', 'Conteúdos com dificuldade');
    choiceGrid(items.map(item => choice(
      item.concept,
      `${item.difficulty_count} ocorrência(s) de dificuldade.`,
      () => startReview(item.concept_id)
    )));
    backButton('Opções de revisão', renderReview);
  }

  function renderReviewConcepts(concepts) {
    setPanelHeading('REVISAR CONTEÚDO', 'Escolher conteúdo');
    choiceGrid(concepts.map(item => choice(
      item.concept,
      'Pedir ao tutor uma revisão deste tema.',
      () => startReview(item.concept_id)
    )));
    backButton('Opções de revisão', renderReview);
  }

  function renderNewStudy() {
    setPanelHeading('NOVO ESTUDO', 'Por onde deseja começar?');
    choiceGrid([
      choice('Escolher área', `Área atual: ${LABEL}.`, renderAreas),
      choice('Escolher conteúdo', 'Iniciar um tema do catálogo.', renderConcepts),
      choice('Definir objetivo', 'Dizer com suas palavras o que deseja aprender.', renderGoal)
    ], { three: true });
  }

  function renderAreas() {
    setPanelHeading('NOVO ESTUDO', 'Escolher área');
    choiceGrid([
      choice('ADS', 'Análise e Desenvolvimento de Sistemas.', () => changeArea('ads')),
      choice('TI', 'Tecnologia da Informação.', () => changeArea('it'))
    ]);
    backButton('Novo estudo', renderNewStudy);
  }

  function changeArea(area) {
    if (area === AREA) {
      renderConcepts();
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set('area', area);
    window.location.assign(url.toString());
  }

  function renderConcepts() {
    const concepts = dashboard ? dashboard.selectable_concepts || [] : [];
    setPanelHeading(`NOVO ESTUDO · ${LABEL}`, 'Escolher conteúdo');
    if (!concepts.length) {
      addParagraph('Nenhum conteúdo está disponível nesta área.');
    } else {
      choiceGrid(concepts.map(item => choice(
        item.canonical_name,
        'O progresso anterior será preservado.',
        () => confirmConcept(item)
      )));
    }
    backButton('Novo estudo', renderNewStudy);
  }

  function confirmConcept(concept) {
    setPanelHeading('NOVO ESTUDO', concept.canonical_name);
    const box = makeElement('div', 'panel-message');
    box.appendChild(makeElement('p', '', 'Escolha como deseja abrir este conteúdo.'));
    panelBody.replaceChildren(box);
    choiceGrid([
      choice(
        'Continuar progresso existente',
        'Retomar o que já foi registrado.',
        () => startStudy(concept, false)
      ),
      choice(
        'Recomeçar do zero',
        'Zerar somente o progresso deste conteúdo.',
        () => startStudy(concept, true)
      )
    ]);
    backButton('Conteúdos', renderConcepts);
  }

  function renderGoal() {
    setPanelHeading('NOVO ESTUDO', 'Definir objetivo');
    const form = makeElement('form');
    form.id = 'home-goal-form';
    const label = makeElement('label', 'home-field', 'O que você quer aprender?');
    label.htmlFor = 'home-goal-input';
    const field = makeElement('input', 'home-input');
    field.id = 'home-goal-input';
    field.name = 'goal';
    field.type = 'text';
    field.maxLength = 300;
    field.required = true;
    field.placeholder = 'Ex.: quero entender lógica de programação';
    const submit = makeElement('button', 'home-primary', 'Começar estudo');
    submit.type = 'submit';
    form.append(label, field, submit);
    form.addEventListener('submit', event => {
      event.preventDefault();
      const goal = field.value.trim();
      if (goal) {
        sendControlMessage(`Quero estudar ${goal}.`);
      }
    });
    panelBody.replaceChildren(form);
    backButton('Novo estudo', renderNewStudy);
    field.focus();
  }

  function renderProgress() {
    setPanelHeading('SUA EVOLUÇÃO', 'Progresso');
    if (!dashboard) {
      addParagraph('O progresso ainda não pôde ser carregado.');
      return;
    }

    const summary = dashboard.summary || {};
    const summaryGrid = makeElement('div', 'progress-summary');
    [
      [summary.started || 0, 'conceitos iniciados'],
      [summary.mastered || 0, 'conceitos dominados'],
      [summary.due_reviews || 0, 'revisões de hoje']
    ].forEach(([value, label]) => {
      const item = makeElement('div', 'progress-summary-item');
      item.append(makeElement('strong', '', value), makeElement('span', '', label));
      summaryGrid.appendChild(item);
    });
    panelBody.appendChild(summaryGrid);

    const started = (dashboard.progress || []).filter(item => item.updated_at);
    if (!started.length) {
      addParagraph('Seu progresso aparecerá aqui depois do primeiro estudo.');
      return;
    }

    const list = makeElement('div', 'progress-list');
    started.forEach(item => {
      const row = makeElement('div', 'progress-item');
      const text = makeElement('div');
      text.append(
        makeElement('strong', '', item.concept),
        makeElement('small', '', `${item.review_count || 0} revisão(ões) · ${item.difficulty_count || 0} dificuldade(s)`)
      );
      row.append(text, makeElement('span', 'progress-percent', `${Math.round(Number(item.mastery || 0) * 100)}%`));
      list.appendChild(row);
    });
    panelBody.appendChild(list);
  }

  function renderNotifications() {
    const due = dashboard ? dashboard.due_reviews || [] : [];
    setPanelHeading('APEX', 'Notificações');
    if (!due.length) {
      addParagraph('Nenhuma revisão está pendente agora.');
      return;
    }
    choiceGrid(due.map(item => choice(
      'Revisão disponível',
      item.concept,
      () => startReview(item.concept_id)
    )));
  }

  function renderSettings() {
    setPanelHeading('PREFERÊNCIAS', 'Configurações');
    const label = makeElement('label', 'home-option-row');
    const checkbox = makeElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = document.body.classList.contains('apex-low-glow');
    checkbox.addEventListener('change', () => {
      document.body.classList.toggle('apex-low-glow', checkbox.checked);
      try {
        window.localStorage.setItem('apex-low-glow', checkbox.checked ? '1' : '0');
      } catch {
        // Preferência visual continua válida nesta aba.
      }
    });
    label.append(checkbox, document.createTextNode('Reduzir brilho do cenário'));
    panelBody.appendChild(label);
    addParagraph('Esse ajuste altera somente a aparência; o estudo não é afetado.');
  }

  function updateDashboardDisplay() {
    if (!dashboard) {
      return;
    }
    const summary = dashboard.summary || {};
    const mean = Math.round(Number(summary.mean_mastery || 0) * 100);
    progressValue.textContent = summary.started
      ? `${mean}% de domínio médio`
      : 'Primeiro estudo ainda não iniciado';
    progressDetail.textContent = `${summary.mastered || 0} dominado(s) · ${summary.due_reviews || 0} revisão(ões)`;

    const due = Number(summary.due_reviews || 0);
    notificationCount.textContent = String(due);
    notificationCount.hidden = due === 0;
  }

  async function refreshDashboard({ quiet = false } = {}) {
    if (!Api || typeof Api.getDashboard !== 'function') {
      if (!quiet) {
        window.toast('A tela inicial não conseguiu consultar o servidor.');
      }
      return null;
    }
    if (dashboardLoading) {
      return dashboardLoading;
    }
    dashboardLoading = Api.getDashboard(AREA)
      .then(result => {
        dashboard = result;
        updateDashboardDisplay();
        return result;
      })
      .catch(error => {
        progressValue.textContent = 'Progresso indisponível';
        progressDetail.textContent = 'Tente novamente em instantes';
        if (!quiet) {
          window.toast(error.message || 'Não foi possível carregar a tela inicial.');
        }
        return null;
      })
      .finally(() => {
        dashboardLoading = null;
      });
    return dashboardLoading;
  }

  async function handleHomeAction(event) {
    const button = event.currentTarget;
    const action = button.dataset.homeAction;
    await refreshDashboard({ quiet: true });
    const renders = {
      continue: renderContinue,
      review: renderReview,
      new: renderNewStudy,
      progress: renderProgress
    };
    if (renders[action]) {
      openPanel(button, action, renders[action]);
    }
  }

  document.querySelectorAll('[data-home-action]')
    .forEach(button => button.addEventListener('click', handleHomeAction));

  document.getElementById('notifications-btn').addEventListener('click', async event => {
    await refreshDashboard({ quiet: true });
    openPanel(event.currentTarget, 'notifications', renderNotifications);
  });

  document.getElementById('settings-btn').addEventListener('click', event => {
    openPanel(event.currentTarget, 'settings', renderSettings);
  });

  document.getElementById('home-logo-btn').addEventListener('click', () => closePanel());
  document.getElementById('back-home-btn').addEventListener('click', showHome);
  panelClose.addEventListener('click', () => closePanel());

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) {
      event.preventDefault();
      closePanel();
    }
  });

  document.addEventListener('apex:session-updated', event => {
    if (dashboard && event.detail && event.detail.session) {
      dashboard.session = event.detail.session;
    }
  });

  try {
    document.body.classList.toggle(
      'apex-low-glow',
      window.localStorage.getItem('apex-low-glow') === '1'
    );
  } catch {
    // Armazenamento local pode estar desativado.
  }

  refreshDashboard();
}());
