/**
 * chat_tati — javascript.js
 * Compilado de javascript.ts
 *
 * Correções v2:
 *   - iOS/Android: AudioContext desbloqueado por interação do usuário
 *   - Login: cookie de sessão + localStorage como fallback
 *   - Player: play() com Promise + retry automático no iOS
 *   - TTS: fallback para Web Speech com seleção de voz feminina
 *   - VAD: tipagem completa, sem bugs silenciosos
 */

"use strict";

// ════════════════════════════════════════════════════════════════════════════
// 1. SESSION PERSISTENCE
// ════════════════════════════════════════════════════════════════════════════

let _audioUnlocked = false;

function pavSaveSession(token) {
  try {
    const maxAge = 60 * 60 * 24 * 30; // 30 dias
    document.cookie = `pav_session=${encodeURIComponent(token)};max-age=${maxAge};path=/;SameSite=Lax`;
  } catch (e) {
    console.warn("[PAV] cookie indisponível:", e);
  }
  try {
    localStorage.setItem("pav_session", token);
  } catch (e) {
    console.warn("[PAV] localStorage indisponível:", e);
  }
}

function pavReadSession() {
  // Cookie tem prioridade
  try {
    const match = document.cookie
      .split(";")
      .map(c => c.trim())
      .find(c => c.startsWith("pav_session="));
    if (match) {
      const val = decodeURIComponent(match.split("=")[1]);
      if (val) return val;
    }
  } catch (e) { /* ignora */ }

  // Fallback: localStorage
  try {
    const val = localStorage.getItem("pav_session") || "";
    if (val) return val;
  } catch (e) { /* ignora */ }

  // Compatibilidade legada
  try {
    return localStorage.getItem("pav_user") || "";
  } catch (e) {
    return "";
  }
}

function pavClearSession() {
  try {
    document.cookie = "pav_session=;max-age=0;path=/;SameSite=Lax";
  } catch (e) { /* ignora */ }
  try {
    localStorage.removeItem("pav_session");
    localStorage.removeItem("pav_user");
  } catch (e) { /* ignora */ }
}

function pavCheckAutoLogin() {
  const val = pavReadSession();
  if (!val) return;

  const url      = new URL(window.parent.location.href);
  const isToken  = val.length > 20;
  const paramKey = isToken ? "_token" : "_u";

  if (url.searchParams.get(paramKey) !== val) {
    url.searchParams.set(paramKey, val);
    window.parent.location.replace(url.toString());
  }
}

// ════════════════════════════════════════════════════════════════════════════
// 2. iOS / ANDROID AUDIO UNLOCK
// ════════════════════════════════════════════════════════════════════════════

function pavUnlockAudio() {
  if (_audioUnlocked) return;

  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtx();
    const buf = ctx.createBuffer(1, 1, 22050);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    src.start(0);

    if (ctx.state === "suspended") {
      ctx.resume().then(() => { _audioUnlocked = true; });
    } else {
      _audioUnlocked = true;
    }
  } catch (e) {
    console.warn("[PAV] falha ao desbloquear AudioContext:", e);
  }

  // Desbloqueia SpeechSynthesis no iOS
  try {
    const u = new SpeechSynthesisUtterance("");
    u.volume = 0;
    speechSynthesis.speak(u);
  } catch (e) { /* ignora */ }
}

function pavRegisterAudioUnlock() {
  const events = ["touchstart", "touchend", "mousedown", "keydown", "click"];
  const handler = () => {
    pavUnlockAudio();
    events.forEach(ev => document.removeEventListener(ev, handler, true));
  };
  events.forEach(ev =>
    document.addEventListener(ev, handler, { capture: true, once: true })
  );
}

// ════════════════════════════════════════════════════════════════════════════
// 3. AUDIO PLAYER com suporte a iOS
// ════════════════════════════════════════════════════════════════════════════

function pavInitAudioPlayer(audioSrc) {
  const audio   = new Audio();
  audio.preload = "metadata";
  audio.src     = audioSrc;

  const btn = document.getElementById("b");
  const pf  = document.getElementById("pf");
  const pw  = document.getElementById("pw");
  const vs  = document.getElementById("vs");
  const vi  = document.getElementById("vi");
  const sw  = document.getElementById("sw");

  if (!btn) return;

  btn.onclick = () => {
    pavUnlockAudio();

    if (!audio.paused) {
      audio.pause();
      btn.textContent = "▶ Ouvir";
      return;
    }

    const promise = audio.play();
    if (promise !== undefined) {
      promise
        .then(() => { btn.textContent = "⏸ Pausar"; })
        .catch(err => {
          console.warn("[PAV] play() bloqueado:", err);
          btn.textContent = "▶ Ouvir";
          // Retry após 300ms
          setTimeout(() => {
            audio.play()
              .then(() => { btn.textContent = "⏸ Pausar"; })
              .catch(() => {});
          }, 300);
        });
    }
  };

  audio.onended = () => {
    btn.textContent = "▶ Ouvir";
    if (pf) pf.style.width = "0%";
  };

  audio.ontimeupdate = () => {
    if (pf && audio.duration) {
      pf.style.width = (audio.currentTime / audio.duration * 100) + "%";
    }
  };

  if (pw) {
    pw.onclick = e => {
      const rect = pw.getBoundingClientRect();
      if (audio.duration) {
        audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
      }
    };
  }

  if (sw) {
    sw.querySelectorAll(".sb").forEach(sbBtn => {
      sbBtn.onclick = function () {
        sw.querySelectorAll(".sb").forEach(x => x.classList.remove("on"));
        this.classList.add("on");
        audio.playbackRate = parseFloat(this.dataset.r || "1");
      };
    });
  }

  if (vs && vi) {
    vs.oninput = () => {
      audio.volume   = parseFloat(vs.value);
      vi.textContent = audio.volume === 0 ? "🔇" : audio.volume < 0.5 ? "🔉" : "🔊";
    };

    vi.onclick = () => {
      if (audio.volume > 0) {
        audio._savedVol = audio.volume;
        audio.volume    = 0;
        vs.value        = "0";
        vi.textContent  = "🔇";
      } else {
        audio.volume   = audio._savedVol || 1;
        vs.value       = String(audio.volume);
        vi.textContent = "🔊";
      }
    };
  }
}

