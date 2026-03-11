"""
ui/voice.py — Modo Conversa: avatar animado + microfone contínuo (VAD).
"""

import base64
import json

import streamlit as st
import streamlit.components.v1 as components

from core.database import load_conversation, append_message
from core.ai import send_to_claude, SYSTEM_PROMPT
from core.audio import transcribe_bytes, text_to_speech, tts_available
from utils.helpers import get_avatar_frames, get_tati_mini_b64, get_photo_b64, PROF_NAME
from utils.i18n import t
import anthropic
import os


def _vm_process_audio(raw: bytes, lang: str, conv_id: str) -> None:
    txt = transcribe_bytes(raw, suffix=".webm", language=None)
    if not txt or txt.startswith("❌") or txt.startswith("⚠️"):
        st.session_state["_vm_error"] = txt or "Não entendi. Tente novamente."
        return

    st.session_state["_vm_user_said"] = txt
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.session_state["_vm_error"] = "❌ ANTHROPIC_API_KEY não configurada."
        return

    user     = st.session_state.user
    username = user["username"]
    history  = st.session_state.get("_vm_history", [])
    context  = f"\n\nStudent: Name={user['name']}, Level={user['level']}, Focus={user['focus']}."

    history.append({"role": "user", "content": txt})
    client = anthropic.Anthropic(api_key=api_key)
    resp   = client.messages.create(
        model="claude-haiku-4-5", max_tokens=1000,
        system=SYSTEM_PROMPT + context, messages=[
            {"role": m["role"], "content": m["content"]} for m in history
        ],
    )
    reply = resp.content[0].text
    history.append({"role": "assistant", "content": reply})
    st.session_state["_vm_history"] = history

    # Detecção de elogio de pronúncia
    _praise = ["great pronunciation", "excellent pronunciation", "perfect pronunciation",
               "well pronounced", "sounded great", "beautifully said", "spot on", "nailed it",
               "ótima pronúncia", "excelente pronúncia", "pronúncia perfeita", "muito bem pronunciado"]
    st.session_state["_vm_good_pronunciation"] = any(p in reply.lower() for p in _praise)

    tts_b64 = ""
    if tts_available():
        ab = text_to_speech(reply)
        if ab:
            tts_b64 = base64.b64encode(ab).decode()

    st.session_state["_vm_reply"]   = reply
    st.session_state["_vm_tts_b64"] = tts_b64

    append_message(username, conv_id, "user",      txt,   audio=True)
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64 or None)


