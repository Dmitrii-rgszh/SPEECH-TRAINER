const STEP_TITLES = [
  "Основное",
  "Сценарий диалога",
  "Выбор персоны",
  "Возражения",
  "Успех и стоп",
  "Анализ",
];

const TAG_OPTIONS = ["Вклады", "Премиум", "Инвест", "Обучение"];
const RED_LINE_PRESETS = [
  "Не люблю давление",
  "Не хочу сложных терминов",
  "Важно иметь возможность снять деньги",
  "Не готов рисковать деньгами",
  "Хочу прозрачные условия",
];
const SUCCESS_PRESETS = [
  "Менеджер выяснил цель и срок",
  "Менеджер уточнил потребность в ликвидности",
  "Объяснил условия простыми словами",
  "Согласовал следующий шаг",
  "Дал сравнение вариантов без давления",
];
const STOP_PRESETS = [
  "Менеджер давит",
  "Менеджер обещает гарантированный доход без оснований",
  "Игнорирует вопросы клиента",
  "Уходит от темы",
];
const ANALYSIS_PRESETS = [
  { id: "deposit_sales", label: "Анализ продажи: Вклад (стандарт)" },
  { id: "consultation", label: "Анализ консультации (без продаж)" },
  { id: "none", label: "Без анализа (только краткий итог)" },
];
const ANALYSIS_FORMATS = [
  { id: "scores_comments", label: "Баллы + комментарии" },
  { id: "scores_examples", label: "Баллы + примеры фраз" },
  { id: "short_recommendations", label: "Короткий итог + 3 рекомендации" },
];
const PERSONA_LIBRARY_MOCK = [
  {
    id: "persona_kseniya",
    name: "Ксения",
    subtitle: "",
    description:
      "Средняя-высокая сложность. Быстро решает, но может оказать давление на менее опытного продавца.",
    instructions:
      "Тебя зовут Ксения, тебе 45 лет. Ты лидер, ориентированный на результат. Ценишь время и эффективность.",
  },
  {
    id: "persona_alexander",
    name: "Александр",
    subtitle: "Персона 1. Доминирующий",
    description:
      "Средняя-высокая сложность. Быстро решает, но может оказать давление на менее опытного продавца.",
    instructions:
      "Тебя зовут Александр, тебе 45 лет. Ты лидер, ориентированный на результат. Ценишь время и эффективность.",
  },
  {
    id: "persona_olga",
    name: "Ольга",
    subtitle: "Персона 5. Новичок",
    description:
      "Сложность очень низкая. Базовый уровень, подходит для первого взаимодействия с продуктом.",
    instructions:
      "Тебя зовут Ольга, тебе 25 лет. Ты открытая и дружелюбная собеседница, легко вовлекаешься в диалог.",
  },
];

const PERSONA_PRESETS = {
  influencer: {
    label: "Влияющий",
    speech_manner: "friendly_emotional",
    decision_style: "fast",
    financial_profile: "moderate",
  },
  stable: {
    label: "Стабильный",
    speech_manner: "calm",
    decision_style: "medium",
    financial_profile: "conservative",
  },
  analyst: {
    label: "Аналитик",
    speech_manner: "reserved",
    decision_style: "slow",
    financial_profile: "moderate",
  },
  skeptic: {
    label: "Скептик",
    speech_manner: "suspicious",
    decision_style: "medium",
    financial_profile: "conservative",
  },
};

const DEFAULT_SCENARIO = {
  title: "",
  context: "",
  first_speaker: "user",
  duration_minutes: 15,
  model: "qwen2.5:7b-instruct",
  knowledge_refs: {
    product_pack_id: "",
    technology_pack_id: "",
  },
  tags: ["Вклады"],
  opening_line:
    "Здравствуйте. У меня закончился вклад, хочу его переоформить.\nПодскажите, какие сейчас условия в вашем банке?",
  persona: {
    name: "",
    age: 35,
    persona_type: "influencer",
    speech_manner: "friendly_emotional",
    decision_style: "fast",
    financial_profile: "moderate",
  },
  persona_selection: {
    selected_persona_id: "persona_kseniya",
  },
  facts: {
    reason: "deposit_matured",
    reason_custom: "",
    goal: "preserve",
    goal_custom: "",
    horizon_months: 12,
    liquidity: "medium",
    amount: 300000,
    currency: "RUB",
    had_deposit_before: true,
    investment_experience: "minimal",
  },
  red_lines: [
    "Не люблю давление",
    "Не хочу сложных терминов",
    "Важно иметь возможность снять деньги",
    "Не готов рисковать деньгами",
  ],
  hidden_motivation: "",
  dialog_rules: {
    no_internet: true,
    ask_if_unknown: true,
    answer_length: "medium",
    max_questions: 2,
    mood_rules: {
      start_mood: "neutral",
      escalate_on_pressure: true,
      soften_on_empathy: true,
    },
  },
  objections: {
    pool: [
      {
        id: "obj_trust",
        name: "Недоверие",
        trigger: "non_deposit_offer",
        trigger_custom: "",
        intensity: 2,
        phrases: [
          "Я не очень доверяю таким продуктам",
          "Я уже сталкивался, не хочу рисковать",
        ],
        repeatable: false,
      },
      {
        id: "obj_simple_deposit",
        name: "Хочу просто вклад",
        trigger: "cross_sell_attempt",
        trigger_custom: "",
        intensity: 2,
        phrases: [
          "Мне бы хотелось всё-таки обычный вклад",
          "Я не уверен, что хочу что-то сложнее",
        ],
        repeatable: false,
      },
      {
        id: "obj_think",
        name: "Нужно подумать",
        trigger: "move_to_closing",
        trigger_custom: "",
        intensity: 1,
        phrases: [
          "Давайте я подумаю и позже вернусь",
          "Мне нужно обсудить это дома",
        ],
        repeatable: true,
      },
    ],
    rules: {
      max_per_call: 3,
      escalate_on_pressure: true,
      no_repeat_in_row: true,
    },
  },
  success: {
    checklist: [
      "Выяснена цель клиента",
      "Выяснен срок",
      "Объяснение без сложных терминов",
      "Согласован следующий шаг",
    ],
    threshold: 3,
    accept_phrase: "Хорошо, давайте так и сделаем.",
  },
  stop: {
    checklist: [
      "Менеджер давит",
      "Менеджер не отвечает на прямые вопросы",
    ],
    stop_phrase: "Спасибо, не надо. Давайте откроем просто вклад.",
  },
  autofinish: {
    on_success: true,
    on_stop: true,
    on_timeout: true,
    finish_message: "",
  },
  analysis: {
    preset: "deposit_sales",
    rubric: [
      { name: "Выявление потребности", weight: 4, enabled: true },
      { name: "Работа с возражениями", weight: 4, enabled: true },
      { name: "Понятность объяснения", weight: 4, enabled: true },
      { name: "Следующий шаг", weight: 3, enabled: true },
      { name: "Эмпатия", weight: 3, enabled: false },
      { name: "Структура звонка и Next Step", weight: 3, enabled: false },
    ],
    format: "scores_comments",
    language: "RU",
  },
};

const deepClone = (value) => JSON.parse(JSON.stringify(value));

const uid = (prefix = "id") => `${prefix}_${Math.random().toString(16).slice(2, 10)}`;

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const formatDateTime = (value) => {
  if (!value) return "—";
  const dt = new Date(value.replace(" ", "T") + "Z");
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("ru-RU");
};

async function api(path, options = {}) {
  const resp = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const err = new Error(data?.error || "Ошибка запроса");
    err.status = resp.status;
    err.payload = data;
    throw err;
  }
  return data;
}

function initialWizardState() {
  return {
    open: false,
    mode: "create",
    scenarioId: null,
    status: "draft",
    version: 1,
    createdAt: "",
    updatedAt: "",
    step: 1,
    data: deepClone(DEFAULT_SCENARIO),
    saving: false,
    dirty: false,
    lastError: "",
  };
}

