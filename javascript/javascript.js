/* ════════════════════════════════════════════════════════════════════════════
   ChatBOT Tati — javascript.js
   ⚠️  ARQUIVO DE REFERÊNCIA / DOCUMENTAÇÃO — não é carregado pelo Streamlit.

   O Streamlit não executa <script> tags via st.markdown() nem via
   components.html() no contexto do documento pai. Por isso, todo o JS
   funcional está embutido INLINE no app.py dentro de components.html()
   ou strings f-string.

   Este arquivo existe para:
   - Documentar a lógica de cada função JS usada no projeto
   - Servir de base para copiar/colar ao editar o app.py
   - Configurar o EmailJS (PAV_EMAILJS) — copie as credenciais para o
     bloco correspondente em app.py → show_login() → const EMAILJS_*

   NOTA: O JS dos iframes isolados (login, voice mode, audio player) está
   diretamente no app.py porque precisa de dados dinâmicos do Python (f-strings).
   Este arquivo contém o JS que roda no contexto principal do Streamlit.
   ════════════════════════════════════════════════════════════════════════════ */

/* ════════════════════════════════════════════════════════════════════════════
   1. AUTO-LOGIN — localStorage persistence
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Salva o username no localStorage para auto-login na próxima visita.
 * Chamado pelo Python após login bem-sucedido.
 * @param {string} username
 */
function pavSaveUser(username) {
  try {
    localStorage.setItem('pav_user', username);
  } catch (e) {
    console.warn('[PAV] localStorage indisponível:', e);
  }
}

/**
 * Remove o username do localStorage (logout).
 */
function pavClearUser() {
  try {
    localStorage.removeItem('pav_user');
  } catch (e) {
    console.warn('[PAV] localStorage indisponível:', e);
  }
}

/**
 * Redireciona para auto-login se houver usuário salvo.
 * Executado no carregamento da página quando não há sessão ativa.
 */
function pavCheckAutoLogin() {
  try {
    const u = localStorage.getItem('pav_user');
    if (u) {
      const url = new URL(window.location.href);
      if (url.searchParams.get('_u') !== u) {
        url.searchParams.set('_u', u);
        window.location.replace(url.toString());
      }
    }
  } catch (e) {
    console.warn('[PAV] auto-login check falhou:', e);
  }
}

/* ════════════════════════════════════════════════════════════════════════════
   2. CHAT BAR — move mic + attach icons para a barra de chat
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Move o st.audio_input e st.file_uploader para dentro da barra de chat
 * como botões de ícone discretos (🎤 e ＋).
 * Usa MutationObserver + retry para aguardar o DOM do Streamlit.
 */

// Cria o Botão de Voz (🎤)
  const mb = parent.createElement('button');
  mb.className = 'pav-icon-btn';
  mb.title = 'Ditar mensagem';
  mb.innerHTML = '🎤';
  
  mb.onclick = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Seu navegador não suporta ditado ao vivo. Use o Chrome ou Edge.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR'; // Ou 'en-US' se preferir ditar em inglês
    recognition.interimResults = true; // Isso faz o texto aparecer ENQUANTO fala!

    const chatArea = parent.querySelector('[data-testid="stChatInput"] textarea');

    recognition.onstart = () => { 
        mb.style.color = "red"; // Fica vermelho pra indicar gravação
    };
    
    recognition.onresult = (e) => {
      let texto = "";
      for (let i = 0; i < e.results.length; i++) {
          texto += e.results[i][0].transcript;
      }
      chatArea.value = texto; // Joga o texto em tempo real pra caixa de digitação
      
      // Ajusta a altura da caixa de texto se a mensagem ficar longa
      chatArea.style.height = 'auto';
      chatArea.style.height = chatArea.scrollHeight + 'px';
    };

    recognition.onend = () => {
      mb.style.color = ""; // Volta a cor normal
      // Avisa o Streamlit que o texto foi preenchido
      chatArea.dispatchEvent(new Event('input', { bubbles: true }));
    };

    recognition.start();
  };

/* ════════════════════════════════════════════════════════════════════════════
   3. VOICE MODE — hide file uploader (injetado quando modo voz está ativo)
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Injeta CSS no documento pai para ocultar o stFileUploader visualmente,
 * SEM usar pointer-events:none (o JS do voice mode precisa injetar arquivos).
 * Chamado pelo iframe do voice mode via window.parent.
 */
