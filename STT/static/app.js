const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const healthBtn = document.getElementById("healthBtn");
const resetChatBtn = document.getElementById("resetChatBtn");
const statusEl = document.getElementById("status");
const chatEl = document.getElementById("chat");
const livePreviewEl = document.getElementById("livePreview");

let chatSessionId = null;

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

const BASE_SILENCE_THRESHOLD = 0.01;
const SILENCE_LIMIT_MS = 3000;
const MAX_RECORDING_MS = 30000;
const PREVIEW_INTERVAL_MS = 500;

startBtn.addEventListener("click", startRecording);
stopBtn.addEventListener("click", stopRecording);
healthBtn.addEventListener("click", checkHealth);
if (resetChatBtn) resetChatBtn.addEventListener("click", resetChat);

function appendChatMessage(role, text) {
  if (!chatEl) return;

  const row = document.createElement("div");
  row.className = `chat-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = text || "(пусто)";

  row.appendChild(bubble);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function setLivePreview(text) {
  if (!livePreviewEl) return;
  livePreviewEl.textContent = text || "—";
}

async function playTts(text) {
  const clean = (text || "").trim();
  if (!clean) return;

  try {
    const resp = await fetch("/tts", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: clean }),
    });
    if (!resp.ok) {
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);

    if (ttsAudio) {
      try {
        ttsAudio.pause();
      } catch (_) {}
      if (ttsAudio.src) URL.revokeObjectURL(ttsAudio.src);
    }

    ttsAudio = new Audio(url);
    ttsAudio.onended = () => {
      URL.revokeObjectURL(url);
    };
    await ttsAudio.play();
  } catch (_) {
    // ignore TTS errors silently
  }
}

async function resetChat() {
  const oldSession = chatSessionId;
  chatSessionId = null;
  if (chatEl) chatEl.innerHTML = "";
  setLivePreview("—");

  if (oldSession) {
    try {
      await fetch("/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: "reset", session_id: oldSession, reset: true }),
      });
    } catch (_) {
      // ignore reset errors
    }
  }

  statusEl.textContent = "Чат сброшен";
}

async function startRecording() {
  if (recording) return;
  userStopped = false;

  setLivePreview("—");
  statusEl.textContent = "Запись...";
  startBtn.disabled = true;
  stopBtn.disabled = false;

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
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

  if (previewTimer) {
    clearInterval(previewTimer);
  }
  previewTimer = setInterval(() => {
    if (!recording || !hasSpoken || previewInFlight) return;
    previewInFlight = true;
    const wavBlob = encodeWav(audioChunks, audioContext.sampleRate);
    sendAudio(wavBlob, { preview: true }).finally(() => {
      previewInFlight = false;
    });
  }, PREVIEW_INTERVAL_MS);

  processorNode.onaudioprocess = (event) => {
    if (!recording) return;

    const input = event.inputBuffer.getChannelData(0);
    audioChunks.push(new Float32Array(input));

    const rms = Math.sqrt(input.reduce((sum, v) => sum + v * v, 0) / input.length);

    if (!calibrated) {
      noiseFloor += rms;
      calibrationSamples += 1;
      if (calibrationSamples >= 5) {
        noiseFloor = noiseFloor / calibrationSamples;
        calibrated = true;
      }
      return;
    }

    const threshold = Math.max(BASE_SILENCE_THRESHOLD, noiseFloor * 2.5);

    if (rms > threshold) {
      hasSpoken = true;
      silenceMs = 0;
      lastVoiceMs = performance.now();
    } else if (hasSpoken) {
      const bufferDurationMs = (input.length / audioContext.sampleRate) * 1000;
      silenceMs += bufferDurationMs;

      if (performance.now() - lastVoiceMs >= SILENCE_LIMIT_MS) {
        stopRecording();
      }
    }

    if (performance.now() - recordingStartMs >= MAX_RECORDING_MS) {
      stopRecording();
    }
  };

  sourceNode.connect(processorNode);
  processorNode.connect(audioContext.destination);
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

  processorNode.disconnect();
  sourceNode.disconnect();

  mediaStream.getTracks().forEach((track) => track.stop());
  const sampleRate = audioContext.sampleRate;
  await audioContext.close();

  if (audioChunks.length === 0) {
    statusEl.textContent = "Нет аудио";
    outputEl.textContent = "Ошибка: пустая запись";
    return;
  }

  const wavBlob = encodeWav(audioChunks, sampleRate);
  await sendAudio(wavBlob, { preview: false });
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
      setLivePreview(data.text || "(пусто)");
      statusEl.textContent = "Распознавание...";
    } else {
      const finalText = (data.text || "").trim();
      setLivePreview(finalText || "(пусто)");

      if (finalText.length > 0) {
        appendChatMessage("user", finalText);
        appendChatMessage("assistant", "...");
        const placeholder = chatEl?.lastElementChild?.querySelector?.(
          ".chat-bubble"
        );

        try {
          const chatResp = await fetch("/chat", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              text: finalText,
              session_id: chatSessionId,
            }),
          });
          const chatData = await chatResp.json();
          if (!chatResp.ok) {
            throw new Error(chatData.error || "Ошибка LLM");
          }
          chatSessionId = chatData.session_id;
          const replyText = chatData.reply || "(пусто)";
          if (placeholder) placeholder.textContent = replyText;
          playTts(replyText);
        } catch (e) {
          if (placeholder)
            placeholder.textContent = "Ошибка LLM: " + (e?.message || String(e));
        }
      }

      statusEl.textContent = "Готово";

      // Auto-restart recording after LLM response (hands-free mode)
      if (autoRestart && !recording) {
        setTimeout(() => {
          if (!recording) startRecording();
        }, 400);
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
    statusEl.textContent = modelPresent
      ? "Связь OK (STT+AI-AGENT+LLM)"
      : "Связь OK (LLM есть, модели нет)";
  } catch (error) {
    statusEl.textContent = "Связь: ошибка";
  }
}
