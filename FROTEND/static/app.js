const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const healthBtn = document.getElementById("healthBtn");
const resetChatBtn = document.getElementById("resetChatBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusEl = document.getElementById("status");
const chatEl = document.getElementById("chat");
const livePreviewEl = document.getElementById("livePreview");
const analysisOutputEl = document.getElementById("analysisOutput");
const lipSyncModeEl = document.getElementById("lipSyncMode");
const lipSyncStatusEl = document.getElementById("lipSyncStatus");
const micLevelBarEl = document.getElementById("micLevelBar");
const micLevelTextEl = document.getElementById("micLevelText");
const micDeviceSelectEl = document.getElementById("micDeviceSelect");
const refreshMicBtn = document.getElementById("refreshMicBtn");
const backToScenariosBtn = document.getElementById("backToScenariosBtn");
const trainerTimerEl = document.getElementById("trainerTimer");
const trainerTelemetryEl = document.getElementById("trainerTelemetry");
const telemetryTrustFillEl = document.getElementById("telemetryTrustFill");
const telemetryTrustValueEl = document.getElementById("telemetryTrustValue");
const telemetryTrustDeltaEl = document.getElementById("telemetryTrustDelta");
const telemetryEmpathyFillEl = document.getElementById("telemetryEmpathyFill");
const telemetryEmpathyValueEl = document.getElementById("telemetryEmpathyValue");
const telemetryEmpathyDeltaEl = document.getElementById("telemetryEmpathyDelta");
const telemetryClarityFillEl = document.getElementById("telemetryClarityFill");
const telemetryClarityValueEl = document.getElementById("telemetryClarityValue");
const telemetryClarityDeltaEl = document.getElementById("telemetryClarityDelta");
const telemetryValueLinkFillEl = document.getElementById("telemetryValueLinkFill");
const telemetryValueLinkValueEl = document.getElementById("telemetryValueLinkValue");
const telemetryValueLinkDeltaEl = document.getElementById("telemetryValueLinkDelta");
const telemetryPressureFlagEl = document.getElementById("telemetryPressureFlag");
const telemetryEmotionFlagEl = document.getElementById("telemetryEmotionFlag");
const telemetryModeFlagEl = document.getElementById("telemetryModeFlag");
const scenarioLaunchPanelEl = document.getElementById("scenarioLaunchPanel");
const launchScenarioTitleEl = document.getElementById("launchScenarioTitle");
const launchScenarioSummaryEl = document.getElementById("launchScenarioSummary");
const launchScenarioBriefEl = document.getElementById("launchScenarioBrief");
const startScenarioBtn = document.getElementById("startScenarioBtn");
const stopScenarioBtn = document.getElementById("stopScenarioBtn");

let chatSessionId = null;
const scenarioId = (new URLSearchParams(window.location.search).get("scenario_id") || "").trim();
let scenarioFirstSpeaker = "user";
let initialClientTurnStarted = false;
let scenarioLaunchStarted = false;
let trainingActive = false;
let scenarioShowTimer = false;
let scenarioDurationMinutes = 15;
let trainerTimerRemainingSec = 15 * 60;
let trainerTimerInterval = null;
let trainerTimerWarn30Played = false;
let dialogLog = [];
let scenarioRuntimeState = {
  trust_level: 50,
  mood: "calm",
  pressure_detected: false,
  emotional_trigger_hit: false,
  memory_slots: {
    goal_known: false,
    horizon_known: false,
    liquidity_known: false,
    risk_attitude_known: false,
    next_step_agreed: false,
  },
  goal_known: false,
  horizon_known: false,
  liquidity_known: false,
  risk_attitude_known: false,
  next_step_agreed: false,
  used_objections: [],
  success_conditions_met: [],
  stop_conditions_met: [],
  manager_quality: {
    direct_answer_score: 0,
    value_link_score: 0,
    clarity_score: 0,
    empathy_score: 0,
  },
};
let prevTelemetrySnapshot = null;

let audioContext;
let mediaStream;
let sourceNode;
let processorNode;
let recording = false;
let audioChunks = [];
let silenceMs = 0;
let hasSpoken = false;
let recordingStartMs = 0;
let noiseFloor = 0;
let calibrated = false;
let calibrationSamples = 0;
let lastVoiceMs = 0;
let previewTimer = null;
let previewInFlight = false;
let autoRestart = true;
let userStopped = false;
let ttsAudio = null;
const avatarImg = document.getElementById("avatarImage");
const avatarVideo = document.getElementById("avatarVideo");
let activeVideoUrl = null;
let lipSyncAbort = null;
let micRmsSmoothed = 0;
let generationInFlight = false;
const TRAINER_AVATAR_LIBRARY = {
  male_senior_1: {
    thumbSrc: "/static/assets/avatars/male_senior_close.png",
    previewSrc: "/static/assets/avatars/male_senior_full.png",
  },
  female_1: {
    thumbSrc: "/static/assets/avatars/female_1_close.png",
    previewSrc: "/static/assets/avatars/female_1_full.png",
  },
};

const BASE_SILENCE_THRESHOLD = 0.006;
const SILENCE_LIMIT_MS = 3000;
const MAX_RECORDING_MS = 120000;
const PREVIEW_INTERVAL_MS = 1200;
const PREVIEW_MIN_AUDIO_MS = 1200;
const PREVIEW_WINDOW_MS = 8000;
const MIN_DB_THRESHOLD = -20; // Жесткий noise gate: сильнее режет фоновые шумы
const MIN_RMS_THRESHOLD = Math.pow(10, MIN_DB_THRESHOLD / 20);
const MIC_DB_FLOOR = -70;
const MIC_DB_CEIL = -10;
const MIC_DEVICE_STORAGE_KEY = "rgsl_mic_device_id";

startBtn.addEventListener("click", startRecording);
stopBtn.addEventListener("click", stopRecording);
healthBtn.addEventListener("click", checkHealth);
if (resetChatBtn) resetChatBtn.addEventListener("click", resetChat);
if (analyzeBtn) analyzeBtn.addEventListener("click", runDialogAnalysis);
if (refreshMicBtn) refreshMicBtn.addEventListener("click", () => populateMicDevices(true));
if (micDeviceSelectEl) {
  micDeviceSelectEl.addEventListener("change", () => {
    const value = micDeviceSelectEl.value || "";
    localStorage.setItem(MIC_DEVICE_STORAGE_KEY, value);
  });
}
if (startScenarioBtn) {
  startScenarioBtn.addEventListener("click", startScenarioSession);
}
if (stopScenarioBtn) {
  stopScenarioBtn.addEventListener("click", stopScenarioSession);
}
if (backToScenariosBtn) {
  backToScenariosBtn.addEventListener("click", () => {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/";
  });
}

function resolveAvatarSrcById(avatarId) {
  const key = String(avatarId || "").trim();
  return TRAINER_AVATAR_LIBRARY[key]?.previewSrc || "/avatar";
}

function formatCountdown(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function renderTrainerTimer() {
  if (!trainerTimerEl) return;
  if (!scenarioShowTimer) {
    trainerTimerEl.classList.add("hidden");
    trainerTimerEl.classList.remove("is-warning");
    trainerTimerEl.classList.remove("is-critical");
    return;
  }
  trainerTimerEl.classList.remove("hidden");
  trainerTimerEl.textContent = formatCountdown(trainerTimerRemainingSec);
  trainerTimerEl.classList.toggle(
    "is-warning",
    trainerTimerRemainingSec <= 120 && trainerTimerRemainingSec > 30
  );
  trainerTimerEl.classList.toggle("is-critical", trainerTimerRemainingSec <= 30);
}

function clampPercent(value) {
  const n = Number(value || 0);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

function setTelemetryDelta(el, current, previous) {
  if (!el) return;
  el.classList.remove("up", "down");
  if (!Number.isFinite(previous)) {
    el.textContent = "—";
    return;
  }
  const delta = Math.round((Number(current) || 0) - previous);
  if (delta > 0) {
    el.textContent = `+${delta}`;
    el.classList.add("up");
  } else if (delta < 0) {
    el.textContent = `${delta}`;
    el.classList.add("down");
  } else {
    el.textContent = "0";
  }
}

function setTelemetryMetric(fillEl, valueEl, deltaEl, value, prevValue) {
  const normalized = clampPercent(value);
  if (fillEl) fillEl.style.width = `${normalized}%`;
  if (valueEl) valueEl.textContent = String(normalized);
  setTelemetryDelta(deltaEl, normalized, prevValue);
}

function updateTelemetryPanel(state) {
  if (!trainerTelemetryEl) return;
  const runtime = state && typeof state === "object" ? state : {};
  const quality =
    runtime.manager_quality && typeof runtime.manager_quality === "object"
      ? runtime.manager_quality
      : {};

  const current = {
    trust: clampPercent(runtime.trust_level ?? 50),
    empathy: clampPercent(quality.empathy_score ?? 0),
    clarity: clampPercent(quality.clarity_score ?? 0),
    valueLink: clampPercent(quality.value_link_score ?? 0),
  };
  const prev = prevTelemetrySnapshot || {};

  setTelemetryMetric(
    telemetryTrustFillEl,
    telemetryTrustValueEl,
    telemetryTrustDeltaEl,
    current.trust,
    Number(prev.trust)
  );
  setTelemetryMetric(
    telemetryEmpathyFillEl,
    telemetryEmpathyValueEl,
    telemetryEmpathyDeltaEl,
    current.empathy,
    Number(prev.empathy)
  );
  setTelemetryMetric(
    telemetryClarityFillEl,
    telemetryClarityValueEl,
    telemetryClarityDeltaEl,
    current.clarity,
    Number(prev.clarity)
  );
  setTelemetryMetric(
    telemetryValueLinkFillEl,
    telemetryValueLinkValueEl,
    telemetryValueLinkDeltaEl,
    current.valueLink,
    Number(prev.valueLink)
  );

  const pressure = Boolean(runtime.pressure_detected);
  const emotion = Boolean(runtime.emotional_trigger_hit);
  const mode = String(runtime.response_mode_hint || "normal_dialog");

  if (telemetryPressureFlagEl) {
    telemetryPressureFlagEl.textContent = `Давление: ${pressure ? "да" : "нет"}`;
    telemetryPressureFlagEl.classList.toggle("alert", pressure);
  }
  if (telemetryEmotionFlagEl) {
    telemetryEmotionFlagEl.textContent = `Эмо-триггер: ${emotion ? "да" : "нет"}`;
    telemetryEmotionFlagEl.classList.toggle("alert", emotion);
  }
  if (telemetryModeFlagEl) {
    telemetryModeFlagEl.textContent = `Режим: ${mode}`;
  }

  prevTelemetrySnapshot = current;
}

function clearTrainerTimer() {
  if (trainerTimerInterval) {
    clearInterval(trainerTimerInterval);
    trainerTimerInterval = null;
  }
}

function resetTrainerTimerFromScenario() {
  trainerTimerRemainingSec = Math.max(0, Math.round((Number(scenarioDurationMinutes) || 15) * 60));
  trainerTimerWarn30Played = false;
  renderTrainerTimer();
}

function playTimerWarningBeep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(940, ctx.currentTime);
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.28);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
    osc.onended = () => {
      try {
        ctx.close();
      } catch (_) {}
    };
  } catch (_) {
    // ignore audio warning failures
  }
}

