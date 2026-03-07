import os
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import streamlit.components.v1 as components
import anthropic
from datetime import datetime
from database import (
    init_db, authenticate, register_student, load_students,
    new_conversation, list_conversations, load_conversation,
    append_message, get_all_students_stats,
    update_profile, update_password
)
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from file_reader import extract_file

# Importa o FontAwesome para os ícones
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">', unsafe_allow_html=True)

init_db()
API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
PHOTO_PATH = os.getenv("PROFESSOR_PHOTO", "assets/professor.jpg")
PROF_NAME  = os.getenv("PROFESSOR_NAME",  "Professor Avatar")

# Cria um contador para limpar o gravador de áudio automaticamente
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0

# ── Foto ──────────────────────────────────────────────────────────────────────
def get_photo_b64():
    p = Path(PHOTO_PATH)
    if p.exists():
        ext = p.suffix.lower().replace(".","")
        mime = "jpeg" if ext in ("jpg","jpeg") else ext
        return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None

PHOTO_B64 = get_photo_b64()

def avatar_html(size=52, speaking=False):
    cls = "speaking" if speaking else ""
    if PHOTO_B64:
        return (f'<div class="avatar-wrap {cls}" style="width:{size}px;height:{size}px">'
                f'<img src="{PHOTO_B64}" class="avatar-img"/><div class="avatar-ring"></div></div>')
    return (f'<div class="avatar-circle {cls}" '
            f'style="width:{size}px;height:{size}px;font-size:{int(size*.48)}px">🧑‍🏫</div>')

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title=f"{PROF_NAME} · English", page_icon="🎓", layout="wide")

def load_css(path: str):
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

load_css("styles/style.css")

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, and encouraging.
Students: teenagers (False Beginner/Pre-Intermediate) and adults focused on Business/News.
Teaching Style:
- Neuro-learning: guide students to discover their own errors. Never just give the answer.
  Example: If they say "he go" → "Quick check — what ending do we add for he/she/it? 😊"
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT responses. **Bold** grammar points. End with ONE engaging question.
Rules: Simple English. Teens→Fortnite/Netflix/TikTok. Adults→LinkedIn/news.
Celebrate progress 🎉. Portuguese → acknowledge briefly, switch to English."""

# ── Session state ─────────────────────────────────────────────────────────────
_defaults = {"logged_in":False,"user":None,"page":"chat","speaking":False,
             "conv_id":None,"voice_mode":False}
for k,v in _defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ── Auto-login via localStorage ───────────────────────────────────────────────
if not st.session_state.logged_in:
    components.html("""<script>
    const u = localStorage.getItem("pav_user");
    if(u){
      const url=new URL(window.parent.location.href);
      if(url.searchParams.get("_u")!==u){
        url.searchParams.set("_u",u);
        window.parent.location.replace(url.toString());
      }
    }
    </script>""", height=0)
    params = st.query_params
    if "_u" in params:
        uname = params["_u"]
        students = load_students()
        if uname in students:
            udata = students[uname]
            st.session_state.logged_in = True
            st.session_state.user = {"username": uname, **udata}
            st.session_state.page = "dashboard" if udata["role"]=="professor" else "chat"
            st.session_state.conv_id = None
            st.query_params.clear()
            st.rerun()

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_or_create_conv(username):
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id

def send_to_claude(username, user, conv_id, text, image_b64=None, image_media_type=None):
    client  = anthropic.Anthropic(api_key=API_KEY)
    context = f"\n\nStudent: Name={user['name']}, Level={user['level']}, Focus={user['focus']}."
    msgs    = load_conversation(username, conv_id)
    api_msgs = [{"role":"user" if m["role"]=="user" else "assistant",
                 "content": m["content"]} for m in msgs]
    if image_b64 and image_media_type and api_msgs and api_msgs[-1]["role"]=="user":
        api_msgs[-1]["content"] = [
            {"type":"image","source":{"type":"base64","media_type":image_media_type,"data":image_b64}},
            {"type":"text","text":text}]
    resp = client.messages.create(
        model="claude-haiku-4-5", max_tokens=400,
        system=SYSTEM_PROMPT + context, messages=api_msgs)
    reply_text = resp.content[0].text
    tts_b64_str = None
    if tts_available():
        audio_bytes = text_to_speech(reply_text)
        if audio_bytes:
            tts_b64_str = base64.b64encode(audio_bytes).decode()
            st.session_state["_tts_audio"] = tts_b64_str
    append_message(username, conv_id, "assistant", reply_text, tts_b64=tts_b64_str)
    return reply_text

def js_save_user(u):
    components.html(f"<script>localStorage.setItem('pav_user','{u}');</script>", height=0)
def js_clear_user():
    components.html("<script>localStorage.removeItem('pav_user');</script>", height=0)

# ── Audio player ──────────────────────────────────────────────────────────────
def render_audio_player(tts_b64: str, msg_time: str, player_id: str) -> str:
    return f"""<!DOCTYPE html><html><head>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:transparent;font-family:'Sora',sans-serif;overflow:hidden;}}