function pavHideVoiceUploader() {
  const parent = window.parent ? window.parent.document : document;
  if (parent.getElementById('vm-hide-css')) return;

  const s = parent.createElement('style');
  s.id = 'vm-hide-css';
  s.textContent = `
    [data-testid="stFileUploader"] {
      position: fixed !important;
      top: -9999px !important;
      left: -9999px !important;
      width: 1px !important;
      height: 1px !important;
      overflow: hidden !important;
      opacity: 0 !important;
      /* NÃO usar pointer-events:none — o JS precisa injetar arquivos */
    }
    audio { display: none !important; }
    [data-testid="stStatusWidget"],
    .stSpinner,
    [data-testid="stSpinner"] { display: none !important; }
  `;
  parent.head.appendChild(s);
}

/**
 * Remove o CSS de ocultação do uploader (ao fechar o modo voz).
 */
function pavShowVoiceUploader() {
  const parent = window.parent ? window.parent.document : document;
  const el = parent.getElementById('vm-hide-css');
  if (el) el.remove();
}

/* ════════════════════════════════════════════════════════════════════════════
   4. AUDIO PLAYER HELPERS
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Inicializa o player de áudio embutido nas mensagens do chat.
 * Cada player está num iframe components.html — o JS completo do player
 * está no app.py (render_audio_player). Este bloco é apenas referência.
 *
 * Interface do player:
 *   ▶/⏸ Play/Pause   ── barra de progresso clicável
 *   vel: 0.75× 1× 1.25× 1.5×
 *   🔊 volume slider
 */

/* ════════════════════════════════════════════════════════════════════════════
   5. EMAILJS — envio de e-mail de boas-vindas
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Configuração EmailJS — preencha com suas credenciais em https://emailjs.com
 *
 * Como configurar:
 *   1. Crie uma conta em https://emailjs.com
 *   2. Adicione um serviço de e-mail (Gmail, Outlook etc.)
 *   3. Crie um template com as variáveis abaixo
 *   4. Cole as chaves nas constantes abaixo
 *
 * Variáveis disponíveis no template EmailJS:
 *   {{to_name}}    — nome completo do usuário
 *   {{to_email}}   — e-mail do usuário
 *   {{username}}   — username escolhido
 *   {{app_name}}   — nome do app (PROF_NAME)
 *   {{login_url}}  — URL de login
 */
const PAV_EMAILJS = {
  publicKey:  '',   // ← ex: 'abc123XYZ'
  serviceId:  '',   // ← ex: 'service_tati01'
  templateId: '',   // ← ex: 'template_welcome'
};

/**
 * Envia e-mail de boas-vindas ao criar conta.
 * Se as credenciais não estiverem preenchidas, chama o callback diretamente.
 *
 * @param {string}   name       Nome completo do usuário
 * @param {string}   email      E-mail do usuário
 * @param {string}   username   Username escolhido
 * @param {string}   appName    Nome do app/professora
 * @param {Function} callback   Função chamada após envio (sucesso ou falha)
 */
function pavSendWelcomeEmail(name, email, username, appName, callback) {
  if (!PAV_EMAILJS.publicKey || !PAV_EMAILJS.serviceId || !PAV_EMAILJS.templateId) {
    // Credenciais não configuradas — pula o e-mail
    if (typeof callback === 'function') callback();
    return;
  }

  // Carrega o SDK do EmailJS dinamicamente
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/@emailjs/browser@4/dist/email.min.js';

  script.onload = () => {
    try {
      emailjs.init(PAV_EMAILJS.publicKey);
      emailjs.send(PAV_EMAILJS.serviceId, PAV_EMAILJS.templateId, {
        to_name:   name,
        to_email:  email,
        username:  username,
        app_name:  appName,
        login_url: window.location.origin,
      })
        .then(() => {
          console.log('[PAV] E-mail de boas-vindas enviado para', email);
          if (typeof callback === 'function') callback();
        })
        .catch(err => {
          console.warn('[PAV] Falha ao enviar e-mail:', err);
          if (typeof callback === 'function') callback(); // falha silenciosa
        });
    } catch (err) {
      console.warn('[PAV] EmailJS init falhou:', err);
      if (typeof callback === 'function') callback();
    }
  };

  script.onerror = () => {
    console.warn('[PAV] Não foi possível carregar EmailJS SDK');
    if (typeof callback === 'function') callback();
  };

  document.head.appendChild(script);
}

