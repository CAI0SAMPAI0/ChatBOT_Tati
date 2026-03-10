"""
pages/voice.py — Tela principal de modo voz.
Melhorias:
  - Histórico renderiza botão ▶ por bolha (com tts_b64 salvo no banco)
  - Menos reruns: só rerun após processar áudio
  - Avatar animado isolado
"""

import base64
import json

import streamlit as st
import streamlit.components.v1 as components
import anthropic

from database import (
    load_conversation,
    new_conversation,
    list_conversations,
    append_message,
)
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from ui_helpers import (
    PROF_NAME,
    get_photo_b64,
    get_tati_mini_b64,
    get_avatar_frames,
    get_or_create_conv,
    t,
)

import os
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} -- warm, witty, very intelligent and encouraging. You help adults speak English with more confidence, over 25 years of experience, Advanced English Hunter College NY, and passionate about teaching.

BILINGUAL POLICY (VERY IMPORTANT)
The student's messages may arrive in English, Portuguese, or a mix.

BEGINNER / PRE-INTERMEDIATE:
  * Student writes/speaks in Portuguese -> Fully acceptable. Respond in simple English
    AND provide the Portuguese translation of key words in parentheses.
  * Always end your reply with an easy, encouraging question in English.

INTERMEDIATE:
  * Respond primarily in English. Use Portuguese ONLY to clarify a specific word.
  * If the student writes in Portuguese, invite them to try in English.

ADVANCED / BUSINESS ENGLISH:
  * Respond exclusively in English.
  * "Let's keep it in English -- you've got this!"

TEACHING STYLE:
- Neuro-learning: guide students to discover errors.
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT conversational responses for voice. Max 3 sentences.
- End with ONE engaging question.
- NO markdown, NO bullet points -- plain natural speech for TTS.
- NEVER start uninvited. Wait for the student to speak first.
- NEVER use EMOTES"""


# =============================================================================
# PROCESSAR ÁUDIO → CLAUDE → TTS
# =============================================================================
def process_voice(raw: bytes, conv_id: str) -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    lang     = profile.get("language", "pt-BR")

    txt = transcribe_bytes(raw, suffix=".webm", language=None)
    if not txt or txt.startswith("❌") or txt.startswith("⚠️"):
        st.session_state["_vm_error"] = txt or t("error_mic", lang)
        return

    st.session_state["_vm_user_said"] = txt
    if not API_KEY:
        st.session_state["_vm_error"] = t("error_api", lang)
        return

    history = st.session_state.get("_vm_history", [])
    context = (
        f"\n\nStudent profile -- Name: {user.get('name','')} | "
        f"Level: {user.get('level','Beginner')} | "
        f"Focus: {user.get('focus','General Conversation')} | "
        f"Native language: Brazilian Portuguese."
    )

    history.append({"role": "user", "content": txt})
    client = anthropic.Anthropic(api_key=API_KEY)
    # Remove chaves extras (ex: tts_b64) — a API da Anthropic só aceita role + content
    api_messages = [{"role": m["role"], "content": m["content"]} for m in history]
    resp   = client.messages.create(
        model="claude-haiku-4-5", max_tokens=400,
        system=SYSTEM_PROMPT + context,
        messages=api_messages,
    )
    reply = resp.content[0].text
    history.append({"role": "assistant", "content": reply})
    st.session_state["_vm_history"] = history

    tts_b64 = ""
    if tts_available():
        ab = text_to_speech(reply)
        if ab:
            tts_b64 = base64.b64encode(ab).decode()

    st.session_state["_vm_reply"]   = reply
    st.session_state["_vm_tts_b64"] = tts_b64

    # Salva no banco — inclui tts_b64 para poder tocar depois no histórico
    append_message(username, conv_id, "user",      txt,   audio=True)
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64 or None)


# =============================================================================
# TELA PRINCIPAL
# =============================================================================
def show_voice() -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    lang     = profile.get("language", "pt-BR")

    ring_color        = profile.get("ring_color",        "#f0a500")
    user_bubble_color = profile.get("user_bubble_color", "#2d6a4f")
    bot_bubble_color  = profile.get("bot_bubble_color",  "#1a1f2e")

    def _rgba(h: str, a: float) -> str:
        h = h.lstrip("#")
        if len(h) == 3: h = h[0]*2+h[1]*2+h[2]*2
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"rgba({r},{g},{b},{a})"

    # Sem scroll no modo voz — layout 100% responsivo (dvh)
    st.markdown("""<style>