export function mountScenariosWorkspace({ mount, newScenarioButton }) {
  const state = {
    models: [{ id: "qwen2.5:7b-instruct", label: "Qwen 2.5 7B Instruct" }],
    knowledge: {
      products: [],
      technologies: [],
    },
    list: [],
    loading: true,
    error: "",
    notice: "",
    wizard: initialWizardState(),
  };

  let beforeUnloadBound = false;

  const setNotice = (text, isError = false) => {
    state.notice = text || "";
    const bar = mount.querySelector(".scenario-notice");
    if (!bar) return;
    bar.textContent = state.notice;
    bar.classList.toggle("is-error", Boolean(isError));
  };

  const setLoading = (loading) => {
    state.loading = loading;
    renderList();
  };

  const loadModels = async () => {
    try {
      const data = await api("/scenarios/models", { method: "GET" });
      if (Array.isArray(data?.models) && data.models.length) {
        state.models = data.models.map((m) => ({
          id: String(m.id),
          label: String(m.label || m.id),
        }));
      }
    } catch (_) {
      // keep defaults
    }
  };

  const loadKnowledgeCatalog = async () => {
    try {
      const data = await api("/knowledge/catalog", { method: "GET" });
      state.knowledge.products = Array.isArray(data?.products) ? data.products : [];
      state.knowledge.technologies = Array.isArray(data?.technologies) ? data.technologies : [];
    } catch (_) {
      state.knowledge.products = [];
      state.knowledge.technologies = [];
    }
  };

  const loadScenarios = async () => {
    state.error = "";
    setLoading(true);
    try {
      const data = await api("/scenarios", { method: "GET" });
      state.list = Array.isArray(data?.items) ? data.items : [];
    } catch (error) {
      state.error = error?.message || "Не удалось загрузить сценарии";
      state.list = [];
    } finally {
      setLoading(false);
    }
  };

  const bindBeforeUnload = () => {
    if (beforeUnloadBound) return;
    beforeUnloadBound = true;
    window.addEventListener("beforeunload", handleBeforeUnload);
  };

  const unbindBeforeUnload = () => {
    if (!beforeUnloadBound) return;
    beforeUnloadBound = false;
    window.removeEventListener("beforeunload", handleBeforeUnload);
  };

  const handleBeforeUnload = (event) => {
    if (!state.wizard.open || !state.wizard.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  };

  const getStepErrors = (step, data) => {
    const errors = [];

    if (step === 1) {
      if (!data.title || data.title.trim().length < 3 || data.title.trim().length > 100) {
        errors.push("Название должно быть от 3 до 100 символов.");
      }
      if (data.first_speaker !== "user" && data.first_speaker !== "ai") {
        errors.push("Выберите, кто говорит первым.");
      }
      if (!data.model) errors.push("Выберите модель ИИ.");
      if (Number(data.duration_minutes) < 5 || Number(data.duration_minutes) > 30) {
        errors.push("Длительность должна быть в диапазоне 5..30 минут.");
      }
    }

    if (step === 2) {
      if (!data.facts?.reason) errors.push("Выберите причину обращения.");
      if (!data.facts?.goal) errors.push("Выберите цель клиента.");
      if (!Number(data.facts?.horizon_months)) errors.push("Укажите горизонт в месяцах.");
      if (!data.facts?.liquidity) errors.push("Укажите потребность в ликвидности.");
      if (!Number(data.facts?.amount) || Number(data.facts?.amount) < 10000) {
        errors.push("Сумма должна быть не меньше 10 000.");
      }
      if (!data.facts?.currency) errors.push("Выберите валюту.");
      if (!Array.isArray(data.red_lines) || data.red_lines.length < 1) {
        errors.push("Добавьте хотя бы одну красную линию.");
      }
      const opening = (data.opening_line || "").trim();
      if (opening.length < 10 || opening.length > 300) {
        errors.push("Стартовая реплика должна быть от 10 до 300 символов.");
      }
    }

    if (step === 3) {
      if (!data.persona_selection?.selected_persona_id) {
        errors.push("Выберите персону из списка.");
      }
    }

    if (step === 4) {
      const pool = Array.isArray(data.objections?.pool) ? data.objections.pool : [];
      if (pool.length < 1) {
        errors.push("Добавьте минимум одно возражение.");
      }
      pool.forEach((item, index) => {
        const phrases = Array.isArray(item?.phrases)
          ? item.phrases.filter((v) => String(v || "").trim().length > 0)
          : [];
        if (phrases.length < 2) {
          errors.push(`Возражение #${index + 1} должно иметь минимум 2 фразы.`);
        }
      });
    }

    if (step === 5) {
      const success = data.success || {};
      const stop = data.stop || {};
      const successCount = Array.isArray(success.checklist) ? success.checklist.length : 0;
      const stopCount = Array.isArray(stop.checklist) ? stop.checklist.length : 0;
      if (successCount < 3) errors.push("Для успеха нужно минимум 3 условия.");
      if (!success.accept_phrase || success.accept_phrase.trim().length < 5) {
        errors.push("Фраза согласия обязательна.");
      }
      if (
        !success.threshold ||
        Number(success.threshold) < 1 ||
        Number(success.threshold) > Math.max(1, successCount)
      ) {
        errors.push("Порог успеха должен быть в диапазоне 1..N.");
      }
      if (stopCount < 2) errors.push("Для стопа нужно минимум 2 условия.");
      if (!stop.stop_phrase || stop.stop_phrase.trim().length < 5) {
        errors.push("Стоп-фраза обязательна.");
      }
    }

    if (step === 6 && data.analysis?.preset !== "none") {
      const rubric = Array.isArray(data.analysis?.rubric) ? data.analysis.rubric : [];
      const selected = rubric.filter((item) => item?.enabled).length;
      if (selected < 3) errors.push("Для анализа нужно минимум 3 активных критерия.");
      const refs = data.knowledge_refs || {};
      if (!refs.product_pack_id || !refs.technology_pack_id) {
        errors.push("Для анализа выберите пакет продукта и пакет технологии.");
      }
    }

    return errors;
  };

  const canMoveNext = () => getStepErrors(state.wizard.step, state.wizard.data).length === 0;

  const markDirty = () => {
    if (!state.wizard.open) return;
    state.wizard.dirty = true;
  };

  const updateScenario = (updater) => {
    if (!state.wizard.open) return;
    updater(state.wizard.data);
    markDirty();
    renderWizard();
  };

  const openWizard = async ({ mode, scenarioId = null } = { mode: "create" }) => {
    setNotice("");
    await loadKnowledgeCatalog();
    state.wizard = initialWizardState();
    state.wizard.open = true;
    state.wizard.mode = mode;
    state.wizard.step = 1;
    bindBeforeUnload();

    if (mode === "edit" && scenarioId) {
      try {
        const data = await api(`/scenarios/${encodeURIComponent(scenarioId)}`, { method: "GET" });
        const item = data?.item || {};
        state.wizard.scenarioId = String(item.id || scenarioId);
        state.wizard.data = deepClone(item);
        state.wizard.status = String(item.status || "draft");
        state.wizard.version = Number(item.version || 1);
        state.wizard.createdAt = String(item.created_at || "");
        state.wizard.updatedAt = String(item.updated_at || "");
      } catch (error) {
        state.wizard.open = false;
        unbindBeforeUnload();
        setNotice(error?.message || "Не удалось загрузить сценарий", true);
        return;
      }
    } else {
      state.wizard.data = deepClone(DEFAULT_SCENARIO);
      state.wizard.scenarioId = null;
      state.wizard.status = "draft";
      state.wizard.version = 1;
    }

    renderWizard();
  };

  const closeWizard = (force = false) => {
    if (!state.wizard.open) return;
    if (!force && state.wizard.dirty) {
      const confirmed = window.confirm("Есть несохранённые изменения. Закрыть без сохранения?");
      if (!confirmed) return;
    }
    state.wizard = initialWizardState();
    unbindBeforeUnload();
    renderWizard();
  };

  const saveDraft = async ({ silent = false } = {}) => {
    if (!state.wizard.open || state.wizard.saving) return null;
    state.wizard.saving = true;
    state.wizard.lastError = "";
    renderWizard();

    try {
      let item;
      if (!state.wizard.scenarioId) {
        const resp = await api("/scenarios", {
          method: "POST",
          body: JSON.stringify({ scenario: state.wizard.data }),
        });
        item = resp?.item;
      } else {
        const resp = await api(`/scenarios/${encodeURIComponent(state.wizard.scenarioId)}`, {
          method: "PATCH",
          body: JSON.stringify({
            scenario: state.wizard.data,
            step: `step_${state.wizard.step}`,
          }),
        });
        item = resp?.item;
      }

      if (item) {
        state.wizard.scenarioId = String(item.id || state.wizard.scenarioId || "");
        state.wizard.status = String(item.status || state.wizard.status);
        state.wizard.version = Number(item.version || state.wizard.version || 1);
        state.wizard.createdAt = String(item.created_at || state.wizard.createdAt || "");
        state.wizard.updatedAt = String(item.updated_at || "");
        state.wizard.data = deepClone(item);
        state.wizard.dirty = false;
      }

      await loadScenarios();
      if (!silent) setNotice("Черновик сохранён.");
      return item || null;
    } catch (error) {
      state.wizard.lastError = error?.message || "Не удалось сохранить черновик";
      if (!silent) setNotice(state.wizard.lastError, true);
      return null;
    } finally {
      state.wizard.saving = false;
      renderWizard();
    }
  };

  const publishScenario = async () => {
    if (!state.wizard.open) return;
    const localErrors = getStepErrors(6, state.wizard.data);
    if (localErrors.length > 0) {
      state.wizard.lastError = localErrors.join(" ");
      renderWizard();
      return;
    }
    const saved = await saveDraft({ silent: true });
    if (!saved || !state.wizard.scenarioId) return;

    state.wizard.saving = true;
    renderWizard();
    try {
      const resp = await api(`/scenarios/${encodeURIComponent(state.wizard.scenarioId)}/publish`, {
        method: "POST",
      });
      state.wizard.status = String(resp?.item?.status || "active");
      state.wizard.version = Number(resp?.item?.version || state.wizard.version);
      state.wizard.data = deepClone(resp?.item || state.wizard.data);
      state.wizard.dirty = false;
      await loadScenarios();
      setNotice("Сценарий опубликован.");
      closeWizard(true);
    } catch (error) {
      const payloadErrors = Array.isArray(error?.payload?.errors) ? error.payload.errors : [];
      const mergedErrors = payloadErrors.map((v) => v?.message).filter(Boolean);
      state.wizard.lastError = mergedErrors.length
        ? mergedErrors.join(" ")
        : error?.message || "Не удалось опубликовать сценарий";
      renderWizard();
    } finally {
      state.wizard.saving = false;
      renderWizard();
    }
  };

  const publishInline = async (scenarioId) => {
    try {
      await api(`/scenarios/${encodeURIComponent(scenarioId)}/publish`, { method: "POST" });
      await loadScenarios();
      setNotice("Сценарий опубликован.");
    } catch (error) {
      setNotice(error?.message || "Не удалось опубликовать сценарий", true);
    }
  };

  const removeScenario = async (scenarioId) => {
    const ok = window.confirm("Удалить сценарий? Это действие нельзя отменить.");
    if (!ok) return;
    try {
      await api(`/scenarios/${encodeURIComponent(scenarioId)}`, { method: "DELETE" });
      await loadScenarios();
      setNotice("Сценарий удалён.");
    } catch (error) {
      setNotice(error?.message || "Не удалось удалить сценарий", true);
    }
  };

  const cloneScenario = async (scenarioId) => {
    try {
      await api(`/scenarios/${encodeURIComponent(scenarioId)}/clone`, { method: "POST" });
      await loadScenarios();
      setNotice("Сценарий клонирован.");
    } catch (error) {
      setNotice(error?.message || "Не удалось клонировать сценарий", true);
    }
  };

  const previewPromptPack = async (scenarioId) => {
    try {
      const data = await api(`/scenarios/${encodeURIComponent(scenarioId)}/prompt-pack`, {
        method: "GET",
      });
      const pack = data?.prompt_pack || {};
      const text = [
        "[system_prompt]",
        pack.system_prompt || "",
        "",
        "[scenario_prompt]",
        pack.scenario_prompt || "",
        "",
        "[runtime_state_prompt]",
        pack.runtime_state_prompt || "",
      ].join("\n");
      window.alert(text.slice(0, 8000));
    } catch (error) {
      setNotice(error?.message || "Не удалось получить prompt-pack", true);
    }
  };

  const renderList = () => {
    const wizardMarkup = mount.querySelector(".scenario-wizard-layer");
    mount.innerHTML = `
      <div class="scenarios-submenu">
        <button type="button" class="scenarios-submenu-btn is-active">Продукты</button>
        <button type="button" class="scenarios-submenu-btn">Навыки</button>
      </div>
      <div class="scenario-notice ${state.notice ? "" : "is-empty"}">${esc(state.notice)}</div>
      <div class="scenario-list-wrap"></div>
      <div class="scenario-wizard-layer"></div>
    `;

    const listWrap = mount.querySelector(".scenario-list-wrap");
    if (!listWrap) return;

    if (state.loading) {
      listWrap.innerHTML = `<div class="scenario-empty">Загрузка сценариев...</div>`;
    } else if (state.error) {
      listWrap.innerHTML = `<div class="scenario-empty is-error">${esc(state.error)}</div>`;
    } else if (!state.list.length) {
      listWrap.innerHTML = `
        <div class="scenario-empty">
          Пока нет сценариев. Нажмите «Новый сценарий», чтобы создать первый.
        </div>
      `;
    } else {
      listWrap.innerHTML = state.list
        .map(
          (item) => `
            <article class="scenario-item" data-scenario-id="${esc(item.id)}">
              <header class="scenario-item-head">
                <h3>${esc(item.title || "Без названия")}</h3>
                <div class="scenario-head-meta">
                  <span class="scenario-ver">v${Number(item.version || 1)}</span>
                  <span class="scenario-status-inline ${
                    item.status === "active" ? "is-active" : "is-draft"
                  }">${esc(item.status || "draft")}</span>
                </div>
              </header>
              <div class="scenario-item-grid">
                <div><strong>Модель:</strong> ${esc(item.model || "—")}</div>
                <div><strong>Длительность:</strong> ${Number(item.duration_minutes || 0)} мин</div>
                <div><strong>Теги:</strong> ${(Array.isArray(item.tags) ? item.tags : []).map(esc).join(", ") || "—"}</div>
                <div><strong>Обновлён:</strong> ${esc(formatDateTime(item.updated_at))}</div>
              </div>
              <div class="scenario-item-actions">
                <button type="button" data-action="start">Запустить</button>
                <button type="button" data-action="edit">Редактировать</button>
                ${
                  item.status !== "active"
                    ? `<button type="button" data-action="publish">Опубликовать</button>`
                    : ""
                }
                <button type="button" data-action="clone">Клонировать</button>
                <button type="button" data-action="prompt">Prompt-pack</button>
                <button type="button" data-action="delete" class="is-danger">Удалить</button>
              </div>
            </article>
          `
        )
        .join("");
    }

    listWrap.querySelectorAll(".scenario-item").forEach((node) => {
      const scenarioId = String(node.getAttribute("data-scenario-id") || "");
      node.querySelectorAll("button[data-action]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const action = btn.getAttribute("data-action");
          if (action === "edit") openWizard({ mode: "edit", scenarioId });
          if (action === "publish") publishInline(scenarioId);
          if (action === "delete") removeScenario(scenarioId);
          if (action === "clone") cloneScenario(scenarioId);
          if (action === "prompt") previewPromptPack(scenarioId);
          if (action === "start") {
            window.location.href = `/trainer?scenario_id=${encodeURIComponent(scenarioId)}`;
          }
        });
      });
    });

    const wizardLayer = mount.querySelector(".scenario-wizard-layer");
    if (wizardLayer && wizardMarkup && state.wizard.open) {
      wizardLayer.replaceWith(wizardMarkup);
    }
  };

  const renderStepBody = (container) => {
    if (!state.wizard.open) return;
    const step = state.wizard.step;
    if (step === 1) renderStep1(container, state, updateScenario);
    if (step === 2) renderStep2(container, state, updateScenario);
    if (step === 3) renderStep3(container, state, updateScenario);
    if (step === 4) renderStep4(container, state, updateScenario);
    if (step === 5) renderStep5(container, state, updateScenario);
    if (step === 6) renderStep6(container, state, updateScenario);
  };

  const captureFocusState = (root) => {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement)) return null;
    if (!root.contains(active)) return null;
    const tag = active.tagName;
    if (!["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return null;

    const path = [];
    let cursor = active;
    while (cursor && cursor !== root) {
      const parent = cursor.parentElement;
      if (!parent) return null;
      const index = Array.prototype.indexOf.call(parent.children, cursor);
      if (index < 0) return null;
      path.push(index);
      cursor = parent;
    }
    if (cursor !== root) return null;
    path.reverse();

    const stateOut = { path, tag, selectionStart: null, selectionEnd: null };
    if (tag === "INPUT" || tag === "TEXTAREA") {
      try {
        stateOut.selectionStart = active.selectionStart;
        stateOut.selectionEnd = active.selectionEnd;
      } catch (_) {
        stateOut.selectionStart = null;
        stateOut.selectionEnd = null;
      }
    }
    return stateOut;
  };

  const resolveByPath = (root, path) => {
    let node = root;
    for (const idx of path) {
      if (!(node instanceof HTMLElement)) return null;
      if (idx < 0 || idx >= node.children.length) return null;
      node = node.children[idx];
    }
    return node instanceof HTMLElement ? node : null;
  };

  const restoreFocusState = (root, focusState) => {
    if (!focusState) return;
    const target = resolveByPath(root, focusState.path);
    if (!(target instanceof HTMLElement)) return;
    if (!["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;

    try {
      target.focus({ preventScroll: true });
    } catch (_) {
      return;
    }

    if (
      (target.tagName === "INPUT" || target.tagName === "TEXTAREA") &&
      focusState.selectionStart !== null &&
      focusState.selectionEnd !== null
    ) {
      try {
        const len = String(target.value || "").length;
        const start = Math.max(0, Math.min(Number(focusState.selectionStart), len));
        const end = Math.max(start, Math.min(Number(focusState.selectionEnd), len));
        target.setSelectionRange(start, end);
      } catch (_) {
        // ignore selection restore errors
      }
    }
  };

  const renderWizard = () => {
    const layer = mount.querySelector(".scenario-wizard-layer");
    if (!layer) return;
    if (!state.wizard.open) {
      layer.innerHTML = "";
      return;
    }

    const focusState = captureFocusState(layer);

    const stepErrors = getStepErrors(state.wizard.step, state.wizard.data);
    const isLastStep = state.wizard.step === STEP_TITLES.length;
    layer.innerHTML = `
      <div class="scenario-wizard-backdrop"></div>
      <section class="scenario-wizard" role="dialog" aria-modal="true">
        <header class="scenario-wizard-head">
          <div>
            <h2>${
              state.wizard.mode === "edit" ? "Редактирование сценария" : "Новый сценарий"
            }</h2>
            <p>Шаг ${state.wizard.step} из ${STEP_TITLES.length}: ${STEP_TITLES[state.wizard.step - 1]}</p>
          </div>
          <button type="button" class="scenario-close-btn" aria-label="Закрыть">×</button>
        </header>
        <nav class="scenario-stepper">
          ${STEP_TITLES.map(
            (title, index) => `
              <button
                type="button"
                class="scenario-step ${index + 1 === state.wizard.step ? "is-current" : ""} ${
                  index + 1 < state.wizard.step ? "is-complete" : ""
                }"
                data-step="${index + 1}"
              >
                <span>${index + 1}</span>${esc(title)}
              </button>
            `
          ).join("")}
        </nav>
        <div class="scenario-step-errors ${
          stepErrors.length || state.wizard.lastError ? "" : "is-empty"
        }">
          ${stepErrors.length ? esc(stepErrors.join(" ")) : esc(state.wizard.lastError || "")}
        </div>
        <div class="scenario-wizard-body"></div>
        <footer class="scenario-wizard-footer">
          <button type="button" class="wizard-btn" data-action="back" ${
            state.wizard.step <= 1 ? "disabled" : ""
          }>← Назад</button>
          <button type="button" class="wizard-btn" data-action="save" ${
            state.wizard.saving ? "disabled" : ""
          }>Сохранить черновик</button>
          <button type="button" class="wizard-btn is-primary" data-action="next" ${
            !isLastStep && !canMoveNext() ? "disabled" : ""
          }>
            ${
              isLastStep
                ? state.wizard.mode === "edit"
                  ? "Обновить сценарий"
                  : "Создать сценарий"
                : "Далее →"
            }
          </button>
        </footer>
      </section>
    `;

    const body = layer.querySelector(".scenario-wizard-body");
    if (body) renderStepBody(body);

    layer.querySelector(".scenario-wizard-backdrop")?.addEventListener("click", () => closeWizard());
    layer.querySelector(".scenario-close-btn")?.addEventListener("click", () => closeWizard());

    layer.querySelectorAll(".scenario-step[data-step]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetStep = Number(btn.getAttribute("data-step") || 1);
        if (targetStep < 1 || targetStep > STEP_TITLES.length) return;
        if (targetStep > state.wizard.step && !canMoveNext()) return;
        state.wizard.step = targetStep;
        renderWizard();
      });
    });

    layer.querySelector('[data-action="back"]')?.addEventListener("click", () => {
      state.wizard.step = Math.max(1, state.wizard.step - 1);
      renderWizard();
    });
    layer.querySelector('[data-action="save"]')?.addEventListener("click", () => {
      saveDraft();
    });
    layer.querySelector('[data-action="next"]')?.addEventListener("click", async () => {
      if (isLastStep) {
        await publishScenario();
        return;
      }
      if (!canMoveNext()) return;
      state.wizard.step += 1;
      renderWizard();
    });

    restoreFocusState(layer, focusState);
  };

  newScenarioButton?.addEventListener("click", () => openWizard({ mode: "create" }));

  const init = async () => {
    renderList();
    await loadModels();
    await loadKnowledgeCatalog();
    await loadScenarios();
    renderList();
    renderWizard();
  };

  void init();

  return {
    refresh: loadScenarios,
    destroy: () => {
      unbindBeforeUnload();
    },
  };
}