/* ════════════════════════════════════════════════════════════════════════════
   6. LOGIN FORM — lógica do formulário (para uso no iframe do login)
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Alterna visibilidade de senha.
 * @param {string} inputId  ID do input de senha
 * @param {HTMLElement} btn Botão do olho
 */
function pavTogglePw(inputId, btn) {
  const el = document.getElementById(inputId);
  if (!el) return;
  el.type = el.type === 'password' ? 'text' : 'password';
  btn.textContent = el.type === 'password' ? '👁' : '🙈';
}

/**
 * Sanitiza o campo username — apenas letras minúsculas, números, . _ -
 * @param {HTMLInputElement} el
 */
function pavSanitizeUsername(el) {
  el.value = el.value.toLowerCase().replace(/[^a-z0-9._-]/g, '');
}

/**
 * Atualiza a barra de força de senha.
 * @param {string} value  Valor atual do campo de senha
 */
function pavCheckPasswordStrength(value) {
  const sf = document.getElementById('sf');
  const st = document.getElementById('st');
  if (!sf || !st) return;

  let score = 0;
  if (value.length >= 6)            score++;
  if (value.length >= 10)           score++;
  if (/[A-Z]/.test(value))          score++;
  if (/[0-9]/.test(value))          score++;
  if (/[^A-Za-z0-9]/.test(value))   score++;

  const levels = [
    { pct:  0, color: '',         label: '' },
    { pct: 20, color: '#f85149',  label: 'Muito fraca' },
    { pct: 40, color: '#e05c2a',  label: 'Fraca' },
    { pct: 60, color: '#f0a500',  label: 'Razoável' },
    { pct: 80, color: '#3fb950',  label: 'Forte' },
    { pct: 100, color: '#3fb950', label: 'Muito forte' },
  ];

  const { pct, color, label } = levels[Math.min(score, 5)];
  sf.style.width      = pct + '%';
  sf.style.background = color;
  st.textContent      = label;
  st.style.color      = color;
}

/**
 * Comunica com o Python via query params (substitui form submit).
 * @param {Object} params  Pares chave-valor para os query params
 */
function pavSetQueryParams(params) {
  const url = new URL(window.parent.location.href);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  window.parent.location.replace(url.toString());
}

/**
 * Alterna entre as abas Login / Criar Conta.
 * @param {'login'|'reg'} tab
 */
function pavShowTab(tab) {
  const formLogin = document.getElementById('formLogin');
  const formReg   = document.getElementById('formReg');
  const tabLogin  = document.getElementById('tabLogin');
  const tabReg    = document.getElementById('tabReg');
  const loginMsg  = document.getElementById('loginMsg');
  const regMsg    = document.getElementById('regMsg');

  if (!formLogin) return;

  formLogin.classList.toggle('show', tab === 'login');
  formReg.classList.toggle('show',   tab === 'reg');
  tabLogin.classList.toggle('active', tab === 'login');
  tabReg.classList.toggle('active',   tab === 'reg');
  if (loginMsg) loginMsg.className = 'msg';
  if (regMsg)   regMsg.className   = 'msg';
}

/**
 * Executa o login — valida campos e envia via query params.
 */
function pavDoLogin() {
  const u   = document.getElementById('liU')?.value.trim() || '';
  const p   = document.getElementById('liP')?.value || '';
  const msg = document.getElementById('loginMsg');

  if (!u || !p) {
    if (msg) { msg.className = 'msg err'; msg.textContent = 'Preencha todos os campos.'; }
    return;
  }
  pavSetQueryParams({ _login_u: u, _login_p: p });
}

/**
 * Executa o registro — valida, envia e-mail e cria conta via query params.
 * @param {string} appName  Nome do app para o e-mail de boas-vindas
 */