def show_voice() -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    lang     = profile.get("language", "pt-BR")

    ring_color        = profile.get("accent_color",       "#f0a500")
    user_bubble_color = profile.get("user_bubble_color",  "#2d6a4f")
    bot_bubble_color  = profile.get("ai_bubble_color",    "#1a1f2e")

    def _rgba(h: str, a: float) -> str:
        h = h.lstrip("#")
        if len(h) == 3: h = h[0]*2+h[1]*2+h[2]*2
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"rgba({r},{g},{b},{a})"

    st.markdown("""<style>
body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#060a10!important;}
section[data-testid="stMain"]>div,.main .block-container{padding:0!important;margin:0!important;overflow:hidden!important;max-height:100vh!important;}
div[data-testid="stVerticalBlock"],div[data-testid="stVerticalBlockBorderWrapper"],div[data-testid="element-container"]{gap:0!important;padding:0!important;margin:0!important;}
html,body{overflow:hidden!important;}
[data-testid="stHeader"],[data-testid="stDecoration"],header[data-testid="stHeader"],#MainMenu,footer,header{display:none!important;height:0!important;visibility:hidden!important;}
[data-testid="stToolbar"]{display:none!important;}
.stApp>[data-testid="stAppViewContainer"]{padding-top:0!important;}
[data-testid="stAppViewContainer"]{padding-top:0!important;margin-top:0!important;}
.vm-close-btn{position:fixed;top:14px;right:16px;z-index:9999;}
.vm-close-btn button{background:rgba(255,255,255,0.08)!important;border:1px solid rgba(255,255,255,0.15)!important;color:#ccc!important;border-radius:8px!important;font-size:0.78rem!important;padding:4px 12px!important;cursor:pointer!important;}
</style>""", unsafe_allow_html=True)

    # Obtém ou cria conversa
    if not st.session_state.conv_id:
        from core.database import new_conversation
        st.session_state.conv_id = new_conversation(username)
    conv_id = st.session_state.conv_id

    with st.container():
        st.markdown('<div class="vm-close-btn">', unsafe_allow_html=True)
        if st.button("✕ Close", key="vm_close_btn"):
            st.session_state.voice_mode = False; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Carrega histórico
    if not st.session_state.get("_vm_history") and conv_id:
        msgs_db = load_conversation(username, conv_id)
        if msgs_db:
            st.session_state["_vm_history"] = [
                {"role": m["role"], "content": m["content"], "tts_b64": m.get("tts_b64", "")}
                for m in msgs_db if m.get("content")
            ]

    # Processa áudio
    audio_val = st.audio_input(" ", key=f"voice_input_{st.session_state.audio_key}",
                               label_visibility="collapsed")
    if audio_val and audio_val != st.session_state.get("_vm_last_upload"):
        st.session_state["_vm_last_upload"] = audio_val
        for k in ["_vm_reply", "_vm_tts_b64", "_vm_user_said", "_vm_error"]:
            st.session_state.pop(k, None)
        with st.spinner(t("processing", lang)):
            _vm_process_audio(audio_val.read(), lang, conv_id)
        st.session_state.audio_key += 1; st.rerun()

    # Estado
    reply    = st.session_state.get("_vm_reply",   "")
    tts_b64  = st.session_state.get("_vm_tts_b64", "")
    vm_error = st.session_state.get("_vm_error",   "")
    history  = st.session_state.get("_vm_history", [])
    frames   = get_avatar_frames()
    has_anim = bool(frames["normal"])

    # Serializa para JS
    history_js       = json.dumps(history)
    tts_js           = json.dumps(tts_b64)
    reply_js         = json.dumps(reply)
    err_js           = json.dumps(vm_error)
    tap_speak        = json.dumps(t("tap_to_speak", lang))
    tap_stop         = json.dumps(t("tap_to_stop",  lang))
    speaking_        = json.dumps(t("speaking_ai",  lang))
    av_normal_js     = json.dumps(frames["normal"])
    av_meio_js       = json.dumps(frames["meio"])
    av_aberta_js     = json.dumps(frames["aberta"])
    av_bem_aberta_js = json.dumps(frames["bem_aberta"])
    av_ouvindo_js    = json.dumps(frames["ouvindo"])
    av_piscando_js   = json.dumps(frames["piscando"])
    av_surpresa_js   = json.dumps(frames["surpresa"])
    has_anim_js      = "true" if has_anim else "false"
    photo_js         = json.dumps(get_tati_mini_b64() or get_photo_b64())
    prof_name_js     = json.dumps(PROF_NAME)
    good_pronunc_js  = json.dumps(bool(st.session_state.get("_vm_good_pronunciation", False)))
    st.session_state.pop("_vm_good_pronunciation", None)

    # Monta HTML substituindo variáveis Python (evita f-string com JS)
    _ring3   = _rgba(ring_color, .3)
    _ring5   = _rgba(ring_color, .5)
    _ring0   = _rgba(ring_color, 0)
    _ring25  = _rgba(ring_color, .25)
    _bot8    = _rgba(bot_bubble_color, .8)

    _html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:#060a10;font-family:'Sora',sans-serif;height:100%;overflow:hidden;padding-bottom:env(safe-area-inset-bottom);}