function startTrainerTimer() {
  clearTrainerTimer();
  if (!scenarioShowTimer) {
    renderTrainerTimer();
    return;
  }
  resetTrainerTimerFromScenario();
  trainerTimerInterval = setInterval(() => {
    if (!trainingActive) {
      clearTrainerTimer();
      return;
    }
    trainerTimerRemainingSec = Math.max(0, trainerTimerRemainingSec - 1);
    renderTrainerTimer();
    if (trainerTimerRemainingSec <= 30 && !trainerTimerWarn30Played) {
      trainerTimerWarn30Played = true;
      playTimerWarningBeep();
    }
    if (trainerTimerRemainingSec <= 0) {
      clearTrainerTimer();
      stopScenarioSession("Тренировка завершена: время вышло.");
    }
  }, 1000);
}

function formatMoney(value, currency = "RUB") {
  const num = Number(value || 0);
  if (!Number.isFinite(num) || num <= 0) return "не указана";
  const formatted = new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 0,
  }).format(num);
  if (String(currency || "RUB").toUpperCase() === "RUB") {
    return `${formatted} рублей`;
  }
  return `${formatted} ${String(currency || "").toUpperCase()}`.trim();
}

function updateRuntimeSlotsFromManagerText(text) {
  const t = String(text || "").toLowerCase();
  if (!t) return;
  if (/цель|для чего|зачем|планируете/.test(t)) {
    scenarioRuntimeState.goal_known = true;
  }
  if (/срок|месяц|месяцев|год|лет/.test(t)) {
    scenarioRuntimeState.horizon_known = true;
  }
  if (/ликвид|снять|досроч|доступ/.test(t)) {
    scenarioRuntimeState.liquidity_known = true;
  }
  if (/риск|рисков|консерват|агрессив|умеренн/.test(t)) {
    scenarioRuntimeState.risk_attitude_known = true;
  }
  if (/следующ|оформим|договорим|подтвержда/.test(t)) {
    scenarioRuntimeState.next_step_agreed = true;
  }
}