function pavDoRegister(appName) {
  const n   = document.getElementById('rN')?.value.trim() || '';
  const e   = document.getElementById('rE')?.value.trim() || '';
  const u   = document.getElementById('rU')?.value.trim() || '';
  const p   = document.getElementById('rP')?.value || '';
  const msg = document.getElementById('regMsg');

  if (!n || !e || !u || !p) {
    if (msg) { msg.className = 'msg err'; msg.textContent = 'Preencha todos os campos.'; }
    return;
  }
  if (!e.includes('@')) {
    if (msg) { msg.className = 'msg err'; msg.textContent = 'E-mail inválido.'; }
    return;
  }
  if (p.length < 6) {
    if (msg) { msg.className = 'msg err'; msg.textContent = 'Senha muito curta (mínimo 6 caracteres).'; }
    return;
  }

  // Envia e-mail antes de criar conta (falha silenciosa)
  pavSendWelcomeEmail(n, e, u, appName, () => {
    pavSetQueryParams({ _reg_u: u, _reg_n: n, _reg_p: p, _reg_e: e });
  });
}

/* ════════════════════════════════════════════════════════════════════════════
   7. VOICE MODE — MediaRecorder + VAD + upload para Whisper
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Módulo do Modo Conversa.
 * Encapsula todo o estado de gravação/VAD/upload num objeto para evitar
 * poluição do escopo global quando o iframe recarrega.
 *
 * NOTA: Este módulo é instanciado pelo código inline do iframe no app.py,
 * que injeta os dados dinâmicos do Python (PY_REPLY, PY_TTS_B64, etc.).
 * As funções aqui são a versão "pura" sem dados dinâmicos.
 */