function createCard(title) {
  const card = document.createElement("section");
  card.className = "wizard-card";
  const heading = document.createElement("h3");
  heading.className = "wizard-card-title";
  heading.textContent = title;
  card.append(heading);
  return card;
}

function createField(labelText, inputEl, helpText, extraClass = "") {
  const wrap = document.createElement("label");
  wrap.className = `wizard-field ${extraClass}`.trim();
  const label = document.createElement("span");
  label.className = "wizard-label";
  label.textContent = labelText;
  const help = document.createElement("span");
  help.className = "wizard-help";
  help.textContent = helpText;
  wrap.append(label, inputEl, help);
  return wrap;
}

function createInput({
  type = "text",
  value = "",
  min,
  max,
  placeholder = "",
  maxLength,
}) {
  const input = document.createElement("input");
  input.className = "wizard-input";
  input.type = type;
  input.value = value ?? "";
  if (min !== undefined) input.min = String(min);
  if (max !== undefined) input.max = String(max);
  if (placeholder) input.placeholder = placeholder;
  if (maxLength !== undefined) input.maxLength = Number(maxLength);
  return input;
}

function createTextArea({ value = "", rows = 3, maxLength = 5000, placeholder = "" }) {
  const area = document.createElement("textarea");
  area.className = "wizard-textarea";
  area.value = value ?? "";
  area.rows = rows;
  area.maxLength = maxLength;
  if (placeholder) area.placeholder = placeholder;
  return area;
}