// ════════════════════════════════════════════════════════════════════════════
// 4. TTS com fallback iOS-safe
// ════════════════════════════════════════════════════════════════════════════

function pavPlayTTS(b64, replyText, speechLang, onEnd) {
  if (!b64 || b64.length < 20) {
    pavFallbackTTS(replyText, speechLang, onEnd);
    return null;
  }

  const audio = new Audio();
  audio.src   = `data:audio/mpeg;base64,${b64}`;

  const promise = audio.play();
  if (promise !== undefined) {
    promise.catch(() => {
      console.warn("[PAV] TTS play() bloqueado, usando Web Speech");
      pavFallbackTTS(replyText, speechLang, onEnd);
    });
  }

  audio.onended = onEnd;
  audio.onerror = () => pavFallbackTTS(replyText, speechLang, onEnd);
  return audio;
}

function pavFallbackTTS(text, speechLang, onEnd) {
  const u  = new SpeechSynthesisUtterance((text || "").substring(0, 500));
  u.lang   = speechLang || "en-US";
  u.rate   = 0.95;
  u.pitch  = 1.05;

  // Prefere voz feminina em inglês
  const voices = speechSynthesis.getVoices();
  const pick   = voices.find(v => v.lang === u.lang && v.name.toLowerCase().includes("female"))
              || voices.find(v => v.lang === u.lang)
              || voices.find(v => v.lang.startsWith((u.lang || "en").split("-")[0]));
  if (pick) u.voice = pick;

  u.onend   = onEnd || (() => {});
  u.onerror = onEnd || (() => {});

  speechSynthesis.cancel();
  setTimeout(() => speechSynthesis.speak(u), 100);
}

// ════════════════════════════════════════════════════════════════════════════
// 5. CHAT BAR
// ════════════════════════════════════════════════════════════════════════════

function pavMoveToChatBar() {
  const par = window.parent ? window.parent.document : document;
  const chatBar = par.querySelector('[data-testid="stChatInput"]');
  if (!chatBar || chatBar.querySelector(".pav-extras")) return;

  const extras = par.createElement("div");
  extras.className = "pav-extras";

  const ab = par.createElement("button");
  ab.className = "pav-icon-btn";
  ab.title     = "Anexar arquivo";
  ab.innerHTML = '<i class="fa-solid fa-paperclip"></i>';
  ab.onclick   = () => {
    pavUnlockAudio();
    const fw = par.querySelector('[data-testid="stFileUploader"]');
    if (fw) {
      const fi = fw.querySelector('input[type="file"]');
      if (fi) fi.click();
    }
  };

  extras.appendChild(ab);
  chatBar.appendChild(extras);

  const fw = par.querySelector('[data-testid="stFileUploader"]');
  if (fw) {
    fw.style.cssText = "position:fixed!important;bottom:-999px!important;left:-9999px!important;opacity:0!important;width:1px!important;height:1px!important;pointer-events:none!important;";
    const fi = fw.querySelector('input[type="file"]');
    if (fi) fi.style.pointerEvents = "auto";
  }
}

// ════════════════════════════════════════════════════════════════════════════
// 6. EMAILJS
// ════════════════════════════════════════════════════════════════════════════

const PAV_EMAILJS = { publicKey: "", serviceId: "", templateId: "" };

function pavSendWelcomeEmail(name, email, username, appName, callback) {
  if (!PAV_EMAILJS.publicKey || !PAV_EMAILJS.serviceId || !PAV_EMAILJS.templateId) {
    if (typeof callback === "function") callback();
    return;
  }
  const script    = document.createElement("script");
  script.src      = "https://cdn.jsdelivr.net/npm/@emailjs/browser@4/dist/email.min.js";
  script.onload   = () => {
    try {
      emailjs.init(PAV_EMAILJS.publicKey);
      emailjs.send(PAV_EMAILJS.serviceId, PAV_EMAILJS.templateId, {
        to_name: name, to_email: email, username,
        app_name: appName, login_url: window.location.origin,
      })
        .then(() => callback && callback())
        .catch(() => callback && callback());
    } catch (e) { callback && callback(); }
  };
  script.onerror  = () => callback && callback();
  document.head.appendChild(script);
}

// ════════════════════════════════════════════════════════════════════════════
// 7. INIT
// ════════════════════════════════════════════════════════════════════════════

window.addEventListener("load", () => {
  pavRegisterAudioUnlock();
});

// Expõe globalmente para uso nos iframes inline do app.py
Object.assign(window, {
  pavSaveSession,
  pavReadSession,
  pavClearSession,
  pavCheckAutoLogin,
  pavUnlockAudio,
  pavRegisterAudioUnlock,
  pavInitAudioPlayer,
  pavPlayTTS,
  pavFallbackTTS,
  pavMoveToChatBar,
  pavSendWelcomeEmail,
});