function appendChatMessage(role, text, showSpinner = false) {
  if (!chatEl) return;

  const row = document.createElement("div");
  row.className = `chat-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  
  if (showSpinner) {
    const spinner = document.createElement("div");
    spinner.className = "spinner";
    bubble.appendChild(spinner);
  } else {
    bubble.textContent = text || "(пусто)";
    if (text && (role === "user" || role === "assistant")) {
      dialogLog.push({ role, text });
    }
  }

  row.appendChild(bubble);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function setLivePreview(text) {
  if (!livePreviewEl) return;
  livePreviewEl.textContent = text || "—";
}

function setLipSyncStatus(text) {
  if (!lipSyncStatusEl) return;
  lipSyncStatusEl.textContent = text || "";
}

function currentLipSyncMode() {
  return lipSyncModeEl ? lipSyncModeEl.value : "talking";
}

function setMicLevel(rms, forceText = null) {
  if (!micLevelBarEl || !micLevelTextEl) return;

  if (forceText) {
    micLevelBarEl.style.width = "0%";
    micLevelBarEl.classList.remove("low", "mid", "high");
    micLevelTextEl.textContent = forceText;
    return;
  }

  const safeRms = Math.max(1e-8, rms || 0);
  const db = 20 * Math.log10(safeRms);
  const pct = Math.max(
    0,
    Math.min(100, ((db - MIC_DB_FLOOR) / (MIC_DB_CEIL - MIC_DB_FLOOR)) * 100)
  );

  micLevelBarEl.style.width = `${pct.toFixed(1)}%`;
  micLevelBarEl.classList.remove("low", "mid", "high");
  if (pct >= 70) micLevelBarEl.classList.add("high");
  else if (pct >= 35) micLevelBarEl.classList.add("mid");
  else if (pct >= 8) micLevelBarEl.classList.add("low");

  micLevelTextEl.textContent = pct < 2 ? "тишина" : `${db.toFixed(1)} dB`;
}

function getPreferredMicId() {
  try {
    return localStorage.getItem(MIC_DEVICE_STORAGE_KEY) || "";
  } catch (_) {
    return "";
  }
}

async function populateMicDevices(showStatus = false) {
  if (!navigator.mediaDevices?.enumerateDevices || !micDeviceSelectEl) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const inputs = devices.filter((d) => d.kind === "audioinput");
    const preferred = getPreferredMicId();
    micDeviceSelectEl.innerHTML = "";

    const autoOpt = document.createElement("option");
    autoOpt.value = "";
    autoOpt.textContent = "Системный по умолчанию";
    micDeviceSelectEl.appendChild(autoOpt);

    inputs.forEach((d, idx) => {
      const opt = document.createElement("option");
      opt.value = d.deviceId;
      opt.textContent = d.label || `Микрофон ${idx + 1}`;
      micDeviceSelectEl.appendChild(opt);
    });

    const hasPreferred = inputs.some((d) => d.deviceId === preferred);
    micDeviceSelectEl.value = hasPreferred ? preferred : "";
    if (showStatus && statusEl) {
      statusEl.textContent = `Микрофоны: ${inputs.length}`;
    }
  } catch (_) {
    if (showStatus && statusEl) {
      statusEl.textContent = "Не удалось получить список микрофонов";
    }
  }
}

function recordingDurationMs(sampleRate) {
  if (!sampleRate || audioChunks.length === 0) return 0;
  const totalSamples = audioChunks.reduce((sum, chunk) => sum + chunk.length, 0);
  return (totalSamples / sampleRate) * 1000;
}

function collectRecentChunks(maxMs, sampleRate) {
  if (!sampleRate || maxMs <= 0) return audioChunks;
  const maxSamples = Math.floor((maxMs / 1000) * sampleRate);
  let collected = 0;
  const recent = [];

  for (let i = audioChunks.length - 1; i >= 0 && collected < maxSamples; i -= 1) {
    recent.push(audioChunks[i]);
    collected += audioChunks[i].length;
  }

  recent.reverse();
  return recent;
}

async function playTts(text, placeholder = null) {
  const clean = (text || "").trim();
  if (!clean) return;

  try {
    // 1. Получаем TTS аудио
    const resp = await fetch("/tts", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: clean, length_scale: 0.86 }),
    });
    if (!resp.ok) {
      if (placeholder) placeholder.textContent = clean;
      return;
    }
    const ttsBlob = await resp.blob();
    const ttsUrl = URL.createObjectURL(ttsBlob);

    // 2. ВРЕМЕННО: отключили LivePortrait/LipSync в цепочке.
    // let videoUrl = null;
    // try {
    //   videoUrl = await requestLipSyncAndWait(ttsBlob);
    // } catch (e) {
    //   console.error("LipSync failed, playing audio only:", e);
    // }

    // 3. Очищаем предыдущее аудио
    if (ttsAudio) {
      try {
        ttsAudio.pause();
      } catch (_) {}
      if (ttsAudio.src) URL.revokeObjectURL(ttsAudio.src);
    }

    // 4. Показываем текст в чате
    if (placeholder) placeholder.textContent = clean;

    // 5. Только TTS-аудио (без видео-синхронизации губ)
    ttsAudio = new Audio(ttsUrl);
    await new Promise((resolve) => {
      ttsAudio.onended = () => {
        URL.revokeObjectURL(ttsUrl);
        showAvatarImage();
        resolve();
      };
      ttsAudio.onerror = () => {
        URL.revokeObjectURL(ttsUrl);
        showAvatarImage();
        resolve();
      };
      ttsAudio.play().catch(() => resolve());
    });
  } catch (e) {
    console.error("TTS error:", e);
    if (placeholder) placeholder.textContent = clean;
  }
}

async function startRecordingWithRetry(maxAttempts = 3, delayMs = 450) {
  if (!trainingActive) return false;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (!trainingActive) return false;
    const ok = await startRecording();
    if (ok) return true;
    if (attempt < maxAttempts) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  return false;
}

function stopScenarioSession(reason = "Тренировка остановлена.") {
  trainingActive = false;
  scenarioLaunchStarted = false;
  initialClientTurnStarted = false;
  autoRestart = false;
  userStopped = true;
  generationInFlight = false;
  clearTrainerTimer();

  if (previewTimer) {
    clearInterval(previewTimer);
    previewTimer = null;
  }
  if (recording) {
    void stopRecording();
  } else {
    if (startBtn) startBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = true;
  }

  if (ttsAudio) {
    try {
      ttsAudio.pause();
      ttsAudio.currentTime = 0;
    } catch (_) {}
  }
  showAvatarImage();

  if (startScenarioBtn) startScenarioBtn.disabled = false;
  if (stopScenarioBtn) stopScenarioBtn.disabled = true;
  if (statusEl) statusEl.textContent = reason;
  renderTrainerTimer();
}

function showAvatarVideoWithAudio(videoUrl, audioUrl) {
  if (!avatarVideo || !avatarImg) return;
  
  if (activeVideoUrl && activeVideoUrl !== videoUrl) {
    URL.revokeObjectURL(activeVideoUrl);
  }
  activeVideoUrl = videoUrl;
  
  avatarVideo.oncanplay = null;
  avatarVideo.onerror = null;
  avatarVideo.onloadeddata = null;
  avatarVideo.onended = null;
  
  // Воспроизводим встроенное аудио lip-sync видео для максимально точной синхронизации губ.
  avatarVideo.muted = false;
  
  avatarVideo.src = videoUrl;
  
  avatarVideo.onloadeddata = () => {
    console.log("Video loaded, showing with audio...");
    avatarImg.style.display = "none";
    avatarVideo.style.cssText = "display: block !important; position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; z-index: 999;";

    avatarVideo.play().catch((e) => {
      console.error("Video play error:", e);
      // Fallback: если браузер заблокировал autoplay с аудио, воспроизводим только TTS.
      ttsAudio = new Audio(audioUrl);
      ttsAudio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        showAvatarImage();
      };
      ttsAudio.play().catch(() => {});
    });
  };
  
  avatarVideo.onended = () => {
    console.log("Video ended");
    showAvatarImage();
    URL.revokeObjectURL(videoUrl);
    URL.revokeObjectURL(audioUrl);
  };

  avatarVideo.onerror = (e) => {
    console.error("Video error:", avatarVideo.error);
    // Fallback: воспроизводим только аудио
    ttsAudio = new Audio(audioUrl);
    ttsAudio.onended = () => {
      URL.revokeObjectURL(audioUrl);
      showAvatarImage();
    };
    ttsAudio.play().catch(() => {});
    showAvatarImage();
  };
  
  avatarVideo.load();
}

function showAvatarVideo(url) {
  if (!avatarVideo || !avatarImg) return;
  if (activeVideoUrl && activeVideoUrl !== url) {
    URL.revokeObjectURL(activeVideoUrl);
  }
  activeVideoUrl = url;
  
  // Clear previous handlers
  avatarVideo.oncanplay = null;
  avatarVideo.onerror = null;
  avatarVideo.onloadeddata = null;
  
  avatarVideo.src = url;
  
  avatarVideo.onloadeddata = () => {
    console.log("Video loaded, showing...");
    avatarImg.style.display = "none";
    avatarVideo.style.cssText = "display: block !important; position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; z-index: 999;";
    avatarVideo.play().then(() => {
      console.log("Video playing!");
    }).catch((e) => console.error("Play error:", e));
  };
  
  avatarVideo.onerror = (e) => {
    console.error("Video error:", avatarVideo.error);
    showAvatarImage();
  };
  
  avatarVideo.load();
}

function showAvatarImage() {
  if (!avatarVideo || !avatarImg) return;
  if (activeVideoUrl) {
    URL.revokeObjectURL(activeVideoUrl);
    activeVideoUrl = null;
  }
  avatarVideo.pause();
  avatarVideo.removeAttribute("src");
  avatarVideo.style.display = "none";
  avatarImg.style.display = "block";
}

async function requestLipSyncAndWait(audioBlob) {
  if (!audioBlob) return null;
  console.log("Starting lipsync request...");

  const formData = new FormData();
  formData.append("audio", audioBlob, "tts.wav");

  const resp = await fetch(`/lipsync?method=${currentLipSyncMode()}`, {
    method: "POST",
    body: formData,
  });
  console.log("Lipsync response status:", resp.status);
  if (!resp.ok) {
    throw new Error("Lipsync failed: " + resp.status);
  }
  const blob = await resp.blob();
  console.log("Lipsync blob size:", blob.size, "type:", blob.type);
  const url = URL.createObjectURL(blob);
  console.log("Lipsync video URL:", url);
  return url;
}

// Legacy function for compatibility
async function requestLipSync(audioBlob) {
  try {
    const url = await requestLipSyncAndWait(audioBlob);
    if (url) showAvatarVideo(url);
  } catch (e) {
    console.error("Lipsync error:", e);
    showAvatarImage();
  }
}

async function resetChat() {
  const oldSession = chatSessionId;
  chatSessionId = null;
  prevTelemetrySnapshot = null;
  scenarioRuntimeState = {
    trust_level: 50,
    mood: "calm",
    pressure_detected: false,
    emotional_trigger_hit: false,
    memory_slots: {
      goal_known: false,
      horizon_known: false,
      liquidity_known: false,
      risk_attitude_known: false,
      next_step_agreed: false,
    },
    goal_known: false,
    horizon_known: false,
    liquidity_known: false,
    risk_attitude_known: false,
    next_step_agreed: false,
    used_objections: [],
    success_conditions_met: [],
    stop_conditions_met: [],
    manager_quality: {
      direct_answer_score: 0,
      value_link_score: 0,
      clarity_score: 0,
      empathy_score: 0,
    },
  };
  updateTelemetryPanel(scenarioRuntimeState);
  if (chatEl) chatEl.innerHTML = "";
  dialogLog = [];
  if (analysisOutputEl) analysisOutputEl.textContent = "—";
  setLivePreview("—");
  initialClientTurnStarted = false;

  if (oldSession) {
    try {
      await fetch("/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          text: "reset",
          session_id: oldSession,
          reset: true,
          scenario_id: scenarioId || undefined,
          runtime_state: scenarioRuntimeState,
        }),
      });
    } catch (_) {
      // ignore reset errors
    }
  }

  statusEl.textContent = "Чат сброшен";

  if (
    scenarioId &&
    scenarioLaunchStarted &&
    scenarioFirstSpeaker === "ai" &&
    !initialClientTurnStarted
  ) {
    initialClientTurnStarted = true;
    await startInitialClientTurn();
  }
}

async function runDialogAnalysis() {
  if (!analyzeBtn || !analysisOutputEl) return;
  if (!scenarioId) {
    statusEl.textContent = "Нужен scenario_id для анализа";
    return;
  }
  if (!Array.isArray(dialogLog) || dialogLog.length < 2) {
    statusEl.textContent = "Недостаточно данных для анализа";
    return;
  }
  try {
    statusEl.textContent = "Анализирую встречу...";
    if (analysisOutputEl) analysisOutputEl.textContent = "Выполняется анализ...";
    const resp = await fetch("/analysis/dialog", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        scenario_id: scenarioId,
        dialog_log: dialogLog,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Ошибка анализа");
    }
    if (analysisOutputEl) {
      analysisOutputEl.textContent = JSON.stringify(data.analysis || {}, null, 2);
    }
    statusEl.textContent = "Анализ готов";
  } catch (error) {
    if (analysisOutputEl) {
      analysisOutputEl.textContent = "Ошибка анализа: " + (error?.message || String(error));
    }
    statusEl.textContent = "Ошибка";
  }
}

async function startRecording() {
  if (recording) return true;
  userStopped = false;

  setLivePreview("—");
  statusEl.textContent = "Запись...";
  setMicLevel(0, "калибровка...");
  startBtn.disabled = true;
  stopBtn.disabled = false;

  try {
    const selectedMicId = micDeviceSelectEl?.value || "";
    const constraints = selectedMicId
      ? { audio: { deviceId: { exact: selectedMicId } } }
      : { audio: true };
    mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (error) {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      statusEl.textContent = "Использую микрофон по умолчанию";
    } catch (_) {
      statusEl.textContent = "Нет доступа к микрофону";
      setMicLevel(0, "нет доступа");
      startBtn.disabled = false;
      stopBtn.disabled = true;
      appendChatMessage("assistant", "Ошибка микрофона: проверь доступ в браузере.");
      return false;
    }
  }

  await populateMicDevices();

  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  if (audioContext.state === "suspended") {
    try {
      await audioContext.resume();
    } catch (_) {}
  }
  sourceNode = audioContext.createMediaStreamSource(mediaStream);
  processorNode = audioContext.createScriptProcessor(4096, 1, 1);

  audioChunks = [];
  silenceMs = 0;
  hasSpoken = false;
  recordingStartMs = performance.now();
  noiseFloor = 0;
  calibrated = false;
  calibrationSamples = 0;
  lastVoiceMs = performance.now();
  recording = true;
  micRmsSmoothed = 0;

  if (previewTimer) {
    clearInterval(previewTimer);
  }
  previewTimer = setInterval(() => {
    if (!recording || previewInFlight || !audioContext || audioChunks.length === 0) return;
    if (recordingDurationMs(audioContext.sampleRate) < PREVIEW_MIN_AUDIO_MS) return;
    previewInFlight = true;
    const previewChunks = collectRecentChunks(PREVIEW_WINDOW_MS, audioContext.sampleRate);
    const wavBlob = encodeWav(previewChunks, audioContext.sampleRate);
    sendAudio(wavBlob, { preview: true }).finally(() => {
      previewInFlight = false;
    });
  }, PREVIEW_INTERVAL_MS);

  processorNode.onaudioprocess = (event) => {
    if (!recording) return;

    const input = event.inputBuffer.getChannelData(0);
    const rms = Math.sqrt(input.reduce((sum, v) => sum + v * v, 0) / input.length);
    const peak = input.reduce((mx, v) => Math.max(mx, Math.abs(v)), 0);
    micRmsSmoothed = micRmsSmoothed * 0.85 + rms * 0.15;
    setMicLevel(micRmsSmoothed);
    const now = performance.now();

    // Всегда сохраняем буферы, чтобы ручной стоп работал даже без срабатывания VAD.
    audioChunks.push(new Float32Array(input));

    // Калибровка шума (первые 5 буферов), но детект голоса не блокируем.
    if (!calibrated) {
      noiseFloor += rms;
      calibrationSamples += 1;
      if (calibrationSamples >= 5) {
        noiseFloor = noiseFloor / calibrationSamples;
        calibrated = true;
        console.log(`[Audio] Calibrated. Noise floor: ${noiseFloor.toFixed(4)}, Min threshold: ${MIN_RMS_THRESHOLD.toFixed(4)}`);
      }
    }

    // Жесткое и простое правило:
    // если входящий сигнал >= -20 dB, это речь; иначе тишина.
    // Используем PEAK по буферу (а не RMS), чтобы не резать нормальную живую речь.
    const isVoice = peak >= MIN_RMS_THRESHOLD;
    if (isVoice) {
      hasSpoken = true;
      silenceMs = 0;
      lastVoiceMs = now;
    }

    // 3 секунды непрерывной тишины (< -20 dB) => стоп и отправка.
    // Не ждём отдельного флага hasSpoken, иначе при "тихом" микрофоне
    // запись может никогда не завершиться.
    if (!isVoice) {
      const bufferDurationMs = (input.length / audioContext.sampleRate) * 1000;
      silenceMs += bufferDurationMs;
      if (
        silenceMs >= SILENCE_LIMIT_MS &&
        now - recordingStartMs >= PREVIEW_MIN_AUDIO_MS
      ) {
        stopRecording();
      }
    }

    if (now - recordingStartMs >= MAX_RECORDING_MS) {
      stopRecording();
    }
  };

  sourceNode.connect(processorNode);
  processorNode.connect(audioContext.destination);
  return true;
}

async function stopRecording() {
  if (!recording) return;
  recording = false;
  userStopped = true;

  statusEl.textContent = "Подготовка аудио...";
  startBtn.disabled = false;
  stopBtn.disabled = true;

  if (previewTimer) {
    clearInterval(previewTimer);
    previewTimer = null;
  }

  try {
    if (processorNode) processorNode.disconnect();
  } catch (_) {}
  try {
    if (sourceNode) sourceNode.disconnect();
  } catch (_) {}

  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }

  const sampleRate = audioContext ? audioContext.sampleRate : 16000;
  if (audioContext && audioContext.state !== "closed") {
    await audioContext.close();
  }

  if (audioChunks.length === 0) {
    statusEl.textContent = "Нет аудио";
    setMicLevel(0, "нет сигнала");
    setLivePreview("(нет аудио)");
    appendChatMessage("assistant", "Не удалось захватить звук с микрофона.");
    return;
  }

  const wavBlob = encodeWav(audioChunks, sampleRate);
  if (!trainingActive) {
    statusEl.textContent = "Тренировка остановлена";
    setMicLevel(0, "остановлено");
    return;
  }
  await sendAudio(wavBlob, { preview: false });
  setMicLevel(0, "ожидание");
}

function encodeWav(chunks, sampleRate) {
  const bufferLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const pcm = new Float32Array(bufferLength);
  let offset = 0;

  for (const chunk of chunks) {
    pcm.set(chunk, offset);
    offset += chunk.length;
  }

  const wavBuffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(wavBuffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + pcm.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, pcm.length * 2, true);

  floatTo16BitPCM(view, 44, pcm);
  return new Blob([view], { type: "audio/wav" });
}

function floatTo16BitPCM(view, offset, input) {
  for (let i = 0; i < input.length; i += 1) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(offset + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
}

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i += 1) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

async function sendAudio(blob, { preview } = { preview: false }) {
  if (!trainingActive && !preview) return;
  if (!preview) {
    statusEl.textContent = "Отправка...";
  }
  const formData = new FormData();
  formData.append("audio", blob, "speech.wav");

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    const response = await fetch(`/transcribe${preview ? "?preview=1" : ""}`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : { error: await response.text() };
    if (!response.ok) {
      throw new Error(data.error || "Ошибка распознавания");
    }
    if (preview) {
      if (!trainingActive) return;
      setLivePreview(data.text || "(пусто)");
      statusEl.textContent = "Распознавание...";
    } else {
      if (!trainingActive) return;
      if (generationInFlight) {
        statusEl.textContent = "Ожидание завершения предыдущей генерации...";
        return;
      }
      const finalText = (data.text || "").trim();
      setLivePreview(finalText || "(пусто)");

      if (finalText.length > 0) {
        generationInFlight = true;
        appendChatMessage("user", finalText);
        appendChatMessage("assistant", null, true); // показать спиннер
        const placeholder = chatEl?.lastElementChild?.querySelector?.(
          ".chat-bubble"
        );

        try {
          statusEl.textContent = "Думаю...";
          const chatResp = await fetch("/chat", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              text: finalText,
              session_id: chatSessionId,
              scenario_id: scenarioId || undefined,
              runtime_state: scenarioRuntimeState,
            }),
          });
          const chatData = await chatResp.json();
          if (!trainingActive) {
            if (placeholder) placeholder.textContent = "";
            return;
          }
          if (!chatResp.ok) {
            throw new Error(chatData.error || "Ошибка LLM");
          }
          if (chatData.runtime_state && typeof chatData.runtime_state === "object") {
            scenarioRuntimeState = chatData.runtime_state;
            updateTelemetryPanel(scenarioRuntimeState);
          }
          chatSessionId = chatData.session_id;
          const replyText = chatData.reply || "(пусто)";
          // Не показываем текст сразу - передаём placeholder в playTts
          statusEl.textContent = "Озвучивание...";
          await playTts(replyText, placeholder);
          if (chatData.stop === true) {
            stopScenarioSession("Тренировка завершена: достигнуто условие стопа.");
            return;
          }
        } catch (e) {
          if (placeholder)
            placeholder.textContent = "Ошибка LLM: " + (e?.message || String(e));
        } finally {
          generationInFlight = false;
        }
      }

      statusEl.textContent = "Готово";

      // Auto-restart recording after LLM response (hands-free mode)
      if (trainingActive && autoRestart && !recording) {
        setTimeout(() => {
          if (trainingActive && !recording) {
            void startRecordingWithRetry(3, 400);
          }
        }, 300);
      }
    }
  } catch (error) {
    if (!preview) {
      const message = error.name === "AbortError" ? "Таймаут запроса" : error.message;
      appendChatMessage("assistant", "Ошибка: " + message);
      statusEl.textContent = "Ошибка";
    }
  }
}

async function checkHealth() {
  statusEl.textContent = "Проверка связи...";
  try {
    const response = await fetch("/health");
    const data = await response.json();
    if (data.status !== "ok") {
      statusEl.textContent = "Связь: ошибка";
      return;
    }

    const agentOk = Boolean(data?.ai_agent?.ok);
    if (!agentOk) {
      statusEl.textContent = "Связь OK (AI-AGENT недоступен)";
      return;
    }

    const llm = data?.ai_agent?.llm || {};
    const llmOk = Boolean(llm?.ok);
    if (!llmOk) {
      statusEl.textContent = "Связь OK (LLM недоступна)";
      return;
    }

    const modelPresent = llm?.provider === "ollama" ? Boolean(llm?.model_present) : true;
    const lipSyncOk = Boolean(data?.lip_sync?.ok);
    const lipSyncLegacyOk = Boolean(data?.lip_sync_legacy?.ok);
    statusEl.textContent = modelPresent
      ? "Связь OK (STT+AI-AGENT+LLM)"
      : "Связь OK (LLM есть, модели нет)";

    const mode = currentLipSyncMode();
    if (mode === "talking" && !lipSyncOk) {
      statusEl.textContent += " + TALKING_AVATAR недоступен";
    }
    if (mode === "legacy" && !lipSyncLegacyOk) {
      statusEl.textContent += " + LIPSYNC недоступен";
    }
    setLipSyncStatus(
      `TALKING_AVATAR: ${lipSyncOk ? "OK" : "ERR"} · LIPSYNC: ${
        lipSyncLegacyOk ? "OK" : "ERR"
      }`
    );
  } catch (error) {
    statusEl.textContent = "Связь: ошибка";
  }
}

if (scenarioId && statusEl) {
  statusEl.textContent = `Готово (сценарий: ${scenarioId})`;
  if (startBtn) startBtn.disabled = true;
  if (stopBtn) stopBtn.disabled = true;
}

async function loadScenarioBrief() {
  if (!scenarioId) return;
  try {
    const resp = await fetch(`/scenarios/${encodeURIComponent(scenarioId)}`, {
      method: "GET",
      credentials: "same-origin",
    });
    if (!resp.ok) return;
    const data = await resp.json().catch(() => ({}));
    const item = data?.item || {};
    const title = String(item.title || "").trim();
    scenarioDurationMinutes = Math.max(
      5,
      Math.min(30, Number(item.duration_minutes || 15))
    );
    scenarioShowTimer = Boolean(item?.ui_options?.show_timer);
    resetTrainerTimerFromScenario();
    scenarioFirstSpeaker = String(item.first_speaker || "user").trim() === "ai" ? "ai" : "user";
    const summary = String(item.context || "").trim();
    const snapshot = item?.persona_selection?.selected_persona_snapshot || {};
    const personaName = String(
      item?.persona_selection?.selected_persona_snapshot?.name ||
        item?.persona?.name ||
        "Клиент"
    ).trim();
    const personaAgeRaw = Number(snapshot?.age || item?.persona?.age || 0);
    const personaAge = Number.isFinite(personaAgeRaw) && personaAgeRaw > 0 ? personaAgeRaw : null;
    const clientTypeRaw = String(snapshot?.client_type || "").trim();
    const clientTypeMap = {
      student: "студент",
      working: "работающий",
      retired: "пенсионер",
      retired_working: "работающий пенсионер",
    };
    const clientTypeText = clientTypeMap[clientTypeRaw] || "статус не указан";
    const amountText = formatMoney(item?.facts?.amount, item?.facts?.currency || "RUB");
    const depositTermMonths = Number(item?.facts?.horizon_months || 0);
    const depositTermText =
      Number.isFinite(depositTermMonths) && depositTermMonths > 0
        ? `${depositTermMonths} мес.`
        : "не указан";
    const avatarId = String(
      item?.persona_selection?.selected_persona_snapshot?.avatar_id || ""
    ).trim();
    const launchAvatarSrc = resolveAvatarSrcById(avatarId);
    const legendText = `Легенда: К вам обратился клиент для пролонгации вклада. Сумма вклада — ${amountText}, срок закончившегося депозита — ${depositTermText}.`;
    const launchBriefLines = [
      `Имя: ${personaName}.`,
      `Возраст: ${personaAge ? `${personaAge}` : "не указан"}; статус: ${clientTypeText}.`,
      legendText,
    ].filter(Boolean);

    if (statusEl) {
      statusEl.textContent = title
        ? `Сценарий: ${title}`
        : `Сценарий: ${scenarioId}`;
    }
    if (scenarioLaunchPanelEl) {
      scenarioLaunchPanelEl.classList.remove("hidden");
    }
    if (launchScenarioTitleEl) {
      launchScenarioTitleEl.textContent = title || "Сценарий встречи";
    }
    if (launchScenarioSummaryEl) {
      launchScenarioSummaryEl.textContent =
        summary || "Описание задачи не заполнено. Используйте параметры сценария.";
    }
    if (launchScenarioBriefEl) {
      launchScenarioBriefEl.textContent = launchBriefLines.join("\n");
    }
    if (avatarImg) {
      avatarImg.src = launchAvatarSrc;
      avatarImg.alt = personaName || "Аватар клиента";
    }
  } catch (_) {
    // ignore if scenario metadata is unavailable
  }
}

async function startScenarioSession() {
  if (!scenarioId || scenarioLaunchStarted || generationInFlight) return;
  scenarioLaunchStarted = true;
  trainingActive = true;
  if (startScenarioBtn) startScenarioBtn.disabled = true;
  if (stopScenarioBtn) stopScenarioBtn.disabled = false;
  if (startBtn) startBtn.disabled = false;
  if (statusEl) statusEl.textContent = "Запуск сценария...";
  autoRestart = true;
  startTrainerTimer();
  try {
    await fetch(`/scenarios/${encodeURIComponent(scenarioId)}/prompt-pack`, {
      method: "GET",
      credentials: "same-origin",
    });
  } catch (_) {
    // If preview endpoint is unavailable, continue: prompt-pack will still be built on /chat.
  }

  if (scenarioFirstSpeaker === "ai" && !initialClientTurnStarted) {
    initialClientTurnStarted = true;
    await startInitialClientTurn();
  } else if (scenarioFirstSpeaker !== "ai") {
    appendChatMessage(
      "assistant",
      "Сценарий запущен. Начинайте встречу первым сообщением менеджера."
    );
    if (statusEl) statusEl.textContent = "Сценарий запущен";
  }
}

async function startInitialClientTurn() {
  if (generationInFlight || !trainingActive) return;
  generationInFlight = true;
  appendChatMessage("assistant", null, true);
  const placeholder = chatEl?.lastElementChild?.querySelector?.(".chat-bubble");

  try {
    statusEl.textContent = "ИИ начинает диалог...";
    const chatResp = await fetch("/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        text: "__INIT_CLIENT_TURN__",
        init_client_turn: true,
        session_id: chatSessionId,
        scenario_id: scenarioId || undefined,
        runtime_state: scenarioRuntimeState,
      }),
    });
    const chatData = await chatResp.json();
    if (!trainingActive) {
      if (placeholder) placeholder.textContent = "";
      return;
    }
    if (!chatResp.ok) {
      throw new Error(chatData.error || "Ошибка инициализации диалога");
    }
    if (chatData.runtime_state && typeof chatData.runtime_state === "object") {
      scenarioRuntimeState = chatData.runtime_state;
      updateTelemetryPanel(scenarioRuntimeState);
    }
    chatSessionId = chatData.session_id;
    const replyText = chatData.reply || "(пусто)";
    statusEl.textContent = "Озвучивание...";
    await playTts(replyText, placeholder);
    if (chatData.stop === true) {
      stopScenarioSession("Тренировка завершена: достигнуто условие стопа.");
      return;
    }
    statusEl.textContent = "Готово";
    if (trainingActive && autoRestart && !recording) {
      setTimeout(() => {
        if (trainingActive && !recording) {
          void startRecordingWithRetry(3, 400);
        }
      }, 250);
    }
  } catch (error) {
    if (placeholder) {
      placeholder.textContent = "Ошибка старта диалога: " + (error?.message || String(error));
    }
    statusEl.textContent = "Ошибка";
    if (scenarioId && !chatSessionId) {
      scenarioLaunchStarted = false;
      initialClientTurnStarted = false;
      if (startScenarioBtn) startScenarioBtn.disabled = false;
    }
  } finally {
    generationInFlight = false;
  }
}

populateMicDevices();
updateTelemetryPanel(scenarioRuntimeState);
void loadScenarioBrief();