function createSelect(options, value) {
  const select = document.createElement("select");
  select.className = "wizard-select";
  options.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(item.value);
    option.textContent = String(item.label);
    if (String(value) === String(item.value)) option.selected = true;
    select.append(option);
  });
  return select;
}

function addCounter(inputEl, maxValue) {
  const counter = document.createElement("div");
  counter.className = "wizard-counter";
  const update = () => {
    const len = String(inputEl.value || "").length;
    counter.textContent = `${len}/${maxValue}`;
  };
  inputEl.addEventListener("input", update);
  update();
  return counter;
}

function renderStep1(container, state, updateScenario) {
  const data = state.wizard.data;
  const card = createCard("Основная информация");

  const titleInput = createInput({
    type: "text",
    value: data.title || "",
    maxLength: 100,
    placeholder: "Например: Продление вклада после срока",
  });
  titleInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.title = titleInput.value;
    });
  });
  const titleField = createField(
    "Название сценария",
    titleInput,
    "Название помогает быстро находить сценарий в списке."
  );
  titleField.append(addCounter(titleInput, 100));

  const contextArea = createTextArea({
    value: data.context || "",
    rows: 6,
    maxLength: 5000,
    placeholder: "Что должен увидеть обучаемый перед началом тренировки: вводная, цель, критерии.",
  });
  contextArea.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.context = contextArea.value;
    });
  });
  const contextField = createField(
    "Контекст тренировки",
    contextArea,
    "Этот текст показывается обучаемому перед стартом и не используется как инструкция для ИИ."
  );
  contextField.append(addCounter(contextArea, 5000));

  const row = document.createElement("div");
  row.className = "wizard-row wizard-row-2";

  const durationInput = createInput({
    type: "number",
    value: data.duration_minutes ?? 15,
    min: 5,
    max: 30,
  });
  durationInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.duration_minutes = Number(durationInput.value || 15);
    });
  });
  const durationField = createField(
    "Длительность (мин)",
    durationInput,
    "Диапазон: от 5 до 30 минут."
  );

  const modelSelect = createSelect(
    state.models.map((m) => ({ value: m.id, label: m.label })),
    data.model || "qwen2.5:7b-instruct"
  );
  modelSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.model = modelSelect.value;
    });
  });
  const modelField = createField(
    "Модель ИИ",
    modelSelect,
    "Модель будет использована для роли клиента."
  );
  row.append(durationField, modelField);

  const firstSpeakerSelect = createSelect(
    [
      { value: "user", label: "Сначала говорит пользователь" },
      { value: "ai", label: "Сначала говорит ИИ-клиент" },
    ],
    data.first_speaker === "ai" ? "ai" : "user"
  );
  firstSpeakerSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.first_speaker = firstSpeakerSelect.value === "ai" ? "ai" : "user";
    });
  });
  const firstSpeakerField = createField(
    "Кто говорит первым",
    firstSpeakerSelect,
    "Определяет старт тренировки: первым приветствует либо ИИ-клиент, либо менеджер."
  );

  const tagsWrap = document.createElement("div");
  tagsWrap.className = "wizard-tags";
  TAG_OPTIONS.forEach((tag) => {
    const id = uid("tag");
    const label = document.createElement("label");
    label.className = "wizard-check";
    label.setAttribute("for", id);
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.checked = Array.isArray(data.tags) && data.tags.includes(tag);
    input.addEventListener("change", () => {
      updateScenario((draft) => {
        const current = Array.isArray(draft.tags) ? draft.tags : [];
        draft.tags = input.checked
          ? [...new Set([...current, tag])]
          : current.filter((item) => item !== tag);
      });
    });
    const text = document.createElement("span");
    text.textContent = tag;
    label.append(input, text);
    tagsWrap.append(label);
  });
  const tagsField = createField(
    "Теги сценария",
    tagsWrap,
    "Теги помогают группировать сценарии по направлениям."
  );

  card.append(titleField, contextField, row, firstSpeakerField, tagsField);
  container.innerHTML = "";
  container.append(card);
}

