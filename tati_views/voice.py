"""
tati_views/voice.py — Teacher Tati · Modo Voz imersivo.

Avatar animado com 7 frames, sincronização labial por volume de áudio,
microfone acionado via st.audio_input oculto, histórico em bolhas.
Idêntico ao modo voz do projeto tati_2.
"""

import json
import base64

import streamlit as st
import streamlit.components.v1 as components
import anthropic

from database import append_message, new_conversation
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from ui_helpers import (
    PROF_NAME, API_KEY, SYSTEM_PROMPT,
    get_tati_mini_b64, get_avatar_frames, t,
)


# ── Wav2Lip opcional ──────────────────────────────────────────────────────────
try:
    from wav2lip_avatar import generate_talking_video, wav2lip_available
    _WAV2LIP_LOADED = True
except ImportError:
    _WAV2LIP_LOADED = False
    def wav2lip_available(): return False
    def generate_talking_video(_): return None


def get_or_create_conv(username: str) -> str:
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id


# ══════════════════════════════════════════════════════════════════════════════
# PROCESSAMENTO DE ÁUDIO
# ══════════════════════════════════════════════════════════════════════════════

def _vm_process_audio(raw: bytes, lang: str, conv_id: str) -> None:
    txt = transcribe_bytes(raw, suffix=".webm", language=None)
    if not txt or txt.startswith("❌") or txt.startswith("⚠️"):
        st.session_state["_vm_error"] = txt or "Não entendi. Tente novamente."
        return

    st.session_state["_vm_user_said"] = txt
    if not API_KEY:
        st.session_state["_vm_error"] = "❌ ANTHROPIC_API_KEY não configurada."
        return

    user     = st.session_state.user
    username = user["username"]
    history  = st.session_state.get("_vm_history", [])
    context  = (
        f"\n\nStudent profile — Name: {user['name']} | "
        f"Level: {user['level']} | Focus: {user['focus']} | "
        f"Native language: Brazilian Portuguese.\n"
        f"Apply the bilingual policy for level '{user['level']}' as instructed."
    )

    history.append({"role": "user", "content": txt})
    client = anthropic.Anthropic(api_key=API_KEY)
    resp   = client.messages.create(
        model="claude-haiku-4-5", max_tokens=1000,
        system=SYSTEM_PROMPT + context, messages=history,
    )
    reply = resp.content[0].text
    history.append({"role": "assistant", "content": reply})
    st.session_state["_vm_history"] = history

    tts_b64   = ""
    tts_bytes = None
    if tts_available():
        ab = text_to_speech(reply)
        if ab:
            tts_bytes = ab
            tts_b64   = base64.b64encode(ab).decode()

    st.session_state["_vm_reply"]   = reply
    st.session_state["_vm_tts_b64"] = tts_b64

    st.session_state["_vm_video_b64"] = ""
    if _WAV2LIP_LOADED and wav2lip_available() and tts_bytes:
        video_b64 = generate_talking_video(tts_bytes)
        if video_b64:
            st.session_state["_vm_video_b64"] = video_b64

    append_message(username, conv_id, "user",      txt,   audio=True)
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64 or None)