const PavVoiceMode = (() => {
  // ── Configuração ──────────────────────────────────────────────────────────
  const SILENCE_MS = 1500;
  const MIN_DB     = -42;

  // ── Estado ────────────────────────────────────────────────────────────────
  let mediaRec  = null;
  let chunks    = [];
  let audioCtx  = null;
  let analyser  = null;
  let micStream = null;
  let isRec     = false;
  let isSpeaking = false;
  let vadActive = false;
  let speechHit = false;
  let silTimer  = null;
  let silStart  = null;
  let curAudio  = null;

  // ── DOM refs (preenchidos em init) ────────────────────────────────────────
  let dom = {};

  // ── UI helpers ─────────────────────────────────────────────────────────────
  function setRing(state) {
    if (!dom.ring) return;
    dom.ring.className  = 'ring ' + state;
    dom.ringW.className = 'ring-wrap ' + state;
    dom.vm.className    = 'vm ' + state;
  }

  function setStatus(text, cls = '') {
    if (!dom.status) return;
    dom.status.textContent = text;
    dom.status.className   = 'status ' + cls;
  }

  function showErr(msg) {
    if (!dom.errBox) return;
    dom.errBox.textContent = msg;
    setTimeout(() => { dom.errBox.textContent = ''; }, 5000);
  }

  function showSil(pct) {
    if (!dom.sil) return;
    dom.sil.classList.add('show');
    dom.silFill.style.width = pct + '%';
  }

  function hideSil() {
    if (!dom.sil) return;
    dom.sil.classList.remove('show');
    dom.silFill.style.width = '0%';
  }

  function showTranscript(userSaid, aiReply) {
    if (!dom.tWait) return;
    dom.tWait.style.display = 'none';
    if (userSaid) {
      dom.tLabel.textContent  = 'Você disse:';
      dom.tUser.textContent   = userSaid;
      dom.tUser.style.display = 'block';
    }
    if (aiReply) {
      dom.tSep.style.display  = 'block';
      dom.tAi.textContent     = aiReply;
      dom.tAi.style.display   = 'block';
    }
  }

  // ── VAD (Voice Activity Detection) ─────────────────────────────────────────
  function getRMS() {
    if (!analyser) return -100;
    const data = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    const rms = Math.sqrt(sum / data.length);
    return rms > 0 ? 20 * Math.log10(rms) : -100;
  }

  function runVAD() {
    if (!vadActive) return;
    const loud = getRMS() > MIN_DB;

    if (loud) {
      speechHit = true;
      clearTimeout(silTimer);
      silStart = null;
      hideSil();
      // Barge-in: interrompe TTS se o usuário começar a falar
      if (isSpeaking && curAudio) {
        curAudio.pause();
        curAudio  = null;
        isSpeaking = false;
      }
    } else if (speechHit) {
      if (!silStart) { silStart = Date.now(); animateSilence(); }
      clearTimeout(silTimer);
      silTimer = setTimeout(() => {
        if (vadActive && speechHit) {
          vadActive  = false;
          speechHit  = false;
          mediaRec.stop();
          setRing('processing');
          setStatus('Processando...', 's-processing');
          if (dom.tLabel) dom.tLabel.textContent = 'Transcrevendo...';
        }
      }, SILENCE_MS);
    }

    requestAnimationFrame(runVAD);
  }

  function animateSilence() {
    if (!silStart) return;
    const pct = Math.min((Date.now() - silStart) / SILENCE_MS * 100, 100);
    showSil(pct);
    if (pct < 100 && silStart) requestAnimationFrame(animateSilence);
  }

  // ── Gravação ────────────────────────────────────────────────────────────────
  async function startRecording() {
    if (isRec) return;

    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 }
      });
    } catch (e) {
      showErr('Permissão de microfone negada. Verifique as configurações do browser.');
      return;
    }

    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    audioCtx.createMediaStreamSource(micStream).connect(analyser);

    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg']
      .find(m => MediaRecorder.isTypeSupported(m)) || '';

    try {
      mediaRec = new MediaRecorder(micStream, mime ? { mimeType: mime } : {});
    } catch (e) {
      mediaRec = new MediaRecorder(micStream); // fallback sem options
    }

    chunks = [];
    mediaRec.ondataavailable = e => { if (e.data && e.data.size > 0) chunks.push(e.data); };
    mediaRec.onstop          = () => uploadAudio(new Blob(chunks, { type: mediaRec.mimeType || 'audio/webm' }));
    mediaRec.onerror         = e => { showErr('Erro na gravação: ' + e.error); resetToIdle(); };
    mediaRec.start(100);

    isRec     = true;
    vadActive = true;
    speechHit = false;

    if (dom.micBtn) { dom.micBtn.classList.add('active'); dom.micBtn.textContent = '⏹'; }
    setRing('listening');
    setStatus('Ouvindo...', 's-listening');

    if (dom.tWait) { dom.tWait.style.display = 'block'; dom.tWait.textContent = '—'; }
    if (dom.tUser) dom.tUser.style.display = 'none';
    if (dom.tSep)  dom.tSep.style.display  = 'none';
    if (dom.tAi)   dom.tAi.style.display   = 'none';
    if (dom.tLabel) dom.tLabel.textContent  = 'Aguardando sua fala...';

    runVAD();
  }

  function stopRecording() {
    vadActive = false;
    isRec     = false;
    speechHit = false;
    clearTimeout(silTimer);
    silStart = null;
    hideSil();

    if (mediaRec && mediaRec.state !== 'inactive') {
      try { mediaRec.stop(); } catch (e) {}
    }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    if (audioCtx)  { try { audioCtx.close(); } catch (e) {} audioCtx = null; analyser = null; }

    if (dom.micBtn) { dom.micBtn.classList.remove('active'); dom.micBtn.textContent = '🎤'; }
  }

  // ── Upload do áudio para o Streamlit ───────────────────────────────────────
  function uploadAudio(blob) {
    if (blob.size < 1500) { resetToIdle(); return; }

    // Injeta CSS de ocultação visual (SEM pointer-events:none)
    pavHideVoiceUploader();

    // Retry até 8× aguardando o DOM montar
    function tryInject(attempt) {
      const par = window.parent.document;
      let input = par.querySelector('[data-testid="stFileUploader"] input[type="file"]')
               || par.querySelector('[data-testid="stFileUploaderDropzone"] input[type="file"]')
               || Array.from(par.querySelectorAll('input[type="file"]'))
                       .find(i => i.accept && i.accept.includes('webm'));

      if (!input) {
        if (attempt < 8) { setTimeout(() => tryInject(attempt + 1), 300); return; }
        showErr('Input de microfone não encontrado — recarregue a página.');
        resetToIdle();
        return;
      }

      // Garante pointer-events ativos no input e pai
      input.style.cssText += 'pointer-events:auto!important;';
      if (input.parentElement) input.parentElement.style.pointerEvents = 'auto';

      const ext  = blob.type.includes('ogg') ? 'ogg' : (blob.type.includes('mp4') ? 'mp4' : 'webm');
      const file = new File([blob], `vm_${Date.now()}.${ext}`, { type: blob.type || 'audio/webm' });
      const dt   = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;

      // Dispara change + input para garantir que o Streamlit detecte
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.dispatchEvent(new Event('input',  { bubbles: true }));
    }

    tryInject(0);
  }

  function resetToIdle() {
    stopRecording();
    setRing('idle');
    setStatus('Clique no microfone para continuar', '');
  }

  // ── TTS ─────────────────────────────────────────────────────────────────────
  function playTTS(b64, replyText, speechLang) {
    isSpeaking = true;
    setRing('speaking');
    setStatus('Professora falando...', 's-speaking');

    if (b64 && b64.length > 20) {
      curAudio = new Audio('data:audio/mpeg;base64,' + b64);
      curAudio.onended = () => { isSpeaking = false; curAudio = null; resetToIdle(); startRecording(); };
      curAudio.onerror = () => { isSpeaking = false; curAudio = null; fallbackTTS(replyText, speechLang); };
      curAudio.play().catch(() => fallbackTTS(replyText, speechLang));
    } else {
      fallbackTTS(replyText, speechLang);
    }
  }

  function fallbackTTS(text, speechLang) {
    isSpeaking = true;
    setRing('speaking');
    setStatus('Professora falando...', 's-speaking');

    const u = new SpeechSynthesisUtterance(text.substring(0, 500));
    u.lang  = speechLang || 'en-US';
    u.rate  = 0.95;
    u.pitch = 1.05;

    const voices = speechSynthesis.getVoices();
    const pick   = voices.find(v => v.lang === u.lang)
                || voices.find(v => v.lang.startsWith(u.lang.split('-')[0]));
    if (pick) u.voice = pick;

    u.onend = u.onerror = () => { isSpeaking = false; resetToIdle(); startRecording(); };
    speechSynthesis.speak(u);
  }

  // ── API pública ─────────────────────────────────────────────────────────────
  return {
    /**
     * Inicializa o módulo com referências ao DOM.
     * Chamado pelo inline script do iframe após o DOM carregar.
     */
    init(domRefs) {
      dom = domRefs;
    },

    start:     startRecording,
    stop:      stopRecording,
    resetIdle: resetToIdle,
    playTTS,
    showTranscript,
    showErr,

    get isRecording() { return isRec; },
    get isSpeaking()  { return isSpeaking; },
  };
})();