function renderStep2(container, state, updateScenario) {
  const data = state.wizard.data;
  const refs = data.knowledge_refs || {};
  const facts = data.facts || {};
  const redLines = Array.isArray(data.red_lines) ? data.red_lines : [];
  const rules = data.dialog_rules || {};
  const mood = rules.mood_rules || {};

  container.innerHTML = "";

  const knowledgeCard = createCard("Знания продукта и технологии");
  const knowledgeRow = document.createElement("div");
  knowledgeRow.className = "wizard-row wizard-row-2";
  const productOptions = [
    { value: "", label: "Не выбран" },
    ...(Array.isArray(state.knowledge.products)
      ? state.knowledge.products.map((item) => ({
          value: String(item.pack_id || ""),
          label: String(item.name || item.pack_id || "Пакет продукта"),
        }))
      : []),
  ];
  const productSelect = createSelect(productOptions, refs.product_pack_id || "");
  productSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.knowledge_refs = draft.knowledge_refs || {};
      draft.knowledge_refs.product_pack_id = productSelect.value;
    });
  });
  knowledgeRow.append(
    createField(
      "Пакет продукта",
      productSelect,
      "Используется в анализе встречи для проверки знания продукта."
    )
  );

  const techOptions = [
    { value: "", label: "Не выбран" },
    ...(Array.isArray(state.knowledge.technologies)
      ? state.knowledge.technologies.map((item) => ({
          value: String(item.pack_id || ""),
          label: String(item.name || item.pack_id || "Пакет технологии"),
        }))
      : []),
  ];
  const techSelect = createSelect(techOptions, refs.technology_pack_id || "");
  techSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.knowledge_refs = draft.knowledge_refs || {};
      draft.knowledge_refs.technology_pack_id = techSelect.value;
    });
  });
  knowledgeRow.append(
    createField(
      "Пакет технологии продаж",
      techSelect,
      "Используется в анализе встречи для проверки соблюдения технологии."
    )
  );
  knowledgeCard.append(knowledgeRow);
  container.append(knowledgeCard);

  const contextCard = createCard("Контекст и цель");
  const contextRowTop = document.createElement("div");
  contextRowTop.className = "wizard-row wizard-row-2";
  const reasonSelect = createSelect(
    [
      { value: "deposit_matured", label: "Закончился вклад, хочу переоформить" },
      { value: "large_sum", label: "Появилась крупная сумма" },
      { value: "safety_cushion", label: "Хочу подушку безопасности" },
      { value: "compare_banks", label: "Сравниваю банки" },
      { value: "recommended", label: "Друг посоветовал" },
      { value: "custom", label: "Своя опция" },
    ],
    facts.reason || "deposit_matured"
  );
  reasonSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.facts.reason = reasonSelect.value;
    });
  });
  const reasonField = createField(
    "Причина обращения",
    reasonSelect,
    "Контекст обращения запускает правильную легенду клиента."
  );
  contextRowTop.append(reasonField);

  const goalSelect = createSelect(
    [
      { value: "preserve", label: "Сохранить" },
      { value: "accumulate", label: "Накопить" },
      { value: "yield", label: "Доходность" },
      { value: "liquidity", label: "Ликвидность" },
      { value: "target_date", label: "К определённому сроку" },
      { value: "custom", label: "Своя опция" },
    ],
    facts.goal || "preserve"
  );
  goalSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.facts.goal = goalSelect.value;
    });
  });
  contextRowTop.append(
    createField("Цель клиента", goalSelect, "Определяет фокус вопросов и согласия клиента.")
  );

  const contextRowCustom = document.createElement("div");
  contextRowCustom.className = "wizard-row wizard-row-2";
  const reasonCustom = createInput({
    type: "text",
    value: facts.reason_custom || "",
    maxLength: 200,
    placeholder: "Своя причина обращения",
  });
  reasonCustom.disabled = reasonSelect.value !== "custom";
  reasonCustom.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.facts.reason_custom = reasonCustom.value;
    });
  });
  contextRowCustom.append(
    createField("Своя причина", reasonCustom, "Заполняется, если выбран пункт «Своя опция».")
  );
  const goalCustom = createInput({
    type: "text",
    value: facts.goal_custom || "",
    maxLength: 200,
    placeholder: "Своя цель клиента",
  });
  goalCustom.disabled = goalSelect.value !== "custom";
  goalCustom.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.facts.goal_custom = goalCustom.value;
    });
  });
  contextRowCustom.append(
    createField("Своя цель", goalCustom, "Заполняется, если выбран пункт «Своя опция».")
  );

  const contextRowBottom = document.createElement("div");
  contextRowBottom.className = "wizard-row wizard-row-2";

  const horizonInput = createInput({
    type: "number",
    value: facts.horizon_months ?? 12,
    min: 1,
    max: 60,
  });
  horizonInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.facts.horizon_months = Number(horizonInput.value || 12);
    });
  });
  contextRowBottom.append(
    createField("Горизонт (мес)", horizonInput, "Срок цели клиента: от 1 до 60 месяцев.")
  );

  const liquiditySelect = createSelect(
    [
      { value: "high", label: "Высокая" },
      { value: "medium", label: "Средняя" },
      { value: "low", label: "Низкая" },
    ],
    facts.liquidity || "medium"
  );
  liquiditySelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.facts.liquidity = liquiditySelect.value;
    });
  });
  contextRowBottom.append(
    createField(
      "Нужна ли ликвидность",
      liquiditySelect,
      "Ликвидность влияет на приемлемость сроков и условий."
    )
  );

  contextCard.append(contextRowTop, contextRowCustom, contextRowBottom);
  container.append(contextCard);

  const amountCard = createCard("Сумма и опыт");
  const amountRowTop = document.createElement("div");
  amountRowTop.className = "wizard-row wizard-row-2";
  const amountInput = createInput({
    type: "number",
    value: facts.amount ?? 300000,
    min: 10000,
  });
  amountInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.facts.amount = Number(amountInput.value || 10000);
    });
  });
  amountRowTop.append(createField("Сумма", amountInput, "Минимум 10 000."));

  const currencySelect = createSelect(
    [
      { value: "RUB", label: "RUB" },
      { value: "USD", label: "USD" },
      { value: "EUR", label: "EUR" },
    ],
    facts.currency || "RUB"
  );
  currencySelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.facts.currency = currencySelect.value;
    });
  });
  amountRowTop.append(createField("Валюта", currencySelect, "Валюта суммы клиента."));

  const amountRowBottom = document.createElement("div");
  amountRowBottom.className = "wizard-row wizard-row-2";
  const hadDepositSelect = createSelect(
    [
      { value: "true", label: "Да" },
      { value: "false", label: "Нет" },
    ],
    String(Boolean(facts.had_deposit_before))
  );
  hadDepositSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.facts.had_deposit_before = hadDepositSelect.value === "true";
    });
  });
  amountRowBottom.append(
    createField("Был вклад ранее?", hadDepositSelect, "Опыт влияет на доверие и ожидания.")
  );

  const expSelect = createSelect(
    [
      { value: "none", label: "Нет" },
      { value: "minimal", label: "Минимальный" },
      { value: "has", label: "Есть" },
    ],
    facts.investment_experience || "minimal"
  );
  expSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.facts.investment_experience = expSelect.value;
    });
  });
  amountRowBottom.append(
    createField("Опыт инвестиций", expSelect, "Определяет готовность к сложным продуктам.")
  );

  amountCard.append(amountRowTop, amountRowBottom);
  container.append(amountCard);

  const redCard = createCard("Красные линии");
  const presetWrap = document.createElement("div");
  presetWrap.className = "wizard-check-grid";
  RED_LINE_PRESETS.forEach((line) => {
    const id = uid("red");
    const label = document.createElement("label");
    label.className = "wizard-check";
    label.setAttribute("for", id);
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = id;
    checkbox.checked = redLines.includes(line);
    checkbox.addEventListener("change", () => {
      updateScenario((draft) => {
        const current = Array.isArray(draft.red_lines) ? draft.red_lines : [];
        draft.red_lines = checkbox.checked
          ? [...new Set([...current, line])]
          : current.filter((item) => item !== line);
      });
    });
    const text = document.createElement("span");
    text.textContent = line;
    label.append(checkbox, text);
    presetWrap.append(label);
  });
  redCard.append(
    createField("Базовые красные линии", presetWrap, "Это условия, при которых клиент раздражается.")
  );

  const customRow = document.createElement("div");
  customRow.className = "wizard-row wizard-row-add";
  const customInput = createInput({
    type: "text",
    value: "",
    maxLength: 200,
    placeholder: "Добавить свою красную линию",
  });
  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "wizard-inline-btn";
  addBtn.textContent = "+ Добавить";
  addBtn.addEventListener("click", () => {
    const value = customInput.value.trim();
    if (!value) return;
    updateScenario((draft) => {
      const current = Array.isArray(draft.red_lines) ? draft.red_lines : [];
      draft.red_lines = [...new Set([...current, value])];
    });
  });
  customRow.append(customInput, addBtn);
  redCard.append(createField("Свой вариант", customRow, "Можно добавлять уникальные ограничения."));

  const customList = document.createElement("div");
  customList.className = "wizard-chip-list";
  redLines
    .filter((item) => !RED_LINE_PRESETS.includes(item))
    .forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "wizard-chip";
      chip.innerHTML = `${esc(item)} <button type="button">×</button>`;
      chip.querySelector("button")?.addEventListener("click", () => {
        updateScenario((draft) => {
          draft.red_lines = (draft.red_lines || []).filter((v) => v !== item);
        });
      });
      customList.append(chip);
    });
  redCard.append(customList);

  const hiddenArea = createTextArea({
    value: data.hidden_motivation || "",
    rows: 4,
    maxLength: 500,
    placeholder: "Например: был негативный опыт, семья против рисков.",
  });
  hiddenArea.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.hidden_motivation = hiddenArea.value;
    });
  });
  const hiddenField = createField(
    "Скрытая мотивация",
    hiddenArea,
    "Скрытая причина помогает сделать реакцию клиента более живой."
  );
  hiddenField.append(addCounter(hiddenArea, 500));
  redCard.append(hiddenField);
  container.append(redCard);

  const startCard = createCard("Старт разговора");
  const openingArea = createTextArea({
    value: data.opening_line || "",
    rows: 6,
    maxLength: 300,
  });
  openingArea.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.opening_line = openingArea.value;
    });
  });
  const openingField = createField(
    "Стартовая реплика клиента",
    openingArea,
    "Это первая фраза, с которой клиент начинает разговор."
  );
  openingField.append(addCounter(openingArea, 300));
  startCard.append(openingField);
  container.append(startCard);

  const rulesCard = createCard("Поведение клиента");
  const noInternetWrap = document.createElement("label");
  noInternetWrap.className = "wizard-check";
  const noInternetInput = document.createElement("input");
  noInternetInput.type = "checkbox";
  noInternetInput.checked = true;
  noInternetInput.disabled = true;
  noInternetWrap.append(noInternetInput, document.createTextNode("Не использует интернет (всегда включено)"));
  rulesCard.append(createField("Ограничение источников", noInternetWrap, "Жёсткое ограничение для роли клиента."));

  const noFactsWrap = document.createElement("label");
  noFactsWrap.className = "wizard-check";
  const noFactsInput = document.createElement("input");
  noFactsInput.type = "checkbox";
  noFactsInput.checked = Boolean(rules.ask_if_unknown ?? true);
  noFactsInput.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.dialog_rules.ask_if_unknown = noFactsInput.checked;
    });
  });
  noFactsWrap.append(
    noFactsInput,
    document.createTextNode("Если нет данных в легенде — не выдумывать факты")
  );
  rulesCard.append(createField("Контроль галлюцинаций", noFactsWrap, "Клиент запрашивает уточнение у менеджера."));

  const row = document.createElement("div");
  row.className = "wizard-row wizard-row-2";
  const lenSelect = createSelect(
    [
      { value: "short", label: "Коротко (1-2 предложения)" },
      { value: "medium", label: "Средне (2-4 предложения)" },
      { value: "long", label: "Развернуто (до 6 предложений)" },
    ],
    rules.answer_length || "medium"
  );
  lenSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.dialog_rules.answer_length = lenSelect.value;
    });
  });
  row.append(
    createField("Длина ответа", lenSelect, "Ограничение помогает удерживать темп диалога.")
  );

  const qSelect = createSelect(
    [
      { value: 0, label: "0" },
      { value: 1, label: "1" },
      { value: 2, label: "2" },
    ],
    Number(rules.max_questions ?? 2)
  );
  qSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.dialog_rules.max_questions = Number(qSelect.value);
    });
  });
  row.append(
    createField(
      "Количество вопросов в реплике",
      qSelect,
      "Ограничение сверху: не более 2 вопросов."
    )
  );
  rulesCard.append(row);
  container.append(rulesCard);

  const moodCard = createCard("Динамика настроения");
  const moodRowTop = document.createElement("div");
  moodRowTop.className = "wizard-row wizard-row-1";
  const moodSelect = createSelect(
    [
      { value: "neutral", label: "Нейтральное" },
      { value: "friendly", label: "Дружелюбное" },
      { value: "cautious", label: "Настороженное" },
      { value: "irritated", label: "Раздражённое" },
    ],
    mood.start_mood || "neutral"
  );
  moodSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.dialog_rules.mood_rules.start_mood = moodSelect.value;
    });
  });
  moodRowTop.append(
    createField("Стартовое настроение", moodSelect, "Начальное состояние клиента в начале звонка.")
  );
  moodCard.append(moodRowTop);

  const flags = document.createElement("div");
  flags.className = "wizard-check-grid";
  const escalateLabel = document.createElement("label");
  escalateLabel.className = "wizard-check";
  const escalateInput = document.createElement("input");
  escalateInput.type = "checkbox";
  escalateInput.checked = Boolean(mood.escalate_on_pressure ?? true);
  escalateInput.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.dialog_rules.mood_rules.escalate_on_pressure = escalateInput.checked;
    });
  });
  escalateLabel.append(escalateInput, document.createTextNode("Усиливать раздражение при давлении"));
  flags.append(escalateLabel);

  const softenLabel = document.createElement("label");
  softenLabel.className = "wizard-check";
  const softenInput = document.createElement("input");
  softenInput.type = "checkbox";
  softenInput.checked = Boolean(mood.soften_on_empathy ?? true);
  softenInput.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.dialog_rules.mood_rules.soften_on_empathy = softenInput.checked;
    });
  });
  softenLabel.append(softenInput, document.createTextNode("Смягчаться при эмпатии"));
  flags.append(softenLabel);

  moodCard.append(createField("Поведенческие флаги", flags, "Регулируют эскалацию в ходе диалога."));
  container.append(moodCard);
}

