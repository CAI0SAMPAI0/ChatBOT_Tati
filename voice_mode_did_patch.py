"""
PATCH: Substituição do show_voice_mode() no app.py para usar D-ID avatar.

Como aplicar:
1. Copie did_avatar.py para a raiz do projeto (junto com app.py)
2. Adicione no .env:
      DID_API_KEY=sua_chave_aqui
      DID_AVATAR_PROFESSOR=https://url-publica-da-foto-tati.jpg
      DID_AVATAR_STUDENT=https://url-publica-da-sua-foto.jpg
3. Substitua a função show_voice_mode() no app.py pelo código abaixo
4. Adicione no topo do app.py:
      from did_avatar import generate_avatar_video, did_available

IMPORTANTE sobre as fotos:
- A D-ID precisa de uma URL PÚBLICA para a foto (não funciona com arquivo local)
- Opções gratuitas para hospedar:
    a) Supabase Storage (já usa no projeto) — faça upload e copie a URL pública
    b) GitHub: suba a imagem e use a URL raw.githubusercontent.com
    c) Imgur: upload anônimo gratuito
- Resolução mínima: 512×512px, rosto centralizado, boa iluminação
- Fundo simples funciona melhor (pode usar fundo branco ou neutro)
"""

# ══════════════════════════════════════════════════════════════════════════════
# ADICIONE NO TOPO DO app.py (junto com os outros imports)
# ══════════════════════════════════════════════════════════════════════════════
#
#   from did_avatar import generate_avatar_video, did_available
#
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# NOVA FUNÇÃO show_voice_mode() — substitui a existente no app.py
# ══════════════════════════════════════════════════════════════════════════════

