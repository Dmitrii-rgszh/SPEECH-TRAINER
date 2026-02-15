import { mountScenariosWorkspace } from '/static/components/ScenarioWizard.js';
const MENU_ITEMS = ['Дэшборд', 'Сценарии', 'Персоны', 'Аналитика'];
const PERSONA_DRAFT_STORAGE_KEY = 'persona_wizard_drafts_v1';
const PERSONAS_MOCK = [];
const PERSONA_STEP_TITLES = ['Название и описание', 'Настройка внешнего вида', 'Поведение персоны'];
const PERSONA_AVATARS_MOCK = [
  {
    id: 'male_senior_1',
    label: 'Мужчина 1',
    thumbSrc: '/static/assets/avatars/male_senior_close.png',
    previewSrc: '/static/assets/avatars/male_senior_full.png',
    gender: 'male',
  },
  {
    id: 'female_1',
    label: 'Женщина 1',
    thumbSrc: '/static/assets/avatars/female_1_close.png',
    previewSrc: '/static/assets/avatars/female_1_full.png',
    gender: 'female',
  },
];

const readPersonaDraftStore = () => {
  try {
    const raw = window.localStorage.getItem(PERSONA_DRAFT_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_) {
    return {};
  }
};

const writePersonaDraftStore = (store) => {
  try {
    window.localStorage.setItem(PERSONA_DRAFT_STORAGE_KEY, JSON.stringify(store || {}));
  } catch (_) {
    // ignore storage quota errors
  }
};

const toCardPersona = (item) => ({
  id: String(item.id || ''),
  name: String(item.name || 'Новая персона'),
  subtitle: String(item.status || '').toLowerCase() === 'active' ? 'Готова' : 'Черновик',
  summary: String(item.description || ''),
  age: Number(item.age || 0),
  clientType: String(item.client_type || ''),
  prompt: String(item.behavior || ''),
  avatarId: String(item.avatar_id || 'male_senior_1'),
  status: String(item.status || 'draft'),
  version: Number(item.version || 1),
  createdAt: String(item.created_at || ''),
  updatedAt: String(item.updated_at || ''),
  greeting: String(item.greeting || ''),
  avatarGender: String(item.avatar_gender || 'male'),
  behaviorMode: String(item.behavior_mode || 'free'),
  behaviorStruct:
    item.behavior_struct && typeof item.behavior_struct === 'object'
      ? {
          communicationStyle: String(item.behavior_struct.communication_style || 'unknown'),
          decisionSpeed: String(item.behavior_struct.decision_speed || 'unknown'),
          openness: String(item.behavior_struct.openness || 'unknown'),
          pressureReaction: String(item.behavior_struct.pressure_reaction || 'unknown'),
          objectionLevel: String(item.behavior_struct.objection_level || 'unknown'),
          answerLength: String(item.behavior_struct.answer_length || 'unknown'),
          empathyEffect: String(item.behavior_struct.empathy_effect || 'unknown'),
          extra: String(item.behavior_struct.extra || ''),
        }
      : null,
  behaviorStructConfidence:
    item.behavior_struct_confidence && typeof item.behavior_struct_confidence === 'object'
      ? {
          communicationStyle: Number(item.behavior_struct_confidence.communication_style || 0),
          decisionSpeed: Number(item.behavior_struct_confidence.decision_speed || 0),
          openness: Number(item.behavior_struct_confidence.openness || 0),
          pressureReaction: Number(item.behavior_struct_confidence.pressure_reaction || 0),
          objectionLevel: Number(item.behavior_struct_confidence.objection_level || 0),
          answerLength: Number(item.behavior_struct_confidence.answer_length || 0),
          empathyEffect: Number(item.behavior_struct_confidence.empathy_effect || 0),
        }
      : null,
});

export function RightPanel() {
  const panel = document.createElement('section');
  panel.className = 'right-panel';

  const card = document.createElement('div');
  card.className = 'auth-card';

  const urlParams = new URLSearchParams(window.location.search);
  const registerToken = (urlParams.get('register_token') || '').trim();
  let currentLogin = '';
  let workspaceActive = false;
  let scenariosController = null;
  let personasStore = PERSONAS_MOCK.map((p) => ({ ...p }));
  const HERO_EXIT_DURATION_MS = 1500;
  const HERO_EXIT_DELAY_MS = 160;
  const LOGIN_ENTER_DURATION_MS = HERO_EXIT_DURATION_MS;

  // TODO: re-enable corporate domain restriction (@vtb.ru / @rgsl.ru).
  const isCorporateEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/i.test((value || '').trim());

  const api = async (path, options = {}) => {
    const resp = await fetch(path, {
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      ...options,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const err = new Error(data?.error || 'Ошибка запроса');
      err.status = resp.status;
      err.payload = data;
      throw err;
    }
    return data;
  };

  const loadPersonasFromApi = async () => {
    try {
      const data = await api('/personas', { method: 'GET' });
      personasStore = Array.isArray(data?.items) ? data.items.map(toCardPersona) : [];
    } catch (_) {
      personasStore = [];
    }
  };

  const buildPersonaCards = () => {
    const cards = personasStore.map((persona) => ({
      ...persona,
      _isDraft: false,
      _draftSlot: '',
      _updatedAt: '',
    }));
    const draftStore = readPersonaDraftStore();
    Object.entries(draftStore || {}).forEach(([slot, item]) => {
      if (!item || typeof item !== 'object' || !item.data) return;
      const data = item.data || {};
      cards.unshift({
        id: `draft_${slot}`,
        name: String(data.name || 'Новая персона'),
        subtitle: 'Черновик',
        complexity: `Шаг ${Math.max(1, Math.min(3, Number(item.step || 0) + 1))} из 3`,
        summary: String(data.description || 'Описание не задано'),
        prompt: String(data.behavior || ''),
        avatarId: String(data.avatarId || 'male_senior_1'),
        _isDraft: true,
        _draftSlot: slot,
        _updatedAt: String(item.updatedAt || ''),
      });
    });
    return cards;
  };

  const setAppMode = (mode) => {
    document.body.classList.remove('app-mode-auth', 'app-mode-workspace');
    document.body.classList.add(mode === 'workspace' ? 'app-mode-workspace' : 'app-mode-auth');
  };

  const prepareAuthCard = () => {
    card.innerHTML = '';
    card.classList.remove('auth-card--centered', 'auth-card--page');
  };

  const renderAuthShell = (activeTab, mountContent) => {
    setAppMode('auth');
    panel.classList.remove('right-panel--workspace');
    panel.innerHTML = '';
    workspaceActive = false;

    const shell = document.createElement('div');
    shell.className = 'auth-shell';

    const topbar = document.createElement('header');
    topbar.className = 'auth-topbar';

    const navCluster = document.createElement('div');
    navCluster.className = 'auth-nav-cluster';

    const brand = document.createElement('div');
    brand.className = 'auth-brand';

    const brandLogo = document.createElement('img');
    brandLogo.className = 'auth-brand-logo';
    brandLogo.src = '/static/assets/logo/logo.svg';
    brandLogo.alt = 'RGSL';

    const brandTitle = document.createElement('strong');
    brandTitle.className = 'auth-brand-title';
    brandTitle.textContent = 'Речевой тренажер RGSL';

    brand.append(brandLogo, brandTitle);

    const nav = document.createElement('nav');
    nav.className = 'auth-nav';
    MENU_ITEMS.forEach((label) => {
      const button = document.createElement('button');
      button.className = 'auth-nav-btn';
      button.type = 'button';
      button.textContent = label;
      nav.append(button);
    });

    const actions = document.createElement('div');
    actions.className = 'auth-actions';

    const loginAction = document.createElement('button');
    loginAction.className = `auth-top-action ${activeTab === 'login' ? 'is-active' : ''}`.trim();
    loginAction.type = 'button';
    loginAction.textContent = 'Войти';
    loginAction.addEventListener('click', () => {
      if (activeTab !== 'login') renderLoginView();
    });

    const registerAction = document.createElement('button');
    registerAction.className = `auth-top-action ${activeTab === 'register' ? 'is-active' : ''}`.trim();
    registerAction.type = 'button';
    registerAction.textContent = 'Зарегистрироваться';
    registerAction.addEventListener('click', () => {
      if (activeTab !== 'register') renderRegistrationRequestView();
    });

    actions.append(loginAction, registerAction);
    navCluster.append(brand, nav);
    topbar.append(navCluster, actions);

    const stage = document.createElement('div');
    stage.className = 'auth-stage';
    if (activeTab === 'landing') {
      stage.classList.add('auth-stage--landing');
    }
    stage.append(mountContent());

    shell.append(topbar, stage);
    panel.append(shell);
  };

  const buildLoginCard = () => {
    const loginCard = document.createElement('div');
    loginCard.className = 'auth-card';

    const title = document.createElement('h1');
    title.className = 'auth-title';
    title.textContent = 'Вход на платформу';

    const subtitle = document.createElement('p');
    subtitle.className = 'auth-subtitle';
    subtitle.textContent = 'Введите логин и пароль';

    const formGrid = document.createElement('div');
    formGrid.className = 'form-grid';

    const loginInput = document.createElement('input');
    loginInput.className = 'input';
    loginInput.type = 'text';
    loginInput.name = 'login';
    loginInput.placeholder = 'Логин';
    loginInput.autocomplete = 'username';

    const loginRow = document.createElement('div');
    loginRow.className = 'field-with-help';

    const loginHelpButton = document.createElement('button');
    loginHelpButton.className = 'help-button';
    loginHelpButton.type = 'button';
    loginHelpButton.textContent = '?';
    loginHelpButton.setAttribute('aria-label', 'Подсказка для поля Логин');

    const loginHelpPopup = document.createElement('div');
    loginHelpPopup.className = 'help-popup hidden';
    loginHelpPopup.textContent =
      'Полностью введите адрес корпоративной почты. Допустимые домены "vtb.ru" и @rgsl.ru".';

    loginHelpButton.addEventListener('click', () => {
      loginHelpPopup.classList.toggle('hidden');
    });

    const passwordInput = document.createElement('input');
    passwordInput.className = 'input';
    passwordInput.type = 'password';
    passwordInput.name = 'password';
    passwordInput.placeholder = 'Пароль';
    passwordInput.autocomplete = 'current-password';

    const rememberRow = document.createElement('label');
    rememberRow.className = 'remember-row';

    const rememberText = document.createElement('span');
    rememberText.className = 'remember-text';
    rememberText.textContent = 'Запомнить логин и пароль?';

    const rememberCheckbox = document.createElement('input');
    rememberCheckbox.className = 'remember-checkbox';
    rememberCheckbox.type = 'checkbox';
    rememberCheckbox.name = 'remember';

    rememberRow.append(rememberText, rememberCheckbox);

    const registerLink = document.createElement('a');
    registerLink.className = 'link-button';
    registerLink.href = '#';
    registerLink.textContent = 'Нет аккаунта? Зарегистрируйтесь!';
    registerLink.addEventListener('click', (event) => {
      event.preventDefault();
      renderRegistrationRequestView();
    });

    const loginButton = document.createElement('button');
    loginButton.className = 'login-button';
    loginButton.type = 'button';
    loginButton.textContent = 'Войти';

    const authMessage = document.createElement('div');
    authMessage.className = 'auth-message';
    authMessage.setAttribute('aria-live', 'polite');

    const isValidCredentials = () => {
      const login = (loginInput.value || '').trim().toLowerCase();
      const password = (passwordInput.value || '').trim();
      // TODO: re-enable corporate domain restriction (@vtb.ru / @rgsl.ru).
      const validLogin = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(login);
      return validLogin && password.length > 0;
    };

    loginButton.addEventListener('click', async () => {
      if (!isValidCredentials()) {
        authMessage.textContent = 'Проверьте логин и пароль.';
        authMessage.classList.add('error');
        return;
      }

      try {
        const resp = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            login: loginInput.value.trim(),
            password: passwordInput.value,
            remember: rememberCheckbox.checked,
          }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          authMessage.textContent = data?.error || 'Ошибка входа.';
          authMessage.classList.add('error');
          return;
        }
        renderWorkspaceView('Дэшборд', loginInput.value.trim());
      } catch (_) {
        authMessage.textContent = 'Сервис авторизации недоступен.';
        authMessage.classList.add('error');
      }
    });

    loginRow.append(loginInput, loginHelpButton, loginHelpPopup);
    formGrid.append(loginRow, passwordInput, rememberRow, registerLink, loginButton, authMessage);
    loginCard.append(title, subtitle, formGrid);
    return loginCard;
  };

  const startLandingToLoginTransition = (heroElement) => {
    const stage = heroElement.closest('.auth-stage');
    if (!stage) {
      renderLoginView();
      return;
    }

    const loginCard = buildLoginCard();
    loginCard.classList.add('auth-card--slide-in');
    stage.append(loginCard);

    const loginEntryStartMs = HERO_EXIT_DELAY_MS;
    const heroExitDoneMs = HERO_EXIT_DELAY_MS + HERO_EXIT_DURATION_MS + 40;
    const loginEntryDoneMs = loginEntryStartMs + LOGIN_ENTER_DURATION_MS + 80;
    const transitionDoneMs = Math.max(heroExitDoneMs, loginEntryDoneMs);

    window.setTimeout(() => {
      requestAnimationFrame(() => {
        loginCard.classList.add('is-entering');
      });
    }, loginEntryStartMs);

    window.setTimeout(() => {
      heroElement.remove();
    }, heroExitDoneMs);

    window.setTimeout(() => {
      stage.classList.remove('auth-stage--landing');
      loginCard.classList.remove('auth-card--slide-in', 'is-entering');
    }, transitionDoneMs);
  };

  const renderLandingView = () => {
    renderAuthShell('landing', () => {
      const hero = document.createElement('section');
      hero.className = 'auth-hero';
      let isExiting = false;

      const title = document.createElement('h1');
      title.className = 'auth-hero-title';
      title.innerHTML = 'Готовьтесь к сложным<br>диалогам уверенно';

      const subtitle = document.createElement('p');
      subtitle.className = 'auth-hero-subtitle';
      subtitle.textContent = 'Речевой тренажер помогает отрабатывать сценарии, повышать качество коммуникации и анализировать прогресс.';

      const startButton = document.createElement('button');
      startButton.className = 'auth-hero-cta';
      startButton.type = 'button';
      startButton.textContent = 'Начать';
      startButton.addEventListener('click', () => {
        if (isExiting) return;
        isExiting = true;
        startButton.disabled = true;
        hero.classList.add('auth-hero--exit');
        startLandingToLoginTransition(hero);
      });

      hero.append(title, subtitle, startButton);
      return hero;
    });
  };

  const renderWorkspaceView = (titleText, login = '') => {
    if (scenariosController) {
      scenariosController.destroy?.();
      scenariosController = null;
    }
    setAppMode('workspace');
    panel.innerHTML = '';
    panel.classList.add('right-panel--workspace');
    workspaceActive = true;
    if (login) currentLogin = login;

    const shell = document.createElement('div');
    shell.className = 'workspace-shell';

    const topbar = document.createElement('header');
    topbar.className = 'auth-topbar workspace-topbar';

    const navCluster = document.createElement('div');
    navCluster.className = 'auth-nav-cluster';

    const brand = document.createElement('div');
    brand.className = 'auth-brand';

    const brandLogo = document.createElement('img');
    brandLogo.className = 'auth-brand-logo';
    brandLogo.src = '/static/assets/logo/logo.svg';
    brandLogo.alt = 'RGSL';

    const brandTitle = document.createElement('strong');
    brandTitle.className = 'auth-brand-title';
    brandTitle.textContent = 'Речевой тренажер RGSL';
    brand.append(brandLogo, brandTitle);

    const nav = document.createElement('nav');
    nav.className = 'auth-nav';
    MENU_ITEMS.forEach((label) => {
      const button = document.createElement('button');
      button.className = 'auth-nav-btn';
      button.type = 'button';
      button.textContent = label;
      if (label === titleText) {
        button.classList.add('is-current');
      }
      button.addEventListener('click', () => {
        if (label === 'Персоны') {
          void (async () => {
            await loadPersonasFromApi();
            renderWorkspaceView(label, currentLogin);
          })();
          return;
        }
        renderWorkspaceView(label, currentLogin);
      });
      nav.append(button);
    });
    navCluster.append(brand, nav);

    const actions = document.createElement('div');
    actions.className = 'workspace-actions';

    const account = document.createElement('div');
    account.className = 'workspace-account';
    account.textContent = `Учетная запись: ${currentLogin || '-'}`;

    const logout = document.createElement('button');
    logout.className = 'workspace-logout';
    logout.type = 'button';
    logout.textContent = 'Выйти';
    logout.addEventListener('click', async () => {
      try {
        await fetch('/auth/logout', {
          method: 'POST',
          credentials: 'same-origin',
        });
      } catch (_) {
        // ignore
      }
      window.location.href = '/';
    });

    actions.append(account, logout);
    topbar.append(navCluster, actions);

    const stage = document.createElement('div');
    stage.className = 'auth-stage workspace-stage';

    card.innerHTML = '';
    card.className = 'auth-card auth-card--page workspace-page';
    card.classList.remove('workspace-page--personas');

    const header = document.createElement('div');
    header.className = 'workspace-header';

    const title = document.createElement('h1');
    title.className = 'workspace-title';
    title.textContent = titleText;
    header.append(title);

    if (titleText === 'Сценарии') {
      const newScenarioButton = document.createElement('button');
      newScenarioButton.className = 'workspace-new-btn';
      newScenarioButton.type = 'button';
      newScenarioButton.textContent = '+ Новый сценарий';
      header.append(newScenarioButton);
      const scenariosMount = document.createElement('div');
      scenariosMount.className = 'scenario-workspace';
      card.append(header, scenariosMount);
      scenariosController = mountScenariosWorkspace({
        mount: scenariosMount,
        newScenarioButton,
      });
    } else if (titleText === 'Персоны') {
      card.classList.add('workspace-page--personas');
      const createPersonaButton = document.createElement('button');
      createPersonaButton.className = 'workspace-new-btn';
      createPersonaButton.type = 'button';
      createPersonaButton.textContent = '+ Создать персону';
      createPersonaButton.addEventListener('click', () => {
        openPersonaWizard({
          mode: 'create',
          onSave: async (payload) => {
            await api('/personas', {
              method: 'POST',
              body: JSON.stringify({
                persona: {
                  name: payload.name,
                  description: payload.description || '',
                  age: Number(payload.age || 0),
                  client_type: payload.clientType || '',
                  avatar_gender: payload.avatarGender || 'male',
                  avatar_id: payload.avatarId || 'male_senior_1',
                  greeting: payload.greeting || '',
                  behavior: payload.behavior || '',
                  behavior_mode: payload.behaviorMode || 'free',
                  behavior_struct: {
                    communication_style: payload.behaviorStruct?.communicationStyle || '',
                    decision_speed: payload.behaviorStruct?.decisionSpeed || '',
                    openness: payload.behaviorStruct?.openness || '',
                    pressure_reaction: payload.behaviorStruct?.pressureReaction || '',
                    objection_level: payload.behaviorStruct?.objectionLevel || '',
                    answer_length: payload.behaviorStruct?.answerLength || '',
                    empathy_effect: payload.behaviorStruct?.empathyEffect || '',
                    extra: payload.behaviorStruct?.extra || '',
                  },
                  behavior_struct_confidence: {
                    communication_style: Number(payload.behaviorStructConfidence?.communicationStyle || 0),
                    decision_speed: Number(payload.behaviorStructConfidence?.decisionSpeed || 0),
                    openness: Number(payload.behaviorStructConfidence?.openness || 0),
                    pressure_reaction: Number(payload.behaviorStructConfidence?.pressureReaction || 0),
                    objection_level: Number(payload.behaviorStructConfidence?.objectionLevel || 0),
                    answer_length: Number(payload.behaviorStructConfidence?.answerLength || 0),
                    empathy_effect: Number(payload.behaviorStructConfidence?.empathyEffect || 0),
                  },
                },
              }),
            });
            await loadPersonasFromApi();
            renderWorkspaceView('Персоны', currentLogin);
          },
        });
      });
      header.append(createPersonaButton);

      const personasWrap = document.createElement('div');
      personasWrap.className = 'personas-grid';
      const personaCards = buildPersonaCards();
      personaCards.forEach((persona) => {
        const cardEl = document.createElement('article');
        cardEl.className = 'persona-card';

        const top = document.createElement('div');
        top.className = 'persona-card-top';

        const avatar = document.createElement('div');
        avatar.className = 'persona-card-avatar';
        const avatarMeta = PERSONA_AVATARS_MOCK.find((item) => item.id === persona.avatarId);
        if (avatarMeta?.thumbSrc) {
          const avatarImg = document.createElement('img');
          avatarImg.className = 'persona-card-avatar-image';
          avatarImg.src = avatarMeta.thumbSrc;
          avatarImg.alt = persona.name || 'Аватар';
          avatarImg.addEventListener('error', () => {
            avatar.innerHTML = '';
            avatar.textContent = persona.name[0] || 'П';
          });
          avatar.append(avatarImg);
        } else {
          avatar.textContent = persona.name[0] || 'П';
        }

        const titleGroup = document.createElement('div');
        titleGroup.className = 'persona-card-title-group';

        const nameEl = document.createElement('h3');
        nameEl.className = 'persona-card-name';
        nameEl.textContent = `${persona.name} — ${persona.subtitle}`;
        titleGroup.append(nameEl);

        const actions = document.createElement('div');
        actions.className = 'persona-card-actions';
        if (persona._isDraft) {
          const draftBadge = document.createElement('span');
          draftBadge.className = 'persona-status-inline is-draft';
          draftBadge.textContent = 'DRAFT';
          actions.append(draftBadge);
        } else if (String(persona.status || '').toLowerCase() !== 'active') {
          const draftBadge = document.createElement('span');
          draftBadge.className = 'persona-status-inline is-draft';
          draftBadge.textContent = 'DRAFT';
          actions.append(draftBadge);
        }

        const copyBtn = document.createElement('button');
        copyBtn.className = 'persona-mini-btn';
        copyBtn.type = 'button';
        copyBtn.textContent = '⧉';
        copyBtn.title = 'Клонировать';
        copyBtn.addEventListener('click', async () => {
          if (persona._isDraft) return;
          await api(`/personas/${encodeURIComponent(persona.id)}/clone`, { method: 'POST' });
          await loadPersonasFromApi();
          renderWorkspaceView('Персоны', currentLogin);
        });

        const editBtn = document.createElement('button');
        editBtn.className = 'persona-mini-btn';
        editBtn.type = 'button';
        editBtn.textContent = '✎';
        editBtn.title = persona._isDraft ? 'Продолжить черновик' : 'Редактировать';
        editBtn.addEventListener('click', () => {
          const slotData = persona._isDraft ? readPersonaDraftStore()[persona._draftSlot] : null;
          const draftData = slotData?.data || {};
          openPersonaWizard({
            mode: persona._isDraft ? (persona._draftSlot === 'create' ? 'create' : 'edit') : 'edit',
            personaId: !persona._isDraft ? persona.id : '',
            draftSlotOverride: persona._isDraft ? persona._draftSlot : '',
            initialData: {
              name: draftData.name || persona.name,
              description: draftData.description || persona.summary,
              age: Number(draftData.age || persona.age || 35),
              clientType: String(draftData.clientType || persona.clientType || ''),
              greeting: draftData.greeting || '',
              behavior: draftData.behavior || persona.prompt || '',
              avatarGender: draftData.avatarGender || persona.avatarGender || 'male',
              avatarId: draftData.avatarId || persona.avatarId || 'male_senior_1',
              behaviorMode: draftData.behaviorMode || persona.behaviorMode || 'free',
              behaviorStruct:
                draftData.behaviorStruct ||
                persona.behaviorStruct || {
                  communicationStyle: 'unknown',
                  decisionSpeed: 'unknown',
                  openness: 'unknown',
                  pressureReaction: 'unknown',
                  objectionLevel: 'unknown',
                  answerLength: 'unknown',
                  empathyEffect: 'unknown',
                  extra: '',
                },
              behaviorStructConfidence:
                draftData.behaviorStructConfidence ||
                persona.behaviorStructConfidence || {
                  communicationStyle: 0,
                  decisionSpeed: 0,
                  openness: 0,
                  pressureReaction: 0,
                  objectionLevel: 0,
                  answerLength: 0,
                  empathyEffect: 0,
                },
            },
            onSave: async (payload) => {
              if (persona._isDraft) {
                await api('/personas', {
                  method: 'POST',
                  body: JSON.stringify({
                    persona: {
                      name: payload.name,
                      description: payload.description || '',
                      age: Number(payload.age || 0),
                      client_type: payload.clientType || '',
                      avatar_gender: payload.avatarGender || 'male',
                      avatar_id: payload.avatarId || 'male_senior_1',
                      greeting: payload.greeting || '',
                      behavior: payload.behavior || '',
                      behavior_mode: payload.behaviorMode || 'free',
                      behavior_struct: {
                        communication_style: payload.behaviorStruct?.communicationStyle || '',
                        decision_speed: payload.behaviorStruct?.decisionSpeed || '',
                        openness: payload.behaviorStruct?.openness || '',
                        pressure_reaction: payload.behaviorStruct?.pressureReaction || '',
                        objection_level: payload.behaviorStruct?.objectionLevel || '',
                        answer_length: payload.behaviorStruct?.answerLength || '',
                        empathy_effect: payload.behaviorStruct?.empathyEffect || '',
                        extra: payload.behaviorStruct?.extra || '',
                      },
                      behavior_struct_confidence: {
                        communication_style: Number(payload.behaviorStructConfidence?.communicationStyle || 0),
                        decision_speed: Number(payload.behaviorStructConfidence?.decisionSpeed || 0),
                        openness: Number(payload.behaviorStructConfidence?.openness || 0),
                        pressure_reaction: Number(payload.behaviorStructConfidence?.pressureReaction || 0),
                        objection_level: Number(payload.behaviorStructConfidence?.objectionLevel || 0),
                        answer_length: Number(payload.behaviorStructConfidence?.answerLength || 0),
                        empathy_effect: Number(payload.behaviorStructConfidence?.empathyEffect || 0),
                      },
                    },
                  }),
                });
              } else {
                await api(`/personas/${encodeURIComponent(persona.id)}`, {
                  method: 'PATCH',
                  body: JSON.stringify({
                    persona: {
                      name: payload.name,
                      description: payload.description || '',
                      age: Number(payload.age || 0),
                      client_type: payload.clientType || '',
                      avatar_gender: payload.avatarGender || 'male',
                      avatar_id: payload.avatarId || 'male_senior_1',
                      greeting: payload.greeting || '',
                      behavior: payload.behavior || '',
                      behavior_mode: payload.behaviorMode || 'free',
                      behavior_struct: {
                        communication_style: payload.behaviorStruct?.communicationStyle || '',
                        decision_speed: payload.behaviorStruct?.decisionSpeed || '',
                        openness: payload.behaviorStruct?.openness || '',
                        pressure_reaction: payload.behaviorStruct?.pressureReaction || '',
                        objection_level: payload.behaviorStruct?.objectionLevel || '',
                        answer_length: payload.behaviorStruct?.answerLength || '',
                        empathy_effect: payload.behaviorStruct?.empathyEffect || '',
                        extra: payload.behaviorStruct?.extra || '',
                      },
                      behavior_struct_confidence: {
                        communication_style: Number(payload.behaviorStructConfidence?.communicationStyle || 0),
                        decision_speed: Number(payload.behaviorStructConfidence?.decisionSpeed || 0),
                        openness: Number(payload.behaviorStructConfidence?.openness || 0),
                        pressure_reaction: Number(payload.behaviorStructConfidence?.pressureReaction || 0),
                        objection_level: Number(payload.behaviorStructConfidence?.objectionLevel || 0),
                        answer_length: Number(payload.behaviorStructConfidence?.answerLength || 0),
                        empathy_effect: Number(payload.behaviorStructConfidence?.empathyEffect || 0),
                      },
                    },
                  }),
                });
              }
              await loadPersonasFromApi();
              renderWorkspaceView('Персоны', currentLogin);
            },
          });
        });

        let publishBtn = null;
        if (!persona._isDraft && String(persona.status || '').toLowerCase() !== 'active') {
          publishBtn = document.createElement('button');
          publishBtn.className = 'persona-mini-btn';
          publishBtn.type = 'button';
          publishBtn.textContent = '✓';
          publishBtn.title = 'Опубликовать персону';
          publishBtn.addEventListener('click', async () => {
            try {
              await api(`/personas/${encodeURIComponent(persona.id)}/publish`, { method: 'POST' });
              await loadPersonasFromApi();
              renderWorkspaceView('Персоны', currentLogin);
            } catch (error) {
              window.alert(error?.message || 'Не удалось опубликовать персону.');
            }
          });
        }

        if (publishBtn) {
          actions.append(copyBtn, publishBtn, editBtn);
        } else {
          actions.append(copyBtn, editBtn);
        }
        top.append(avatar, titleGroup, actions);

        const descriptionValue = String(persona.summary || '').trim();
        const descriptionLabel = document.createElement('p');
        descriptionLabel.className = 'persona-card-label';
        descriptionLabel.textContent = 'Описание';

        const descriptionText = document.createElement('p');
        descriptionText.className = 'persona-card-prompt';
        descriptionText.textContent = descriptionValue || 'Пока не заполнено';
        if (!descriptionValue) {
          descriptionText.classList.add('is-placeholder');
        }
        cardEl.append(top, descriptionLabel, descriptionText);
        personasWrap.append(cardEl);
      });
      if (!personaCards.length) {
        const empty = document.createElement('div');
        empty.className = 'scenario-empty';
        empty.textContent = 'Пока нет персон. Нажмите «Создать персону», чтобы добавить первую.';
        personasWrap.append(empty);
      }

      card.append(header, personasWrap);
    } else {
      card.append(header);
    }

    stage.append(card);
    shell.append(topbar, stage);
    panel.append(shell);
  };

  const openPersonaWizard = ({
    mode = 'create',
    initialData = null,
    onSave,
    draftSlotOverride = '',
    personaId = '',
  }) => {
    const layer = document.createElement('div');
    layer.className = 'scenario-wizard-layer';

    const backdrop = document.createElement('div');
    backdrop.className = 'scenario-wizard-backdrop';

    const modal = document.createElement('section');
    modal.className = 'scenario-wizard persona-wizard';

    const draft = {
      name: initialData?.name || 'Александр — Персона 1. Доминирующий',
      description: initialData?.description ?? '',
      age: Number(initialData?.age || 35),
      clientType: String(initialData?.clientType || ''),
      avatarGender: initialData?.avatarGender || 'male',
      avatarId: initialData?.avatarId || 'male_senior_1',
      greeting: initialData?.greeting || '',
      behaviorMode: initialData?.behaviorMode || 'free',
      behaviorStruct: {
        communicationStyle: initialData?.behaviorStruct?.communicationStyle || 'unknown',
        decisionSpeed: initialData?.behaviorStruct?.decisionSpeed || 'unknown',
        openness: initialData?.behaviorStruct?.openness || 'unknown',
        pressureReaction: initialData?.behaviorStruct?.pressureReaction || 'unknown',
        objectionLevel: initialData?.behaviorStruct?.objectionLevel || 'unknown',
        answerLength: initialData?.behaviorStruct?.answerLength || 'unknown',
        empathyEffect: initialData?.behaviorStruct?.empathyEffect || 'unknown',
        extra: initialData?.behaviorStruct?.extra || '',
      },
      behaviorStructConfidence: {
        communicationStyle: Number(initialData?.behaviorStructConfidence?.communicationStyle || 0),
        decisionSpeed: Number(initialData?.behaviorStructConfidence?.decisionSpeed || 0),
        openness: Number(initialData?.behaviorStructConfidence?.openness || 0),
        pressureReaction: Number(initialData?.behaviorStructConfidence?.pressureReaction || 0),
        objectionLevel: Number(initialData?.behaviorStructConfidence?.objectionLevel || 0),
        answerLength: Number(initialData?.behaviorStructConfidence?.answerLength || 0),
        empathyEffect: Number(initialData?.behaviorStructConfidence?.empathyEffect || 0),
      },
      behavior: initialData?.behavior || '',
    };
    let step = 0;
    let dirty = false;
    const draftSlot = draftSlotOverride || (mode === 'edit' ? `edit:${initialData?.name || 'persona'}` : 'create');
    const store = readPersonaDraftStore();
    const savedDraft = store[draftSlot];
    if (savedDraft && typeof savedDraft === 'object' && savedDraft.data) {
      Object.assign(draft, savedDraft.data);
      step = Math.max(0, Math.min(2, Number(savedDraft.step || 0)));
    }
    if (!draft.behaviorStruct || typeof draft.behaviorStruct !== 'object') {
      draft.behaviorStruct = {
        communicationStyle: 'unknown',
        decisionSpeed: 'unknown',
        openness: 'unknown',
        pressureReaction: 'unknown',
        objectionLevel: 'unknown',
        answerLength: 'unknown',
        empathyEffect: 'unknown',
        extra: '',
      };
    }
    if (!draft.behaviorStructConfidence || typeof draft.behaviorStructConfidence !== 'object') {
      draft.behaviorStructConfidence = {
        communicationStyle: 0,
        decisionSpeed: 0,
        openness: 0,
        pressureReaction: 0,
        objectionLevel: 0,
        answerLength: 0,
        empathyEffect: 0,
      };
    }
    const normalizeStructValue = (v) => {
      const s = String(v || '').trim();
      return s ? s : 'unknown';
    };
    draft.behaviorStruct.communicationStyle = normalizeStructValue(draft.behaviorStruct.communicationStyle);
    draft.behaviorStruct.decisionSpeed = normalizeStructValue(draft.behaviorStruct.decisionSpeed);
    draft.behaviorStruct.openness = normalizeStructValue(draft.behaviorStruct.openness);
    draft.behaviorStruct.pressureReaction = normalizeStructValue(draft.behaviorStruct.pressureReaction);
    draft.behaviorStruct.objectionLevel = normalizeStructValue(draft.behaviorStruct.objectionLevel);
    draft.behaviorStruct.answerLength = normalizeStructValue(draft.behaviorStruct.answerLength);
    draft.behaviorStruct.empathyEffect = normalizeStructValue(draft.behaviorStruct.empathyEffect);
    if (draft.behaviorMode !== 'free' && draft.behaviorMode !== 'structured') {
      draft.behaviorMode = 'free';
    }

    const markDirty = () => {
      dirty = true;
    };

    const persistDraft = () => {
      const nextStore = readPersonaDraftStore();
      nextStore[draftSlot] = {
        mode,
        step,
        data: { ...draft },
        updatedAt: new Date().toISOString(),
      };
      writePersonaDraftStore(nextStore);
      dirty = false;
    };

    const askCloseAction = () =>
      new Promise((resolve) => {
        const promptBackdrop = document.createElement('div');
        promptBackdrop.className = 'scenario-modal-backdrop';

        const promptModal = document.createElement('div');
        promptModal.className = 'scenario-modal persona-exit-modal';
        promptModal.innerHTML = `
          <div class="scenario-modal-head">
            <h3>Сохранить персону в черновиках?</h3>
          </div>
          <div class="scenario-modal-body">
            <p class="wizard-help">Выберите действие перед закрытием формы.</p>
          </div>
          <div class="scenario-modal-footer persona-exit-actions">
            <button type="button" data-action="yes" class="is-primary">Да</button>
            <button type="button" data-action="no">Нет</button>
            <button type="button" data-action="continue">Продолжить создание</button>
          </div>
        `;

        const finish = (action) => {
          promptBackdrop.remove();
          resolve(action);
        };
        promptModal.querySelector('[data-action="yes"]')?.addEventListener('click', () => finish('yes'));
        promptModal.querySelector('[data-action="no"]')?.addEventListener('click', () => finish('no'));
        promptModal
          .querySelector('[data-action="continue"]')
          ?.addEventListener('click', () => finish('continue'));
        promptBackdrop.addEventListener('click', (event) => {
          if (event.target === promptBackdrop) finish('continue');
        });
        promptBackdrop.append(promptModal);
        document.body.append(promptBackdrop);
      });

    const closeWizard = async (force = false) => {
      if (!force) {
        const action = await askCloseAction();
        if (action === 'continue') return;
        if (action === 'yes') {
          persistDraft();
        }
      }
      layer.remove();
      renderWorkspaceView('Персоны', currentLogin);
    };
    backdrop.addEventListener('click', () => {
      closeWizard();
    });

    const head = document.createElement('header');
    head.className = 'scenario-wizard-head';
    const headLeft = document.createElement('div');
    const headTitle = document.createElement('h2');
    headTitle.textContent = mode === 'edit' ? 'Редактирование персоны' : 'Новая персона';
    const headSubtitle = document.createElement('p');
    headSubtitle.textContent = `Шаг ${step + 1} из 3`;
    headLeft.append(headTitle, headSubtitle);
    const closeBtn = document.createElement('button');
    closeBtn.className = 'scenario-close-btn';
    closeBtn.type = 'button';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', () => {
      closeWizard();
    });
    head.append(headLeft, closeBtn);

    const stepper = document.createElement('nav');
    stepper.className = 'scenario-stepper';

    const errors = document.createElement('div');
    errors.className = 'scenario-step-errors is-empty';

    const body = document.createElement('div');
    body.className = 'scenario-wizard-body';

    const footer = document.createElement('footer');
    footer.className = 'scenario-wizard-footer';

    const backBtn = document.createElement('button');
    backBtn.className = 'wizard-btn';
    backBtn.type = 'button';
    backBtn.textContent = '← Назад';
    backBtn.addEventListener('click', () => {
      if (step > 0) {
        step -= 1;
        render();
      }
    });

    const saveDraftBtn = document.createElement('button');
    saveDraftBtn.className = 'wizard-btn';
    saveDraftBtn.type = 'button';
    saveDraftBtn.textContent = 'Сохранить';

    const nextBtn = document.createElement('button');
    nextBtn.className = 'wizard-btn is-primary';
    nextBtn.type = 'button';
    nextBtn.addEventListener('click', async () => {
      const issue = validateStep(step);
      if (issue) {
        errors.className = 'scenario-step-errors';
        errors.textContent = issue;
        return;
      }
      errors.className = 'scenario-step-errors is-empty';
      errors.textContent = '';
      if (step < PERSONA_STEP_TITLES.length - 1) {
        step += 1;
        render();
        return;
      }
      if (draft.behaviorMode === 'structured') {
        draft.behavior = composeStructuredBehavior();
      } else {
        const inferred = inferBehaviorStructFromText(draft.behavior);
        draft.behaviorStruct = {
          ...draft.behaviorStruct,
          ...inferred.behaviorStruct,
        };
        draft.behaviorStructConfidence = inferred.behaviorStructConfidence;
      }
      try {
        await Promise.resolve(onSave?.({ ...draft, personaId }));
        const nextStore = readPersonaDraftStore();
        delete nextStore[draftSlot];
        writePersonaDraftStore(nextStore);
        dirty = false;
        closeWizard(true);
      } catch (error) {
        errors.className = 'scenario-step-errors';
        errors.textContent = error?.message || 'Не удалось сохранить персону.';
      }
    });

    saveDraftBtn.addEventListener('click', () => {
      persistDraft();
      errors.className = 'scenario-step-errors';
      errors.textContent = 'Черновик сохранен.';
      window.setTimeout(() => {
        errors.className = 'scenario-step-errors is-empty';
        errors.textContent = '';
      }, 1800);
    });

    footer.append(backBtn, saveDraftBtn, nextBtn);

    const validateStep = (stepIdx) => {
      if (stepIdx === 0) {
        if (!draft.name || draft.name.trim().length < 2) return 'Укажите имя персоны (минимум 2 символа).';
        if (!Number(draft.age) || Number(draft.age) < 18 || Number(draft.age) > 90) {
          return 'Укажите возраст персоны в диапазоне 18..90.';
        }
        if (!draft.clientType) return 'Выберите тип клиента.';
      }
      if (stepIdx === 1) {
        if (!draft.avatarGender) return 'Выберите пол аватара.';
      }
      return '';
    };

    const renderCounter = (value, max) => `${(value || '').length}/${max}`;

    const composeStructuredBehavior = () => {
      const s = draft.behaviorStruct || {};
      const view = (v) => (String(v || 'unknown') === 'unknown' ? 'не указано' : v);
      const lines = [
        'Параметры поведения персоны:',
        `- Манера общения: ${view(s.communicationStyle)}`,
        `- Скорость принятия решений: ${view(s.decisionSpeed)}`,
        `- Открытость в диалоге: ${view(s.openness)}`,
        `- Реакция на давление: ${view(s.pressureReaction)}`,
        `- Частота возражений: ${view(s.objectionLevel)}`,
        `- Длина ответов: ${view(s.answerLength)}`,
        `- Влияние эмпатии: ${view(s.empathyEffect)}`,
      ];
      const extra = String(s.extra || '').trim();
      if (extra) {
        lines.push('', 'Дополнительно:', extra);
      }
      return lines.join('\n');
    };

    const inferBehaviorStructFromText = (text) => {
      const raw = String(text || '').toLowerCase();
      const has = (list) => list.some((w) => raw.includes(w));
      const pick = (candidates) => {
        for (const item of candidates) {
          if (has(item.keywords)) return item;
        }
        return { value: 'unknown', confidence: 0 };
      };

      const result = {
        communicationStyle: pick([
          { value: 'эмоциональный', confidence: 85, keywords: ['эмоцион', 'энергич', 'вдохнов'] },
          { value: 'напористый', confidence: 85, keywords: ['напорист', 'жестк', 'давит', 'требовательн'] },
          { value: 'деловой', confidence: 80, keywords: ['делов', 'по делу', 'конкрет', 'структур'] },
          { value: 'спокойный', confidence: 80, keywords: ['спокойн', 'ровн', 'сдержан'] },
        ]),
        decisionSpeed: pick([
          { value: 'быстро', confidence: 85, keywords: ['быстро реш', 'сразу реш', 'моментально', 'оперативно'] },
          { value: 'долго', confidence: 85, keywords: ['долго', 'подум', 'взвеш', 'не спеш'] },
          { value: 'средне', confidence: 70, keywords: ['средне', 'обычно'] },
        ]),
        openness: pick([
          { value: 'закрытый', confidence: 85, keywords: ['закрыт', 'не раскры', 'не расска', 'коротко'] },
          { value: 'открытый', confidence: 85, keywords: ['открыт', 'подробно', 'делится', 'охотно'] },
          { value: 'нейтральный', confidence: 70, keywords: ['нейтральн'] },
        ]),
        pressureReaction: pick([
          { value: 'резко негативная', confidence: 90, keywords: ['не люблю давление', 'раздраж', 'резко', 'агрессив'] },
          { value: 'терпимая', confidence: 80, keywords: ['терпим', 'спокойно реаг', 'нормально к давлению'] },
          { value: 'умеренная', confidence: 70, keywords: ['умерен', 'настораж', 'чувствителен к давлению'] },
        ]),
        objectionLevel: pick([
          { value: 'высокая', confidence: 85, keywords: ['много возраж', 'часто возраж', 'скептич', 'сомнева'] },
          { value: 'низкая', confidence: 80, keywords: ['редко возраж', 'доверяет', 'легко соглаша'] },
          { value: 'средняя', confidence: 70, keywords: ['средняя', 'умеренно возраж'] },
        ]),
        answerLength: pick([
          { value: 'коротко', confidence: 85, keywords: ['кратко', 'коротко', 'без лишних', 'по делу'] },
          { value: 'развернуто', confidence: 85, keywords: ['развернуто', 'подробно', 'длинно'] },
          { value: 'средне', confidence: 70, keywords: ['средне', 'умеренно подробно'] },
        ]),
        empathyEffect: pick([
          { value: 'смягчается', confidence: 85, keywords: ['смягча', 'эмпатия помогает', 'при эмпатии лучше'] },
          { value: 'не смягчается', confidence: 85, keywords: ['не смягча', 'эмпатия не влияет', 'жестко держит позицию'] },
          { value: 'нейтрально', confidence: 70, keywords: ['нейтрально', 'почти не влияет'] },
        ]),
      };

      return {
        behaviorStruct: {
          communicationStyle: result.communicationStyle.value,
          decisionSpeed: result.decisionSpeed.value,
          openness: result.openness.value,
          pressureReaction: result.pressureReaction.value,
          objectionLevel: result.objectionLevel.value,
          answerLength: result.answerLength.value,
          empathyEffect: result.empathyEffect.value,
          extra: draft.behaviorStruct.extra || '',
        },
        behaviorStructConfidence: {
          communicationStyle: result.communicationStyle.confidence,
          decisionSpeed: result.decisionSpeed.confidence,
          openness: result.openness.confidence,
          pressureReaction: result.pressureReaction.confidence,
          objectionLevel: result.objectionLevel.confidence,
          answerLength: result.answerLength.confidence,
          empathyEffect: result.empathyEffect.confidence,
        },
      };
    };

    const buildStep1 = () => {
      const cardEl = document.createElement('section');
      cardEl.className = 'wizard-card';
      const titleEl = document.createElement('h3');
      titleEl.className = 'wizard-card-title';
      titleEl.textContent = 'Название и описание';
      const subtitleEl = document.createElement('p');
      subtitleEl.className = 'wizard-help';
      subtitleEl.textContent = 'Укажите название и краткое описание персоны.';
      const fieldName = document.createElement('div');
      fieldName.className = 'wizard-field';
      fieldName.innerHTML = '<label class="wizard-label">Имя <b>*</b></label>';
      const nameInput = document.createElement('input');
      nameInput.className = 'wizard-input';
      nameInput.maxLength = 40;
      nameInput.value = draft.name;
      const nameCounter = document.createElement('div');
      nameCounter.className = 'wizard-counter';
      nameCounter.textContent = renderCounter(draft.name, 40);
      nameInput.addEventListener('input', () => {
        draft.name = nameInput.value;
        nameCounter.textContent = renderCounter(draft.name, 40);
        markDirty();
      });
      fieldName.append(nameInput, nameCounter);

      const profileRow = document.createElement('div');
      profileRow.className = 'wizard-row wizard-row-2';

      const ageField = document.createElement('div');
      ageField.className = 'wizard-field';
      ageField.innerHTML = '<label class="wizard-label">Возраст <b>*</b></label>';
      const ageInput = document.createElement('input');
      ageInput.className = 'wizard-input';
      ageInput.type = 'number';
      ageInput.min = '18';
      ageInput.max = '90';
      ageInput.value = String(draft.age || 35);
      ageInput.addEventListener('input', () => {
        draft.age = Number(ageInput.value || 0);
        markDirty();
      });
      ageField.append(ageInput);

      const typeField = document.createElement('div');
      typeField.className = 'wizard-field';
      typeField.innerHTML = '<label class="wizard-label">Тип клиента <b>*</b></label>';
      const typeSelect = document.createElement('select');
      typeSelect.className = 'wizard-select';
      [
        { value: '', label: 'Выберите тип клиента' },
        { value: 'student', label: 'Студент' },
        { value: 'working', label: 'Работающий' },
        { value: 'retired', label: 'Пенсионер' },
        { value: 'retired_working', label: 'Пенсионер + работающий' },
      ].forEach((opt) => {
        const el = document.createElement('option');
        el.value = opt.value;
        el.textContent = opt.label;
        if (draft.clientType === opt.value) el.selected = true;
        typeSelect.append(el);
      });
      typeSelect.addEventListener('change', () => {
        draft.clientType = typeSelect.value;
        markDirty();
      });
      typeField.append(typeSelect);
      profileRow.append(ageField, typeField);

      const fieldDescription = document.createElement('div');
      fieldDescription.className = 'wizard-field';
      fieldDescription.innerHTML = '<label class="wizard-label">Описание (опционально)</label>';
      const descriptionInput = document.createElement('textarea');
      descriptionInput.className = 'wizard-textarea persona-description-input';
      descriptionInput.rows = 6;
      descriptionInput.maxLength = 500;
      descriptionInput.value = draft.description;
      const descriptionHelp = document.createElement('div');
      descriptionHelp.className = 'wizard-help';
      descriptionHelp.textContent =
        'Это описание не влияет на поведение персоны, оно нужно только для ориентации в списке.';
      const descriptionCounter = document.createElement('div');
      descriptionCounter.className = 'wizard-counter';
      descriptionCounter.textContent = renderCounter(draft.description, 500);
      descriptionInput.addEventListener('input', () => {
        draft.description = descriptionInput.value;
        descriptionCounter.textContent = renderCounter(draft.description, 500);
        markDirty();
      });
      fieldDescription.append(descriptionInput, descriptionHelp, descriptionCounter);
      cardEl.append(titleEl, subtitleEl, fieldName, profileRow, fieldDescription);
      return cardEl;
    };

    const buildStep2 = () => {
      const cardEl = document.createElement('section');
      cardEl.className = 'wizard-card';
      const titleEl = document.createElement('h3');
      titleEl.className = 'wizard-card-title';
      titleEl.textContent = 'Настройка внешнего вида';
      const subtitleEl = document.createElement('p');
      subtitleEl.className = 'wizard-help';
      subtitleEl.textContent = 'Настройте внешний вид персоны.';

      const rowBottom = document.createElement('div');
      rowBottom.className = 'wizard-row wizard-row-2 persona-layout-row';

      const picker = document.createElement('div');
      picker.className = 'wizard-field';
      const genderAvatars = PERSONA_AVATARS_MOCK.filter(
        (avatar) => !avatar.gender || avatar.gender === draft.avatarGender,
      );
      if (!genderAvatars.some((avatar) => avatar.id === draft.avatarId)) {
        draft.avatarId = genderAvatars[0]?.id || '';
      }
      const genderLabel = document.createElement('label');
      genderLabel.className = 'wizard-label';
      genderLabel.innerHTML = 'Пол аватара <b>*</b>';
      const genderWrap = document.createElement('div');
      genderWrap.className = 'persona-gender-toggle';
      const maleBtn = document.createElement('button');
      maleBtn.type = 'button';
      maleBtn.className = 'persona-gender-btn';
      if (draft.avatarGender === 'male') maleBtn.classList.add('is-active');
      maleBtn.textContent = '👨 Мужской';
      maleBtn.addEventListener('click', () => {
        draft.avatarGender = 'male';
        const firstMale = PERSONA_AVATARS_MOCK.find((avatar) => avatar.gender === 'male');
        if (firstMale) draft.avatarId = firstMale.id;
        markDirty();
        render();
      });
      const femaleBtn = document.createElement('button');
      femaleBtn.type = 'button';
      femaleBtn.className = 'persona-gender-btn';
      if (draft.avatarGender === 'female') femaleBtn.classList.add('is-active');
      femaleBtn.textContent = '👩 Женский';
      femaleBtn.addEventListener('click', () => {
        draft.avatarGender = 'female';
        const firstFemale = PERSONA_AVATARS_MOCK.find((avatar) => avatar.gender === 'female');
        if (firstFemale) draft.avatarId = firstFemale.id;
        markDirty();
        render();
      });
      genderWrap.append(maleBtn, femaleBtn);
      const avatarLabel = document.createElement('label');
      avatarLabel.className = 'wizard-label';
      avatarLabel.textContent = 'Выберите аватар';
      const grid = document.createElement('div');
      grid.className = 'persona-avatar-grid';
      genderAvatars.forEach((avatar) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'persona-avatar-item';
        if (draft.avatarId === avatar.id) btn.classList.add('is-active');
        if (avatar.thumbSrc) {
          const img = document.createElement('img');
          img.src = avatar.thumbSrc;
          img.alt = avatar.label;
          img.className = 'persona-avatar-item-image';
          img.addEventListener('error', () => {
            btn.innerHTML = '';
            btn.textContent = avatar.label;
          });
          btn.append(img);
        } else {
          btn.textContent = avatar.label;
        }
        btn.addEventListener('click', () => {
          draft.avatarId = avatar.id;
          markDirty();
          render();
        });
        grid.append(btn);
      });
      picker.append(genderLabel, genderWrap, avatarLabel, grid);

      const preview = document.createElement('div');
      preview.className = 'wizard-field';
      preview.innerHTML = '<label class="wizard-label">Предпросмотр аватара</label>';
      const previewBox = document.createElement('div');
      previewBox.className = 'persona-avatar-preview';
      const selectedAvatar = PERSONA_AVATARS_MOCK.find((avatar) => avatar.id === draft.avatarId);
      if (selectedAvatar?.previewSrc) {
        const previewImg = document.createElement('img');
        previewImg.src = selectedAvatar.previewSrc;
        previewImg.alt = selectedAvatar.label || 'Аватар';
        previewImg.className = 'persona-avatar-preview-image';
        previewImg.addEventListener('error', () => {
          previewBox.innerHTML = '';
          previewBox.textContent = (selectedAvatar.label || draft.name || 'П').trim()[0] || 'П';
        });
        previewBox.append(previewImg);
      } else {
        previewBox.textContent = (draft.name || 'П').trim()[0] || 'П';
      }
      preview.append(previewBox);
      rowBottom.append(picker, preview);

      cardEl.append(titleEl, subtitleEl, rowBottom);
      return cardEl;
    };

    const buildStep3 = () => {
      const cardEl = document.createElement('section');
      cardEl.className = 'wizard-card';
      const titleEl = document.createElement('h3');
      titleEl.className = 'wizard-card-title';
      titleEl.textContent = 'Поведение персоны';
      const subtitleEl = document.createElement('p');
      subtitleEl.className = 'wizard-help';
      subtitleEl.textContent =
        'Выберите способ настройки: свободный текст или структурированные параметры.';

      const modeField = document.createElement('div');
      modeField.className = 'wizard-field';
      modeField.innerHTML = '<label class="wizard-label">Способ настройки <b>*</b></label>';
      const modeWrap = document.createElement('div');
      modeWrap.className = 'persona-gender-toggle';

      const freeBtn = document.createElement('button');
      freeBtn.type = 'button';
      freeBtn.className = 'persona-gender-btn';
      if (draft.behaviorMode === 'free') freeBtn.classList.add('is-active');
      freeBtn.textContent = 'Свободный ввод';
      freeBtn.addEventListener('click', () => {
        draft.behaviorMode = 'free';
        markDirty();
        render();
      });

      const structuredBtn = document.createElement('button');
      structuredBtn.type = 'button';
      structuredBtn.className = 'persona-gender-btn';
      if (draft.behaviorMode === 'structured') structuredBtn.classList.add('is-active');
      structuredBtn.textContent = 'Выбор параметров';
      structuredBtn.addEventListener('click', () => {
        draft.behaviorMode = 'structured';
        markDirty();
        render();
      });
      modeWrap.append(freeBtn, structuredBtn);
      modeField.append(modeWrap);

      const contentField = document.createElement('div');
      contentField.className = 'wizard-field';
      if (draft.behaviorMode === 'free') {
        contentField.innerHTML = '<label class="wizard-label">Поведение персоны (свободный ввод)</label>';
        const behaviorInput = document.createElement('textarea');
        behaviorInput.className = 'wizard-textarea persona-behavior-input';
        behaviorInput.rows = 12;
        behaviorInput.value = draft.behavior;
        behaviorInput.addEventListener('input', () => {
          draft.behavior = behaviorInput.value;
          markDirty();
          const inferred = inferBehaviorStructFromText(draft.behavior);
          extractedView.value = [
            'Извлеченные параметры (предпросмотр):',
            `- Манера общения: ${inferred.behaviorStruct.communicationStyle} (${inferred.behaviorStructConfidence.communicationStyle}%)`,
            `- Скорость решений: ${inferred.behaviorStruct.decisionSpeed} (${inferred.behaviorStructConfidence.decisionSpeed}%)`,
            `- Открытость: ${inferred.behaviorStruct.openness} (${inferred.behaviorStructConfidence.openness}%)`,
            `- Реакция на давление: ${inferred.behaviorStruct.pressureReaction} (${inferred.behaviorStructConfidence.pressureReaction}%)`,
            `- Частота возражений: ${inferred.behaviorStruct.objectionLevel} (${inferred.behaviorStructConfidence.objectionLevel}%)`,
            `- Длина ответов: ${inferred.behaviorStruct.answerLength} (${inferred.behaviorStructConfidence.answerLength}%)`,
            `- Влияние эмпатии: ${inferred.behaviorStruct.empathyEffect} (${inferred.behaviorStructConfidence.empathyEffect}%)`,
          ].join('\n');
        });
        contentField.append(behaviorInput);
        const inferBtn = document.createElement('button');
        inferBtn.type = 'button';
        inferBtn.className = 'wizard-inline-btn';
        inferBtn.textContent = 'Автозаполнить параметры из текста';
        inferBtn.addEventListener('click', () => {
          const inferred = inferBehaviorStructFromText(draft.behavior);
          draft.behaviorStruct = {
            ...draft.behaviorStruct,
            ...inferred.behaviorStruct,
          };
          draft.behaviorStructConfidence = inferred.behaviorStructConfidence;
          markDirty();
          render();
        });
        const extractField = document.createElement('div');
        extractField.className = 'wizard-field';
        extractField.innerHTML =
          '<label class="wizard-label">Структурированные признаки (автоизвлечение из текста)</label>';
        const extractedView = document.createElement('textarea');
        extractedView.className = 'wizard-textarea';
        extractedView.rows = 7;
        extractedView.readOnly = true;
        const initialInferred = inferBehaviorStructFromText(draft.behavior);
        extractedView.value = [
          'Извлеченные параметры (предпросмотр):',
          `- Манера общения: ${initialInferred.behaviorStruct.communicationStyle} (${initialInferred.behaviorStructConfidence.communicationStyle}%)`,
          `- Скорость решений: ${initialInferred.behaviorStruct.decisionSpeed} (${initialInferred.behaviorStructConfidence.decisionSpeed}%)`,
          `- Открытость: ${initialInferred.behaviorStruct.openness} (${initialInferred.behaviorStructConfidence.openness}%)`,
          `- Реакция на давление: ${initialInferred.behaviorStruct.pressureReaction} (${initialInferred.behaviorStructConfidence.pressureReaction}%)`,
          `- Частота возражений: ${initialInferred.behaviorStruct.objectionLevel} (${initialInferred.behaviorStructConfidence.objectionLevel}%)`,
          `- Длина ответов: ${initialInferred.behaviorStruct.answerLength} (${initialInferred.behaviorStructConfidence.answerLength}%)`,
          `- Влияние эмпатии: ${initialInferred.behaviorStruct.empathyEffect} (${initialInferred.behaviorStructConfidence.empathyEffect}%)`,
        ].join('\n');
        extractField.append(inferBtn, extractedView);
        contentField.append(extractField);
      } else {
        contentField.innerHTML =
          '<label class="wizard-label">Параметры поведения (+дополнительное поле)</label>';
        let previewTextarea = null;
        const refreshStructuredPreview = () => {
          if (previewTextarea) {
            previewTextarea.value = composeStructuredBehavior();
          }
        };

        const makeSelectField = (label, key, options) => {
          const field = document.createElement('div');
          field.className = 'wizard-field';
          const labelEl = document.createElement('label');
          labelEl.className = 'wizard-label';
          labelEl.textContent = label;
          const select = document.createElement('select');
          select.className = 'wizard-select';
          options.forEach((opt) => {
            const el = document.createElement('option');
            el.value = opt.value;
            el.textContent = opt.label;
            if ((draft.behaviorStruct?.[key] || '') === opt.value) el.selected = true;
            select.append(el);
          });
          select.addEventListener('change', () => {
            draft.behaviorStruct[key] = select.value;
            draft.behaviorStructConfidence[key] = select.value === 'unknown' ? 0 : 100;
            markDirty();
            refreshStructuredPreview();
          });
          field.append(labelEl, select);
          return field;
        };

        const grid = document.createElement('div');
        grid.className = 'wizard-row wizard-row-2';
        grid.append(
          makeSelectField('Манера общения', 'communicationStyle', [
            { value: 'unknown', label: 'Не указано' },
            { value: 'спокойный', label: 'Спокойный' },
            { value: 'деловой', label: 'Деловой' },
            { value: 'эмоциональный', label: 'Эмоциональный' },
            { value: 'напористый', label: 'Напористый' },
          ]),
          makeSelectField('Скорость решений', 'decisionSpeed', [
            { value: 'unknown', label: 'Не указано' },
            { value: 'быстро', label: 'Быстро' },
            { value: 'средне', label: 'Средне' },
            { value: 'долго', label: 'Долго' },
          ]),
        );

        const grid2 = document.createElement('div');
        grid2.className = 'wizard-row wizard-row-2';
        grid2.append(
          makeSelectField('Открытость', 'openness', [
            { value: 'unknown', label: 'Не указано' },
            { value: 'закрытый', label: 'Закрытый' },
            { value: 'нейтральный', label: 'Нейтральный' },
            { value: 'открытый', label: 'Открытый' },
          ]),
          makeSelectField('Реакция на давление', 'pressureReaction', [
            { value: 'unknown', label: 'Не указано' },
            { value: 'резко негативная', label: 'Резко негативная' },
            { value: 'умеренная', label: 'Умеренная' },
            { value: 'терпимая', label: 'Терпимая' },
          ]),
        );

        const grid3 = document.createElement('div');
        grid3.className = 'wizard-row wizard-row-2';
        grid3.append(
          makeSelectField('Частота возражений', 'objectionLevel', [
            { value: 'unknown', label: 'Не указано' },
            { value: 'низкая', label: 'Низкая' },
            { value: 'средняя', label: 'Средняя' },
            { value: 'высокая', label: 'Высокая' },
          ]),
          makeSelectField('Длина ответов', 'answerLength', [
            { value: 'unknown', label: 'Не указано' },
            { value: 'коротко', label: 'Коротко' },
            { value: 'средне', label: 'Средне' },
            { value: 'развернуто', label: 'Развернуто' },
          ]),
        );

        const empathyRow = document.createElement('div');
        empathyRow.className = 'wizard-row wizard-row-1';
        empathyRow.append(
          makeSelectField('Влияние эмпатии', 'empathyEffect', [
            { value: 'unknown', label: 'Не указано' },
            { value: 'смягчается', label: 'Смягчается при эмпатии' },
            { value: 'нейтрально', label: 'Почти не влияет' },
            { value: 'не смягчается', label: 'Не смягчается' },
          ]),
        );

        const extraField = document.createElement('div');
        extraField.className = 'wizard-field';
        extraField.innerHTML =
          '<label class="wizard-label">Дополнительно (то, чего нет в параметрах)</label>';
        const extraInput = document.createElement('textarea');
        extraInput.className = 'wizard-textarea';
        extraInput.rows = 5;
        extraInput.maxLength = 1200;
        extraInput.value = draft.behaviorStruct.extra || '';
        extraInput.addEventListener('input', () => {
          draft.behaviorStruct.extra = extraInput.value;
          markDirty();
          refreshStructuredPreview();
        });
        extraField.append(extraInput);

        const previewField = document.createElement('div');
        previewField.className = 'wizard-field';
        previewField.innerHTML = '<label class="wizard-label">Собранный текст поведения</label>';
        const preview = document.createElement('textarea');
        preview.className = 'wizard-textarea persona-behavior-input';
        preview.rows = 8;
        preview.readOnly = true;
        previewTextarea = preview;
        refreshStructuredPreview();
        previewField.append(preview);

        contentField.append(grid, grid2, grid3, empathyRow, extraField, previewField);
      }

      cardEl.append(titleEl, subtitleEl, modeField, contentField);
      return cardEl;
    };

    const render = () => {
      headSubtitle.textContent = `Шаг ${step + 1} из 3`;
      stepper.innerHTML = '';
      PERSONA_STEP_TITLES.forEach((titleText, idx) => {
        const stepBtn = document.createElement('button');
        stepBtn.type = 'button';
        stepBtn.className = 'scenario-step';
        if (idx === step) stepBtn.classList.add('is-current');
        if (idx < step) stepBtn.classList.add('is-complete');
        stepBtn.innerHTML = `<span>${idx + 1}</span>${titleText}`;
        stepBtn.addEventListener('click', () => {
          step = idx;
          render();
        });
        stepper.append(stepBtn);
      });
      body.innerHTML = '';
      if (step === 0) body.append(buildStep1());
      if (step === 1) body.append(buildStep2());
      if (step === 2) body.append(buildStep3());
      backBtn.disabled = step === 0;
      nextBtn.textContent = step < 2 ? 'Далее →' : mode === 'edit' ? '✓ Обновить персону' : '✓ Создать персону';
      nextBtn.classList.toggle('is-success', step === 2);
    };

    modal.append(head, stepper, errors, body, footer);
    layer.append(backdrop, modal);
    document.body.append(layer);
    render();
  };

  const buildPasswordField = (name, placeholder, autocomplete) => {
    const wrap = document.createElement('div');
    wrap.className = 'password-with-toggle';

    const input = document.createElement('input');
    input.className = 'input';
    input.type = 'password';
    input.name = name;
    input.placeholder = placeholder;
    input.autocomplete = autocomplete;

    const toggle = document.createElement('button');
    toggle.className = 'password-toggle';
    toggle.type = 'button';
    toggle.setAttribute('aria-label', 'Показать пароль');

    const eyeSvg = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 5C6.5 5 2.3 8.4 1 12c1.3 3.6 5.5 7 11 7s9.7-3.4 11-7c-1.3-3.6-5.5-7-11-7Zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8Z" />
      </svg>
    `;
    const eyeOffSvg = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m3 4.3 1.4-1.4 16.3 16.3-1.4 1.4-3.1-3.1A12.4 12.4 0 0 1 12 19c-5.5 0-9.7-3.4-11-7a11.9 11.9 0 0 1 4.4-5.4L3 4.3Zm7.3 7.3 2.4 2.4a2 2 0 0 1-2.4-2.4Zm7.8 2.1-1.5-1.5c.2-.8.2-1.6 0-2.3a4.7 4.7 0 0 0-5.9-3l-1.5-1.5A12.6 12.6 0 0 1 12 5c5.5 0 9.7 3.4 11 7-.8 2.1-2.5 3.9-4.9 5.2Z" />
      </svg>
    `;

    const setIcon = (isVisible) => {
      toggle.innerHTML = isVisible ? eyeSvg : eyeOffSvg;
    };
    setIcon(false);

    toggle.addEventListener('click', () => {
      const isHidden = input.type === 'password';
      input.type = isHidden ? 'text' : 'password';
      setIcon(isHidden);
      toggle.setAttribute('aria-label', isHidden ? 'Скрыть пароль' : 'Показать пароль');
    });

    wrap.append(input, toggle);
    return { wrap, input };
  };

  const renderRegistrationSentView = () => {
    renderAuthShell('register', () => {
      prepareAuthCard();

      const notice = document.createElement('p');
      notice.className = 'registration-notice';
      notice.textContent = 'Уважаемый пользователь, на указанную почту мы отправали ссылку для регистрации. Перейдите по ней, чтобы продолжить регистрацию';
      card.append(notice);
      return card;
    });
  };

  const renderRegistrationRequestView = () => {
    renderAuthShell('register', () => {
      prepareAuthCard();

      const title = document.createElement('h1');
      title.className = 'auth-title';
      title.textContent = 'Регистрация на платформе';

      const subtitle = document.createElement('p');
      subtitle.className = 'auth-subtitle';
      subtitle.textContent = 'Введите полностью адрес корпоративной почты';

      const formGrid = document.createElement('div');
      formGrid.className = 'form-grid';

      const emailInput = document.createElement('input');
      emailInput.className = 'input';
      emailInput.type = 'email';
      emailInput.name = 'registration_email';
      emailInput.placeholder = 'Корпоративная почта';
      emailInput.autocomplete = 'email';

      const registerButton = document.createElement('button');
      registerButton.className = 'login-button';
      registerButton.type = 'button';
      registerButton.textContent = 'Зарегистрироваться';

      const message = document.createElement('div');
      message.className = 'auth-message';

      registerButton.addEventListener('click', async () => {
        const email = emailInput.value.trim();
        if (!isCorporateEmail(email)) {
          message.textContent = 'Укажите корректный email.';
          message.classList.add('error');
          return;
        }

        try {
          const resp = await fetch('/auth/register/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ email }),
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok) {
            message.textContent = data?.error || 'Не удалось отправить письмо регистрации.';
            message.classList.add('error');
            return;
          }
          renderRegistrationSentView();
        } catch (_) {
          message.textContent = 'Сервис регистрации недоступен.';
          message.classList.add('error');
        }
      });

      formGrid.append(emailInput, registerButton, message);
      card.append(title, subtitle, formGrid);
      return card;
    });
  };

  const renderSetPasswordView = (token) => {
    renderAuthShell('register', () => {
      prepareAuthCard();

      const title = document.createElement('h1');
      title.className = 'auth-title';
      title.textContent = 'Создайте пароль к учетной записи';

      const subtitle = document.createElement('p');
      subtitle.className = 'auth-subtitle';
      subtitle.textContent = 'Введите пароль (не менее 8 символов, 1 прописная буква, 1 спецсимвол, латиница)';

      const formGrid = document.createElement('div');
      formGrid.className = 'form-grid';

      const passwordField = buildPasswordField('new_password', 'Введите пароль', 'new-password');
      const repeatPasswordField = buildPasswordField('repeat_password', 'Повторите пароль', 'new-password');

      const finishButton = document.createElement('button');
      finishButton.className = 'login-button';
      finishButton.type = 'button';
      finishButton.textContent = 'Завершить регистрацию';

      const message = document.createElement('div');
      message.className = 'auth-message';

      finishButton.addEventListener('click', async () => {
        const password = passwordField.input.value;
        const passwordRepeat = repeatPasswordField.input.value;

        try {
          const resp = await fetch('/auth/register/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
              token,
              password,
              password_repeat: passwordRepeat,
            }),
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok) {
            message.textContent = data?.error || 'Не удалось завершить регистрацию.';
            message.classList.add('error');
            return;
          }
          const cleanUrl = new URL(window.location.href);
          cleanUrl.searchParams.delete('register_token');
          window.history.replaceState({}, '', cleanUrl.toString());
          renderWorkspaceView('Дэшборд');
        } catch (_) {
          message.textContent = 'Сервис регистрации недоступен.';
          message.classList.add('error');
        }
      });

      formGrid.append(passwordField.wrap, repeatPasswordField.wrap, finishButton, message);
      card.append(title, subtitle, formGrid);
      return card;
    });
  };

  const renderLoginView = () => {
    renderAuthShell('login', () => {
      return buildLoginCard();
    });
  };

  const loadSession = async () => {
    try {
      const resp = await fetch('/auth/session', { credentials: 'same-origin' });
      if (!resp.ok) return false;
      const data = await resp.json().catch(() => ({}));
      if (data?.authenticated && data?.login) {
        renderWorkspaceView('Дэшборд', data.login);
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  };

  if (registerToken) {
    renderSetPasswordView(registerToken);
  } else {
    renderLandingView();
    loadSession();
  }

  window.addEventListener('app:navigate', (event) => {
    if (!workspaceActive) return;
    const title = event?.detail?.title || 'Дэшборд';
    renderWorkspaceView(title);
  });

  return panel;
}