function renderStep3(container, state, updateScenario) {
  const data = state.wizard.data;
  const selectedId = data.persona_selection?.selected_persona_id || "";
  container.innerHTML = "";

  const personaCard = createCard("Выбор персоны");
  const head = document.createElement("div");
  head.className = "wizard-persona-library-head";
  head.innerHTML = `
    <span>Доступные персоны <b>*</b></span>
    <span class="wizard-persona-selected">Выбрано: ${selectedId ? 1 : 0}</span>
  `;
  personaCard.append(head);

  const list = document.createElement("div");
  list.className = "wizard-persona-library-list";
  PERSONA_LIBRARY_MOCK.forEach((item) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `wizard-persona-library-item ${selectedId === item.id ? "is-active" : ""}`;
    const title = item.subtitle ? `${item.name} - ${item.subtitle}` : item.name;
    const initials = item.name.slice(0, 1).toUpperCase();
    card.innerHTML = `
      <span class="wizard-persona-avatar">${esc(initials)}</span>
      <span class="wizard-persona-content">
        <span class="wizard-persona-name">${esc(title)}</span>
        <span class="wizard-persona-meta"><b>Описание:</b> ${esc(item.description)}</span>
        <span class="wizard-persona-meta"><b>Инструкция:</b> ${esc(item.instructions)}</span>
      </span>
    `;
    card.addEventListener("click", () => {
      updateScenario((draft) => {
        draft.persona_selection = draft.persona_selection || {};
        draft.persona_selection.selected_persona_id = item.id;
      });
    });
    list.append(card);
  });
  personaCard.append(list);
  const note = document.createElement("p");
  note.className = "wizard-persona-note";
  note.textContent =
    "Пока это мок-список. Параметры персоны сохранены и будут вынесены на страницу «Персона».";
  personaCard.append(note);
  container.append(personaCard);
}

function newObjectionDraft() {
  return {
    id: uid("obj"),
    name: "",
    trigger: "cross_sell_attempt",
    trigger_custom: "",
    intensity: 2,
    phrases: ["", ""],
    repeatable: false,
  };
}