# ══════════════════════════════════════════════════════════════════════════════
# MODO VOZ PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def show_voice_mode() -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang         = profile.get("language",    "pt-BR")
    whisper_lang    = profile.get("voice_lang",  "en")
    speech_lang_val = profile.get("speech_lang", "en-US")
    accent_color    = profile.get("accent_color", "#f0a500")

    conv_id = get_or_create_conv(username)

    # Botão fechar — oculto, acionado pelo JS do iframe
    if st.button(t("close_voice", ui_lang), key="close_voice_inner"):
        st.session_state.voice_mode = False
        for k in ["_vm_history", "_vm_reply", "_vm_tts_b64", "_vm_user_said",
                  "_vm_error", "_vm_last_upload", "_vm_video_b64", "_vm_audio_key"]:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("""<style>
[data-testid="stMain"] button { display:none!important; }
[data-testid="stSidebar"]     { display:none!important; }
[data-testid="stHeader"]      { display:none!important; }
[data-testid="stToolbar"]     { display:none!important; }
footer { display:none!important; }
.main .block-container { padding:0!important; max-width:100%!important; }
section[data-testid="stMain"] > div { padding:0!important; }
[data-testid="stAudioInput"] {
    position:fixed!important; bottom:-200px!important; left:-200px!important;
    opacity:0!important; pointer-events:none!important;
    width:1px!important; height:1px!important;
}
</style>""", unsafe_allow_html=True)

    # ── Processa áudio ────────────────────────────────────────────────────────
    if "_vm_audio_key" not in st.session_state:
        st.session_state["_vm_audio_key"] = 0

    audio_val = st.audio_input(
        " ", key=f"vm_audio_{st.session_state['_vm_audio_key']}",
        label_visibility="collapsed",
    )
    if audio_val and audio_val != st.session_state.get("_vm_last_upload"):
        st.session_state["_vm_last_upload"] = audio_val
        for k in ["_vm_reply", "_vm_tts_b64", "_vm_user_said", "_vm_error", "_vm_video_b64"]:
            st.session_state.pop(k, None)
        _vm_process_audio(audio_val.read(), whisper_lang, conv_id)
        st.session_state["_vm_audio_key"] += 1
        st.rerun()

    # ── Estado ────────────────────────────────────────────────────────────────
    user_said = st.session_state.get("_vm_user_said", "")
    reply     = st.session_state.get("_vm_reply",     "")
    tts_b64   = st.session_state.get("_vm_tts_b64",   "")
    video_b64 = st.session_state.get("_vm_video_b64", "")
    vm_error  = st.session_state.get("_vm_error",     "")
    history   = st.session_state.get("_vm_history",   [])

    # ── Avatar — 7 frames ─────────────────────────────────────────────────────
    photo_src = get_tati_mini_b64()
    _frames   = get_avatar_frames()
    av_base     = _frames.get("base",    "")
    av_closed   = _frames.get("closed",  "")
    av_mid      = _frames.get("mid",     "")
    av_open     = _frames.get("open",    "")
    av_smile    = _frames.get("smile",   "")
    av_wink     = _frames.get("wink",    "")
    av_surprise = _frames.get("surprise","")

    is_speaking   = bool(reply)
    is_processing = bool(user_said and not reply and not vm_error)

    # Serializa para JS
    tts_js        = json.dumps(tts_b64)
    video_js      = json.dumps(video_b64)
    reply_js      = json.dumps(reply)
    us_js         = json.dumps(user_said)
    err_js        = json.dumps(vm_error)
    sl_js         = json.dumps(speech_lang_val)
    photo_js      = json.dumps(photo_src)
    av_base_js    = json.dumps(av_base)
    av_closed_js  = json.dumps(av_closed)
    av_mid_js     = json.dumps(av_mid)
    av_open_js    = json.dumps(av_open)
    av_smile_js   = json.dumps(av_smile)
    av_wink_js    = json.dumps(av_wink)
    av_surprise_js= json.dumps(av_surprise)
    accent_js     = json.dumps(accent_color)
    pnm_js        = json.dumps(PROF_NAME)

    js_speaking   = json.dumps(t("speaking",     ui_lang))
    js_listening  = json.dumps(t("listening",    ui_lang))
    js_processing = json.dumps(t("processing",   ui_lang))
    js_tap_speak  = json.dumps(t("tap_to_speak", ui_lang))
    js_tap_record = json.dumps(t("tap_to_record",ui_lang))
    js_tap_stop   = json.dumps(t("tap_to_stop",  ui_lang))
    js_wait       = json.dumps(t("wait",         ui_lang))
    js_close      = json.dumps(t("close",        ui_lang))

    # ── Bolhas do histórico ───────────────────────────────────────────────────
    bubbles_html = ""
    msgs = history[:-2] if (reply and len(history) >= 2) else history
    for m in msgs:
        txt = m["content"].replace("<","&lt;").replace(">","&gt;")
        css = "user-bubble" if m["role"] == "user" else "ai-bubble"
        bubbles_html += f'<div class="bubble {css}">{txt}</div>'
    if user_said:
        bubbles_html += f'<div class="bubble user-bubble">{user_said.replace("<","&lt;").replace(">","&gt;")}</div>'
    if reply:
        bubbles_html += f'<div class="bubble ai-bubble">{reply.replace("<","&lt;").replace(">","&gt;")}</div>'
    if vm_error:
        bubbles_html += f'<div class="bubble err-bubble">❌ {vm_error}</div>'
    if is_processing:
        bubbles_html += '<div class="bubble ai-bubble typing"><span></span><span></span><span></span></div>'

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{
    background:#080c12;font-family:'Sora',sans-serif;
    color:#e6edf3;height:100vh;overflow:hidden;
    display:flex;flex-direction:column;
}}
.vm-wrap{{
    display:flex;flex-direction:column;height:100vh;
    position:relative;overflow:hidden;
    background:radial-gradient(ellipse at 50% 0%,rgba(240,165,0,.06) 0%,transparent 60%);
}}
.close-btn{{
    position:absolute;top:14px;left:16px;z-index:100;
    background:rgba(255,255,255,.06);border:1px solid #2a3545;
    color:#8b949e;border-radius:8px;padding:6px 14px;
    font-size:.75rem;font-family:'Sora',sans-serif;cursor:pointer;
    transition:all .2s;
}}
.close-btn:hover{{background:rgba(255,255,255,.12);color:#e6edf3;}}

/* ── Avatar ── */
.avatar-section{{
    display:flex;flex-direction:column;align-items:center;
    padding-top:28px;padding-bottom:12px;gap:6px;flex-shrink:0;
    position:sticky;top:0;z-index:10;
    background:linear-gradient(180deg,#080c12 80%,transparent 100%);
}}
.avatar-outer{{
    position:relative;width:220px;height:220px;
    display:flex;align-items:center;justify-content:center;
}}
.wave{{
    position:absolute;border-radius:50%;border:2px solid rgba(240,165,0,0);
    width:100%;height:100%;transition:border-color .4s;
}}
.speaking .wave:nth-child(1){{animation:wave1 1.4s ease-out infinite;}}
.speaking .wave:nth-child(2){{animation:wave1 1.4s ease-out infinite .35s;}}
.speaking .wave:nth-child(3){{animation:wave1 1.4s ease-out infinite .7s;}}
@keyframes wave1{{
    0%  {{transform:scale(1);   border-color:var(--accent-70);opacity:1;}}
    100%{{transform:scale(1.55);border-color:transparent;     opacity:0;}}
}}
.avatar-ring{{
    width:200px;height:200px;border-radius:50%;overflow:hidden;
    box-shadow:0 0 0 3px var(--accent-30),0 0 20px var(--accent-15);
    transition:box-shadow .4s;position:relative;z-index:2;flex-shrink:0;
}}
.speaking .avatar-ring{{
    box-shadow:0 0 0 4px var(--accent-full),0 0 40px var(--accent-40);
}}
.avatar-ring img{{width:100%;height:100%;object-fit:cover;object-position:top center;}}
.avatar-ring .emoji{{
    width:100%;height:100%;display:flex;align-items:center;
    justify-content:center;font-size:60px;background:#0f1824;
}}
.av-name{{color:#e6edf3;font-weight:700;font-size:.95rem;}}
.av-status{{color:#8b949e;font-size:.72rem;min-height:18px;letter-spacing:.3px;}}

/* ── Mensagens ── */
.messages{{
    flex:1;overflow-y:auto;padding:16px 20px 12px;
    display:flex;flex-direction:column;gap:10px;
    scrollbar-width:thin;scrollbar-color:#1e2530 transparent;
}}
.messages::-webkit-scrollbar{{width:4px;}}
.messages::-webkit-scrollbar-track{{background:transparent;}}
.messages::-webkit-scrollbar-thumb{{background:#1e2530;border-radius:4px;}}
.bubble{{
    max-width:62%;padding:10px 14px;border-radius:18px;
    font-size:.86rem;line-height:1.55;word-break:break-word;
}}
.user-bubble{{
    align-self:flex-end;
    background:var(--bubble-bg);border:1px solid var(--bubble-border);
    color:var(--bubble-text);border-bottom-right-radius:4px;
}}
.ai-bubble{{
    align-self:flex-start;
    background:#0f1824;border:1px solid #1e2d40;
    color:#e6edf3;border-bottom-left-radius:4px;
}}
.err-bubble{{
    align-self:center;background:rgba(248,81,73,.1);
    border:1px solid rgba(248,81,73,.3);color:#f85149;
    border-radius:10px;font-size:.78rem;
}}
.typing{{display:flex;align-items:center;gap:5px;padding:12px 16px!important;}}
.typing span{{
    width:7px;height:7px;border-radius:50%;background:#f0a500;opacity:.4;
    animation:tdot 1.1s ease-in-out infinite;
}}
.typing span:nth-child(2){{animation-delay:.18s;}}
.typing span:nth-child(3){{animation-delay:.36s;}}
@keyframes tdot{{
    0%,80%,100%{{transform:scale(.7);opacity:.3;}}
    40%{{transform:scale(1.1);opacity:1;}}
}}

/* ── Barra inferior ── */
.bottom-bar{{
    display:flex;align-items:center;justify-content:center;
    padding:14px 24px 20px;gap:20px;flex-shrink:0;
    border-top:1px solid #0f1419;
}}
.mic-icon-btn{{
    width:58px;height:58px;border-radius:50%;border:none;cursor:pointer;
    display:flex;align-items:center;justify-content:center;font-size:22px;
    background:linear-gradient(135deg,#3fb950,#2ea043);
    box-shadow:0 0 20px rgba(63,185,80,.3);color:#fff;transition:all .25s;
}}
.mic-icon-btn:hover{{transform:scale(1.08);}}
.mic-icon-btn.recording{{
    background:linear-gradient(135deg,#f85149,#c03030);
    box-shadow:0 0 28px rgba(248,81,73,.5);
    animation:micpulse .8s ease-in-out infinite alternate;
}}
.mic-icon-btn.processing{{
    background:linear-gradient(135deg,#58a6ff,#1f6feb);
    box-shadow:0 0 20px rgba(88,166,255,.3);
    animation:none;cursor:default;
}}
@keyframes micpulse{{
    from{{box-shadow:0 0 14px rgba(248,81,73,.3);}}
    to  {{box-shadow:0 0 36px rgba(248,81,73,.8);}}
}}
.hint-text{{color:#2d3a4a;font-size:.65rem;text-align:center;}}
</style>
</head>
<body>
<div class="vm-wrap">
  <button class="close-btn" onclick="closeModeVoz()">Fechar</button>

  <div class="avatar-section">
    <div class="avatar-outer {'speaking' if is_speaking else ''}" id="avOuter">
      <div class="wave"></div><div class="wave"></div><div class="wave"></div>
      <div class="avatar-ring" id="avatarRing">
        <img id="avImg" src="" alt="Tati"
             style="width:100%;height:100%;object-fit:cover;object-position:top;">
      </div>
    </div>
    <div class="av-name">{PROF_NAME}</div>
    <div class="av-status" id="avStatus">
        {"🗣 Falando..." if is_speaking else "Toque no microfone para falar"}
    </div>
  </div>

  <div class="messages" id="messages">{bubbles_html}</div>

  <div class="bottom-bar">
    <div>
      <button class="mic-icon-btn" id="micBtn" onclick="toggleMic()">
        <i class="fa-solid fa-microphone" id="micIcon"></i>
      </button>
      <div class="hint-text" id="hintText">Toque para gravar</div>
    </div>
  </div>
</div>

<script>
const TTS_B64     = {tts_js};
const VIDEO_B64   = {video_js};
const REPLY_TEXT  = {reply_js};
const USER_SAID   = {us_js};
const VM_ERROR    = {err_js};
const SPEECH_LANG = {sl_js};
const PHOTO_SRC   = {photo_js};
const AV_BASE     = {av_base_js};
const AV_CLOSED   = {av_closed_js};
const AV_MID      = {av_mid_js};
const AV_OPEN     = {av_open_js};
const AV_SMILE    = {av_smile_js};
const AV_WINK     = {av_wink_js};
const AV_SURPRISE = {av_surprise_js};
const ACCENT      = {accent_js};
const PROF_NAME   = {pnm_js};

const STR_SPEAKING  = {js_speaking};
const STR_LISTENING = {js_listening};
const STR_PROCESSING= {js_processing};
const STR_TAP_SPEAK = {js_tap_speak};
const STR_TAP_RECORD= {js_tap_record};
const STR_TAP_STOP  = {js_tap_stop};
const STR_WAIT      = {js_wait};
const STR_CLOSE     = {js_close};

// CSS vars dinâmicas
(function(){{
    function hexToRgb(h){{
        h=h.replace('#','');
        if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
        const n=parseInt(h,16);
        return [(n>>16)&255,(n>>8)&255,n&255].join(',');
    }}
    const rgb=hexToRgb(ACCENT||'#f0a500');
    const r=document.documentElement;
    r.style.setProperty('--accent-full',ACCENT||'#f0a500');
    r.style.setProperty('--accent-70',`rgba(${{rgb}},.7)`);
    r.style.setProperty('--accent-40',`rgba(${{rgb}},.4)`);
    r.style.setProperty('--accent-30',`rgba(${{rgb}},.3)`);
    r.style.setProperty('--accent-15',`rgba(${{rgb}},.15)`);
    r.style.setProperty('--bubble-bg',    `rgba(${{rgb}},.12)`);
    r.style.setProperty('--bubble-border',`rgba(${{rgb}},.3)`);
    r.style.setProperty('--bubble-text',  '#e6edf3');
}})();

document.querySelector('.close-btn').textContent = STR_CLOSE;

const msgEl   = document.getElementById('messages');
const avOuter = document.getElementById('avOuter');
const avStatus= document.getElementById('avStatus');
const micBtn  = document.getElementById('micBtn');
const micIcon = document.getElementById('micIcon');
const hintText= document.getElementById('hintText');
const avImg   = document.getElementById('avImg');

// Scroll ao fundo
function scrollBottom(){{ msgEl.scrollTop=msgEl.scrollHeight; }}
scrollBottom();

// Init avatar — revela após carregamento
(function(){{
    const ring=document.getElementById('avatarRing');
    ring.style.opacity='0';ring.style.transition='opacity .3s';
    avImg.onload=function(){{ring.style.opacity='1';}};
    if(AV_BASE)avImg.src=AV_BASE;
    else if(PHOTO_SRC)avImg.src=PHOTO_SRC;
}})();

// Estado do avatar
function setAvatarState(state){{
    avOuter.classList.remove('speaking');
    micBtn.classList.remove('recording','processing');
    if(state==='speaking'){{
        avOuter.classList.add('speaking');
        avStatus.textContent=STR_SPEAKING;
        micBtn.classList.add('processing');
        micIcon.className='fa-solid fa-volume-high';
        hintText.textContent=STR_WAIT;
    }} else if(state==='recording'){{
        avStatus.textContent=STR_LISTENING;
        micBtn.classList.add('recording');
        micIcon.className='fa-solid fa-stop';
        hintText.textContent=STR_TAP_STOP;
    }} else if(state==='processing'){{
        avStatus.textContent=STR_PROCESSING;
        micBtn.classList.add('processing');
        micIcon.className='fa-solid fa-spinner fa-spin';
        hintText.textContent=STR_WAIT;
    }} else {{
        avStatus.textContent=STR_TAP_SPEAK;
        micIcon.className='fa-solid fa-microphone';
        hintText.textContent=STR_TAP_RECORD;
    }}
}}

// ── Animação labial com 7 frames ──────────────────────────────────────────────
let _avAnimFrame=null;

function stopMouthAnim(){{
    if(_avAnimFrame){{cancelAnimationFrame(_avAnimFrame);_avAnimFrame=null;}}
    if(AV_CLOSED)avImg.src=AV_CLOSED;
    else if(AV_BASE)avImg.src=AV_BASE;
}}

function startMouthAnim(audioEl){{
    stopMouthAnim();
    if(!AV_CLOSED||!AV_MID||!AV_OPEN)return;
    let ctx,analyser,source;
    try{{
        ctx=new(window.AudioContext||window.webkitAudioContext)();
        analyser=ctx.createAnalyser();analyser.fftSize=256;
        source=ctx.createMediaElementSource(audioEl);
        source.connect(analyser);analyser.connect(ctx.destination);
    }}catch(e){{return;}}
    const data=new Uint8Array(analyser.frequencyBinCount);
    let lastSrc='',frameCount=0,smileShown=false;

    function loop(){{
        _avAnimFrame=requestAnimationFrame(loop);
        frameCount++;if(frameCount%3!==0)return; // ~20fps
        analyser.getByteFrequencyData(data);
        const vol=data.slice(0,16).reduce((a,b)=>a+b,0)/16;
        const progress=audioEl.duration?audioEl.currentTime/audioEl.duration:0;
        let src;
        // No início da fala → surpresa; no final → sorriso
        if(progress<0.08&&AV_SURPRISE){{src=AV_SURPRISE;}}
        else if(progress>0.90&&AV_SMILE){{src=AV_SMILE;}}
        else if(vol<8)  {{src=AV_CLOSED;}}
        else if(vol<25) {{src=AV_MID;}}
        else            {{src=AV_OPEN;}}
        if(src!==lastSrc){{avImg.src=src;lastSrc=src;}}
    }}
    loop();
}}

// ── TTS autoplay ──────────────────────────────────────────────────────────────
function playTTSAuto(b64,text){{
    setAvatarState('speaking');
    if(b64&&b64.length>20){{
        const audio=new Audio('data:audio/mpeg;base64,'+b64);
        startMouthAnim(audio);
        audio.onended=()=>{{stopMouthAnim();setAvatarState('idle');}};
        audio.onerror=()=>{{stopMouthAnim();fallbackSpeech(text);}};
        audio.play().catch(()=>{{stopMouthAnim();fallbackSpeech(text);}});
    }} else {{
        fallbackSpeech(text);
    }}
}}

function fallbackSpeech(text){{
    const u=new SpeechSynthesisUtterance((text||'').substring(0,500));
    u.lang=SPEECH_LANG;u.rate=0.95;u.pitch=1.05;
    speechSynthesis.getVoices();
    setTimeout(()=>{{
        const vv=speechSynthesis.getVoices();
        const pick=vv.find(v=>v.lang===SPEECH_LANG)||vv.find(v=>v.lang.startsWith('en'));
        if(pick)u.voice=pick;
        u.onend=u.onerror=()=>setAvatarState('idle');
        speechSynthesis.cancel();speechSynthesis.speak(u);
    }},100);
}}

// ── Mic ───────────────────────────────────────────────────────────────────────
let isRecording=false;

function triggerAudioInput(){{
    const par=window.parent?window.parent.document:document;
    const btn=par.querySelector('[data-testid="stAudioInput"] button')
           ||par.querySelector('[data-testid="stAudioInputRecordButton"]')
           ||par.querySelector('button[title*="ecord"]')
           ||par.querySelector('button[aria-label*="ecord"]');
    if(btn){{btn.click();return true;}}
    return false;
}}

function toggleMic(){{
    if(micBtn.classList.contains('processing'))return;
    if(!isRecording){{
        isRecording=true;setAvatarState('recording');triggerAudioInput();
    }} else {{
        isRecording=false;setAvatarState('processing');
        triggerAudioInput();hintText.textContent=STR_PROCESSING;
    }}
}}

// ── Fechar ────────────────────────────────────────────────────────────────────
function closeModeVoz(){{
    try{{speechSynthesis.cancel();}}catch(e){{}}
    stopMouthAnim();
    const par=window.parent?window.parent.document:document;
    let closeBtn=par.querySelector('[data-testid="stButton"][key="close_voice_inner"] button');
    if(!closeBtn){{
        const btns=Array.from(par.querySelectorAll('button'));
        closeBtn=btns.find(b=>{{
            const txt=b.textContent.trim();
            return txt.includes('Fechar')||txt.includes('Close');
        }});
    }}
    if(!closeBtn)closeBtn=par.querySelector('button');
    if(closeBtn)closeBtn.click();
}}

// ── Auto-play na carga ────────────────────────────────────────────────────────
window.addEventListener('load',()=>{{
    if(REPLY_TEXT&&REPLY_TEXT.length>1){{
        playTTSAuto(TTS_B64,REPLY_TEXT);
    }} else if(USER_SAID&&USER_SAID.length>1){{
        setAvatarState('processing');
    }}
    scrollBottom();
}});
</script>
</body></html>""", height=700, scrolling=False)