.app{display:flex;flex-direction:column;align-items:center;height:100vh;height:100dvh;padding:0 16px 0;gap:0;overflow:hidden;}
.avatar-section{flex-shrink:0;width:100%;display:flex;flex-direction:column;align-items:center;gap:4px;padding:12px 0 8px;position:sticky;top:0;z-index:10;background:linear-gradient(180deg,#060a10 85%,transparent 100%);}
.avatar-wrap{position:relative;width:200px;height:200px;flex-shrink:0;}
@media(max-height:700px){.avatar-wrap{width:130px;height:130px;}.avatar-img,.avatar-emoji{width:130px!important;height:130px!important;}.avatar-section{padding:6px 0 4px;}.prof-name{font-size:.85rem!important;}}
.avatar-ring{position:absolute;inset:-8px;border-radius:50%;border:2px solid RING3;animation:ring-pulse 2s ease-in-out infinite;}
.avatar-ring.active{border-color:RING_COLOR;box-shadow:0 0 0 0 RING5;animation:ring-glow 1s ease-in-out infinite;}
@keyframes ring-pulse{0%,100%{opacity:.4;transform:scale(1);}50%{opacity:.8;transform:scale(1.03);}}
@keyframes ring-glow{0%{box-shadow:0 0 0 0 RING5;}70%{box-shadow:0 0 14px RING0;}100%{box-shadow:0 0 0 0 RING0;}}
.avatar-img{width:200px;height:200px;border-radius:50%;object-fit:cover;object-position:top center;border:3px solid RING_COLOR;box-shadow:0 0 32px RING25;}
.avatar-emoji{width:200px;height:200px;border-radius:50%;background:linear-gradient(135deg,#1a2535,#0f1824);border:3px solid RING_COLOR;display:flex;align-items:center;justify-content:center;font-size:54px;}
.prof-name{font-size:1rem;font-weight:700;color:#e6edf3;margin-top:6px;}
.status{font-size:.68rem;color:RING_COLOR;margin-top:1px;}
.history-wrap{width:100%;max-width:1890px;flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding:8px 4px;scrollbar-width:thin;scrollbar-color:#1a2535 transparent;-webkit-overflow-scrolling:touch;}
.bubble{max-width:82%;padding:10px 15px;border-radius:18px;font-size:.84rem;line-height:1.55;word-break:break-word;}
.bubble.user{align-self:flex-end;background:USER_BUBBLE;color:#fff;border-bottom-right-radius:4px;}
.bubble.bot{align-self:flex-start;background:BOT_BUBBLE;color:#e6edf3;border:1px solid BOT8;border-bottom-left-radius:4px;}
.bubble-label{font-size:.6rem;color:#4a5a6a;margin:2px 4px;}
.bubble-label.right{text-align:right;}
.bubble-play-btn{align-self:flex-start;background:transparent;border:1px solid #1a2535;color:#3a6a8a;font-size:.72rem;padding:4px 12px;border-radius:8px;cursor:pointer;font-family:inherit;transition:all .15s;margin-bottom:4px;min-height:32px;}
.bubble-play-btn:hover{color:#f0a500;border-color:rgba(240,165,0,.4);background:rgba(240,165,0,.06);}
.bubble-play-btn.playing{color:#e05c2a;border-color:rgba(224,92,42,.5);}
.error-box{background:rgba(224,92,42,.1);border:1px solid rgba(224,92,42,.3);border-radius:10px;padding:8px 14px;font-size:.78rem;color:#e05c2a;max-width:560px;width:100%;text-align:center;flex-shrink:0;}
.mic-footer{flex-shrink:0;width:100%;max-width:620px;display:flex;flex-direction:column;align-items:center;gap:6px;padding:8px 0 max(16px,env(safe-area-inset-bottom));background:linear-gradient(to top,#060a10 70%,transparent);position:sticky;bottom:0;}
.audio-controls{display:flex;align-items:center;gap:6px;padding:8px 12px;background:#0d1420;border:1px solid #1a2535;border-radius:12px;width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;white-space:nowrap;scrollbar-width:none;flex-wrap:nowrap;min-height:44px;}
.audio-controls::-webkit-scrollbar{display:none;}
.ctrl-label{font-size:.68rem;color:#4a5a6a;white-space:nowrap;flex-shrink:0;}
.ctrl-val{font-size:.68rem;color:#8b949e;min-width:28px;text-align:left;flex-shrink:0;}
input[type=range].ctrl-range{-webkit-appearance:none;flex-shrink:0;width:60px;height:4px;background:#1a2535;border-radius:2px;outline:none;cursor:pointer;touch-action:none;}
@media(min-width:480px){input[type=range].ctrl-range{width:80px;}}
input[type=range].ctrl-range::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;background:RING_COLOR;cursor:pointer;}
#global-play-btn{background:#1a2535;color:#e6edf3;border:1px solid #252d3d;border-radius:8px;padding:5px 12px;font-size:.78rem;cursor:pointer;white-space:nowrap;transition:background .15s;font-family:inherit;flex-shrink:0;min-height:32px;touch-action:manipulation;}
#global-play-btn:hover{background:#252d3d;}
.mic-btn{width:72px;height:72px;border-radius:50%;border:none;cursor:pointer;background:linear-gradient(135deg,#1a2535,#131c2a);color:#8b949e;font-size:28px;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 20px rgba(0,0,0,.4);transition:all .2s;outline:none;touch-action:manipulation;-webkit-tap-highlight-color:transparent;flex-shrink:0;}
.mic-btn:hover{background:linear-gradient(135deg,#1e2f40,#182130);color:#e6edf3;}
.mic-btn.recording{background:linear-gradient(135deg,#e05c2a,#c44a1a);color:#fff;animation:mic-pulse 1.2s ease-in-out infinite;}
.mic-btn.processing{background:linear-gradient(135deg,#f0a500,#c88800);color:#060a10;animation:none;}
@keyframes mic-pulse{0%{box-shadow:0 0 0 0 rgba(224,92,42,.6),0 4px 20px rgba(224,92,42,.3);}70%{box-shadow:0 0 0 16px rgba(224,92,42,0),0 4px 20px rgba(224,92,42,.3);}100%{box-shadow:0 0 0 0 rgba(224,92,42,0),0 4px 20px rgba(224,92,42,.3);}}
.mic-hint{font-size:.68rem;color:#4a5a6a;letter-spacing:.3px;}
</style></head><body>
<div class="app" id="app">
    <div class="avatar-section">
        <div class="avatar-wrap">
            <div class="avatar-ring" id="ring"></div>
            <img id="avImg" class="avatar-img" src="" alt="" style="display:none;" onerror="this.style.display='none';document.getElementById('avEmoji').style.display='flex';">
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
(function(){
var TTS_B64=__TTS_JS__,REPLY=__REPLY_JS__,HISTORY=__HISTORY_JS__,VM_ERROR=__ERR_JS__;
var TAP_SPEAK=__TAP_SPEAK__,TAP_STOP=__TAP_STOP__,SPEAKING=__SPEAKING__;
var HAS_ANIM=__HAS_ANIM__,GOOD_PRONUNC=__GOOD_PRONUNC__,PHOTO=__PHOTO_JS__,PROF_NAME=__PROF_NAME_JS__;
var F_NORMAL=__F_NORMAL__,F_MEIO=__F_MEIO__,F_ABERTA=__F_ABERTA__,F_BEM_ABERTA=__F_BEM_ABERTA__;
var F_OUVINDO=__F_OUVINDO__,F_PISCANDO=__F_PISCANDO__,F_SURPRESA=__F_SURPRESA__;
var micBtn=document.getElementById('micBtn'),micHint=document.getElementById('micHint');
var statusTxt=document.getElementById('statusTxt'),errBox=document.getElementById('errBox');
var ring=document.getElementById('ring'),avImg=document.getElementById('avImg');
var avEmoji=document.getElementById('avEmoji'),histWrap=document.getElementById('historyWrap');
var profName=document.getElementById('profName');
profName.textContent=PROF_NAME; micHint.textContent=TAP_SPEAK;
var _lastFrame='';
function setFrame(src){if(!src||src===_lastFrame)return;_lastFrame=src;avImg.src=src;avImg.style.display='block';avEmoji.style.display='none';}
setFrame(HAS_ANIM?F_NORMAL:(PHOTO||F_NORMAL));
var _state='idle',_blinkTimer=null,_mouthTimer=null,_analyser=null,_audioCtx=null;
function _stopAll(){if(_blinkTimer){clearTimeout(_blinkTimer);clearInterval(_blinkTimer);_blinkTimer=null;}if(_mouthTimer){clearInterval(_mouthTimer);_mouthTimer=null;}}
function enterIdle(){_stopAll();_state='idle';setFrame(F_NORMAL);ring.classList.remove('active');statusTxt.textContent='● Online';function sched(){var d=3210+Math.random()*2000;_blinkTimer=setTimeout(function(){if(_state!=='idle')return;setFrame(F_PISCANDO);setTimeout(function(){if(_state!=='idle')return;setFrame(F_NORMAL);sched();},150);},d);}sched();}
function enterListening(){_stopAll();_state='listening';setFrame(F_OUVINDO);ring.classList.remove('active');statusTxt.textContent='🎙 Ouvindo…';}
function enterProcessing(){_stopAll();_state='processing';setFrame(F_NORMAL);ring.classList.remove('active');statusTxt.textContent='⏳ Processando…';_blinkTimer=setInterval(function(){if(_state!=='processing')return;setFrame(F_PISCANDO);setTimeout(function(){if(_state!=='processing')return;setFrame(F_NORMAL);},180);},2200);}
function enterSpeaking(audioEl){_stopAll();_state='speaking';ring.classList.add('active');statusTxt.textContent=SPEAKING;if(!HAS_ANIM)return;try{if(!_audioCtx)_audioCtx=new(window.AudioContext||window.webkitAudioContext)();if(!_analyser){_analyser=_audioCtx.createAnalyser();_analyser.fftSize=1024;_analyser.smoothingTimeConstant=0.1;var src=_audioCtx.createMediaElementSource(audioEl);src.connect(_analyser);_analyser.connect(_audioCtx.destination);}var buf=new Uint8Array(_analyser.frequencyBinCount);_mouthTimer=setInterval(function(){if(_state!=='speaking')return;_analyser.getByteFrequencyData(buf);var sum=0,n=Math.min(100,buf.length);for(var i=4;i<n;i++)sum+=buf[i];setFrame(sum/(n-4)<18?F_NORMAL:F_MEIO);},60);}catch(e){var idx=0;_mouthTimer=setInterval(function(){if(_state!=='speaking')return;setFrame(idx++%2===0?F_MEIO:F_NORMAL);},250);}}
function onSpeakingEnded(good){_stopAll();if(good&&F_BEM_ABERTA){setFrame(F_BEM_ABERTA);setTimeout(enterIdle,1200);}else enterIdle();}
var currentAudio=null,lastB64=null;
function getVol(){return parseFloat(document.getElementById('vol-slider').value)||1;}
function getSpd(){return parseFloat(document.getElementById('spd-slider').value)||1;}
function playTTS(b64,cb){if(currentAudio){currentAudio.pause();currentAudio=null;}_analyser=null;if(!b64)return;lastB64=b64;var a=new Audio('data:audio/mp3;base64,'+b64);a.volume=getVol();a.playbackRate=getSpd();a._srcB64=b64;currentAudio=a;a.onplay=function(){enterSpeaking(a);updateBtn(true);};a.onended=function(){currentAudio=null;updateBtn(false);onSpeakingEnded(GOOD_PRONUNC);if(cb)cb();};a.onerror=function(){currentAudio=null;updateBtn(false);enterIdle();};a.play().catch(function(){currentAudio=null;updateBtn(false);enterIdle();});}
function stopTTS(){if(currentAudio){currentAudio.pause();currentAudio=null;}_analyser=null;updateBtn(false);enterIdle();}
function updateBtn(p){var b=document.getElementById('global-play-btn');if(!b)return;b.textContent=p?'⏹ Parar':'▶ Ouvir';b.style.background=p?'#8b2a2a':'#1a2535';}
document.getElementById('global-play-btn').addEventListener('click',function(){if(currentAudio&&!currentAudio.paused)stopTTS();else if(lastB64||TTS_B64)playTTS(lastB64||TTS_B64);});
document.getElementById('vol-slider').addEventListener('input',function(){document.getElementById('vol-val').textContent=Math.round(this.value*100)+'%';if(currentAudio)currentAudio.volume=parseFloat(this.value);});
document.getElementById('spd-slider').addEventListener('input',function(){document.getElementById('spd-val').textContent=parseFloat(this.value).toFixed(1)+'x';if(currentAudio)currentAudio.playbackRate=parseFloat(this.value);});
function addBubble(role,text,b64){
  var lbl=document.createElement('div');lbl.className='bubble-label'+(role==='user'?' right':'');lbl.textContent=role==='user'?'Você':PROF_NAME;
  var bub=document.createElement('div');bub.className='bubble '+role;bub.textContent=text;
  histWrap.appendChild(lbl);histWrap.appendChild(bub);
  if(role==='bot'&&b64){var pbtn=document.createElement('button');pbtn.className='bubble-play-btn';pbtn.textContent='▶ Ouvir';pbtn.addEventListener('click',function(){var ip=currentAudio&&!currentAudio.paused&&currentAudio._srcB64===b64;if(ip){stopTTS();pbtn.textContent='▶ Ouvir';pbtn.classList.remove('playing');}else{document.querySelectorAll('.bubble-play-btn').forEach(function(x){x.textContent='▶ Ouvir';x.classList.remove('playing');});pbtn.textContent='⏹ Parar';pbtn.classList.add('playing');playTTS(b64,function(){pbtn.textContent='▶ Ouvir';pbtn.classList.remove('playing');});}});histWrap.appendChild(pbtn);}
  histWrap.scrollTop=histWrap.scrollHeight;
}
if(VM_ERROR){errBox.textContent=VM_ERROR;errBox.style.display='block';enterIdle();}
else{errBox.style.display='none';if(HISTORY&&HISTORY.length>0){HISTORY.forEach(function(m){addBubble(m.role==='user'?'user':'bot',m.content,m.tts_b64||'');});}if(TTS_B64)setTimeout(function(){playTTS(TTS_B64);},300);else enterIdle();}
var recording=false;
function getRealMicBtn(){var ai=window.parent.document.querySelector('[data-testid="stAudioInput"]');if(!ai)return null;var btns=ai.querySelectorAll('button');for(var i=0;i<btns.length;i++){var lbl=(btns[i].getAttribute('aria-label')||'').toLowerCase();if(lbl.indexOf('download')>=0)continue;return btns[i];}return btns[0]||null;}
micBtn.addEventListener('click',function(){var rb=getRealMicBtn();if(!rb)return;if(recording){recording=false;micBtn.classList.remove('recording');micBtn.classList.add('processing');micBtn.innerHTML='<i class="fa-solid fa-spinner fa-spin"></i>';micHint.textContent=TAP_SPEAK;enterProcessing();rb.click();}else{if(currentAudio){currentAudio.pause();currentAudio=null;}recording=true;micBtn.classList.remove('processing');micBtn.classList.add('recording');micBtn.innerHTML='<i class="fa-solid fa-stop"></i>';micHint.textContent=TAP_STOP;enterListening();rb.click();}});
function hideNativeAudio(){var ai=window.parent.document.querySelector('[data-testid="stAudioInput"]');if(ai){ai.style.cssText='position:fixed;bottom:-999px;left:-9999px;opacity:0;pointer-events:none;width:1px;height:1px;';var b=ai.querySelector('button');if(b)b.style.pointerEvents='auto';}}
hideNativeAudio();
try{var obs=new MutationObserver(hideNativeAudio);obs.observe(window.parent.document.body,{childList:true,subtree:true});setTimeout(function(){obs.disconnect();},15000);}catch(e){}
(function resizeIframe(){try{var par=window.parent,h=par.innerHeight;try{if(par.visualViewport)h=par.visualViewport.height;}catch(e){}var iframes=par.document.querySelectorAll('iframe');for(var i=0;i<iframes.length;i++){try{if(iframes[i].contentWindow===window){iframes[i].style.height=h+'px';iframes[i].style.maxHeight=h+'px';iframes[i].style.minHeight='200px';iframes[i].style.display='block';iframes[i].style.border='none';iframes[i].style.width='100%';var p=iframes[i].parentElement;for(var j=0;j<10&&p&&p!==par.document.body;j++){p.style.margin='0';p.style.padding='0';p.style.overflow='hidden';p.style.maxHeight=h+'px';p=p.parentElement;}break;}}catch(e){}}try{par.removeEventListener('resize',resizeIframe);par.addEventListener('resize',resizeIframe);if(par.visualViewport){par.visualViewport.removeEventListener('resize',resizeIframe);par.visualViewport.addEventListener('resize',resizeIframe);}}catch(e){}}catch(e){}})();
})();
</script></body></html>"""

    # Substitui placeholders pelas variáveis Python
    _html = (_html
        .replace('RING3',      _ring3)
        .replace('RING5',      _ring5)
        .replace('RING0',      _ring0)
        .replace('RING25',     _ring25)
        .replace('RING_COLOR', ring_color)
        .replace('USER_BUBBLE',user_bubble_color)
        .replace('BOT_BUBBLE', bot_bubble_color)
        .replace('BOT8',       _bot8)
        .replace('__TTS_JS__',        tts_js)
        .replace('__REPLY_JS__',      reply_js)
        .replace('__HISTORY_JS__',    history_js)
        .replace('__ERR_JS__',        err_js)
        .replace('__TAP_SPEAK__',     tap_speak)
        .replace('__TAP_STOP__',      tap_stop)
        .replace('__SPEAKING__',      speaking_)
        .replace('__HAS_ANIM__',      has_anim_js)
        .replace('__GOOD_PRONUNC__',  good_pronunc_js)
        .replace('__PHOTO_JS__',      photo_js)
        .replace('__PROF_NAME_JS__',  prof_name_js)
        .replace('__F_NORMAL__',      av_normal_js)
        .replace('__F_MEIO__',        av_meio_js)
        .replace('__F_ABERTA__',      av_aberta_js)
        .replace('__F_BEM_ABERTA__',  av_bem_aberta_js)
        .replace('__F_OUVINDO__',     av_ouvindo_js)
        .replace('__F_PISCANDO__',    av_piscando_js)
        .replace('__F_SURPRESA__',    av_surpresa_js)
    )
    components.html(_html, height=920, scrolling=False)

    # ── File uploader (oculto — acionado pelo clipe na chat bar) ─────────────
    from core.file_handler import extract_file
    uploaded_list = st.file_uploader(
        "📎", key="vm_file_upload", label_visibility="collapsed",
        accept_multiple_files=True,
        type=["mp3", "wav", "ogg", "m4a", "webm", "flac",
              "pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "webp"])

    if uploaded_list:
        names_key = ",".join(sorted(f.name for f in uploaded_list))
        if names_key != st.session_state.get("_vm_last_files_key"):
            st.session_state["_vm_last_files_key"] = names_key
            staged_list = []
            for uf in uploaded_list:
                raw    = uf.read()
                result = extract_file(raw, uf.name)
                staged_list.append({"raw": raw, "name": uf.name,
                                     "kind": result["kind"], "result": result})
            st.session_state.staged_file      = staged_list
            st.session_state.staged_file_name = ", ".join(f["name"] for f in staged_list)
            st.rerun()

    # ── Handler único para todos os botões Ouvir ──────────────────────────────
    components.html("""<!DOCTYPE html><html><body><script>
(function(){
  var par = window.parent ? window.parent.document : document;
  var cur = null;
  function initBtns(){
    par.querySelectorAll('[data-pav-tts]').forEach(function(btn){
      if(btn._pavInit) return;
      btn._pavInit = true;
      btn.addEventListener('click', function(){
        if(cur && cur !== btn){
          speechSynthesis.cancel();
          cur.textContent='▶ Ouvir'; cur.classList.remove('speaking'); cur=null;
        }
        if(btn.classList.contains('speaking')){
          speechSynthesis.cancel();
          btn.textContent='▶ Ouvir'; btn.classList.remove('speaking'); cur=null; return;
        }
        var txt = btn.getAttribute('data-text') || '';
        var u = new SpeechSynthesisUtterance(txt);
        u.lang='en-US'; u.rate=0.95; u.pitch=1.05;
        speechSynthesis.getVoices();
        setTimeout(function(){
          var vv=speechSynthesis.getVoices();
          var pick=vv.find(function(v){return v.lang==='en-US';})||vv.find(function(v){return v.lang.startsWith('en');});
          if(pick) u.voice=pick;
          u.onstart=function(){ btn.textContent='⏹ Parar'; btn.classList.add('speaking'); cur=btn; };
          u.onend=u.onerror=function(){ btn.textContent='▶ Ouvir'; btn.classList.remove('speaking'); cur=null; };
          speechSynthesis.cancel(); speechSynthesis.speak(u);
        },80);
      });
    });
  }
  initBtns();
  var obs = new MutationObserver(initBtns);
  obs.observe(par.body, {childList:true, subtree:true});
})();
</script></body></html>""", height=1)

    # ── Botões mic e clipe — carregados de arquivos externos ──────────────────
    from pathlib import Path
    _btn_html = Path("static/pav_buttons.html")
    _btn_css  = Path("static/pav_buttons.css")
    if _btn_css.exists():
        st.markdown(f"<style>{_btn_css.read_text()}</style>", unsafe_allow_html=True)
    if _btn_html.exists():
        components.html(_btn_html.read_text(), height=1)
    else:
        st.warning("static/pav_buttons.html não encontrado")