function openObjectionModal(initial, onSave) {
  const draft = initial ? deepClone(initial) : newObjectionDraft();
  const backdrop = document.createElement("div");
  backdrop.className = "scenario-modal-backdrop";
  backdrop.innerHTML = `
    <section class="scenario-modal" role="dialog" aria-modal="true">
      <header class="scenario-modal-head">
        <h3>${initial ? "Редактировать возражение" : "Добавить возражение"}</h3>
        <button type="button" class="scenario-modal-close">×</button>
      </header>
      <div class="scenario-modal-body"></div>
      <footer class="scenario-modal-footer">
        <button type="button" data-action="cancel">Отмена</button>
        <button type="button" data-action="save" class="is-primary">Сохранить</button>
      </footer>
    </section>
  `;
  document.body.append(backdrop);

  const close = () => backdrop.remove();
  backdrop.querySelector(".scenario-modal-close")?.addEventListener("click", close);
  backdrop.querySelector('[data-action="cancel"]')?.addEventListener("click", close);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) close();
  });

  const body = backdrop.querySelector(".scenario-modal-body");
  if (!body) return;
  body.innerHTML = `
    <label class="wizard-field">
      <span class="wizard-label">Название</span>
      <input class="wizard-input" data-field="name" maxlength="120" />
      <span class="wizard-help">Короткое название возражения.</span>
    </label>
    <label class="wizard-field">
      <span class="wizard-label">Триггер</span>
      <select class="wizard-select" data-field="trigger">
        <option value="non_deposit_offer">При предложении не вклада</option>
        <option value="cross_sell_attempt">При попытке кросс-сейла</option>
        <option value="too_many_questions">Когда менеджер задаёт слишком много вопросов</option>
        <option value="investment_terms">Когда звучат термины инвестиции/страхование</option>
        <option value="no_direct_answer">Когда нет ответа на прямой вопрос</option>
        <option value="move_to_closing">При переходе к оформлению</option>
        <option value="custom">Свой триггер</option>
      </select>
      <span class="wizard-help">Когда именно срабатывает возражение.</span>
    </label>
    <label class="wizard-field">
      <span class="wizard-label">Свой триггер</span>
      <input class="wizard-input" data-field="trigger_custom" maxlength="200" />
      <span class="wizard-help">Используется только если выбран «Свой триггер».</span>
    </label>
    <label class="wizard-field">
      <span class="wizard-label">Интенсивность (1-3)</span>
      <input class="wizard-input" data-field="intensity" type="number" min="1" max="3" />
      <span class="wizard-help">1 — мягко, 3 — резко.</span>
    </label>
    <div class="wizard-field">
      <span class="wizard-label">Фразы</span>
      <div class="objection-phrases"></div>
      <span class="wizard-help">Минимум две фразы на каждое возражение.</span>
    </div>
    <label class="wizard-check">
      <input type="checkbox" data-field="repeatable" />
      <span>Можно повторять</span>
    </label>
    <div class="scenario-modal-error is-empty"></div>
  `;

  const nameInput = body.querySelector('[data-field="name"]');
  const triggerInput = body.querySelector('[data-field="trigger"]');
  const triggerCustomInput = body.querySelector('[data-field="trigger_custom"]');
  const intensityInput = body.querySelector('[data-field="intensity"]');
  const repeatInput = body.querySelector('[data-field="repeatable"]');
  const phrasesWrap = body.querySelector(".objection-phrases");
  const errorEl = body.querySelector(".scenario-modal-error");

  const renderPhrases = () => {
    if (!phrasesWrap) return;
    phrasesWrap.innerHTML = "";
    draft.phrases.forEach((phrase, index) => {
      const row = document.createElement("div");
      row.className = "objection-phrase-row";
      const input = createInput({
        type: "text",
        value: phrase || "",
        maxLength: 220,
        placeholder: `Фраза ${index + 1}`,
      });
      input.addEventListener("input", () => {
        draft.phrases[index] = input.value;
      });
      row.append(input);
      if (draft.phrases.length > 2) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "wizard-inline-btn is-danger";
        remove.textContent = "Удалить";
        remove.addEventListener("click", () => {
          draft.phrases.splice(index, 1);
          renderPhrases();
        });
        row.append(remove);
      }
      phrasesWrap.append(row);
    });
    const add = document.createElement("button");
    add.type = "button";
    add.className = "wizard-inline-btn";
    add.textContent = "+ Ещё фраза";
    add.addEventListener("click", () => {
      draft.phrases.push("");
      renderPhrases();
    });
    phrasesWrap.append(add);
  };

  if (nameInput) nameInput.value = draft.name || "";
  if (triggerInput) triggerInput.value = draft.trigger || "cross_sell_attempt";
  if (triggerCustomInput) triggerCustomInput.value = draft.trigger_custom || "";
  if (intensityInput) intensityInput.value = String(draft.intensity || 2);
  if (repeatInput) repeatInput.checked = Boolean(draft.repeatable);

  renderPhrases();

  const applyFromFields = () => {
    draft.name = String(nameInput?.value || "").trim();
    draft.trigger = String(triggerInput?.value || "cross_sell_attempt");
    draft.trigger_custom = String(triggerCustomInput?.value || "").trim();
    draft.intensity = Math.max(1, Math.min(3, Number(intensityInput?.value || 2)));
    draft.repeatable = Boolean(repeatInput?.checked);
    draft.phrases = (draft.phrases || []).map((v) => String(v || "").trim());
  };

  backdrop.querySelector('[data-action="save"]')?.addEventListener("click", () => {
    applyFromFields();
    const phrases = draft.phrases.filter((v) => v.length > 0);
    if (!draft.name) {
      if (errorEl) {
        errorEl.textContent = "Заполните название возражения.";
        errorEl.classList.remove("is-empty");
      }
      return;
    }
    if (!draft.trigger) {
      if (errorEl) {
        errorEl.textContent = "Выберите триггер.";
        errorEl.classList.remove("is-empty");
      }
      return;
    }
    if (draft.trigger === "custom" && !draft.trigger_custom) {
      if (errorEl) {
        errorEl.textContent = "Укажите свой триггер.";
        errorEl.classList.remove("is-empty");
      }
      return;
    }
    if (phrases.length < 2) {
      if (errorEl) {
        errorEl.textContent = "Добавьте минимум две фразы.";
        errorEl.classList.remove("is-empty");
      }
      return;
    }
    draft.phrases = phrases;
    onSave?.(draft);
    close();
  });
}

function renderStep4(container, state, updateScenario) {
  const data = state.wizard.data;
  const objections = data.objections || {};
  const pool = Array.isArray(objections.pool) ? objections.pool : [];
  const rules = objections.rules || {};
  container.innerHTML = "";

  const objectionsCard = createCard("Возражения клиента");
  const table = document.createElement("div");
  table.className = "wizard-table";
  const head = document.createElement("div");
  head.className = "wizard-table-row wizard-table-head";
  head.innerHTML = `
    <div>Название</div>
    <div>Триггер</div>
    <div>Инт.</div>
    <div>Фраз</div>
    <div>Повторять</div>
    <div></div>
  `;
  table.append(head);

  pool.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "wizard-table-row";
    row.innerHTML = `
      <div>${esc(item.name || "—")}</div>
      <div>${esc(item.trigger_custom || item.trigger || "—")}</div>
      <div>${Number(item.intensity || 1)}</div>
      <div>${Array.isArray(item.phrases) ? item.phrases.length : 0}</div>
      <div>${item.repeatable ? "Да" : "Нет"}</div>
      <div class="wizard-table-actions"></div>
    `;
    const actions = row.querySelector(".wizard-table-actions");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => {
      openObjectionModal(item, (saved) => {
        updateScenario((draft) => {
          draft.objections.pool[index] = saved;
        });
      });
    });
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Удалить";
    deleteBtn.className = "is-danger";
    deleteBtn.addEventListener("click", () => {
      updateScenario((draft) => {
        draft.objections.pool = draft.objections.pool.filter((_, i) => i !== index);
      });
    });
    actions?.append(editBtn, deleteBtn);
    table.append(row);
  });
  objectionsCard.append(table);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "wizard-inline-btn";
  addBtn.textContent = "+ Добавить возражение";
  addBtn.addEventListener("click", () => {
    openObjectionModal(null, (saved) => {
      updateScenario((draft) => {
        const current = Array.isArray(draft.objections.pool) ? draft.objections.pool : [];
        draft.objections.pool = [...current, saved];
      });
    });
  });
  objectionsCard.append(addBtn);
  container.append(objectionsCard);

  const rulesCard = createCard("Правила выдачи возражений");
  const row = document.createElement("div");
  row.className = "wizard-row wizard-row-1";
  const maxInput = createInput({
    type: "number",
    value: Number(rules.max_per_call ?? 3),
    min: 1,
    max: 6,
  });
  maxInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.objections.rules.max_per_call = Number(maxInput.value || 3);
    });
  });
  row.append(
    createField(
      "Максимум возражений за звонок",
      maxInput,
      "Ограничение на количество срабатываний возражений."
    )
  );
  rulesCard.append(row);

  const checks = document.createElement("div");
  checks.className = "wizard-check-grid";
  const escalate = document.createElement("label");
  escalate.className = "wizard-check";
  const escalateInput = document.createElement("input");
  escalateInput.type = "checkbox";
  escalateInput.checked = Boolean(rules.escalate_on_pressure ?? true);
  escalateInput.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.objections.rules.escalate_on_pressure = escalateInput.checked;
    });
  });
  escalate.append(escalateInput, document.createTextNode("Эскалация при давлении"));
  checks.append(escalate);

  const noRepeat = document.createElement("label");
  noRepeat.className = "wizard-check";
  const noRepeatInput = document.createElement("input");
  noRepeatInput.type = "checkbox";
  noRepeatInput.checked = Boolean(rules.no_repeat_in_row ?? true);
  noRepeatInput.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.objections.rules.no_repeat_in_row = noRepeatInput.checked;
    });
  });
  noRepeat.append(noRepeatInput, document.createTextNode("Не повторять одно и то же подряд"));
  checks.append(noRepeat);
  rulesCard.append(createField("Флаги", checks, "Параметры, ограничивающие повторяемость."));

  container.append(rulesCard);
}