def show_voice_mode() -> None:
    """
    Modo conversa com avatar D-ID realista + VAD.
    O avatar pisca os lábios sincronizado com a voz via D-ID API.
    """
    import json
    import base64
    from pathlib import Path

    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    whisper_lang = profile.get("voice_lang", "en")
    is_prof  = (user.get("role") == "professor")

    # Voz D-ID: feminino para professora, masculino para alunos
    did_voice = "en-US-JennyNeural" if is_prof else "en-US-GuyNeural"

    conv_id = get_or_create_conv(username)

    if st.button("✕ Fechar Modo Voz", key="close_voice_inner"):
        st.session_state.voice_mode = False
        for k in ["_vm_history","_vm_reply","_vm_tts_b64","_vm_user_said",
                  "_vm_error","_vm_last_upload","_vm_video_url"]:
            st.session_state.pop(k, None)
        st.rerun()

    # Uploader oculto para receber áudio do JS VAD
    audio_upload = st.file_uploader(
        "vm_audio", key="vm_audio_upload", label_visibility="collapsed",
        type=["webm","wav","ogg","mp4","m4a"])

    if audio_upload:
        uid = f"{audio_upload.name}_{audio_upload.size}"
        if uid != st.session_state.get("_vm_last_upload"):
            st.session_state["_vm_last_upload"] = uid
            for k in ["_vm_reply","_vm_tts_b64","_vm_user_said","_vm_error","_vm_video_url"]:
                st.session_state.pop(k, None)
            _vm_process_audio_did(audio_upload.read(), whisper_lang, conv_id, did_voice, is_prof)
            st.rerun()

    user_said  = st.session_state.get("_vm_user_said", "")
    reply      = st.session_state.get("_vm_reply", "")
    tts_b64    = st.session_state.get("_vm_tts_b64", "")
    video_url  = st.session_state.get("_vm_video_url", "")
    vm_error   = st.session_state.get("_vm_error", "")

    # Foto do avatar atual (fallback se D-ID não disponível)
    def _photo_b64(path_str):
        p = Path(path_str)
        if p.exists():
            ext  = p.suffix.lower().lstrip(".")
            mime = "jpeg" if ext in ("jpg","jpeg") else ext
            return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
        return ""

    if is_prof:
        photo_b64 = _photo_b64("assets/professor.jpg") or \
                    _photo_b64("data/avatars/professor.png") or ""
    else:
        photo_b64 = _photo_b64(f"data/avatars/{username}.jpg") or \
                    _photo_b64(f"data/avatars/{username}.png") or ""

    us_js    = json.dumps(user_said)
    rep_js   = json.dumps(reply)
    tts_js   = json.dumps(tts_b64)
    vid_js   = json.dumps(video_url)
    err_js   = json.dumps(vm_error)
    pnm_js   = json.dumps(PROF_NAME)
    did_ok   = json.dumps(did_available())

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
:root{{--bg:#080c12;--surface:#0f1419;--border:#1e2530;
       --accent:#f0a500;--text:#e6edf3;--muted:#8b949e;
       --green:#3fb950;--red:#f85149;--blue:#58a6ff;}}
html,body{{background:var(--bg);font-family:'Sora',sans-serif;color:var(--text);height:100%;overflow:hidden;}}

.vm{{display:flex;flex-direction:column;align-items:center;justify-content:center;
     height:100vh;gap:14px;padding:20px;
     background:radial-gradient(ellipse at 50% 25%,rgba(240,165,0,.07),transparent 60%);}}

/* Container do avatar — foto estática ou vídeo D-ID */
.avatar-wrap{{
  width:220px;height:220px;border-radius:50%;overflow:hidden;flex-shrink:0;
  position:relative;
  box-shadow:0 0 0 3px rgba(240,165,0,.4),0 0 40px rgba(240,165,0,.2);
  background:#0d1520;
}}
.avatar-wrap img,
.avatar-wrap video{{
  width:100%;height:100%;object-fit:cover;object-position:top;
  border-radius:50%;display:block;
}}
/* Anel pulsante enquanto fala */
.avatar-wrap.speaking{{
  animation:ring-pulse 1s ease-in-out infinite alternate;
}}
@keyframes ring-pulse{{
  from{{box-shadow:0 0 0 3px rgba(240,165,0,.4),0 0 20px rgba(240,165,0,.2);}}
  to  {{box-shadow:0 0 0 5px rgba(240,165,0,.8),0 0 50px rgba(240,165,0,.5);}}
}}

/* Badge D-ID */
.did-badge{{
  position:absolute;bottom:6px;right:6px;
  background:rgba(0,0,0,.7);border:1px solid var(--accent);
  border-radius:6px;padding:2px 6px;font-size:.55rem;color:var(--accent);
}}

.info{{text-align:center;}}
.prof-name{{font-size:1rem;font-weight:700;color:var(--accent);margin-bottom:3px;}}
.status{{font-size:.78rem;color:var(--muted);transition:color .3s;}}
.status.s-listening{{color:var(--green);}}.status.s-speaking{{color:var(--accent);}}
.status.s-processing{{color:var(--blue);}}.status.s-generating{{color:#a371f7;}}

.transcript{{max-width:480px;width:100%;background:var(--surface);border:1px solid var(--border);
             border-radius:14px;padding:12px 16px;font-size:.84rem;line-height:1.65;min-height:60px;}}
.t-label{{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}}
.t-user{{color:#adbac7;margin-bottom:6px;display:none;}}
.t-sep{{border:none;border-top:1px solid var(--border);margin:6px 0;display:none;}}
.t-ai{{color:var(--text);display:none;}}.t-wait{{color:#3d4a5c;font-style:italic;}}

.sil{{width:130px;height:3px;background:var(--border);border-radius:2px;overflow:hidden;visibility:hidden;margin:0 auto;}}
.sil-fill{{height:100%;background:linear-gradient(90deg,var(--green),var(--accent));border-radius:2px;width:0%;}}
.sil.show{{visibility:visible;}}

.mic-btn{{width:64px;height:64px;border-radius:50%;border:none;cursor:pointer;font-size:26px;
          display:flex;align-items:center;justify-content:center;
          background:linear-gradient(135deg,var(--green),#2ea043);
          box-shadow:0 0 20px rgba(63,185,80,.3);transition:all .2s;}}
.mic-btn:hover{{transform:scale(1.07);}}
.mic-btn.active{{background:linear-gradient(135deg,var(--red),#c03030);
                 box-shadow:0 0 26px rgba(248,81,73,.5);
                 animation:mpulse .8s ease-in-out infinite alternate;}}
@keyframes mpulse{{from{{box-shadow:0 0 14px rgba(248,81,73,.3);}}to{{box-shadow:0 0 32px rgba(248,81,73,.7);}}}}
.hint{{font-size:.65rem;color:#2d3a4a;text-align:center;}}
.err{{font-size:.74rem;color:var(--red);text-align:center;max-width:340px;min-height:18px;}}
</style></head><body>
<div class="vm">

  <!-- Avatar: vídeo D-ID (quando disponível) ou foto estática -->
  <div class="avatar-wrap" id="avatarWrap">
    {"<img id='avatarImg' src='" + photo_b64 + "'/>" if photo_b64 else "<div style='width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:60px;'>🧑‍🏫</div>"}
    <!-- Vídeo D-ID será injetado aqui via JS -->
    <div class="did-badge" id="didBadge" style="display:none">D-ID ✨</div>
  </div>

  <div class="info">
    <div class="prof-name">{PROF_NAME}</div>
    <div class="status" id="status">Clique no microfone para falar</div>
  </div>

  <div class="transcript">
    <div class="t-label" id="tLabel">Aguardando...</div>
    <div class="t-user" id="tUser"></div>
    <hr class="t-sep" id="tSep">
    <div class="t-ai" id="tAi"></div>
    <div class="t-wait" id="tWait">—</div>
  </div>

  <div class="sil" id="sil"><div class="sil-fill" id="silFill"></div></div>
  <button class="mic-btn" id="micBtn">🎤</button>
  <div class="hint">Detecção automática de silêncio (1.5s)</div>
  <div class="err" id="errBox"></div>
</div>

<script>
const PY_USER_SAID = {us_js};
const PY_REPLY     = {rep_js};
const PY_TTS_B64   = {tts_js};
const PY_VIDEO_URL = {vid_js};
const PY_ERROR     = {err_js};
const DID_OK       = {did_ok};

// ── Elementos ─────────────────────────────────────────────────────────────────
const wrap    = document.getElementById('avatarWrap');
const statusEl= document.getElementById('status');
const tLabel  = document.getElementById('tLabel');
const tUser   = document.getElementById('tUser');
const tSep    = document.getElementById('tSep');
const tAi     = document.getElementById('tAi');
const tWait   = document.getElementById('tWait');
const sil     = document.getElementById('sil');
const silFill = document.getElementById('silFill');
const micBtn  = document.getElementById('micBtn');
const errBox  = document.getElementById('errBox');
const didBadge= document.getElementById('didBadge');

function setStatus(t,c=''){{statusEl.textContent=t;statusEl.className='status '+c;}}
function showErr(m){{errBox.textContent=m;setTimeout(()=>errBox.textContent='',6000);}}
function showSil(p){{sil.classList.add('show');silFill.style.width=p+'%';}}
function hideSil(){{sil.classList.remove('show');silFill.style.width='0%';}}
function showTranscript(u,a){{
  tWait.style.display='none';
  if(u){{tLabel.textContent='Você disse:';tUser.textContent=u;tUser.style.display='block';}}
  if(a){{tSep.style.display='block';tAi.textContent=a;tAi.style.display='block';}}
}}

// ── Player D-ID ───────────────────────────────────────────────────────────────
let currentVideo = null;
let isSpeaking   = false;

function playDIDVideo(videoUrl, fallbackTts, fallbackText) {{
  // Remove vídeo anterior
  if(currentVideo) {{ currentVideo.pause(); currentVideo.remove(); currentVideo=null; }}

  if(videoUrl && videoUrl.length > 10) {{
    // Cria elemento <video> sobre a foto
    const vid = document.createElement('video');
    vid.src         = videoUrl;
    vid.autoplay    = true;
    vid.playsInline = true;
    vid.muted       = false;
    vid.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;border-radius:50%;z-index:2;';
    wrap.appendChild(vid);
    currentVideo = vid;
    didBadge.style.display = 'block';

    wrap.classList.add('speaking');
    isSpeaking = true;
    setStatus('Falando...','s-speaking');

    vid.onended = () => {{
      wrap.classList.remove('speaking');
      vid.remove(); currentVideo=null; isSpeaking=false;
      didBadge.style.display='none';
      resetToIdle(); startRec();
    }};
    vid.onerror = () => {{
      vid.remove(); currentVideo=null;
      // Fallback para TTS de áudio normal
      playFallbackAudio(fallbackTts, fallbackText);
    }};
  }} else {{
    playFallbackAudio(fallbackTts, fallbackText);
  }}
}}

function playFallbackAudio(b64, text) {{
  wrap.classList.add('speaking');
  isSpeaking=true; setStatus('Falando...','s-speaking');

  if(b64 && b64.length>20) {{
    const audio = new Audio('data:audio/mpeg;base64,'+b64);
    audio.onended = () => {{
      wrap.classList.remove('speaking'); isSpeaking=false;
      resetToIdle(); startRec();
    }};
    audio.onerror = () => {{
      wrap.classList.remove('speaking'); isSpeaking=false;
      fallbackTTS(text);
    }};
    audio.play().catch(()=>fallbackTTS(text));
  }} else {{
    fallbackTTS(text);
  }}
}}

function fallbackTTS(text) {{
  const u=new SpeechSynthesisUtterance((text||'').substring(0,500));
  u.lang='en-US'; u.rate=0.95; u.pitch=1.05;
  speechSynthesis.getVoices();
  setTimeout(()=>{{
    const vv=speechSynthesis.getVoices();
    const pick=vv.find(v=>v.lang==='en-US')||vv.find(v=>v.lang.startsWith('en'));
    if(pick)u.voice=pick;
    u.onend=u.onerror=()=>{{wrap.classList.remove('speaking');isSpeaking=false;resetToIdle();startRec();}};
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  }},100);
}}

// ── VAD + gravação (igual ao original) ───────────────────────────────────────
const SILENCE_MS=1500, MIN_DB=-42;
let mediaRec=null,chunks=[],audioCtx=null,analyser=null,micStream=null;
let isRec=false,vadActive=false,speechHit=false,silTimer=null,silStart=null;

function getMicRMS(){{
  if(!analyser)return -100;
  const d=new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(d);
  let s=0; for(let i=0;i<d.length;i++)s+=d[i]*d[i];
  const r=Math.sqrt(s/d.length); return r>0?20*Math.log10(r):-100;
}}

function runVAD(){{
  if(!vadActive)return;
  const loud=getMicRMS()>MIN_DB;
  if(loud){{
    speechHit=true;clearTimeout(silTimer);silStart=null;hideSil();
    if(isSpeaking&&currentVideo){{currentVideo.pause();currentVideo.remove();currentVideo=null;isSpeaking=false;wrap.classList.remove('speaking');}}
  }}else if(speechHit){{
    if(!silStart){{silStart=Date.now();animSil();}}
    clearTimeout(silTimer);
    silTimer=setTimeout(()=>{{
      if(vadActive&&speechHit){{
        vadActive=false;speechHit=false;mediaRec.stop();
        setStatus('Processando...','s-processing');
        tLabel.textContent='Transcrevendo e gerando resposta...';
      }}
    }},SILENCE_MS);
  }}
  requestAnimationFrame(runVAD);
}}

function animSil(){{
  if(!silStart)return;
  const p=Math.min((Date.now()-silStart)/SILENCE_MS*100,100);
  showSil(p); if(p<100&&silStart)requestAnimationFrame(animSil);
}}

async function startRec(){{
  if(isRec)return;
  try{{micStream=await navigator.mediaDevices.getUserMedia({{audio:{{echoCancellation:true,noiseSuppression:true,sampleRate:16000}}}});}}
  catch(e){{showErr('Permissão de microfone negada.');return;}}
  audioCtx=new(window.AudioContext||window.webkitAudioContext)();
  analyser=audioCtx.createAnalyser();analyser.fftSize=512;
  audioCtx.createMediaStreamSource(micStream).connect(analyser);
  const mime=['audio/webm;codecs=opus','audio/webm','audio/ogg'].find(m=>MediaRecorder.isTypeSupported(m))||'';
  try{{mediaRec=new MediaRecorder(micStream,mime?{{mimeType:mime}}:{{}});}}
  catch(e){{mediaRec=new MediaRecorder(micStream);}}
  chunks=[];
  mediaRec.ondataavailable=e=>{{if(e.data&&e.data.size>0)chunks.push(e.data);}};
  mediaRec.onstop=()=>uploadAudio(new Blob(chunks,{{type:mediaRec.mimeType||'audio/webm'}}));
  mediaRec.start(100);
  isRec=true;vadActive=true;speechHit=false;
  micBtn.classList.add('active');micBtn.textContent='⏹';
  setStatus('Ouvindo...','s-listening');
  tWait.style.display='block';tWait.textContent='—';
  tUser.style.display='none';tSep.style.display='none';tAi.style.display='none';
  tLabel.textContent='Aguardando sua fala...';
}}

function stopRec(){{
  vadActive=false;isRec=false;speechHit=false;
  clearTimeout(silTimer);silStart=null;hideSil();
  if(mediaRec&&mediaRec.state!=='inactive')try{{mediaRec.stop();}}catch(e){{}}
  if(micStream)micStream.getTracks().forEach(t=>t.stop());micStream=null;
  if(audioCtx)try{{audioCtx.close();}}catch(e){{}}audioCtx=null;analyser=null;
  micBtn.classList.remove('active');micBtn.textContent='🎤';
}}

function uploadAudio(blob){{
  if(blob.size<1500){{resetToIdle();return;}}
  const par=window.parent.document;
  function tryInject(attempt){{
    let input=par.querySelector('[data-testid="stFileUploader"] input[type="file"]')
           ||par.querySelector('[data-testid="stFileUploaderDropzone"] input[type="file"]')
           ||Array.from(par.querySelectorAll('input[type="file"]')).find(i=>i.accept&&i.accept.includes('webm'));
    if(!input){{
      if(attempt<8){{setTimeout(()=>tryInject(attempt+1),300);return;}}
      showErr('Input não encontrado.'); resetToIdle(); return;
    }}
    const ext=blob.type.includes('ogg')?'ogg':'webm';
    const file=new File([blob],`vm_${{Date.now()}}.${{ext}}`,{{type:blob.type||'audio/webm'}});
    const dt=new DataTransfer(); dt.items.add(file);
    input.files=dt.files;
    input.dispatchEvent(new Event('change',{{bubbles:true}}));
    input.dispatchEvent(new Event('input',{{bubbles:true}}));
  }}
  tryInject(0);
}}

function resetToIdle(){{
  stopRec();
  setStatus('Clique no microfone para continuar','');
}}

micBtn.onclick=()=>{{
  if(currentVideo){{currentVideo.pause();currentVideo.remove();currentVideo=null;}}
  try{{speechSynthesis.cancel();}}catch(e){{}}
  isSpeaking=false; wrap.classList.remove('speaking');
  if(isRec) resetToIdle();
  else startRec();
}};

// ── Restaura estado (Python já tem resposta pronta) ───────────────────────────
window.addEventListener('load',()=>{{
  if(PY_ERROR&&PY_ERROR.length>1){{showErr(PY_ERROR);setStatus('Erro','');return;}}
  if(PY_REPLY&&PY_REPLY.length>1){{
    showTranscript(PY_USER_SAID,PY_REPLY);
    if(DID_OK&&PY_VIDEO_URL&&PY_VIDEO_URL.length>10){{
      setStatus('Gerando avatar D-ID...','s-generating');
      playDIDVideo(PY_VIDEO_URL, PY_TTS_B64, PY_REPLY);
    }} else {{
      playFallbackAudio(PY_TTS_B64, PY_REPLY);
    }}
    return;
  }}
  if(PY_USER_SAID&&PY_USER_SAID.length>1) showTranscript(PY_USER_SAID,'');
}});
</script></body></html>""", height=720, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# NOVA FUNÇÃO _vm_process_audio_did() — substitui _vm_process_audio() no app.py
# ══════════════════════════════════════════════════════════════════════════════

def _vm_process_audio_did(raw: bytes, lang: str, conv_id: str,
                           did_voice: str, is_prof: bool) -> None:
    """
    Versão do _vm_process_audio com suporte a D-ID.
    Gera vídeo com lip-sync real quando D-ID está disponível.
    """
    from did_avatar import generate_avatar_video, did_available

    txt = transcribe_bytes(raw, suffix=".webm", language=lang)
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
    context  = f"\n\nStudent: Name={user['name']}, Level={user['level']}, Focus={user['focus']}."

    history.append({"role": "user", "content": txt})
    client = anthropic.Anthropic(api_key=API_KEY)
    resp   = client.messages.create(
        model="claude-haiku-4-5", max_tokens=1000,
        system=SYSTEM_PROMPT + context, messages=history
    )
    reply = resp.content[0].text
    history.append({"role": "assistant", "content": reply})
    st.session_state["_vm_history"] = history
    st.session_state["_vm_reply"]   = reply

    # Geração paralela: TTS de áudio (fallback) + D-ID vídeo
    tts_b64 = ""
    if tts_available():
        ab = text_to_speech(reply)
        if ab:
            tts_b64 = base64.b64encode(ab).decode()
    st.session_state["_vm_tts_b64"] = tts_b64

    # D-ID: gera vídeo com lip-sync (leva 5-15s)
    if did_available():
        video_url = generate_avatar_video(reply, is_professor=is_prof, voice_id=did_voice)
        st.session_state["_vm_video_url"] = video_url or ""
    else:
        st.session_state["_vm_video_url"] = ""

    # Persiste no histórico
    append_message(username, conv_id, "user", txt, audio=True)
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64 or None)