.player{{display:flex;align-items:center;gap:8px;padding:3px 0;flex-wrap:wrap;}}
.tl{{font-size:.62rem;color:#8b949e;font-family:'JetBrains Mono',monospace;flex-shrink:0;}}
.pb{{background:none;border:1px solid #30363d;border-radius:20px;color:#f0a500;font-size:.75rem;
     padding:2px 10px;cursor:pointer;transition:background .15s,border-color .15s;white-space:nowrap;flex-shrink:0;}}
.pb:hover{{background:rgba(240,165,0,.12);border-color:#f0a500;}}
.pw{{flex:1;min-width:60px;height:3px;background:#30363d;border-radius:2px;cursor:pointer;}}
.pf{{height:100%;background:linear-gradient(90deg,#f0a500,#e05c2a);border-radius:2px;width:0%;transition:width .1s linear;pointer-events:none;}}
.sw{{display:flex;align-items:center;gap:3px;flex-shrink:0;}}
.sb{{background:none;border:1px solid #30363d;border-radius:4px;color:#8b949e;font-size:.65rem;
     padding:1px 5px;cursor:pointer;transition:all .15s;}}
.sb:hover,.sb.on{{border-color:#f0a500;color:#f0a500;background:rgba(240,165,0,.08);}}
.vw{{display:flex;align-items:center;gap:4px;flex-shrink:0;}}
.vi{{font-size:.75rem;cursor:pointer;color:#8b949e;}}
.vs{{width:50px;height:3px;accent-color:#f0a500;cursor:pointer;}}
</style></head><body>
<div class="player">
  <span class="tl">{msg_time}</span>
  <button class="pb" id="b">▶ Ouvir</button>
  <div class="pw" id="pw"><div class="pf" id="pf"></div></div>
  <div class="sw" id="sw">
    <span style="font-size:.6rem;color:#8b949e;">vel:</span>
    <button class="sb" data-r="0.75">0.75×</button>
    <button class="sb on" data-r="1">1×</button>
    <button class="sb" data-r="1.25">1.25×</button>
    <button class="sb" data-r="1.5">1.5×</button>
  </div>
  <div class="vw">
    <span class="vi" id="vi">🔊</span>
    <input type="range" class="vs" id="vs" min="0" max="1" step="0.05" value="1">
  </div>
</div>
<script>
(function(){{
  const audio=new Audio('data:audio/mpeg;base64,{tts_b64}');
  const b=document.getElementById('b'),pf=document.getElementById('pf'),
        pw=document.getElementById('pw'),vs=document.getElementById('vs'),
        vi=document.getElementById('vi'),sw=document.getElementById('sw');
  b.onclick=()=>{{ if(!audio.paused){{audio.pause();b.textContent='▶ Ouvir';}}
                   else{{audio.play();b.textContent='⏸ Pausar';}} }};
  audio.onended=()=>{{b.textContent='▶ Ouvir';pf.style.width='0%';}};
  audio.ontimeupdate=()=>{{ if(audio.duration) pf.style.width=(audio.currentTime/audio.duration*100)+'%'; }};
  pw.onclick=e=>{{ const r=pw.getBoundingClientRect();
                   audio.currentTime=((e.clientX-r.left)/r.width)*audio.duration; }};
  sw.querySelectorAll('.sb').forEach(btn=>{{
    btn.onclick=function(){{ sw.querySelectorAll('.sb').forEach(x=>x.classList.remove('on'));
      this.classList.add('on'); audio.playbackRate=parseFloat(this.dataset.r); }};
  }});
  vs.oninput=()=>{{ audio.volume=parseFloat(vs.value);
    vi.textContent=audio.volume===0?'🔇':audio.volume<0.5?'🔉':'🔊'; }};
  vi.onclick=()=>{{ if(audio.volume>0){{audio._v=audio.volume;audio.volume=0;vs.value=0;vi.textContent='🔇';}}
                    else{{audio.volume=audio._v||1;vs.value=audio.volume;vi.textContent='🔊';}} }};
}})();
</script></body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN — widgets nativos Streamlit + CSS customizado
# ══════════════════════════════════════════════════════════════════════════════
def show_login():
    # CSS específico da tela de login
    st.markdown("""
<style>
/* Esconde elementos padrão do Streamlit na tela de login */
[data-testid="stSidebar"]         { display: none !important; }
[data-testid="stHeader"]          { display: none !important; }
[data-testid="stToolbar"]         { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
footer                            { display: none !important; }
.stApp > div:first-child          { padding: 0 !important; }

/* Centraliza o conteúdo */
.login-outer {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #080c12;
  position: relative;
  overflow: hidden;
  padding: 20px;
}

/* Orbs de fundo */
.login-outer::before {
  content: '';
  position: fixed;
  width: 500px; height: 500px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(240,165,0,.12), transparent 70%);
  top: -120px; right: -100px;
  animation: drift 12s ease-in-out infinite alternate;
  pointer-events: none;
}
.login-outer::after {
  content: '';
  position: fixed;
  width: 400px; height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(224,92,42,.10), transparent 70%);
  bottom: -100px; left: -80px;
  animation: drift 12s ease-in-out infinite alternate-reverse;
  pointer-events: none;
}
@keyframes drift {
  from { transform: translate(0,0) scale(1); }
  to   { transform: translate(30px,20px) scale(1.08); }
}

/* Card */
.login-card {
  background: #131b28;
  border: 1px solid #1e2a3a;
  border-radius: 24px;
  padding: 40px 36px 32px;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 24px 80px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.03);
  position: relative;
  z-index: 1;
}

/* Avatar */
.login-avatar-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}
.login-avatar-img {
  width: 88px; height: 88px;
  border-radius: 50%;
  border: 2.5px solid #f0a500;
  object-fit: cover; object-position: top;
  box-shadow: 0 0 0 5px rgba(240,165,0,.12), 0 0 32px rgba(240,165,0,.2);
}
.login-avatar-emoji {
  width: 88px; height: 88px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f0a500, #e05c2a);
  display: flex; align-items: center; justify-content: center;
  font-size: 40px;
  box-shadow: 0 0 0 5px rgba(240,165,0,.12), 0 0 32px rgba(240,165,0,.2);
}

/* Título */
.login-title {
  text-align: center;
  margin-bottom: 24px;
}
.login-title h2 {
  font-size: 1.5rem;
  font-weight: 800;
  background: linear-gradient(135deg, #f0a500, #e05c2a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0 0 4px;
}
.login-title p {
  font-size: .8rem;
  color: #7a8899;
  margin: 0;
}

/* Tabs customizadas */
.login-tabs {
  display: flex;
  background: rgba(255,255,255,.04);
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 20px;
}
.login-tab {
  flex: 1;
  text-align: center;
  padding: 8px;
  border-radius: 9px;
  cursor: pointer;
  font-size: .83rem;
  font-weight: 600;
  color: #7a8899;
  transition: all .2s;
  border: none;
  background: none;
}
.login-tab.active {
  background: #0f1520;
  color: #e6edf3;
  box-shadow: 0 2px 8px rgba(0,0,0,.3);
}

/* Streamlit input overrides */
.stTextInput label {
  font-size: .72rem !important;
  color: #7a8899 !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: .8px !important;
}
.stTextInput input {
  background: rgba(255,255,255,.05) !important;
  border: 1px solid #2a3a50 !important;
  border-radius: 10px !important;
  color: #e6edf3 !important;
  font-family: 'Sora', sans-serif !important;
  font-size: .88rem !important;
}
.stTextInput input:focus {
  border-color: #f0a500 !important;
  box-shadow: 0 0 0 3px rgba(240,165,0,.12) !important;
}

/* Submit button */
.stForm [data-testid="stFormSubmitButton"] button,
div[data-testid="stButton"] > button.login-btn {
  background: linear-gradient(135deg, #f0a500, #e05c2a) !important;
  border: none !important;
  border-radius: 12px !important;
  color: #000 !important;
  font-weight: 700 !important;
  font-size: .9rem !important;
  padding: 12px !important;
  width: 100% !important;
  letter-spacing: .3px !important;
  box-shadow: 0 4px 20px rgba(240,165,0,.25) !important;
  transition: all .2s !important;
}
.stForm [data-testid="stFormSubmitButton"] button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 28px rgba(240,165,0,.35) !important;
}

/* Força largura dos forms */
.login-form-wrap {
  max-width: 420px;
  margin: 0 auto;
}

/* Footer */
.login-footer {
  text-align: center;
  font-size: .7rem;
  color: #2a3a4a;
  margin-top: 20px;
}

/* Oculta o stApp background padrão */
.stApp { background: #080c12 !important; }
</style>
""", unsafe_allow_html=True)

    # ── Controle de aba via session_state ─────────────────────────────────────
    if "_login_tab" not in st.session_state:
        st.session_state["_login_tab"] = "login"

    # ── Cabeçalho visual ──────────────────────────────────────────────────────
    avatar_tag = (f'<div class="login-avatar-img" style="background:url({PHOTO_B64}) center/cover;border-radius:50%;width:88px;height:88px;border:2.5px solid #f0a500;box-shadow:0 0 0 5px rgba(240,165,0,.12),0 0 32px rgba(240,165,0,.2);margin:0 auto 20px;"></div>'
                  if PHOTO_B64 else '<div class="login-avatar-emoji" style="width:88px;height:88px;border-radius:50%;background:linear-gradient(135deg,#f0a500,#e05c2a);display:flex;align-items:center;justify-content:center;font-size:40px;margin:0 auto 20px;">🧑‍🏫</div>')

    st.markdown(f"""
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#080c12;padding:20px;position:relative;">
<div style="background:#131b28;border:1px solid #1e2a3a;border-radius:24px;padding:36px 32px 28px;width:100%;max-width:420px;box-shadow:0 24px 80px rgba(0,0,0,.5);position:relative;z-index:1;">
  {avatar_tag}
  <div style="text-align:center;margin-bottom:24px;">
    <h2 style="font-size:1.4rem;font-weight:800;background:linear-gradient(135deg,#f0a500,#e05c2a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 4px;">{PROF_NAME}</h2>
    <p style="font-size:.8rem;color:#7a8899;margin:0;">Your personal English practice companion</p>
  </div>
</div>
</div>
""", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    col_login, col_reg = st.columns(2)
    with col_login:
        if st.button("🔑 Entrar", use_container_width=True, key="tab_btn_login",
                     type="primary" if st.session_state["_login_tab"]=="login" else "secondary"):
            st.session_state["_login_tab"] = "login"
            st.rerun()
    with col_reg:
        if st.button("✨ Criar Conta", use_container_width=True, key="tab_btn_reg",
                     type="primary" if st.session_state["_login_tab"]=="reg" else "secondary"):
            st.session_state["_login_tab"] = "reg"
            st.rerun()

    # ── Mensagens de feedback ─────────────────────────────────────────────────
    login_err = st.session_state.pop("_login_err", "")
    reg_err   = st.session_state.pop("_reg_err",   "")
    reg_ok    = st.session_state.pop("_reg_ok",    False)
    reg_name  = st.session_state.pop("_reg_name",  "")

    if login_err: st.error(f"❌ {login_err}")
    if reg_err:   st.error(f"❌ {reg_err}")
    if reg_ok:    st.success(f"✅ Conta criada! Bem-vindo(a), {reg_name}! Faça login.")

    # ── Formulário de LOGIN ───────────────────────────────────────────────────
    if st.session_state["_login_tab"] == "login":
        with st.form("form_login", clear_on_submit=False):
            u = st.text_input("Username", placeholder="seu.usuario", key="li_u")
            p = st.text_input("Senha", type="password", placeholder="••••••••", key="li_p")
            submitted = st.form_submit_button("Entrar →", use_container_width=True)
            if submitted:
                if not u or not p:
                    st.error("❌ Preencha todos os campos.")
                else:
                    user = authenticate(u, p)
                    if user:
                        st.session_state.update(
                            logged_in=True,
                            user={"username": u, **user},
                            page="dashboard" if user["role"] == "professor" else "chat",
                            conv_id=None
                        )
                        js_save_user(u)
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha incorretos.")

    # ── Formulário de REGISTRO ────────────────────────────────────────────────
    else:
        with st.form("form_reg", clear_on_submit=False):
            rn = st.text_input("Nome completo", placeholder="João Silva",     key="r_n")
            re = st.text_input("E-mail",        placeholder="joao@email.com", key="r_e")
            ru = st.text_input("Username",       placeholder="joao.silva",    key="r_u")
            rp = st.text_input("Senha", type="password",
                               placeholder="mínimo 6 caracteres",             key="r_p")
            submitted = st.form_submit_button("Criar Conta →", use_container_width=True)
            if submitted:
                if not rn or not re or not ru or not rp:
                    st.error("❌ Preencha todos os campos.")
                elif "@" not in re:
                    st.error("❌ E-mail inválido.")
                elif len(rp) < 6:
                    st.error("❌ Senha muito curta (mínimo 6 caracteres).")
                else:
                    ok, msg = register_student(ru, rn, rp, email=re)
                    if ok:
                        components.html(f"""<script>
const PAV_EMAILJS={{publicKey:'',serviceId:'',templateId:''}};
if(PAV_EMAILJS.publicKey){{
  const s=document.createElement('script');
  s.src='https://cdn.jsdelivr.net/npm/@emailjs/browser@4/dist/email.min.js';
  s.onload=()=>{{
    emailjs.init(PAV_EMAILJS.publicKey);
    emailjs.send(PAV_EMAILJS.serviceId,PAV_EMAILJS.templateId,{{
      to_name:{json.dumps(rn)},to_email:{json.dumps(re)},
      username:{json.dumps(ru)},app_name:{json.dumps(PROF_NAME)},
      login_url:window.parent.location.origin
    }});
  }};
  document.head.appendChild(s);
}}
</script>""", height=0)
                        st.session_state["_reg_ok"]   = True
                        st.session_state["_reg_name"]  = rn
                        st.session_state["_login_tab"] = "login"
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    st.markdown(f'<div style="text-align:center;font-size:.7rem;color:#2a3a4a;margin-top:16px;">© 2025 · {PROF_NAME} · AI English Coach</div>',
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL DO USUÁRIO
# ══════════════════════════════════════════════════════════════════════════════
def show_profile():
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})

    st.markdown("## ⚙️ Configurações do Perfil")
    st.markdown("---")

    tab_geral, tab_pers, tab_conta = st.tabs(["🎨 Geral", "🧠 Personalização", "👤 Conta"])

    # ── ABA GERAL ─────────────────────────────────────────────────────────────
    with tab_geral:
        st.markdown("### Aparência")
        col1, col2 = st.columns(2)
        with col1:
            theme = st.selectbox("Tema", ["dark","light","system"],
                index=["dark","light","system"].index(profile.get("theme","dark")),
                key="pf_theme")
            lang = st.selectbox("Idioma da interface", ["pt-BR","en-US","en-GB"],
                index=["pt-BR","en-US","en-GB"].index(profile.get("language","pt-BR")),
                key="pf_lang")
        with col2:
            accent = st.color_picker("Cor de destaque",
                value=profile.get("accent_color","#f0a500"), key="pf_accent")

        st.markdown("### Voz")
        col3, col4 = st.columns(2)
        with col3:
            voice_lang = st.selectbox("Idioma da transcrição (Whisper)",
                ["en","pt","es","fr","de"],
                index=["en","pt","es","fr","de"].index(profile.get("voice_lang","en")),
                key="pf_vlang")
        with col4:
            speech_lang = st.selectbox("Sotaque (Text-to-Speech fallback)",
                ["en-US","en-GB","pt-BR"],
                index=["en-US","en-GB","pt-BR"].index(profile.get("speech_lang","en-US")),
                key="pf_slang")

        if st.button("💾 Salvar Geral", key="save_geral"):
            update_profile(username, {
                "theme": theme, "language": lang,
                "accent_color": accent,
                "voice_lang": voice_lang, "speech_lang": speech_lang,
            })
            # Atualiza session_state
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Configurações salvas!")

    # ── ABA PERSONALIZAÇÃO ────────────────────────────────────────────────────
    with tab_pers:
        st.markdown("### Sobre Você")
        col1, col2 = st.columns(2)
        with col1:
            nickname   = st.text_input("Apelido (como a IA te chama)",
                value=profile.get("nickname",""), key="pf_nick")
            occupation = st.text_input("Ocupação",
                value=profile.get("occupation",""), placeholder="ex: Desenvolvedor, Estudante",
                key="pf_occ")
        with col2:
            level = st.selectbox("Nível de inglês",
                ["False Beginner","Pre-Intermediate","Intermediate","Business English"],
                index=["False Beginner","Pre-Intermediate","Intermediate","Business English"]
                      .index(user.get("level","False Beginner")),
                key="pf_level")
            focus = st.selectbox("Foco das aulas",
                ["General Conversation","Sports & Games","Business & News","Series & Pop Culture"],
                index=["General Conversation","Sports & Games","Business & News","Series & Pop Culture"]
                      .index(user.get("focus","General Conversation")),
                key="pf_focus")

        st.markdown("### Estilo da IA")
        col3, col4 = st.columns(2)
        with col3:
            ai_style = st.selectbox("Tom das conversas",
                ["Warm & Encouraging","Formal & Professional","Fun & Casual","Strict & Direct"],
                index=["Warm & Encouraging","Formal & Professional","Fun & Casual","Strict & Direct"]
                      .index(profile.get("ai_style","Warm & Encouraging")),
                key="pf_aistyle")
        with col4:
            ai_tone = st.selectbox("Papel da IA",
                ["Teacher","Conversation Partner","Tutor","Business Coach"],
                index=["Teacher","Conversation Partner","Tutor","Business Coach"]
                      .index(profile.get("ai_tone","Teacher")),
                key="pf_aitone")

        custom = st.text_area("Instruções personalizadas para a IA",
            value=profile.get("custom_instructions",""),
            placeholder="ex: Sempre me corrija quando eu errar o Past Simple. Use exemplos de tecnologia.",
            height=100, key="pf_custom")

        if st.button("💾 Salvar Personalização", key="save_pers"):
            update_profile(username, {
                "nickname": nickname, "occupation": occupation,
                "ai_style": ai_style, "ai_tone": ai_tone,
                "custom_instructions": custom,
                "level": level, "focus": focus,
            })
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Perfil salvo!")

    # ── ABA CONTA ─────────────────────────────────────────────────────────────
    with tab_conta:
        st.markdown("### Informações da Conta")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Nome completo",
                value=user.get("name",""), key="pf_fname")
        with col2:
            email = st.text_input("E-mail",
                value=user.get("email",""), key="pf_email")

        st.markdown(f"**Username:** `{username}`")
        st.markdown(f"**Conta criada em:** {user.get('created_at','')[:10]}")

        if st.button("💾 Salvar Dados", key="save_conta"):
            update_profile(username, {"name": full_name, "email": email})
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Dados atualizados!")

        st.markdown("---")
        st.markdown("### Alterar Senha")
        col3, col4 = st.columns(2)
        with col3:
            new_pw  = st.text_input("Nova senha", type="password", key="pf_newpw")
        with col4:
            conf_pw = st.text_input("Confirmar senha", type="password", key="pf_confpw")

        if st.button("🔒 Alterar Senha", key="save_pw"):
            if len(new_pw) < 6:
                st.error("Senha muito curta.")
            elif new_pw != conf_pw:
                st.error("As senhas não coincidem.")
            else:
                from database import update_password
                update_password(username, new_pw)
                st.success("✅ Senha alterada!")

    if st.button("← Voltar ao Chat", key="back_chat"):
        st.session_state.page = "chat"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MODO CONVERSA
# ══════════════════════════════════════════════════════════════════════════════
def _vm_process_audio(raw: bytes, lang: str) -> None:
    txt = transcribe_bytes(raw, suffix=".webm", language=lang)
    if not txt or txt.startswith("❌") or txt.startswith("⚠️"):
        st.session_state["_vm_error"] = txt or "Não entendi. Tente novamente."
        return
    st.session_state["_vm_user_said"] = txt
    if not API_KEY:
        st.session_state["_vm_error"] = "❌ ANTHROPIC_API_KEY não configurada."
        return
    user    = st.session_state.user
    history = st.session_state.get("_vm_history", [])
    context = f"\n\nStudent: Name={user['name']}, Level={user['level']}, Focus={user['focus']}."
    history.append({"role":"user","content":txt})
    client = anthropic.Anthropic(api_key=API_KEY)
    resp   = client.messages.create(
        model="claude-haiku-4-5", max_tokens=1000,
        system=SYSTEM_PROMPT + context, messages=history)
    reply = resp.content[0].text
    history.append({"role":"assistant","content":reply})
    st.session_state["_vm_history"] = history
    tts_b64 = ""
    if tts_available():
        ab = text_to_speech(reply)
        if ab: tts_b64 = base64.b64encode(ab).decode()
    st.session_state["_vm_reply"]   = reply
    st.session_state["_vm_tts_b64"] = tts_b64


def show_voice_mode():
    user     = st.session_state.user
    profile  = user.get("profile", {})
    # Idioma vem do perfil do usuário
    whisper_lang    = profile.get("voice_lang",  "en")
    speech_lang_val = profile.get("speech_lang", "en-US")

    if st.button("✕ Fechar Modo Voz", key="close_voice_inner"):
        st.session_state.voice_mode = False
        for k in ["_vm_history","_vm_reply","_vm_tts_b64","_vm_user_said",
                  "_vm_error","_vm_last_upload"]:
            st.session_state.pop(k, None)
        st.rerun()

    # Esconde file uploader VISUALMENTE — sem pointer-events:none (JS precisa injetar no input)
    st.markdown("""<style>
[data-testid="stFileUploader"]{
  position:fixed!important;top:-9999px!important;left:-9999px!important;
  width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;
}
</style>""", unsafe_allow_html=True)

    # Recebe áudio
    audio_upload = st.file_uploader(
        "vm_audio", key="vm_audio_upload", label_visibility="collapsed",
        type=["webm","wav","ogg","mp4","m4a"])
    if audio_upload:
        uid = f"{audio_upload.name}_{audio_upload.size}"
        if uid != st.session_state.get("_vm_last_upload"):
            st.session_state["_vm_last_upload"] = uid
            for k in ["_vm_reply","_vm_tts_b64","_vm_user_said","_vm_error"]:
                st.session_state.pop(k, None)
            _vm_process_audio(audio_upload.read(), whisper_lang)
            st.rerun()

    user_said = st.session_state.get("_vm_user_said", "")
    reply     = st.session_state.get("_vm_reply",     "")
    tts_b64   = st.session_state.get("_vm_tts_b64",   "")
    vm_error  = st.session_state.get("_vm_error",     "")

    photo_tag = (f'<img src="{PHOTO_B64}" class="vm-avatar-img" />'
                 if PHOTO_B64 else '<div class="vm-avatar-emoji">🧑‍🏫</div>')

    us_js  = json.dumps(user_said)
    rep_js = json.dumps(reply)
    tts_js = json.dumps(tts_b64)
    err_js = json.dumps(vm_error)
    pnm_js = json.dumps(PROF_NAME)
    sl_js  = json.dumps(speech_lang_val)

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
:root{{--bg:#080c12;--surface:#0f1419;--border:#1e2530;
       --accent:#f0a500;--accent2:#e05c2a;--text:#e6edf3;--muted:#8b949e;
       --green:#3fb950;--red:#f85149;--blue:#58a6ff;}}
html,body{{background:var(--bg);font-family:'Sora',sans-serif;color:var(--text);height:100%;overflow:hidden;}}
.vm{{display:flex;flex-direction:column;align-items:center;justify-content:center;
     height:100vh;gap:20px;padding:20px;
     background:radial-gradient(ellipse at 50% 25%,rgba(240,165,0,.08) 0%,transparent 60%);}}
.ring-wrap{{position:relative;width:140px;height:140px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}}
.vm-avatar-img{{width:124px;height:124px;border-radius:50%;object-fit:cover;object-position:top;border:2px solid var(--accent);position:relative;z-index:2;}}
.vm-avatar-emoji{{width:124px;height:124px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-size:58px;position:relative;z-index:2;}}
.ring{{position:absolute;inset:-8px;border-radius:50%;border:2.5px solid transparent;
       background:conic-gradient(from 0deg,var(--accent),var(--accent2),var(--accent)) border-box;
       -webkit-mask:linear-gradient(#fff 0 0) padding-box,linear-gradient(#fff 0 0);
       -webkit-mask-composite:destination-out;mask-composite:exclude;
       animation:spin 5s linear infinite;opacity:.35;transition:opacity .4s;}}
.ring.listening{{opacity:1;animation-duration:1.2s;background:conic-gradient(from 0deg,var(--green),#58a6ff,var(--green)) border-box;}}
.ring.speaking {{opacity:1;animation-duration:.7s;}}
.ring.processing{{opacity:.9;animation-duration:2s;background:conic-gradient(from 0deg,var(--blue),#a371f7,var(--blue)) border-box;}}
@keyframes spin{{to{{transform:rotate(360deg);}}}}
.pulse{{position:absolute;inset:-18px;border-radius:50%;border:1px solid rgba(63,185,80,.25);animation:pulse-out 1.6s ease-out infinite;display:none;pointer-events:none;}}
.pulse:nth-child(2){{animation-delay:.53s;}}.pulse:nth-child(3){{animation-delay:1.06s;}}
.listening .pulse{{display:block;}}
@keyframes pulse-out{{0%{{transform:scale(1);opacity:.5;}}100%{{transform:scale(1.6);opacity:0;}}}}
.bars{{display:none;align-items:flex-end;gap:4px;height:32px;}}
.speaking .bars{{display:flex;}}
.bar{{width:4px;border-radius:3px;background:linear-gradient(180deg,var(--accent2),var(--accent));animation:bdance .55s ease-in-out infinite alternate;}}
.bar:nth-child(1){{height:8px;animation-delay:0s;}}.bar:nth-child(2){{height:22px;animation-delay:.1s;}}.bar:nth-child(3){{height:14px;animation-delay:.2s;}}.bar:nth-child(4){{height:28px;animation-delay:.07s;}}.bar:nth-child(5){{height:10px;animation-delay:.17s;}}.bar:nth-child(6){{height:24px;animation-delay:.27s;}}.bar:nth-child(7){{height:6px;animation-delay:.12s;}}
@keyframes bdance{{from{{transform:scaleY(.25);}}to{{transform:scaleY(1);}}}}
.info{{text-align:center;min-height:44px;}}
.prof-name{{font-size:1rem;font-weight:700;color:var(--accent);margin-bottom:3px;}}
.status{{font-size:.78rem;color:var(--muted);transition:color .3s;}}
.status.s-listening{{color:var(--green);}}.status.s-speaking{{color:var(--accent);}}.status.s-processing{{color:var(--blue);}}
.transcript{{max-width:480px;width:100%;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:12px 16px;font-size:.84rem;line-height:1.65;min-height:60px;}}
.t-label{{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}}
.t-user{{color:#adbac7;margin-bottom:6px;display:none;}}
.t-sep{{border:none;border-top:1px solid var(--border);margin:6px 0;display:none;}}
.t-ai{{color:var(--text);display:none;}}.t-wait{{color:#3d4a5c;font-style:italic;}}
.sil{{width:130px;height:3px;background:var(--border);border-radius:2px;overflow:hidden;visibility:hidden;margin:0 auto;}}
.sil-fill{{height:100%;background:linear-gradient(90deg,var(--green),var(--accent));border-radius:2px;width:0%;}}
.sil.show{{visibility:visible;}}
.mic-btn{{width:64px;height:64px;border-radius:50%;border:none;cursor:pointer;font-size:26px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,var(--green),#2ea043);box-shadow:0 0 20px rgba(63,185,80,.3);transition:all .2s;}}
.mic-btn:hover{{transform:scale(1.07);}}
.mic-btn.active{{background:linear-gradient(135deg,var(--red),#c03030);box-shadow:0 0 26px rgba(248,81,73,.5);animation:mpulse .8s ease-in-out infinite alternate;}}
@keyframes mpulse{{from{{box-shadow:0 0 14px rgba(248,81,73,.3);}}to{{box-shadow:0 0 32px rgba(248,81,73,.7);}}}}
.hint{{font-size:.65rem;color:#2d3a4a;text-align:center;}}
.err{{font-size:.74rem;color:var(--red);text-align:center;max-width:340px;min-height:18px;}}
</style></head><body>
<div class="vm" id="vm">
  <div class="ring-wrap" id="ringWrap">
    {photo_tag}
    <div class="ring" id="ring"></div>
    <div class="pulse"></div><div class="pulse"></div><div class="pulse"></div>
  </div>
  <div class="info" id="infoWrap">
    <div class="prof-name">{PROF_NAME}</div>
    <div class="status" id="status">Clique no microfone para falar</div>
    <div class="bars">
      <div class="bar"></div><div class="bar"></div><div class="bar"></div>
      <div class="bar"></div><div class="bar"></div><div class="bar"></div>
      <div class="bar"></div>
    </div>
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
const PY_USER_SAID={us_js}, PY_REPLY={rep_js}, PY_TTS_B64={tts_js};
const PY_ERROR={err_js}, SPEECH_LANG={sl_js}, PROF_NAME={pnm_js};
const SILENCE_MS=1500, MIN_DB=-42;

let mediaRec=null,chunks=[],audioCtx=null,analyser=null,micStream=null;
let isRec=false,isSpeaking=false,vadActive=false,speechHit=false;
let silTimer=null,silStart=null,curAudio=null;

const vm=document.getElementById('vm'), ring=document.getElementById('ring'),
      ringW=document.getElementById('ringWrap'), status=document.getElementById('status'),
      tLabel=document.getElementById('tLabel'), tUser=document.getElementById('tUser'),
      tSep=document.getElementById('tSep'), tAi=document.getElementById('tAi'),
      tWait=document.getElementById('tWait'), sil=document.getElementById('sil'),
      silFill=document.getElementById('silFill'), micBtn=document.getElementById('micBtn'),
      errBox=document.getElementById('errBox');

function setRing(s){{ ring.className='ring '+s; ringW.className='ring-wrap '+s; vm.className='vm '+s; }}
function setStatus(t,c=''){{ status.textContent=t; status.className='status '+c; }}
function showErr(m){{ errBox.textContent=m; setTimeout(()=>errBox.textContent='',5000); }}
function showSil(p){{ sil.classList.add('show'); silFill.style.width=p+'%'; }}
function hideSil(){{ sil.classList.remove('show'); silFill.style.width='0%'; }}
function showTranscript(u,a){{
  tWait.style.display='none';
  if(u){{ tLabel.textContent='Você disse:'; tUser.textContent=u; tUser.style.display='block'; }}
  if(a){{ tSep.style.display='block'; tAi.textContent=a; tAi.style.display='block'; }}
}}

function getRMS(){{
  if(!analyser) return -100;
  const d=new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(d);
  let s=0; for(let i=0;i<d.length;i++) s+=d[i]*d[i];
  const r=Math.sqrt(s/d.length); return r>0?20*Math.log10(r):-100;
}}

function runVAD(){{
  if(!vadActive) return;
  const loud=getRMS()>MIN_DB;
  if(loud){{
    speechHit=true; clearTimeout(silTimer); silStart=null; hideSil();
    if(isSpeaking&&curAudio){{ curAudio.pause(); curAudio=null; isSpeaking=false; }}
  }} else if(speechHit){{
    if(!silStart){{ silStart=Date.now(); animSil(); }}
    clearTimeout(silTimer);
    silTimer=setTimeout(()=>{{
      if(vadActive&&speechHit){{
        vadActive=false; speechHit=false; mediaRec.stop();
        setRing('processing'); setStatus('Processando...','s-processing');
        tLabel.textContent='Transcrevendo...';
      }}
    }},SILENCE_MS);
  }}
  requestAnimationFrame(runVAD);
}}

function animSil(){{
  if(!silStart) return;
  const p=Math.min((Date.now()-silStart)/SILENCE_MS*100,100);
  showSil(p); if(p<100&&silStart) requestAnimationFrame(animSil);
}}

async function startRec(){{
  if(isRec) return;
  try{{
    micStream=await navigator.mediaDevices.getUserMedia({{audio:{{
      echoCancellation:true, noiseSuppression:true, sampleRate:16000
    }}}});
  }}catch(e){{ showErr('Permissão de microfone negada.'); return; }}

  audioCtx=new(window.AudioContext||window.webkitAudioContext)();
  analyser=audioCtx.createAnalyser(); analyser.fftSize=512;
  audioCtx.createMediaStreamSource(micStream).connect(analyser);

  // Escolhe o melhor formato disponível
  const mime=['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/ogg']
             .find(m=>MediaRecorder.isTypeSupported(m))||'';

  try{{
    mediaRec=new MediaRecorder(micStream,mime?{{mimeType:mime}}:{{}});
  }}catch(e){{
    mediaRec=new MediaRecorder(micStream);  // fallback sem options
  }}
  chunks=[];
  mediaRec.ondataavailable=e=>{{ if(e.data&&e.data.size>0) chunks.push(e.data); }};
  mediaRec.onstop=()=>uploadAudio(new Blob(chunks,{{type:mediaRec.mimeType||'audio/webm'}}));
  mediaRec.onerror=e=>{{ showErr('Erro na gravação: '+e.error); resetToIdle(); }};
  mediaRec.start(100);

  isRec=true; vadActive=true; speechHit=false;
  micBtn.classList.add('active'); micBtn.textContent='⏹';
  setRing('listening'); setStatus('Ouvindo...','s-listening');
  tWait.style.display='block'; tWait.textContent='—';
  tUser.style.display='none'; tSep.style.display='none'; tAi.style.display='none';
  tLabel.textContent='Aguardando sua fala...';
  runVAD();
}}

function stopRec(){{
  vadActive=false; isRec=false; speechHit=false;
  clearTimeout(silTimer); silStart=null; hideSil();
  if(mediaRec&&mediaRec.state!=='inactive') try{{mediaRec.stop();}}catch(e){{}}
  if(micStream) micStream.getTracks().forEach(t=>t.stop()); micStream=null;
  if(audioCtx) try{{audioCtx.close();}}catch(e){{}} audioCtx=null; analyser=null;
  micBtn.classList.remove('active'); micBtn.textContent='🎤';
}}

function uploadAudio(blob){{
  if(blob.size<1500){{ resetToIdle(); return; }}

  const par=window.parent.document;

  // Injeta CSS de ocultação visual (NUNCA pointer-events:none no container)
  if(!par.getElementById('vm-hide-css')){{
    const s=par.createElement('style'); s.id='vm-hide-css';
    s.textContent=`
      [data-testid="stFileUploader"]{{
        position:fixed!important;top:-9999px!important;left:-9999px!important;
        width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;
      }}
      audio{{display:none!important;}}
      [data-testid="stStatusWidget"],.stSpinner,[data-testid="stSpinner"]{{display:none!important;}}
    `;
    par.head.appendChild(s);
  }}

  // Retry até 8x (300ms entre tentativas) — DOM pode ainda estar montando
  function tryInject(attempt){{
    let input=par.querySelector('[data-testid="stFileUploader"] input[type="file"]')
           || par.querySelector('[data-testid="stFileUploaderDropzone"] input[type="file"]')
           || par.querySelector('section[data-testid="stFileUploader"] input')
           || Array.from(par.querySelectorAll('input[type="file"]')).find(i=>i.accept&&i.accept.includes('webm'));

    if(!input){{
      if(attempt<8){{ setTimeout(()=>tryInject(attempt+1),300); return; }}
      showErr('Mic input não encontrado — recarregue a página.');
      resetToIdle(); return;
    }}

    // Força pointer-events no input e pai imediato
    input.style.cssText+='pointer-events:auto!important;';
    if(input.parentElement) input.parentElement.style.pointerEvents='auto';

    const ext=blob.type.includes('ogg')?'ogg':(blob.type.includes('mp4')?'mp4':'webm');
    const file=new File([blob],`vm_${{Date.now()}}.${{ext}}`,{{type:blob.type||'audio/webm'}});
    const dt=new DataTransfer(); dt.items.add(file);
    input.files=dt.files;
    input.dispatchEvent(new Event('change',{{bubbles:true}}));
    input.dispatchEvent(new Event('input', {{bubbles:true}}));
  }}
  tryInject(0);
}}

function resetToIdle(){{
  stopRec(); setRing('idle'); setStatus('Clique no microfone para continuar','');
}}

function playTTS(b64,txt){{
  isSpeaking=true; setRing('speaking'); setStatus('Professora falando...','s-speaking');
  if(b64&&b64.length>20){{
    curAudio=new Audio('data:audio/mpeg;base64,'+b64);
    curAudio.onended=()=>{{ isSpeaking=false; curAudio=null; resetToIdle(); startRec(); }};
    curAudio.onerror=()=>{{ isSpeaking=false; curAudio=null; fallbackTTS(txt); }};
    curAudio.play().catch(()=>fallbackTTS(txt));
  }} else {{ fallbackTTS(txt); }}
}}

function fallbackTTS(text){{
  isSpeaking=true; setRing('speaking'); setStatus('Professora falando...','s-speaking');
  const u=new SpeechSynthesisUtterance(text.substring(0,500));
  u.lang=SPEECH_LANG; u.rate=0.95; u.pitch=1.05;
  const vv=speechSynthesis.getVoices();
  const pick=vv.find(v=>v.lang===SPEECH_LANG)||vv.find(v=>v.lang.startsWith(SPEECH_LANG.split('-')[0]));
  if(pick) u.voice=pick;
  u.onend=u.onerror=()=>{{ isSpeaking=false; resetToIdle(); startRec(); }};
  speechSynthesis.speak(u);
}}

micBtn.onclick=()=>{{ if(isRec) resetToIdle(); else startRec(); }};

window.addEventListener('load',()=>{{
  if(PY_ERROR&&PY_ERROR.length>1){{
    showErr(PY_ERROR); setRing(''); setStatus('Erro — tente novamente',''); return;
  }}
  if(PY_REPLY&&PY_REPLY.length>1){{
    showTranscript(PY_USER_SAID,PY_REPLY);
    playTTS(PY_TTS_B64,PY_REPLY); return;
  }}
  if(PY_USER_SAID&&PY_USER_SAID.length>1) showTranscript(PY_USER_SAID,'');
}});
</script></body></html>""", height=660, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════════════════
def show_chat():
    user     = st.session_state.user
    username = user["username"]
    conv_id  = get_or_create_conv(username)
    messages = load_conversation(username, conv_id)
    speaking = st.session_state.speaking

    if st.session_state.voice_mode:
        show_voice_mode()
        return

    with st.sidebar:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div>
            <div style="font-weight:600;font-size:.9rem;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#8b949e;"><span class="status-dot"></span>Online</div>
            </div></div><hr style="border-color:#30363d;margin:6px 0 12px">""",
            unsafe_allow_html=True)

        user_msgs = len([m for m in messages if m["role"]=="user"])
        st.markdown(f"""<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
            padding:10px 12px;margin-bottom:10px;font-size:.82rem;">
            <div style="color:#8b949e;font-size:.68rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
                👤 {user['name'].split()[0]} · {user['level']}</div>
            <div style="display:flex;justify-content:space-between;padding:2px 0;">
                <span>Msgs hoje</span>
                <span style="color:#f0a500;font-family:'JetBrains Mono',monospace">{user_msgs}</span>
            </div></div>""", unsafe_allow_html=True)

        if st.button("🎙️ Modo Conversa", use_container_width=True, key="btn_voice"):
            st.session_state.voice_mode = True; st.rerun()

        st.markdown("""<div style="font-size:.72rem;color:#8b949e;text-transform:uppercase;
            letter-spacing:1px;margin-bottom:8px;">🕘 Conversas</div>""", unsafe_allow_html=True)

        if st.button("➕ Nova conversa", use_container_width=True, key="btn_new"):
            st.session_state.conv_id = new_conversation(username); st.rerun()

        convs = list_conversations(username)
        if not convs:
            st.markdown('<div style="font-size:.78rem;color:#8b949e;padding:6px 2px;">Nenhuma conversa ainda.</div>',
                        unsafe_allow_html=True)
        for c in convs:
            is_active = c["id"] == conv_id
            prefix = "▶ " if is_active else ""
            if st.button(f"{prefix}{c['title']}", key=f"conv_{c['id']}",
                         use_container_width=True,
                         help=f"📅 {c['date']} · 💬 {c['count']} msgs"):
                st.session_state.conv_id = c["id"]; st.rerun()
            st.markdown(f'<div style="font-size:.65rem;color:#8b949e;margin:-10px 0 4px 4px;">'
                        f'📅 {c["date"]} · 💬 {c["count"]} msg</div>', unsafe_allow_html=True)

        st.markdown("<hr style='border-color:#30363d;margin:10px 0'>", unsafe_allow_html=True)
        if user["role"]=="professor":
            if st.button("📊 Painel", use_container_width=True):
                st.session_state.page="dashboard"; st.rerun()
        if st.button("⚙️ Perfil", use_container_width=True, key="btn_profile"):
            st.session_state.page="profile"; st.rerun()
        if st.button("🚪 Sair", use_container_width=True):
            js_clear_user()
            st.session_state.update(logged_in=False, user=None, conv_id=None); st.rerun()

    st.markdown(f"""<div class="prof-header">
        {avatar_html(56, speaking)}
        <div class="prof-info">
            <h1>{PROF_NAME}</h1>
            <p><span class="status-dot"></span>Online · {user['level']} · {user['focus']}</p>
        </div></div>""", unsafe_allow_html=True)

    if not messages:
        name_display = user.get("profile",{}).get("nickname","") or user['name'].split()[0]
        greeting = (f"Hey, {name_display}! 👋 Great to see you!\n\n"
                    f"Ready to practice? **What have you been up to lately?** "
                    f"Tell me in English — no worries about mistakes! 😊")
        append_message(username, conv_id, "assistant", greeting)
        messages = load_conversation(username, conv_id)

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for i, msg in enumerate(messages):
        content = msg["content"].replace("\n","<br>")
        t       = msg.get("time","")
        if msg["role"]=="assistant":
            av      = avatar_html(36, speaking and i==len(messages)-1)
            tts_b64 = msg.get("tts_b64","")
            st.markdown(
                f'<div class="bubble-row bot"><div class="bav-s">{av}</div><div>'
                f'<div class="bubble bot">{content}</div></div></div>',
                unsafe_allow_html=True)
            if tts_b64:
                components.html(render_audio_player(tts_b64, t, f"msg_{i}_{conv_id}"),
                                height=44, scrolling=False)
            else:
                st.markdown(f'<div class="btime" style="margin-left:46px;">{t}</div>',
                            unsafe_allow_html=True)
        else:
            extra = " audio-msg" if msg.get("audio") else ""
            icon  = "🎙️ " if msg.get("audio") else ""
            st.markdown(
                f'<div class="bubble-row user"><div class="bav-u">🎓</div><div>'
                f'<div class="bubble user{extra}">{icon}{content}</div>'
                f'<div class="btime">{t}</div></div></div>',
                unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    prompt = st.chat_input("Type a message")
    if prompt:
      with st.chat_message("user"):
        st.write(prompt)
        #if not API_KEY: st.error("Configure ANTHROPIC_API_KEY no .env"); st.stop()
        append_message(username, conv_id, "user", prompt)
        #st.session_state.speaking = True
        with st.chat_message("assistant", avatar=PHOTO_B64 or "🧑‍🏫"):
          with st.spinner("A Teacher Tati está digitando..."):
            try:
                # Aqui você chama o Anthropic (Claude)
                # OBS: Lembre-se de passar o histórico completo se desejar, aqui estou passando só o prompt atual para simplificar
                client = anthropic.Anthropic(api_key=API_KEY)
                
                resposta_claude = client.messages.create(
                    model="claude-3-haiku-20240307", # Ou o modelo que você preferir (sonnet, opus)
                    max_tokens=1000,
                    system="Você é a Teacher Tati, uma professora de inglês empática. Use o método sanduíche para corrigir os alunos.", # Coloque seu prompt do método Sanduíche aqui
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # Extrai o texto da resposta da IA
                resposta_ia = resposta_claude.content[0].text
                
                # 4. Mostra o texto da IA na tela
                st.write(resposta_ia)
                
                # 5. Gera a voz da Teacher Tati em background (ElevenLabs)
                tts_b64 = None
                if tts_available():
                    audio_bytes = text_to_speech(resposta_ia)
                    if audio_bytes:
                        # Converte para base64 para salvar no banco, se necessário
                        tts_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                        
                        # Mostra o player de áudio na tela embaixo do texto
                        st.audio(audio_bytes, format="audio/mpeg")
                
                # 6. Salva a resposta da IA no banco de dados (junto com o áudio em base64, se houver)
                append_message(username, conv_id, "assistant", resposta_ia, tts_b64=tts_b64)

            except Exception as e:
                st.error(f"Ops! Deu um erro de comunicação com a Teacher Tati: {e}")

    audio_val = st.audio_input(" ", key=f"voice_input_{st.session_state.audio_key}", label_visibility="collapsed")
    if audio_val and audio_val != st.session_state.get("_last_audio"):
        st.session_state["_last_audio"] = audio_val
        with st.spinner("Transcrevendo..."):
            txt = transcribe_bytes(audio_val.read(), ".wav", "en")
        if txt and not txt.startswith("❌") and not txt.startswith("⚠️"):
            if not API_KEY: st.error("Configure ANTHROPIC_API_KEY"); st.stop()
            append_message(username, conv_id, "user", txt, audio=True)
            st.session_state.speaking = True
            try:    send_to_claude(username, user, conv_id, txt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
            st.session_state.audio_key += 1
            st.rerun()
        elif txt: st.error(txt)

    uploaded = st.file_uploader("📎", key="file_upload", label_visibility="collapsed",
        type=["mp3","wav","ogg","m4a","webm","flac","pdf","doc","docx","txt","png","jpg","jpeg","webp"])
    if uploaded and uploaded.name != st.session_state.get("_last_file"):
        st.session_state["_last_file"] = uploaded.name
        raw = uploaded.read()
        if not API_KEY: st.error("Configure ANTHROPIC_API_KEY"); st.stop()
        result = extract_file(raw, uploaded.name)
        kind, label = result["kind"], result["label"]
        if kind=="audio":
            with st.spinner("🔄 Transcrevendo áudio..."):
                text = transcribe_bytes(raw, suffix=Path(uploaded.name).suffix.lower(), language="en")
            if text.startswith("❌") or text.startswith("⚠️"): st.error(text)
            else:
                append_message(username, conv_id, "user", f"🎙️ [Áudio: '{uploaded.name}']\n{text}", audio=True)
                st.session_state.speaking = True
                try:    send_to_claude(username, user, conv_id, f"🎙️ [Áudio: '{uploaded.name}']\n{text}")
                except Exception as e: st.error(f"❌ {e}")
                st.session_state.speaking = False; st.rerun()
        elif kind=="text":
            extracted = result["text"]
            if extracted.startswith("❌"): st.error(extracted)
            elif not extracted: st.warning(f"Sem texto em '{uploaded.name}'.")
            else:
                preview = extracted[:200].replace('\n',' ')
                msg = (f"📄 [{label}: '{uploaded.name}']\n\n{extracted}\n\n"
                       "Please help me understand this content — explain vocabulary, grammar, and key ideas.")
                append_message(username, conv_id, "user",
                               f"📄 [{label}: '{uploaded.name}'] — {preview}{'…' if len(extracted)>200 else ''}")
                st.session_state.speaking = True
                try:    send_to_claude(username, user, conv_id, msg)
                except Exception as e: st.error(f"❌ {e}")
                st.session_state.speaking = False; st.rerun()
        elif kind=="image":
            msg_text = (f"📸 [Imagem: '{uploaded.name}']\nPlease look at this image and help me learn English from it.")
            append_message(username, conv_id, "user", f"📸 [Imagem: '{uploaded.name}']")
            st.session_state.speaking = True
            try:    send_to_claude(username, user, conv_id, msg_text,
                                   image_b64=result["b64"], image_media_type=result["media_type"])
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False; st.rerun()
        else: st.warning(f"⚠️ Formato '{label}' não suportado.")

    st.markdown("""<script>
(function moveToChatBar(){
  const bottom=window.parent.document.querySelector('[data-testid="stBottom"]');
  if(!bottom){setTimeout(moveToChatBar,300);return;}
  if(bottom.querySelector('.pav-extras')) return;
  const aw=window.parent.document.querySelector('[data-testid="stAudioInput"]');
  const fw=window.parent.document.querySelector('[data-testid="stFileUploader"]');
  if(!aw||!fw){setTimeout(moveToChatBar,300);return;}
  const extras=window.parent.document.createElement('div');
  extras.className='pav-extras';
  const mb=window.parent.document.createElement('button');
  mb.className='pav-icon-btn'; mb.title='Gravar voz'; mb.innerHTML='🎤';
  mb.onclick=()=>{const b=aw.querySelector('button');if(b)b.click();};
  const ab=window.parent.document.createElement('button');
  ab.className='pav-icon-btn'; ab.title='Anexar arquivo'; ab.innerHTML='＋';
  ab.onclick=()=>{const i=fw.querySelector('input[type="file"]');if(i)i.click();};
  extras.appendChild(ab); extras.appendChild(mb);
  bottom.insertBefore(extras,bottom.firstChild);
  aw.style.cssText='position:fixed;bottom:-999px;left:-9999px;width:1px;height:1px;overflow:hidden;opacity:0';
  fw.style.cssText='position:fixed;bottom:-999px;left:-9999px;width:1px;height:1px;overflow:hidden;opacity:0';
  fw.querySelector('input[type="file"]').style.pointerEvents='auto';
})();
</script>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def show_dashboard():
    with st.sidebar:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div style="font-weight:600">{PROF_NAME}</div></div>
            <hr style="border-color:#30363d;margin:6px 0 12px">""", unsafe_allow_html=True)
        if st.button("💬 Chat", use_container_width=True): st.session_state.page="chat"; st.rerun()
        if st.button("🚪 Sair", use_container_width=True):
            js_clear_user(); st.session_state.update(logged_in=False,user=None); st.rerun()

    st.markdown("## 📊 Painel do Professor")
    st.markdown("---")
    stats = get_all_students_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    c1,c2,c3,c4=st.columns(4)
    for col,val,lbl in zip([c1,c2,c3,c4],
        [len(stats),sum(s["messages"] for s in stats),sum(s["corrections"] for s in stats),
         sum(1 for s in stats if s["last_active"][:10]==today)],
        ["Alunos","Mensagens","Correções","Ativos Hoje"]):
        col.markdown(f'<div class="stat-card"><div class="val">{val}</div><div class="lbl">{lbl}</div></div>',
                     unsafe_allow_html=True)
    st.markdown("<br>")
    st.markdown("### 👥 Alunos")
    if not stats: st.info("Nenhum aluno ainda.")
    else:
        badge={"False Beginner":"badge-blue","Pre-Intermediate":"badge-green",
               "Intermediate":"badge-gold","Business English":"badge-gold"}
        rows="".join(f"""<tr>
            <td><b>{s['name']}</b><br><span style="color:#8b949e;font-size:.75rem">@{s['username']}</span></td>
            <td><span class="badge {badge.get(s['level'],'badge-blue')}">{s['level']}</span></td>
            <td>{s['focus']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['messages']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['corrections']}</td>
            <td style="color:#8b949e">{s['last_active']}</td>
        </tr>""" for s in sorted(stats,key=lambda x:x["messages"],reverse=True))
        st.markdown(f'<div style="background:var(--surface);border:1px solid var(--border);'
                    f'border-radius:12px;overflow:hidden"><table class="dash-table"><thead>'
                    f'<tr><th>Aluno</th><th>Nível</th><th>Foco</th><th>Msgs</th>'
                    f'<th>Correções</th><th>Último Acesso</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
    st.markdown("<br>")
    st.markdown("### <i class='fa-solid fa-comments'></i> Histórico do Aluno", unsafe_allow_html=True)
    #st.markdown("### Histórico do Aluno")
    students = load_students()
    opts = {u:d["name"] for u,d in students.items() if d["role"]=="student"}
    if opts:
        sel = st.selectbox("Selecione",list(opts.keys()),
                           format_func=lambda u:f"{opts[u]} (@{u})")
        convs = list_conversations(sel)
        if convs:
            csel = st.selectbox("Conversa",convs,
                                format_func=lambda c:f"{c['date']} — {c['title']} ({c['count']} msgs)")
            hist = load_conversation(sel, csel["id"])
            with st.expander(f"📖 {len(hist)} mensagens"):
                for m in hist:
                    who  = PROF_NAME if m["role"]=="assistant" else opts[sel]
                    icon = "<i class='fa-solid fa-chalkboard-user'></i>" if m["role"]=="assistant" else "<i class='fa-solid fa-user-graduate'></i>"
                    atag = " <i class='fa-solid fa-microphone'></i>" if m.get("audio") else ""
                    st.markdown(f"**{icon} {who}{atag}** `{m.get('date','')} {m.get('time','')}`\n\n{m['content']}\n\n---", unsafe_allow_html=True)
                    '''icon = "🧑‍🏫" if m["role"]=="assistant" else "🎓"
                    atag = " 🎙️" if m.get("audio") else ""
                    st.markdown(f"**{icon} {who}{atag}** `{m.get('date','')} {m.get('time','')}`"
                                f"\n\n{m['content']}\n\n---")'''
        else: st.info("Aluno ainda não conversou.")

# Injeta o JavaScript para mover o Microfone e o Anexo para dentro do st.chat_input
components.html("""
<script>
function pavMoveToChatBar() {
  const parent = window.parent ? window.parent.document : document;
  
  const chatInputContainer = parent.querySelector('[data-testid="stChatInput"]');
  if (!chatInputContainer) return; 
  if (chatInputContainer.querySelector('.pav-extras')) return; 

  const extras = parent.createElement('div');
  extras.className = 'pav-extras';

  // ─── APENAS O BOTÃO DE ANEXO (CLIP) ───
  const ab = parent.createElement('button');
  ab.className = 'pav-icon-btn';
  ab.title = 'Anexar arquivo';
  ab.innerHTML = '<i class="fa-solid fa-paperclip"></i>';
  
  ab.onclick = () => {
    const fw = parent.querySelector('[data-testid="stFileUploader"]');
    if (fw) {
        const fileInput = fw.querySelector('input[type="file"]');
        if (fileInput) fileInput.click();
    }
  };

  extras.appendChild(ab);
  
  const chatInner = chatInputContainer.querySelector('div');
  if(chatInner) chatInner.style.position = 'relative';
  chatInputContainer.appendChild(extras);

  // Esconde APENAS o File Uploader. O Áudio agora fica livre na tela!
  const fw = parent.querySelector('[data-testid="stFileUploader"]');
  if (fw) {
      fw.style.cssText = 'position: fixed !important; bottom: -999px !important; left: -9999px !important; opacity: 0 !important; width: 1px !important; height: 1px !important; pointer-events: none !important;';
      const fileInput = fw.querySelector('input[type="file"]');
      if (fileInput) fileInput.style.pointerEvents = 'auto'; // Mantém o clipe clicável
  }
}

setInterval(pavMoveToChatBar, 1000);
</script>
""", height=0)
# ══════════════════════════════════════════════════════════════════════════════
# ROTEADOR
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:       show_login()
elif st.session_state.page=="profile":   show_profile()
elif st.session_state.page=="dashboard": show_dashboard()
else:                                    show_chat()