/* Esconde todo o chrome do Streamlit */
[data-testid="stSidebar"]{display:none!important;}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],
#MainMenu,footer,header{display:none!important;}

/* Fundo e overflow */
body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{
    background:#060a10!important;
    overflow:hidden!important;
}
html,body{
    overflow:hidden!important;
    height:100%!important;
    /* iOS safe area */
    padding-bottom:env(safe-area-inset-bottom,0px);
}

/* Remove todo padding/margin do Streamlit */
section[data-testid="stMain"]>div,
.main .block-container,
div[data-testid="stVerticalBlock"],
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="element-container"]{
    padding:0!important;
    margin:0!important;
    gap:0!important;
    overflow:hidden!important;
}
/* O iframe de voz deve ocupar todo o viewport */
iframe{
    display:block!important;
    border:none!important;
    max-height:100dvh!important;
}
/* Esconde o st.audio_input nativo */
[data-testid="stAudioInput"]{
    position:fixed!important;
    bottom:-9999px!important;left:-9999px!important;
    opacity:0!important;pointer-events:none!important;
    width:1px!important;height:1px!important;overflow:hidden!important;
}
[data-testid="stAudioInput"] button{pointer-events:auto!important;}
</style>""", unsafe_allow_html=True)

    conv_id = get_or_create_conv(username)

    # Carrega histórico do banco se _vm_history estiver vazio
    if not st.session_state.get("_vm_history") and conv_id:
        msgs_db = load_conversation(username, conv_id)
        if msgs_db:
            st.session_state["_vm_history"] = [
                {
                    "role":    m["role"],
                    "content": m["content"],
                    "tts_b64": m.get("tts_b64", ""),   # ← preserva áudio por mensagem
                }
                for m in msgs_db if m.get("content")
            ]

    # Processa áudio recebido — só 1 rerun após processar
    audio_val = st.audio_input(
        " ", key=f"voice_input_{st.session_state.audio_key}",
        label_visibility="collapsed",
    )
    if audio_val and audio_val != st.session_state.get("_vm_last_upload"):
        st.session_state["_vm_last_upload"] = audio_val
        for k in ["_vm_reply", "_vm_tts_b64", "_vm_user_said", "_vm_error"]:
            st.session_state.pop(k, None)
        with st.spinner(t("processing", lang)):
            process_voice(audio_val.read(), conv_id)
        st.session_state.audio_key += 1
        st.rerun()

    # Estado atual
    reply   = st.session_state.get("_vm_reply",   "")
    tts_b64 = st.session_state.get("_vm_tts_b64", "")
    vm_error = st.session_state.get("_vm_error",  "")
    history  = st.session_state.get("_vm_history", [])

    # Frames do avatar
    frames    = get_avatar_frames()
    has_anim  = bool(frames["base"] and frames["closed"] and frames["mid"] and frames["open"])

    # Serializa dados para JS
    history_js  = json.dumps(history)
    tts_js      = json.dumps(tts_b64)
    reply_js    = json.dumps(reply)
    err_js      = json.dumps(vm_error)
    tap_speak   = json.dumps(t("tap_to_speak", lang))
    tap_stop    = json.dumps(t("tap_to_stop",  lang))
    speaking_   = json.dumps(t("speaking_ai",  lang))
    proc_       = json.dumps(t("processing",   lang))

    av_b64_js   = json.dumps(frames["base"])
    avc_js      = json.dumps(frames["closed"])
    avm_js      = json.dumps(frames["mid"])
    avo_js      = json.dumps(frames["open"])
    has_anim_js = "true" if has_anim else "false"
    photo_js    = json.dumps(get_tati_mini_b64() or get_photo_b64())
    prof_name_js = json.dumps(PROF_NAME)

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{
    background:#060a10;font-family:'Sora',sans-serif;
    height:100%;overflow:hidden;
    /* iOS safe area */
    padding-bottom:env(safe-area-inset-bottom);
}}
.app{{
    display:flex;flex-direction:column;align-items:center;
    height:100vh;
    height:100dvh;
    padding:0 16px 0;
    gap:0;overflow:hidden;
}}

/* ── Avatar ── */
.avatar-section{{
    flex-shrink:0;width:100%;
    display:flex;flex-direction:column;align-items:center;gap:4px;
    padding:12px 0 8px;
    position:sticky;top:0;z-index:10;
    background:linear-gradient(180deg,#060a10 85%,transparent 100%);
}}
/* Avatar menor em telas pequenas */
.avatar-wrap{{position:relative;width:200px;height:200px;flex-shrink:0;}}
@media(max-height:700px){{
    .avatar-wrap{{width:130px;height:130px;}}
    .avatar-img,.avatar-emoji{{width:130px!important;height:130px!important;}}
    .avatar-section{{padding:6px 0 4px;}}
    .prof-name{{font-size:.85rem!important;}}
}}
.avatar-ring{{
    position:absolute;inset:-8px;border-radius:50%;
    border:2px solid {_rgba(ring_color,.3)};
    animation:ring-pulse 2s ease-in-out infinite;
}}
.avatar-ring.active{{
    border-color:{ring_color};
    box-shadow:0 0 0 0 {_rgba(ring_color,.5)};
    animation:ring-glow 1s ease-in-out infinite;
}}
@keyframes ring-pulse{{0%,100%{{opacity:.4;transform:scale(1);}}50%{{opacity:.8;transform:scale(1.03);}}}}
@keyframes ring-glow{{0%{{box-shadow:0 0 0 0 {_rgba(ring_color,.5)};}}70%{{box-shadow:0 0 14px {_rgba(ring_color,0)};}}100%{{box-shadow:0 0 0 0 {_rgba(ring_color,0)};}}}}
.avatar-img{{
    width:200px;height:200px;border-radius:50%;
    object-fit:cover;object-position:top center;
    border:3px solid {ring_color};
    box-shadow:0 0 32px {_rgba(ring_color,.25)};
}}
.avatar-emoji{{
    width:200px;height:200px;border-radius:50%;
    background:linear-gradient(135deg,#1a2535,#0f1824);
    border:3px solid {ring_color};
    display:flex;align-items:center;justify-content:center;font-size:54px;
}}
.prof-name{{font-size:1rem;font-weight:700;color:#e6edf3;margin-top:6px;}}
.status{{font-size:.68rem;color:{ring_color};margin-top:1px;}}

/* ── Histórico de bolhas ── */
.history-wrap{{
    width:100%;max-width:1890px;
    flex:1;min-height:0;
    overflow-y:auto;display:flex;flex-direction:column;gap:8px;
    padding:8px 4px;
    scrollbar-width:thin;scrollbar-color:#1a2535 transparent;
    -webkit-overflow-scrolling:touch;
}}
.history-wrap::-webkit-scrollbar{{width:4px;}}
.history-wrap::-webkit-scrollbar-thumb{{background:#1a2535;border-radius:4px;}}
.bubble{{
    max-width:82%;padding:10px 15px;border-radius:18px;
    font-size:.84rem;line-height:1.55;word-break:break-word;
}}
.bubble.user{{
    align-self:flex-end;
    background:{user_bubble_color};color:#fff;
    border-bottom-right-radius:4px;
}}
.bubble.bot{{
    align-self:flex-start;
    background:{bot_bubble_color};color:#e6edf3;
    border:1px solid {_rgba(bot_bubble_color,.8)};
    border-bottom-left-radius:4px;
}}
.bubble-label{{font-size:.6rem;color:#4a5a6a;margin:2px 4px;}}
.bubble-label.right{{text-align:right;}}

/* ── Botão de áudio por bolha ── */
.bubble-play-btn{{
    align-self:flex-start;
    background:transparent;border:1px solid #1a2535;color:#3a6a8a;
    font-size:.72rem;padding:4px 12px;border-radius:8px;
    cursor:pointer;font-family:inherit;transition:all .15s;margin-bottom:4px;
    /* touch-friendly */
    min-height:32px;
}}
.bubble-play-btn:hover{{color:#f0a500;border-color:rgba(240,165,0,.4);background:rgba(240,165,0,.06);}}
.bubble-play-btn.playing{{color:#e05c2a;border-color:rgba(224,92,42,.5);}}

/* ── Erro ── */
.error-box{{
    background:rgba(224,92,42,.1);border:1px solid rgba(224,92,42,.3);
    border-radius:10px;padding:8px 14px;font-size:.78rem;color:#e05c2a;
    max-width:560px;width:100%;text-align:center;flex-shrink:0;
}}

/* ── Rodapé do mic — RESPONSIVO ── */
.mic-footer{{
    flex-shrink:0;
    width:100%;max-width:620px;
    display:flex;flex-direction:column;align-items:center;
    gap:6px;
    padding:8px 0 max(16px, env(safe-area-inset-bottom));
    background:linear-gradient(to top,#060a10 70%,transparent);
    position:sticky;bottom:0;
}}

/* ── Controles de áudio: linha única que não quebra ── */
.audio-controls{{
    display:flex;
    align-items:center;
    gap:6px;
    padding:8px 12px;
    background:#0d1420;
    border:1px solid #1a2535;
    border-radius:12px;
    width:100%;
    overflow-x:auto;          /* scroll horizontal se necessário */
    overflow-y:hidden;
    -webkit-overflow-scrolling:touch;
    white-space:nowrap;
    scrollbar-width:none;     /* esconde scrollbar */
    flex-wrap:nowrap;         /* NUNCA quebra linha */
    min-height:44px;
}}
.audio-controls::-webkit-scrollbar{{display:none;}}

/* Em telas muito pequenas, reduz padding e fonte */
@media(max-width:400px){{
    .audio-controls{{padding:6px 10px;gap:4px;}}
    .ctrl-label{{font-size:.6rem;}}
    .ctrl-val{{font-size:.6rem;min-width:24px;}}
    #global-play-btn{{padding:4px 10px;font-size:.72rem;}}
}}

.ctrl-label{{font-size:.68rem;color:#4a5a6a;white-space:nowrap;flex-shrink:0;}}
.ctrl-val{{font-size:.68rem;color:#8b949e;min-width:28px;text-align:left;flex-shrink:0;}}

input[type=range].ctrl-range{{
    -webkit-appearance:none;
    flex-shrink:0;
    width:60px;
    height:4px;
    background:#1a2535;border-radius:2px;outline:none;cursor:pointer;
    touch-action:none;   /* evita scroll ao arrastar no mobile */
}}
@media(min-width:480px){{
    input[type=range].ctrl-range{{ width:80px; }}
}}
input[type=range].ctrl-range::-webkit-slider-thumb{{
    -webkit-appearance:none;width:16px;height:16px;  /* maior para touch */
    border-radius:50%;background:{ring_color};cursor:pointer;
}}
input[type=range].ctrl-range::-moz-range-thumb{{
    width:16px;height:16px;border-radius:50%;background:{ring_color};cursor:pointer;border:none;
}}

#global-play-btn{{
    background:#1a2535;color:#e6edf3;border:1px solid #252d3d;
    border-radius:8px;padding:5px 12px;font-size:.78rem;cursor:pointer;
    white-space:nowrap;transition:background .15s;font-family:inherit;
    flex-shrink:0;
    min-height:32px;        /* touch-friendly */
    touch-action:manipulation;
}}
#global-play-btn:hover{{background:#252d3d;}}

/* ── Botão mic ── */
.mic-btn{{
    width:72px;height:72px;border-radius:50%;border:none;cursor:pointer;
    background:linear-gradient(135deg,#1a2535,#131c2a);
    color:#8b949e;font-size:28px;
    display:flex;align-items:center;justify-content:center;
    box-shadow:0 4px 20px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.05);
    transition:all .2s;outline:none;
    touch-action:manipulation;   /* remove delay 300ms no mobile */
    -webkit-tap-highlight-color:transparent;
    flex-shrink:0;
}}
/* Mic maior em tablets */
@media(min-width:600px){{
    .mic-btn{{width:80px;height:80px;font-size:32px;}}
}}
.mic-btn:hover{{background:linear-gradient(135deg,#1e2f40,#182130);color:#e6edf3;}}
.mic-btn.recording{{
    background:linear-gradient(135deg,#e05c2a,#c44a1a);color:#fff;
    box-shadow:0 0 0 0 rgba(224,92,42,.6),0 4px 20px rgba(224,92,42,.3);
    animation:mic-pulse 1.2s ease-in-out infinite;
}}
.mic-btn.processing{{
    background:linear-gradient(135deg,#f0a500,#c88800);color:#060a10;animation:none;
}}
@keyframes mic-pulse{{
    0%{{box-shadow:0 0 0 0 rgba(224,92,42,.6),0 4px 20px rgba(224,92,42,.3);}}
    70%{{box-shadow:0 0 0 16px rgba(224,92,42,0),0 4px 20px rgba(224,92,42,.3);}}
    100%{{box-shadow:0 0 0 0 rgba(224,92,42,0),0 4px 20px rgba(224,92,42,.3);}}
}}
.mic-hint{{font-size:.68rem;color:#4a5a6a;letter-spacing:.3px;}}
</style>
</head><body>
<div class="app" id="app">
    <div class="avatar-section">
        <div class="avatar-wrap">
            <div class="avatar-ring" id="ring"></div>
            <img id="avImg" class="avatar-img" src="" alt="" style="display:none;"
                 onerror="this.style.display='none';document.getElementById('avEmoji').style.display='flex';">
            <div id="avEmoji" class="avatar-emoji">&#129489;&#8205;&#127979;</div>
        </div>
        <div class="prof-name" id="profName"></div>
        <div class="status" id="statusTxt">&#9679; Online</div>
    </div>

    <div class="history-wrap" id="historyWrap"></div>
    <div class="error-box" id="errBox" style="display:none;"></div>

    <div class="mic-footer">
        <div class="audio-controls" id="audioControls">
            <button id="global-play-btn">&#9654; Ouvir</button>
            <span class="ctrl-label">Vol</span>
            <input type="range" class="ctrl-range" id="vol-slider" min="0" max="1" step="0.05" value="1">
            <span class="ctrl-val" id="vol-val">100%</span>
            <span class="ctrl-label">Vel</span>
            <input type="range" class="ctrl-range" id="spd-slider" min="0.5" max="2" step="0.1" value="1">
            <span class="ctrl-val" id="spd-val">1.0x</span>
        </div>
        <button class="mic-btn" id="micBtn"><i class="fa-solid fa-microphone"></i></button>
        <div class="mic-hint" id="micHint"></div>
    </div>
</div>

<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<script>
(function(){{
// ── Dados do Python ──
var TTS_B64    = {tts_js};
var REPLY      = {reply_js};
var HISTORY    = {history_js};
var VM_ERROR   = {err_js};
var TAP_SPEAK  = {tap_speak};
var TAP_STOP   = {tap_stop};
var SPEAKING   = {speaking_};
var HAS_ANIM   = {has_anim_js};
var AV_BASE    = {av_b64_js};
var AV_CLOSED  = {avc_js};
var AV_MID     = {avm_js};
var AV_OPEN    = {avo_js};
var PHOTO      = {photo_js};
var PROF_NAME  = {prof_name_js};

// ── Elementos ──
var micBtn   = document.getElementById('micBtn');
var micHint  = document.getElementById('micHint');
var statusTxt= document.getElementById('statusTxt');
var errBox   = document.getElementById('errBox');
var ring     = document.getElementById('ring');
var avImg    = document.getElementById('avImg');
var avEmoji  = document.getElementById('avEmoji');
var histWrap = document.getElementById('historyWrap');
var profName = document.getElementById('profName');

profName.textContent = PROF_NAME;
micHint.textContent  = TAP_SPEAK;

// ── Avatar ──
var photoSrc = HAS_ANIM ? AV_BASE : (PHOTO || AV_BASE);
if(photoSrc){{ avImg.src=photoSrc; avImg.style.display='block'; avEmoji.style.display='none'; }}

// ── Animação boca ──
var mouthTimer=null, analyser=null, audioCtx=null, mouthIdx=0;
function stopMouthAnim(){{
    if(mouthTimer){{ clearInterval(mouthTimer); mouthTimer=null; }}
    if(HAS_ANIM && avImg.src !== AV_BASE) avImg.src=AV_BASE;
}}
function startMouthAnim(audioEl){{
    if(!HAS_ANIM) return;
    try{{
        if(!audioCtx) audioCtx=new(window.AudioContext||window.webkitAudioContext)();
        if(!analyser){{
            analyser=audioCtx.createAnalyser(); analyser.fftSize=256;
            var src=audioCtx.createMediaElementSource(audioEl);
            src.connect(analyser); analyser.connect(audioCtx.destination);
        }}
        var buf=new Uint8Array(analyser.frequencyBinCount);
        mouthTimer=setInterval(function(){{
            analyser.getByteFrequencyData(buf);
            var vol=buf.reduce(function(a,b){{return a+b;}},0)/buf.length/128;
            if(vol<0.05) avImg.src=AV_BASE;
            else if(vol<0.2) avImg.src=AV_CLOSED;
            else if(vol<0.5) avImg.src=AV_MID;
            else avImg.src=AV_OPEN;
        }},80);
    }}catch(e){{
        mouthTimer=setInterval(function(){{
            mouthIdx=(mouthIdx+1)%4;
            avImg.src=[AV_BASE,AV_CLOSED,AV_MID,AV_OPEN][mouthIdx];
        }},200);
    }}
}}

// ── Áudio global ──
var currentAudio=null, lastB64=null;
function getVol(){{ return parseFloat(document.getElementById('vol-slider').value)||1; }}
function getSpd(){{ return parseFloat(document.getElementById('spd-slider').value)||1; }}

function playTTS(b64, onEndCallback){{
    if(currentAudio){{ currentAudio.pause(); currentAudio=null; stopMouthAnim(); }}
    if(!b64) return;
    lastB64 = b64;
    ring.classList.add('active');
    statusTxt.textContent=SPEAKING;
    var audio=new Audio('data:audio/mp3;base64,'+b64);
    audio.volume=getVol(); audio.playbackRate=getSpd(); audio._srcB64=b64;
    currentAudio=audio;
    audio.onplay=function(){{ startMouthAnim(audio); updateGlobalBtn(true); }};
    audio.onended=function(){{
        stopMouthAnim(); ring.classList.remove('active');
        statusTxt.textContent='Online'; currentAudio=null;
        updateGlobalBtn(false);
        if(onEndCallback) onEndCallback();
    }};
    audio.onerror=function(){{ stopMouthAnim(); ring.classList.remove('active'); updateGlobalBtn(false); }};
    audio.play().catch(function(){{ stopMouthAnim(); ring.classList.remove('active'); updateGlobalBtn(false); }});
}}
function stopTTS(){{
    if(currentAudio){{ currentAudio.pause(); currentAudio=null; stopMouthAnim(); ring.classList.remove('active'); statusTxt.textContent='Online'; updateGlobalBtn(false); }}
}}
function updateGlobalBtn(playing){{
    var btn=document.getElementById('global-play-btn');
    if(!btn) return;
    btn.textContent = playing ? '⏹ Parar' : '▶ Ouvir';
    btn.style.background = playing ? '#8b2a2a' : '#1a2535';
}}

// ── Controles ──
document.getElementById('global-play-btn').addEventListener('click',function(){{
    if(currentAudio&&!currentAudio.paused) stopTTS();
    else if(lastB64||TTS_B64) playTTS(lastB64||TTS_B64);
}});
document.getElementById('vol-slider').addEventListener('input',function(){{
    document.getElementById('vol-val').textContent=Math.round(this.value*100)+'%';
    if(currentAudio) currentAudio.volume=parseFloat(this.value);
}});
document.getElementById('spd-slider').addEventListener('input',function(){{
    document.getElementById('spd-val').textContent=parseFloat(this.value).toFixed(1)+'x';
    if(currentAudio) currentAudio.playbackRate=parseFloat(this.value);
}});

// ── Renderiza bolhas com botão ▶ por bolha ──
function addBubble(role, text, b64){{
    var label=document.createElement('div');
    label.className='bubble-label'+(role==='user'?' right':'');
    label.textContent=role==='user'?'Você':PROF_NAME;

    var bub=document.createElement('div');
    bub.className='bubble '+role;
    bub.textContent=text;

    histWrap.appendChild(label);
    histWrap.appendChild(bub);

    // Botão ▶ apenas para mensagens do bot COM áudio salvo
    if(role==='bot'&&b64){{
        var pbtn=document.createElement('button');
        pbtn.className='bubble-play-btn';
        pbtn.textContent='▶ Ouvir';
        pbtn.addEventListener('click',function(){{
            var isPlaying=currentAudio&&!currentAudio.paused&&currentAudio._srcB64===b64;
            if(isPlaying){{
                stopTTS(); pbtn.textContent='▶ Ouvir'; pbtn.classList.remove('playing');
            }}else{{
                // reseta todos os outros botões de bolha
                document.querySelectorAll('.bubble-play-btn').forEach(function(b){{
                    b.textContent='▶ Ouvir'; b.classList.remove('playing');
                }});
                pbtn.textContent='⏹ Parar'; pbtn.classList.add('playing');
                playTTS(b64, function(){{
                    pbtn.textContent='▶ Ouvir'; pbtn.classList.remove('playing');
                }});
            }}
        }});
        histWrap.appendChild(pbtn);
    }}
    histWrap.scrollTop=histWrap.scrollHeight;
}}

// ── Renderiza estado atual ──
if(VM_ERROR){{
    errBox.textContent=VM_ERROR; errBox.style.display='block';
}}else{{
    errBox.style.display='none';
    if(HISTORY&&HISTORY.length>0){{
        HISTORY.forEach(function(msg){{
            var role=msg.role==='user'?'user':'bot';
            addBubble(role, msg.content, msg.tts_b64||'');
        }});
    }}
    // Autoplay da resposta mais recente
    if(TTS_B64) setTimeout(function(){{ playTTS(TTS_B64); }},300);
}}

// ── Mic ──
var recording=false;
function getRealMicBtn(){{
    var doc=window.parent.document;
    var ai=doc.querySelector('[data-testid="stAudioInput"]');
    if(!ai) return null;
    return ai.querySelector('button')||ai.querySelector('[data-testid="stAudioInputRecordButton"]');
}}
micBtn.addEventListener('click',function(){{
    var realBtn=getRealMicBtn();
    if(!realBtn) return;
    if(recording){{
        micBtn.classList.remove('recording');
        micBtn.innerHTML='<i class="fa-solid fa-microphone"></i>';
        micHint.textContent=TAP_SPEAK;
        micBtn.classList.add('processing');
        recording=false;
        realBtn.click();
    }}else{{
        if(currentAudio){{ currentAudio.pause(); currentAudio=null; stopMouthAnim(); ring.classList.remove('active'); }}
        if(window.parent.speechSynthesis) window.parent.speechSynthesis.cancel();
        micBtn.classList.add('recording');
        micBtn.innerHTML='<i class="fa-solid fa-stop"></i>';
        micHint.textContent=TAP_STOP;
        recording=true;
        realBtn.click();
    }}
}});

// ── Esconde stAudioInput nativo ──
function hideNativeAudio(){{
    var doc=window.parent.document;
    var ai=doc.querySelector('[data-testid="stAudioInput"]');
    if(ai){{
        ai.style.cssText='position:fixed;bottom:-999px;left:-9999px;opacity:0;pointer-events:none;width:1px;height:1px;';
        var btn=ai.querySelector('button');
        if(btn) btn.style.pointerEvents='auto';
    }}
}}
hideNativeAudio();
try{{
    var obs=new MutationObserver(hideNativeAudio);
    obs.observe(window.parent.document.body,{{childList:true,subtree:true}});
    setTimeout(function(){{obs.disconnect();}},15000);
}}catch(e){{}}

// ── Resize iframe — usa dvh para mobile (esconde barra do browser) ──
(function resizeIframe(){{
    try{{
        var par = window.parent;
        // Altura real do viewport (dvh = dynamic viewport height, funciona no mobile)
        var h = par.innerHeight;
        try{{
            // visualViewport é mais preciso no mobile (exclui teclado virtual)
            if(par.visualViewport) h = par.visualViewport.height;
        }}catch(e){{}}

        var iframes = par.document.querySelectorAll('iframe');
        for(var i=0;i<iframes.length;i++){{
            try{{
                if(iframes[i].contentWindow===window){{
                    iframes[i].style.cssText=[
                        'height:'+h+'px',
                        'max-height:'+h+'px',
                        'min-height:200px',
                        'display:block',
                        'border:none',
                        'width:100%',
                    ].join(';');
                    // Remove padding/margin dos wrappers Streamlit
                    var p=iframes[i].parentElement;
                    for(var j=0;j<10&&p&&p!==par.document.body;j++){{
                        p.style.margin='0';p.style.padding='0';
                        p.style.overflow='hidden';p.style.maxHeight=h+'px';
                        p=p.parentElement;
                    }}
                    break;
                }}
            }}catch(e){{}}
        }}
    }}catch(e){{}}

    // Re-executa ao redimensionar E ao mudar visualViewport (teclado mobile)
    try{{
        par.removeEventListener('resize',resizeIframe);
        par.addEventListener('resize',resizeIframe);
        if(par.visualViewport){{
            par.visualViewport.removeEventListener('resize',resizeIframe);
            par.visualViewport.addEventListener('resize',resizeIframe);
        }}
    }}catch(e){{}}
}})();

}})();
</script>
</body></html>""", height=10000, scrolling=False)