/* ════════════════════════════════════════════════════════════════════════════
   8. AUDIO PLAYER — lógica do mini-player nas mensagens
   ════════════════════════════════════════════════════════════════════════════ */

/**
 * Inicializa um player de áudio embutido numa mensagem.
 * Chamado pelo código inline do iframe render_audio_player().
 *
 * @param {string} audioSrc  Data URI do áudio (audio/mpeg base64)
 */
function pavInitAudioPlayer(audioSrc) {
  const audio  = new Audio(audioSrc);
  const b      = document.getElementById('b');
  const pf     = document.getElementById('pf');
  const pw     = document.getElementById('pw');
  const vs     = document.getElementById('vs');
  const vi     = document.getElementById('vi');
  const sw     = document.getElementById('sw');

  if (!b) return;

  // Play / Pause
  b.onclick = () => {
    if (!audio.paused) { audio.pause(); b.textContent = '▶ Ouvir'; }
    else               { audio.play();  b.textContent = '⏸ Pausar'; }
  };

  audio.onended      = () => { b.textContent = '▶ Ouvir'; pf.style.width = '0%'; };
  audio.ontimeupdate = () => {
    if (audio.duration) pf.style.width = (audio.currentTime / audio.duration * 100) + '%';
  };

  // Seek
  pw.onclick = e => {
    const rect = pw.getBoundingClientRect();
    audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
  };

  // Velocidade
  sw.querySelectorAll('.sb').forEach(btn => {
    btn.onclick = function () {
      sw.querySelectorAll('.sb').forEach(x => x.classList.remove('on'));
      this.classList.add('on');
      audio.playbackRate = parseFloat(this.dataset.r);
    };
  });

  // Volume
  vs.oninput = () => {
    audio.volume = parseFloat(vs.value);
    vi.textContent = audio.volume === 0 ? '🔇' : audio.volume < 0.5 ? '🔉' : '🔊';
  };

  // Mute toggle
  vi.onclick = () => {
    if (audio.volume > 0) {
      audio._savedVol = audio.volume;
      audio.volume    = 0;
      vs.value        = 0;
      vi.textContent  = '🔇';
    } else {
      audio.volume   = audio._savedVol || 1;
      vs.value       = audio.volume;
      vi.textContent = '🔊';
    }
  };
}