function renderChecklistEditor({
  title,
  presets,
  current,
  onChange,
  customPlaceholder,
  helpText,
}) {
  const card = createCard(title);

  const checks = document.createElement("div");
  checks.className = "wizard-check-grid";
  presets.forEach((item) => {
    const id = uid("chk");
    const label = document.createElement("label");
    label.className = "wizard-check";
    label.setAttribute("for", id);
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.checked = current.includes(item);
    input.addEventListener("change", () => {
      const next = input.checked
        ? [...new Set([...current, item])]
        : current.filter((v) => v !== item);
      onChange(next);
    });
    label.append(input, document.createTextNode(item));
    checks.append(label);
  });
  card.append(createField("Базовые пункты", checks, helpText));

  const customRow = document.createElement("div");
  customRow.className = "wizard-row wizard-row-add";
  const input = createInput({
    type: "text",
    value: "",
    maxLength: 160,
    placeholder: customPlaceholder,
  });
  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "wizard-inline-btn";
  addBtn.textContent = "+ Добавить";
  addBtn.addEventListener("click", () => {
    const value = input.value.trim();
    if (!value) return;
    onChange([...new Set([...current, value])]);
  });
  customRow.append(input, addBtn);
  card.append(createField("Свой пункт", customRow, "Можно расширить чек-лист под бизнес-задачу."));

  const customItems = current.filter((item) => !presets.includes(item));
  if (customItems.length) {
    const chips = document.createElement("div");
    chips.className = "wizard-chip-list";
    customItems.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "wizard-chip";
      chip.innerHTML = `${esc(item)} <button type="button">×</button>`;
      chip.querySelector("button")?.addEventListener("click", () => {
        onChange(current.filter((v) => v !== item));
      });
      chips.append(chip);
    });
    card.append(chips);
  }

  return card;
}

function renderStep5(container, state, updateScenario) {
  const data = state.wizard.data;
  const success = data.success || {};
  const stop = data.stop || {};
  const autofinish = data.autofinish || {};
  container.innerHTML = "";

  const successItems = Array.isArray(success.checklist) ? success.checklist : [];
  const successCard = renderChecklistEditor({
    title: "Когда клиент соглашается",
    presets: SUCCESS_PRESETS,
    current: successItems,
    onChange: (items) => {
      updateScenario((draft) => {
        draft.success.checklist = items;
        const maxThreshold = Math.max(1, items.length);
        if (Number(draft.success.threshold || 1) > maxThreshold) {
          draft.success.threshold = maxThreshold;
        }
      });
    },
    customPlaceholder: "Добавить условие успеха",
    helpText: "Минимум 3 условия для публикации сценария.",
  });

  const successRow = document.createElement("div");
  successRow.className = "wizard-row wizard-row-2";
  const thresholdInput = createInput({
    type: "number",
    value: Number(success.threshold || 1),
    min: 1,
    max: Math.max(1, successItems.length),
  });
  thresholdInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.success.threshold = Number(thresholdInput.value || 1);
    });
  });
  successRow.append(
    createField(
      "Порог успеха",
      thresholdInput,
      "Сколько условий из чек-листа нужно закрыть для согласия."
    )
  );

  const acceptInput = createInput({
    type: "text",
    value: success.accept_phrase || "",
    maxLength: 200,
    placeholder: "Хорошо, давайте так и сделаем.",
  });
  acceptInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.success.accept_phrase = acceptInput.value;
    });
  });
  successRow.append(
    createField(
      "Фраза согласия",
      acceptInput,
      "Фраза, которой клиент завершает успешный сценарий."
    )
  );
  successCard.append(successRow);
  container.append(successCard);

  const stopItems = Array.isArray(stop.checklist) ? stop.checklist : [];
  const stopCard = renderChecklistEditor({
    title: "Когда клиент останавливает продажу",
    presets: STOP_PRESETS,
    current: stopItems,
    onChange: (items) => {
      updateScenario((draft) => {
        draft.stop.checklist = items;
      });
    },
    customPlaceholder: "Добавить стоп-условие",
    helpText: "Минимум 2 стоп-условия для публикации сценария.",
  });

  const stopPhraseInput = createInput({
    type: "text",
    value: stop.stop_phrase || "",
    maxLength: 200,
    placeholder: "Спасибо, не надо. Давайте откроем просто вклад.",
  });
  stopPhraseInput.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.stop.stop_phrase = stopPhraseInput.value;
    });
  });
  stopCard.append(
    createField(
      "Стоп-фраза",
      stopPhraseInput,
      "Фраза, которую клиент произносит при завершении продажи."
    )
  );
  container.append(stopCard);

  const finishCard = createCard("Автозавершение");
  const flags = document.createElement("div");
  flags.className = "wizard-check-grid";
  [
    { key: "on_success", label: "при успехе" },
    { key: "on_stop", label: "при стопе" },
    { key: "on_timeout", label: "по таймеру" },
  ].forEach((item) => {
    const id = uid("finish");
    const label = document.createElement("label");
    label.className = "wizard-check";
    label.setAttribute("for", id);
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.checked = Boolean(autofinish[item.key]);
    input.addEventListener("change", () => {
      updateScenario((draft) => {
        draft.autofinish[item.key] = input.checked;
      });
    });
    label.append(input, document.createTextNode(item.label));
    flags.append(label);
  });
  finishCard.append(createField("Когда завершать звонок", flags, "Логика автозавершения сценария."));

  const finishMessage = createTextArea({
    value: autofinish.finish_message || "",
    rows: 3,
    maxLength: 240,
    placeholder: "Сообщение, которое увидит менеджер при завершении.",
  });
  finishMessage.addEventListener("input", () => {
    updateScenario((draft) => {
      draft.autofinish.finish_message = finishMessage.value;
    });
  });
  const finishField = createField(
    "Сообщение при завершении",
    finishMessage,
    "Необязательный текст после автоматического завершения."
  );
  finishField.append(addCounter(finishMessage, 240));
  finishCard.append(finishField);
  container.append(finishCard);
}

function renderStep6(container, state, updateScenario) {
  const data = state.wizard.data;
  const analysis = data.analysis || {};
  const rubric = Array.isArray(analysis.rubric) ? analysis.rubric : [];
  container.innerHTML = "";

  const presetCard = createCard("Тип анализа");
  const presetCards = document.createElement("div");
  presetCards.className = "wizard-persona-cards";
  ANALYSIS_PRESETS.forEach((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `wizard-persona-card ${
      analysis.preset === preset.id ? "is-active" : ""
    }`;
    button.textContent = preset.label;
    button.addEventListener("click", () => {
      updateScenario((draft) => {
        draft.analysis.preset = preset.id;
      });
    });
    presetCards.append(button);
  });
  presetCard.append(
    createField("Пресет анализа", presetCards, "Выберите формат анализа после тренировки.")
  );
  container.append(presetCard);

  const rubricCard = createCard("Критерии");
  const rubricWrap = document.createElement("div");
  rubricWrap.className = "wizard-rubric";
  rubric.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "wizard-rubric-row";
    const check = document.createElement("label");
    check.className = "wizard-check";
    const checkInput = document.createElement("input");
    checkInput.type = "checkbox";
    checkInput.checked = Boolean(item.enabled);
    checkInput.addEventListener("change", () => {
      updateScenario((draft) => {
        draft.analysis.rubric[index].enabled = checkInput.checked;
      });
    });
    const checkText = document.createElement("span");
    checkText.textContent = item.name;
    check.append(checkInput, checkText);
    row.append(check);

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "1";
    slider.max = "5";
    slider.value = String(Number(item.weight || 3));
    slider.addEventListener("input", () => {
      updateScenario((draft) => {
        draft.analysis.rubric[index].weight = Number(slider.value);
      });
    });
    const sliderValue = document.createElement("span");
    sliderValue.className = "wizard-slider-value";
    sliderValue.textContent = String(Number(item.weight || 3));
    slider.addEventListener("input", () => {
      sliderValue.textContent = slider.value;
    });
    row.append(slider, sliderValue);
    rubricWrap.append(row);
  });
  rubricCard.append(
    createField("Критерии и веса", rubricWrap, "Для включённого анализа выберите минимум 3 критерия.")
  );
  container.append(rubricCard);

  const formatCard = createCard("Формат отчёта");
  const formatSelect = createSelect(
    ANALYSIS_FORMATS.map((item) => ({ value: item.id, label: item.label })),
    analysis.format || "scores_comments"
  );
  formatSelect.addEventListener("change", () => {
    updateScenario((draft) => {
      draft.analysis.format = formatSelect.value;
    });
  });
  formatCard.append(
    createField(
      "Формат вывода",
      formatSelect,
      "Определяет структуру отчёта после завершения диалога."
    )
  );

  const langInput = createInput({
    type: "text",
    value: analysis.language || "RU",
    maxLength: 2,
  });
  langInput.disabled = true;
  formatCard.append(createField("Язык отчёта", langInput, "По умолчанию: RU."));
  container.append(formatCard);
}
