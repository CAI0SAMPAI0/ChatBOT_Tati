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
    append_message, get_all_students_stats, delete_conversation,
    update_profile, update_password,
    create_session, validate_session, delete_session,
    save_user_avatar_db, get_user_avatar_db, remove_user_avatar_db,
)
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from file_reader import extract_file

init_db()

API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
PHOTO_PATH = os.getenv("PROFESSOR_PHOTO", "assets/tati.png")
PROF_NAME  = os.getenv("PROFESSOR_NAME",  "Professor Avatar")

# ══════════════════════════════════════════════════════════════════════════════
# i18n
# ══════════════════════════════════════════════════════════════════════════════
_STRINGS = {
    "pt-BR": {
        "type_message": "Digite uma mensagem…", "new_conv": "➕  Nova conversa",
        "voice_mode": "🎙️  Modo Voz", "chat_mode": "💬  Modo Chat",
        "dashboard": "📊 Painel", "profile": "⚙️ Perfil", "logout": "🚪 Sair",
        "username": "Usuário", "password": "Senha", "full_name": "Nome completo",
        "email": "E-mail", "enter": "Entrar", "create_account": "Criar Conta",
        "save_general": "💾 Salvar", "save_custom": "💾 Salvar", "save_data": "💾 Salvar",
        "change_password": "🔒 Alterar Senha", "remove_attachment": "✕ Remover anexo",
        "back": "← Voltar", "use_as_student": "Usar como Aluno",
        "my_profile": "⚙️ Meu Perfil", "interface_lang": "Idioma da interface",
        "transcription_lang": "Idioma da transcrição", "tts_accent": "Sotaque (TTS)",
        "nickname": "Apelido", "occupation": "Ocupação", "english_level": "Nível de inglês",
        "focus": "Foco", "conv_tone": "Tom", "ai_role": "Papel da IA",
        "new_password": "Nova senha", "confirm_password": "Confirmar senha",
        "tap_to_speak": "Toque no microfone para falar", "tap_to_stop": "Toque para parar",
        "speaking_ai": "IA falando...", "processing": "⏳ Processando...",
        "error_mic": "Erro ao processar áudio.", "error_api": "API não configurada.",
    },
    "en-US": {
        "type_message": "Type a message…", "new_conv": "➕  New conversation",
        "voice_mode": "🎙️  Voice Mode", "chat_mode": "💬  Chat Mode",
        "dashboard": "📊 Dashboard", "profile": "⚙️ Profile", "logout": "🚪 Logout",
        "username": "Username", "password": "Password", "full_name": "Full name",
        "email": "E-mail", "enter": "Sign In", "create_account": "Create Account",
        "save_general": "💾 Save", "save_custom": "💾 Save", "save_data": "💾 Save",
        "change_password": "🔒 Change Password", "remove_attachment": "✕ Remove attachment",
        "back": "← Back", "use_as_student": "Use as Student",
        "my_profile": "⚙️ My Profile", "interface_lang": "Interface language",
        "transcription_lang": "Transcription language", "tts_accent": "Accent (TTS)",
        "nickname": "Nickname", "occupation": "Occupation", "english_level": "English level",
        "focus": "Focus", "conv_tone": "Tone", "ai_role": "AI role",
        "new_password": "New password", "confirm_password": "Confirm password",
        "tap_to_speak": "Tap the mic to speak", "tap_to_stop": "Tap to stop",
        "speaking_ai": "AI speaking...", "processing": "⏳ Processing...",
        "error_mic": "Could not process audio.", "error_api": "API not configured.",
    },
}

def t(key: str, lang: str = "pt-BR") -> str:
    return _STRINGS.get(lang, _STRINGS["pt-BR"]).get(key, _STRINGS["pt-BR"].get(key, key))

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE IMAGEM
# ══════════════════════════════════════════════════════════════════════════════
def get_photo_b64() -> str | None:
    p = Path(PHOTO_PATH)
    if p.exists():
        ext = p.suffix.lower().replace(".", "")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None

PHOTO_B64 = get_photo_b64()

@st.cache_data(show_spinner=False)
def get_tati_mini_b64() -> str:
    for _p in [Path("assets/tati.png"), Path("assets/tati.jpg")]:
        if _p.exists():
            ext = _p.suffix.lstrip(".").lower()
            mime = "jpeg" if ext in ("jpg","jpeg") else ext
            return f"data:image/{mime};base64,{base64.b64encode(_p.read_bytes()).decode()}"
    return get_photo_b64() or ""

@st.cache_data(show_spinner=False)
def get_avatar_frames() -> dict:
    base = Path(__file__).parent
    def _load(*paths):
        for p in paths:
            p = Path(p)
            if p.exists():
                return f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"
        return ""
    return {
        "base":   _load(base/"assets"/"avatar_tati_normal.png",     "assets/avatar_tati_normal.png"),
        "closed": _load(base/"assets"/"avatar_tati_closed.png",     "assets/avatar_tati_closed.png"),
        "mid":    _load(base/"assets"/"avatar_tati_meio.png",       "assets/avatar_tati_meio.png"),
        "open":   _load(base/"assets"/"avatar_tati_bem_aberta.png", "assets/avatar_tati_bem_aberta.png",
                        base/"assets"/"avatar_tati_aberta.png",     "assets/avatar_tati_aberta.png"),
    }

def get_user_avatar_b64(username: str, _bust: int = 0) -> str | None:
    result = get_user_avatar_db(username)
    if not result: return None
    raw, mime = result
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

def _avatar_circle_html(b64: str | None, size: int, border: str = "#8800f0") -> str:
    if b64:
        return (f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
                f'background:url({b64}) center/cover no-repeat;border:2px solid {border};flex-shrink:0;"></div>')
    return (f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'background:linear-gradient(135deg,#1e2a3a,#2a3a50);'
            f'display:flex;align-items:center;justify-content:center;'
            f'border:2px solid #1e2a3a;font-size:{int(size*.45)}px;flex-shrink:0;">👤</div>')

def _bump_avatar(): st.session_state["_avatar_v"] = st.session_state.get("_avatar_v", 0) + 1

def user_avatar_html(username: str, size: int = 36) -> str:
    return _avatar_circle_html(get_user_avatar_b64(username, st.session_state.get("_avatar_v", 0)), size)

def avatar_html(size: int = 52, speaking: bool = False) -> str:
    cls = "speaking" if speaking else ""
    photo = PHOTO_B64
    if photo:
        return (f'<div class="avatar-wrap {cls}" style="width:{size}px;height:{size}px;border-radius:50%;'
                f'flex-shrink:0;background:url({photo}) center top/cover no-repeat;'
                f'position:relative;overflow:hidden;"><div class="avatar-ring"></div></div>')
    return f'<div class="avatar-circle {cls}" style="width:{size}px;height:{size}px;font-size:{int(size*.48)}px">🧑‍🏫</div>'

def get_or_create_conv(username: str) -> str:
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id

# ══════════════════════════════════════════════════════════════════════════════
# SESSÃO PERSISTENTE
# ══════════════════════════════════════════════════════════════════════════════
def js_save_session(token: str) -> None:
    components.html(f"""<!DOCTYPE html><html><head><style>html,body{{margin:0;padding:0;overflow:hidden;}}</style></head><body><script>
(function(){{var t='{token}';
try{{window.parent.localStorage.setItem('pav_session',t);}}catch(e){{}}
try{{var exp=new Date(Date.now()+2592000000).toUTCString();window.parent.document.cookie='pav_session='+encodeURIComponent(t)+';expires='+exp+';path=/;SameSite=Lax';}}catch(e){{}}
}})();</script></body></html>""", height=1)

def js_clear_session() -> None:
    components.html("""<!DOCTYPE html><html><head><style>html,body{margin:0;padding:0;overflow:hidden;}</style></head><body><script>
(function(){
try{window.parent.localStorage.removeItem('pav_session');}catch(e){}
try{window.parent.document.cookie='pav_session=;expires=Thu,01 Jan 1970 00:00:00 GMT;path=/';}catch(e){}
})();</script></body></html>""", height=1)

def _logout() -> None:
    token = st.session_state.get("_session_token", "")
    if token: delete_session(token)
    js_clear_session()
    st.session_state.pop("_session_token", None)
    st.session_state.pop("_session_saved", None)
    st.session_state.update(logged_in=False, user=None, conv_id=None)

# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title=f"{PROF_NAME} · English",
    page_icon=str(Path(PHOTO_PATH)) if Path(PHOTO_PATH).exists() else "🎓",
    layout="wide",
)
_css = Path("styles/style.css")
if _css.exists():
    st.markdown(f"<style>{_css.read_text()}</style>", unsafe_allow_html=True)

st.markdown("""<style>
[data-stale="true"],[data-stale="false"]{opacity:1!important;transition:none!important;}
.stSpinner,[data-testid="stSpinner"]{display:none!important;}
html,body{height:100%;height:100dvh;}
.main .block-container{
    max-width:100%!important;
    padding-left:clamp(8px,2vw,40px)!important;
    padding-right:clamp(8px,2vw,40px)!important;
    padding-top:clamp(8px,1vh,24px)!important;
    padding-bottom:clamp(60px,8vh,100px)!important;
}
[data-testid="stAudioInput"]{position:fixed!important;bottom:-9999px!important;left:-9999px!important;opacity:0!important;pointer-events:none!important;width:1px!important;height:1px!important;overflow:hidden!important;}
[data-testid="stAudioInput"] button{pointer-events:auto!important;}
[data-testid="stFileUploader"]{position:fixed!important;bottom:-999px!important;left:-9999px!important;opacity:0!important;width:1px!important;height:1px!important;pointer-events:none!important;overflow:hidden!important;}
[data-testid="stFileUploader"] input[type="file"]{pointer-events:auto!important;}
@media(max-width:768px){
    section[data-testid="stSidebar"]{min-width:0!important;}
    .main .block-container{padding-left:8px!important;padding-right:8px!important;padding-bottom:80px!important;}
}
</style>""", unsafe_allow_html=True)
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, very intelligent and encouraging. Over 25 years of experience, Advanced English Hunter College NY.

BILINGUAL POLICY
BEGINNER / PRE-INTERMEDIATE:
  • Student writes in Portuguese → Respond in simple English + Portuguese translation of key words in parentheses.
  • Always end with an easy encouraging question in English.
INTERMEDIATE:
  • Respond primarily in English. Use Portuguese ONLY to clarify one specific word.
ADVANCED / BUSINESS:
  • Respond exclusively in English. "Let's keep it in English — you've got this!"
TRANSLATION REQUESTS: always provide translation + example sentence.

TEACHING STYLE:
- Neuro-learning: guide students to discover errors. Never just give the answer.
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT responses. Bold grammar points when appropriate.
- End with ONE engaging question.
- NEVER use emojis. Plain text only.
- NEVER start uninvited. Wait for the student to speak first.

ACTIVITY GENERATION — when asked for a FILE respond ONLY with:
  <<<GENERATE_FILE>>>
  {{"format":"pdf","filename":"activity.pdf","title":"Title","content":"content with \\n for line breaks"}}
  <<<END_FILE>>>"""

VOICE_SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} -- warm, witty, very intelligent and encouraging. Over 25 years of experience, Advanced English Hunter College NY.

BILINGUAL POLICY
BEGINNER / PRE-INTERMEDIATE:
  * Student speaks in Portuguese -> Respond in simple English + Portuguese key words in parentheses.
  * End with an easy encouraging question.
INTERMEDIATE: Respond in English, invite them to try in English if they speak Portuguese.
ADVANCED / BUSINESS: Respond exclusively in English.

TEACHING STYLE:
- SHORT responses for voice. Max 3 sentences. End with ONE question.
- NO markdown, NO bullet points -- plain natural speech for TTS.
- NEVER start uninvited. NEVER use EMOTES."""

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k, v in {"logged_in": False, "user": None, "page": "chat", "speaking": False,
              "conv_id": None, "staged_file": None, "audio_key": 0}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Auto-login via ?s= token
if not st.session_state.logged_in:
    _s = st.query_params.get("s", "")
    if _s and len(_s) > 10:
        _ud = validate_session(_s)
        if _ud:
            _un = _ud.get("_resolved_username") or next(
                (k for k, v in load_students().items() if v.get("password") == _ud.get("password")), None)
            if _un:
                st.session_state.update(logged_in=True, user={"username": _un, **_ud},
                    page="dashboard" if _ud.get("role") == "professor" else "chat", conv_id=None)
                st.session_state["_session_token"] = _s
        else:
            st.query_params.pop("s", None)

# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE — chat
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=10, show_spinner=False)
def cached_load_conversation(username: str, conv_id: str) -> list:
    return load_conversation(username, conv_id)

def send_to_claude(username, user, conv_id, text, image_b64=None, image_media_type=None):
    client = anthropic.Anthropic(api_key=API_KEY)
    context = (f"\n\nStudent: {user['name']} | Level: {user['level']} | "
               f"Focus: {user['focus']} | Native: Brazilian Portuguese.")
    msgs = load_conversation(username, conv_id)
    api_msgs = [{"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]} for m in msgs]
    if not api_msgs or api_msgs[-1]["role"] != "user" or api_msgs[-1]["content"] != text:
        api_msgs.append({"role": "user", "content": text})
    if image_b64 and image_media_type and api_msgs and api_msgs[-1]["role"] == "user":
        api_msgs[-1]["content"] = [
            {"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": image_b64}},
            {"type": "text", "text": text},
        ]
    is_activity = any(w in text.lower() for w in ["pdf","word","docx","atividade","exercício","worksheet","activity","generate"])
    resp = client.messages.create(model="claude-haiku-4-5", max_tokens=2000 if is_activity else 400,
                                  system=SYSTEM_PROMPT + context, messages=api_msgs)
    reply = resp.content[0].text
    import re as _re
    reply = _re.sub(r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF\u2600-\u27BF\U0001FA00-\U0001FAFF\u200d\ufe0f]', '', reply).strip()
    if "<<<GENERATE_FILE>>>" in reply:
        return _intercept_file(reply, username, conv_id)
    tts_b64 = None
    if tts_available():
        ab = text_to_speech(reply)
        if ab:
            tts_b64 = base64.b64encode(ab).decode()
            st.session_state["_tts_audio"] = tts_b64
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64)
    cached_load_conversation.clear()
    return reply

def _intercept_file(reply, username, conv_id):
    import re
    try:
        m = re.search(r'<<<GENERATE_FILE>>>\s*(\{.*?\})\s*<<<END_FILE>>>', reply, re.DOTALL)
        if not m:
            append_message(username, conv_id, "assistant", reply); return reply
        meta = json.loads(m.group(1))
        fmt = meta.get("format","pdf").lower(); title = meta.get("title","Activity")
        content = meta.get("content",""); filename = meta.get("filename",f"activity.{fmt}")
        if not filename.endswith(f".{fmt}"): filename += f".{fmt}"
        out = Path("data/generated"); out.mkdir(parents=True, exist_ok=True)
        path = out / filename
        if fmt == "pdf": _gen_pdf(title, content, path)
        else: _gen_docx(title, content, path)
        file_bytes = path.read_bytes()
        st.session_state["_pending_download"] = {
            "b64": base64.b64encode(file_bytes).decode(), "filename": filename,
            "mime": "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        msg = f"📎 Arquivo gerado: **{filename}**\n\n_{title}_\n\nClique em **⬇ Baixar** abaixo."
        append_message(username, conv_id, "assistant", msg, is_file=True)
        cached_load_conversation.clear()
        return msg
    except Exception as e:
        err = f"Não consegui gerar o arquivo: {e}"
        append_message(username, conv_id, "assistant", err); cached_load_conversation.clear(); return err

def _gen_pdf(title, content, path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_CENTER
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2.5*cm, rightMargin=2.5*cm, topMargin=2.5*cm, bottomMargin=2.5*cm)
    ss = getSampleStyleSheet(); story = []
    story.append(Paragraph(title, ParagraphStyle("t", parent=ss["Title"], fontSize=18, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER)))
    story.append(Paragraph(f"Teacher {PROF_NAME}", ParagraphStyle("s", parent=ss["Normal"], fontSize=9, spaceAfter=14, textColor=colors.HexColor("#888888"), alignment=TA_CENTER)))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#f0a500")))
    story.append(Spacer(1, 0.4*cm))
    b = ParagraphStyle("b", parent=ss["Normal"], fontSize=11, leading=18, spaceAfter=8)
    for line in content.split("\\n"):
        story.append(Paragraph(line.strip(), b) if line.strip() else Spacer(1, 0.2*cm))
    doc.build(story)

def _gen_docx(title, content, path):
    from docx import Document; from docx.shared import Pt, RGBColor, Cm; from docx.enum.text import WD_ALIGN_PARAGRAPH
    doc = Document()
    for sec in doc.sections: sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Cm(2.5)
    h = doc.add_heading(title, 0); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs: run.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)
    sub = doc.add_paragraph(f"Teacher {PROF_NAME}"); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size = Pt(9); sub.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    doc.add_paragraph()
    for line in content.split("\\n"):
        p = doc.add_paragraph(line.strip()) if line.strip() else doc.add_paragraph()
        if line.strip(): p.style.font.size = Pt(11)
    doc.save(str(path))

# ══════════════════════════════════════════════════════════════════════════════
# TELA DE LOGIN  (do login.py enviado, sem ui_helpers)
# ══════════════════════════════════════════════════════════════════════════════
def show_login() -> None:
    # Se já está logado (auto-login pelo roteador), não renderiza o login
    if st.session_state.logged_in:
        return

    photo_src = get_photo_b64() or ""

    st.markdown("""<style>
[data-testid='stSidebar']{display:none!important;}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
.stApp{background:#060a10!important;}
section[data-testid="stMain"],section[data-testid="stMain"]>div,.main .block-container{
    padding:0!important;margin:0!important;max-width:100%!important;width:100%!important;}
div[data-testid="stButton"]>button{border-radius:10px!important;font-weight:600!important;
    border:1px solid #2a2a4a!important;background:transparent!important;color:#6b7280!important;}
div[data-testid="stButton"]>button[kind="primary"],
div[data-testid="stButton"]>button[data-testid="baseButton-primary"]{
    background:linear-gradient(135deg,#6c3fc5,#8b5cf6)!important;
    border-color:#7c4dcc!important;color:#fff!important;box-shadow:0 0 14px rgba(139,92,246,.35)!important;}
div[data-testid="stFormSubmitButton"]>button{
    background:linear-gradient(135deg,#6c3fc5,#8b5cf6)!important;border:1px solid #7c4dcc!important;
    color:#fff!important;border-radius:10px!important;font-weight:700!important;
    box-shadow:0 0 14px rgba(139,92,246,.3)!important;width:100%!important;padding:12px!important;}
div[data-testid="stFormSubmitButton"]>button:hover{
    background:linear-gradient(135deg,#7c4dcc,#9d6ff7)!important;box-shadow:0 0 22px rgba(139,92,246,.5)!important;}
.stTextInput label{font-size:.7rem!important;color:#4a5a6a!important;font-weight:700!important;
    text-transform:uppercase!important;letter-spacing:1px!important;}
.stTextInput input{background:rgba(255,255,255,.04)!important;border:1px solid #1e2a3a!important;
    border-radius:10px!important;color:#e6edf3!important;font-size:.88rem!important;}
.stTextInput input:focus{border-color:#8b5cf6!important;box-shadow:0 0 0 3px rgba(139,92,246,.12)!important;}
iframe[height="1"]{position:fixed!important;opacity:0!important;pointer-events:none!important;bottom:0!important;left:0!important;}
section[data-testid="stMain"]>div>div>div{display:flex!important;flex-direction:column!important;align-items:center!important;}
div[data-testid="stVerticalBlock"]{width:100%!important;max-width:420px!important;margin:0 auto!important;padding:0 16px!important;}
[data-testid="InputInstructions"]{display:none!important;}
</style>""", unsafe_allow_html=True)

    # Auto-login via localStorage
    components.html("""<!DOCTYPE html><html><head><style>html,body{margin:0;padding:0;overflow:hidden;}</style></head><body><script>
(function(){
    function readToken(){
        try{var s=window.parent.localStorage.getItem('pav_session');if(s&&s.length>10)return s;}catch(e){}
        try{var m=window.parent.document.cookie.split(';').map(function(c){return c.trim();})
            .find(function(c){return c.startsWith('pav_session=');});
            if(m){var v=decodeURIComponent(m.split('=')[1]);if(v&&v.length>10)return v;}}catch(e){}
        return '';
    }
    var val=readToken();if(!val)return;
    var url=new URL(window.parent.location.href);
    if(url.searchParams.get('s')!==val){url.searchParams.set('s',val);window.parent.location.replace(url.toString());}
})();
</script></body></html>""", height=1)

    if "_login_tab" not in st.session_state:
        st.session_state["_login_tab"] = "login"

    # Card do avatar
    if photo_src:
        av_html = (f'<div style="width:90px;height:90px;border-radius:50%;flex-shrink:0;'
                   f'background:url({photo_src}) center top/cover no-repeat;'
                   f'border:2.5px solid #8b5cf6;margin-bottom:12px;'
                   f'box-shadow:0 0 0 6px rgba(139,92,246,.12),0 0 28px rgba(139,92,246,.25);"></div>')
    else:
        av_html = ('<div style="width:90px;height:90px;border-radius:50%;'
                   'background:linear-gradient(135deg,#6c3fc5,#8b5cf6);'
                   'display:flex;align-items:center;justify-content:center;'
                   'font-size:38px;margin-bottom:12px;">&#129489;&#8203;&#127979;</div>')

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;700;800&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:#060a10;font-family:'Sora',sans-serif;width:100%;height:100%;overflow:hidden;
    display:flex;align-items:center;justify-content:center;}}
.bg{{position:fixed;inset:0;overflow:hidden;pointer-events:none;}}
.orb1{{position:absolute;width:400px;height:400px;border-radius:50%;
       background:radial-gradient(circle,rgba(139,92,246,.12),transparent 70%);
       top:-120px;right:-100px;animation:d1 12s ease-in-out infinite alternate;}}
.orb2{{position:absolute;width:320px;height:320px;border-radius:50%;
       background:radial-gradient(circle,rgba(108,63,197,.08),transparent 70%);
       bottom:-80px;left:-80px;animation:d2 12s ease-in-out infinite alternate;}}
@keyframes d1{{from{{transform:translate(0,0);}}to{{transform:translate(20px,14px) scale(1.04);}}}}
@keyframes d2{{from{{transform:translate(0,0);}}to{{transform:translate(-14px,10px) scale(1.03);}}}}
.card{{position:relative;z-index:1;background:linear-gradient(180deg,#0f1824,#0a1020);
    border:1px solid #1a2535;border-radius:24px;padding:28px 24px 20px;width:100%;
    box-shadow:0 24px 64px rgba(0,0,0,.7);display:flex;flex-direction:column;align-items:center;}}
h2{{font-size:1.35rem;font-weight:800;text-align:center;margin:0 0 3px;
    background:linear-gradient(135deg,#8b5cf6 30%,#c084fc 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
p{{font-size:.7rem;color:#3a4e5e;text-align:center;}}
.line{{width:36px;height:2px;background:linear-gradient(90deg,#8b5cf6,#c084fc);border-radius:2px;margin:10px auto 0;opacity:.5;}}
</style></head><body>
<div class="bg"><div class="orb1"></div><div class="orb2"></div></div>
<div class="card">{av_html}<h2>{PROF_NAME}</h2><p>Voice English Coach</p><div class="line"></div></div>
</body></html>""", height=220, scrolling=False)

    # Feedback
    if st.session_state.pop("_login_err", ""): st.error(f"❌ {st.session_state.get('_login_err','')}")
    login_err = st.session_state.pop("_login_err", "")
    reg_err   = st.session_state.pop("_reg_err",   "")
    reg_ok    = st.session_state.pop("_reg_ok",    False)
    reg_name  = st.session_state.pop("_reg_name",  "")
    if login_err: st.error(f"❌ {login_err}")
    if reg_err:   st.error(f"❌ {reg_err}")
    if reg_ok:    st.success(f"✅ Conta criada! Bem-vindo(a), {reg_name}!")

    tab = st.session_state["_login_tab"]
    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("enter"), use_container_width=True, key="tab_login",
                     type="primary" if tab == "login" else "secondary"):
            st.session_state["_login_tab"] = "login"; st.rerun()
    with c2:
        if st.button(t("create_account"), use_container_width=True, key="tab_reg",
                     type="primary" if tab == "reg" else "secondary"):
            st.session_state["_login_tab"] = "reg"; st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if tab == "login":
        with st.form("form_login", clear_on_submit=True):
            u = st.text_input(t("username"), placeholder="seu.usuario")
            p = st.text_input(t("password"), type="password", placeholder="••••••••")
            if st.form_submit_button(t("enter"), use_container_width=True):
                if not u or not p:
                    st.session_state["_login_err"] = "Preencha todos os campos."; st.rerun()
                else:
                    user = authenticate(u, p)
                    if user:
                        real_u = user.get("_resolved_username", u.lower())
                        st.session_state.update(logged_in=True, user={"username": real_u, **user},
                            page="dashboard" if user["role"] == "professor" else "chat", conv_id=None)
                        token = create_session(real_u)
                        st.session_state["_session_token"] = token
                        st.session_state["_session_saved"] = True
                        js_save_session(token); st.rerun()
                    else:
                        st.session_state["_login_err"] = "Usuário ou senha incorretos."; st.rerun()
    else:
        with st.form("form_reg", clear_on_submit=True):
            rn  = st.text_input(t("full_name"),    placeholder="João Silva")
            re_ = st.text_input(t("email"),        placeholder="joao@email.com")
            ru  = st.text_input(t("username"),     placeholder="joao.silva")
            rp  = st.text_input("Senha", type="password", placeholder="mínimo 6 caracteres")
            if st.form_submit_button(t("create_account"), use_container_width=True):
                if not rn or not re_ or not ru or not rp:
                    st.session_state["_reg_err"] = "Preencha todos os campos."; st.rerun()
                elif "@" not in re_:
                    st.session_state["_reg_err"] = "E-mail inválido."; st.rerun()
                elif len(rp) < 6:
                    st.session_state["_reg_err"] = "Senha muito curta (mínimo 6)."; st.rerun()
                else:
                    ok, msg = register_student(ru, rn, rp, email=re_)
                    if ok:
                        st.session_state.update(_reg_ok=True, _reg_name=rn, **{"_login_tab": "login"}); st.rerun()
                    else:
                        st.session_state["_reg_err"] = msg; st.rerun()

    st.markdown(f'<p style="text-align:center;font-size:.6rem;color:#1a2535;margin-top:14px;">2025 © {PROF_NAME}</p>',
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MODO VOZ  (do voice.py enviado, sem ui_helpers)
# ══════════════════════════════════════════════════════════════════════════════
def process_voice(raw: bytes, conv_id: str) -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    lang     = profile.get("language", "pt-BR")

    txt = transcribe_bytes(raw, suffix=".webm", language=None)
    if not txt or txt.startswith("❌") or txt.startswith("⚠️"):
        st.session_state["_vm_error"] = txt or t("error_mic", lang); return

    st.session_state["_vm_user_said"] = txt
    if not API_KEY:
        st.session_state["_vm_error"] = t("error_api", lang); return

    history = st.session_state.get("_vm_history", [])
    context = (f"\n\nStudent: {user.get('name','')} | Level: {user.get('level','Beginner')} | "
               f"Focus: {user.get('focus','General Conversation')} | Native: Brazilian Portuguese.")
    history.append({"role": "user", "content": txt})
    client = anthropic.Anthropic(api_key=API_KEY)
    resp = client.messages.create(model="claude-haiku-4-5", max_tokens=400,
        system=VOICE_SYSTEM_PROMPT + context,
        messages=[{"role": m["role"], "content": m["content"]} for m in history])
    reply = resp.content[0].text
    history.append({"role": "assistant", "content": reply})
    st.session_state["_vm_history"] = history

    tts_b64 = ""
    if tts_available():
        ab = text_to_speech(reply)
        if ab: tts_b64 = base64.b64encode(ab).decode()

    st.session_state["_vm_reply"]   = reply
    st.session_state["_vm_tts_b64"] = tts_b64
    append_message(username, conv_id, "user",      txt,   audio=True)
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64 or None)


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

    # CSS Streamlit — sem scroll, sem chrome
    st.markdown("""<style>
[data-testid="stSidebar"],[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],#MainMenu,footer,header{display:none!important;}
body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#060a10!important;overflow:hidden!important;}
html,body{overflow:hidden!important;height:100%!important;}
section[data-testid="stMain"]>div,.main .block-container,
div[data-testid="stVerticalBlock"],div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="element-container"]{padding:0!important;margin:0!important;gap:0!important;overflow:hidden!important;}
iframe{display:block!important;border:none!important;}
</style>""", unsafe_allow_html=True)

    conv_id = get_or_create_conv(username)

    # Carrega histórico do banco
    if not st.session_state.get("_vm_history") and conv_id:
        msgs_db = load_conversation(username, conv_id)
        if msgs_db:
            st.session_state["_vm_history"] = [
                {"role": m["role"], "content": m["content"], "tts_b64": m.get("tts_b64", "")}
                for m in msgs_db if m.get("content")
            ]

    # Processa áudio
    audio_val = st.audio_input(" ", key=f"voice_input_{st.session_state.audio_key}", label_visibility="collapsed")
    if audio_val and audio_val != st.session_state.get("_vm_last_upload"):
        st.session_state["_vm_last_upload"] = audio_val
        for k in ["_vm_reply","_vm_tts_b64","_vm_user_said","_vm_error"]:
            st.session_state.pop(k, None)
        with st.spinner(t("processing", lang)):
            process_voice(audio_val.read(), conv_id)
        st.session_state.audio_key += 1
        st.rerun()

    reply    = st.session_state.get("_vm_reply",   "")
    tts_b64  = st.session_state.get("_vm_tts_b64", "")
    vm_error = st.session_state.get("_vm_error",   "")
    history  = st.session_state.get("_vm_history",  [])

    frames       = get_avatar_frames()
    has_anim     = bool(frames["base"] and frames["closed"] and frames["mid"] and frames["open"])
    history_js   = json.dumps(history)
    tts_js       = json.dumps(tts_b64)
    reply_js     = json.dumps(reply)
    err_js       = json.dumps(vm_error)
    tap_speak    = json.dumps(t("tap_to_speak", lang))
    tap_stop     = json.dumps(t("tap_to_stop",  lang))
    speaking_    = json.dumps(t("speaking_ai",  lang))
    proc_        = json.dumps(t("processing",   lang))
    av_b64_js    = json.dumps(frames["base"])
    avc_js       = json.dumps(frames["closed"])
    avm_js       = json.dumps(frames["mid"])
    avo_js       = json.dumps(frames["open"])
    has_anim_js  = "true" if has_anim else "false"
    photo_js     = json.dumps(get_tati_mini_b64() or get_photo_b64())
    prof_name_js = json.dumps(PROF_NAME)
    chat_lbl_js  = json.dumps(t("chat_mode", lang))

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:#060a10;font-family:'Sora',sans-serif;height:100%;overflow:hidden;padding-bottom:env(safe-area-inset-bottom);}}
.app{{display:flex;flex-direction:column;align-items:center;height:100vh;height:100dvh;padding:0 16px 0;gap:0;overflow:hidden;}}
/* ── Nav topo ── */
.top-bar{{flex-shrink:0;width:100%;display:flex;justify-content:space-between;align-items:center;padding:10px 0 4px;}}
.nav-btn{{background:rgba(255,255,255,.06);border:1px solid #2a3545;color:#8b949e;border-radius:8px;
    padding:6px 14px;font-size:.72rem;font-family:'Sora',sans-serif;cursor:pointer;transition:all .2s;white-space:nowrap;}}
.nav-btn:hover{{background:rgba(255,255,255,.12);color:#e6edf3;}}
/* ── Avatar ── */
.avatar-section{{flex-shrink:0;width:100%;display:flex;flex-direction:column;align-items:center;gap:4px;
    padding:12px 0 8px;position:sticky;top:0;z-index:10;
    background:linear-gradient(180deg,#060a10 85%,transparent 100%);}}
.avatar-wrap{{position:relative;width:200px;height:200px;flex-shrink:0;}}
@media(max-height:700px){{
    .avatar-wrap{{width:130px;height:130px;}}
    .avatar-img,.avatar-emoji{{width:130px!important;height:130px!important;}}
    .avatar-section{{padding:6px 0 4px;}}
    .prof-name{{font-size:.85rem!important;}}
}}
@media(max-height:560px){{.avatar-wrap{{width:90px;height:90px;}}.avatar-img,.avatar-emoji{{width:90px!important;height:90px!important;}}}}
.avatar-ring{{position:absolute;inset:-8px;border-radius:50%;border:2px solid {_rgba(ring_color,.3)};animation:ring-pulse 2s ease-in-out infinite;}}
.avatar-ring.active{{border-color:{ring_color};box-shadow:0 0 0 0 {_rgba(ring_color,.5)};animation:ring-glow 1s ease-in-out infinite;}}
@keyframes ring-pulse{{0%,100%{{opacity:.4;transform:scale(1);}}50%{{opacity:.8;transform:scale(1.03);}}}}
@keyframes ring-glow{{0%{{box-shadow:0 0 0 0 {_rgba(ring_color,.5)};}}70%{{box-shadow:0 0 14px {_rgba(ring_color,0)};}}100%{{box-shadow:0 0 0 0 {_rgba(ring_color,0)};}}}}
.avatar-img{{width:200px;height:200px;border-radius:50%;object-fit:cover;object-position:top center;border:3px solid {ring_color};box-shadow:0 0 32px {_rgba(ring_color,.25)};}}
.avatar-emoji{{width:200px;height:200px;border-radius:50%;background:linear-gradient(135deg,#1a2535,#0f1824);border:3px solid {ring_color};display:flex;align-items:center;justify-content:center;font-size:54px;}}
.prof-name{{font-size:1rem;font-weight:700;color:#e6edf3;margin-top:6px;}}
.status{{font-size:.68rem;color:{ring_color};margin-top:1px;}}
/* ── Histórico ── */
.history-wrap{{width:100%;max-width:680px;flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:8px;
    padding:8px 4px;scrollbar-width:thin;scrollbar-color:#1a2535 transparent;-webkit-overflow-scrolling:touch;}}
.history-wrap::-webkit-scrollbar{{width:4px;}}
.history-wrap::-webkit-scrollbar-thumb{{background:#1a2535;border-radius:4px;}}
.bubble{{max-width:82%;padding:10px 15px;border-radius:18px;font-size:.84rem;line-height:1.55;word-break:break-word;}}
.bubble.user{{align-self:flex-end;background:{user_bubble_color};color:#fff;border-bottom-right-radius:4px;}}
.bubble.bot{{align-self:flex-start;background:{bot_bubble_color};color:#e6edf3;border:1px solid {_rgba(bot_bubble_color,.8)};border-bottom-left-radius:4px;}}
.bubble-label{{font-size:.6rem;color:#4a5a6a;margin:2px 4px;}}
.bubble-label.right{{text-align:right;}}
.bubble-play-btn{{align-self:flex-start;background:transparent;border:1px solid #1a2535;color:#3a6a8a;
    font-size:.72rem;padding:4px 12px;border-radius:8px;cursor:pointer;font-family:inherit;transition:all .15s;margin-bottom:4px;min-height:32px;}}
.bubble-play-btn:hover{{color:{ring_color};border-color:{_rgba(ring_color,.4)};background:{_rgba(ring_color,.06)};}}
.bubble-play-btn.playing{{color:#e05c2a;border-color:rgba(224,92,42,.5);}}
.error-box{{background:rgba(224,92,42,.1);border:1px solid rgba(224,92,42,.3);border-radius:10px;
    padding:8px 14px;font-size:.78rem;color:#e05c2a;max-width:560px;width:100%;text-align:center;flex-shrink:0;}}
/* ── Rodapé mic ── */
.mic-footer{{flex-shrink:0;width:100%;max-width:620px;display:flex;flex-direction:column;align-items:center;
    gap:6px;padding:8px 0 max(16px,env(safe-area-inset-bottom));
    background:linear-gradient(to top,#060a10 70%,transparent);position:sticky;bottom:0;}}
.audio-controls{{display:flex;align-items:center;gap:6px;padding:8px 12px;background:#0d1420;
    border:1px solid #1a2535;border-radius:12px;width:100%;overflow-x:auto;overflow-y:hidden;
    -webkit-overflow-scrolling:touch;white-space:nowrap;scrollbar-width:none;flex-wrap:nowrap;min-height:44px;}}
.audio-controls::-webkit-scrollbar{{display:none;}}
@media(max-width:400px){{.audio-controls{{padding:6px 10px;gap:4px;}}}}
.ctrl-label{{font-size:.68rem;color:#4a5a6a;white-space:nowrap;flex-shrink:0;}}
.ctrl-val{{font-size:.68rem;color:#8b949e;min-width:28px;text-align:left;flex-shrink:0;}}
input[type=range].ctrl-range{{-webkit-appearance:none;flex-shrink:0;width:60px;height:4px;
    background:#1a2535;border-radius:2px;outline:none;cursor:pointer;touch-action:none;}}
@media(min-width:480px){{input[type=range].ctrl-range{{width:80px;}}}}
input[type=range].ctrl-range::-webkit-slider-thumb{{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;background:{ring_color};cursor:pointer;}}
input[type=range].ctrl-range::-moz-range-thumb{{width:16px;height:16px;border-radius:50%;background:{ring_color};cursor:pointer;border:none;}}
#global-play-btn{{background:#1a2535;color:#e6edf3;border:1px solid #252d3d;border-radius:8px;
    padding:5px 12px;font-size:.78rem;cursor:pointer;white-space:nowrap;transition:background .15s;
    font-family:inherit;flex-shrink:0;min-height:32px;touch-action:manipulation;}}
#global-play-btn:hover{{background:#252d3d;}}
.mic-btn{{width:72px;height:72px;border-radius:50%;border:none;cursor:pointer;
    background:linear-gradient(135deg,#1a2535,#131c2a);color:#8b949e;font-size:28px;
    display:flex;align-items:center;justify-content:center;
    box-shadow:0 4px 20px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.05);
    transition:all .2s;outline:none;touch-action:manipulation;-webkit-tap-highlight-color:transparent;flex-shrink:0;}}
@media(min-width:600px){{.mic-btn{{width:80px;height:80px;font-size:32px;}}}}
.mic-btn:hover{{background:linear-gradient(135deg,#1e2f40,#182130);color:#e6edf3;}}
.mic-btn.recording{{background:linear-gradient(135deg,#e05c2a,#c44a1a);color:#fff;
    box-shadow:0 0 0 0 rgba(224,92,42,.6),0 4px 20px rgba(224,92,42,.3);animation:mic-pulse 1.2s ease-in-out infinite;}}
.mic-btn.processing{{background:linear-gradient(135deg,{ring_color},#c88800);color:#060a10;animation:none;}}
@keyframes mic-pulse{{
    0%{{box-shadow:0 0 0 0 rgba(224,92,42,.6),0 4px 20px rgba(224,92,42,.3);}}
    70%{{box-shadow:0 0 0 16px rgba(224,92,42,0),0 4px 20px rgba(224,92,42,.3);}}
    100%{{box-shadow:0 0 0 0 rgba(224,92,42,0),0 4px 20px rgba(224,92,42,.3);}}}}
.mic-hint{{font-size:.68rem;color:#4a5a6a;letter-spacing:.3px;}}
</style>
</head><body>
<div class="app" id="app">
    <div class="top-bar">
        <button class="nav-btn" id="chatBtn"></button>
        <div></div>
        <button class="nav-btn" id="profileBtn">⚙️</button>
    </div>
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
var TTS_B64   = {tts_js};
var REPLY     = {reply_js};
var HISTORY   = {history_js};
var VM_ERROR  = {err_js};
var TAP_SPEAK = {tap_speak};
var TAP_STOP  = {tap_stop};
var SPEAKING  = {speaking_};
var HAS_ANIM  = {has_anim_js};
var AV_BASE   = {av_b64_js};
var AV_CLOSED = {avc_js};
var AV_MID    = {avm_js};
var AV_OPEN   = {avo_js};
var PHOTO     = {photo_js};
var PROF_NAME = {prof_name_js};
var CHAT_LBL  = {chat_lbl_js};

var micBtn    = document.getElementById('micBtn');
var micHint   = document.getElementById('micHint');
var statusTxt = document.getElementById('statusTxt');
var errBox    = document.getElementById('errBox');
var ring      = document.getElementById('ring');
var avImg     = document.getElementById('avImg');
var avEmoji   = document.getElementById('avEmoji');
var histWrap  = document.getElementById('historyWrap');
var profName  = document.getElementById('profName');

profName.textContent = PROF_NAME;
micHint.textContent  = TAP_SPEAK;
document.getElementById('chatBtn').textContent = CHAT_LBL;

// Navegação — aciona botões ocultos do Streamlit
function clickStBtn(contains){{
    var par=window.parent?window.parent.document:document;
    var btns=par.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){{
        if(btns[i].textContent.trim().indexOf(contains)!==-1){{btns[i].click();return true;}}
    }}
    return false;
}}
document.getElementById('chatBtn').addEventListener('click',function(){{clickStBtn('Chat');}});
document.getElementById('profileBtn').addEventListener('click',function(){{clickStBtn('Perfil')||clickStBtn('Profile');}});

// Avatar
var photoSrc = HAS_ANIM ? AV_BASE : (PHOTO || AV_BASE);
if(photoSrc){{ avImg.src=photoSrc; avImg.style.display='block'; avEmoji.style.display='none'; }}

// Animação boca
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

// Áudio global
var currentAudio=null, lastB64=null;
function getVol(){{ return parseFloat(document.getElementById('vol-slider').value)||1; }}
function getSpd(){{ return parseFloat(document.getElementById('spd-slider').value)||1; }}
function playTTS(b64, onEndCb){{
    if(currentAudio){{ currentAudio.pause(); currentAudio=null; stopMouthAnim(); }}
    if(!b64) return;
    lastB64=b64; ring.classList.add('active'); statusTxt.textContent=SPEAKING;
    var audio=new Audio('data:audio/mp3;base64,'+b64);
    audio.volume=getVol(); audio.playbackRate=getSpd(); audio._srcB64=b64;
    currentAudio=audio;
    audio.onplay=function(){{ startMouthAnim(audio); updateGlobalBtn(true); }};
    audio.onended=function(){{ stopMouthAnim(); ring.classList.remove('active'); statusTxt.textContent='Online'; currentAudio=null; updateGlobalBtn(false); if(onEndCb) onEndCb(); }};
    audio.onerror=function(){{ stopMouthAnim(); ring.classList.remove('active'); updateGlobalBtn(false); }};
    audio.play().catch(function(){{ stopMouthAnim(); ring.classList.remove('active'); updateGlobalBtn(false); }});
}}
function stopTTS(){{
    if(currentAudio){{ currentAudio.pause(); currentAudio=null; stopMouthAnim(); ring.classList.remove('active'); statusTxt.textContent='Online'; updateGlobalBtn(false); }}
}}
function updateGlobalBtn(playing){{
    var btn=document.getElementById('global-play-btn');
    if(!btn) return;
    btn.textContent=playing?'⏹ Parar':'▶ Ouvir';
    btn.style.background=playing?'#8b2a2a':'#1a2535';
}}
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

// Bolhas
function addBubble(role, text, b64){{
    var label=document.createElement('div');
    label.className='bubble-label'+(role==='user'?' right':'');
    label.textContent=role==='user'?'Você':PROF_NAME;
    var bub=document.createElement('div');
    bub.className='bubble '+role;
    bub.textContent=text;
    histWrap.appendChild(label);
    histWrap.appendChild(bub);
    if(role==='bot'&&b64){{
        var pbtn=document.createElement('button');
        pbtn.className='bubble-play-btn'; pbtn.textContent='▶ Ouvir';
        pbtn.addEventListener('click',function(){{
            var isPlaying=currentAudio&&!currentAudio.paused&&currentAudio._srcB64===b64;
            if(isPlaying){{ stopTTS(); pbtn.textContent='▶ Ouvir'; pbtn.classList.remove('playing'); }}
            else{{
                document.querySelectorAll('.bubble-play-btn').forEach(function(b){{b.textContent='▶ Ouvir';b.classList.remove('playing');}});
                pbtn.textContent='⏹ Parar'; pbtn.classList.add('playing');
                playTTS(b64,function(){{pbtn.textContent='▶ Ouvir';pbtn.classList.remove('playing');}});
            }}
        }});
        histWrap.appendChild(pbtn);
    }}
    histWrap.scrollTop=histWrap.scrollHeight;
}}

// Renderiza estado
if(VM_ERROR){{ errBox.textContent=VM_ERROR; errBox.style.display='block'; }}
else{{
    errBox.style.display='none';
    if(HISTORY&&HISTORY.length>0){{
        HISTORY.forEach(function(msg){{ addBubble(msg.role==='user'?'user':'bot',msg.content,msg.tts_b64||''); }});
    }}
    if(TTS_B64) setTimeout(function(){{ playTTS(TTS_B64); }},300);
}}

// Mic
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
        recording=false; realBtn.click();
    }}else{{
        if(currentAudio){{ currentAudio.pause(); currentAudio=null; stopMouthAnim(); ring.classList.remove('active'); }}
        if(window.parent.speechSynthesis) window.parent.speechSynthesis.cancel();
        micBtn.classList.add('recording');
        micBtn.innerHTML='<i class="fa-solid fa-stop"></i>';
        micHint.textContent=TAP_STOP;
        recording=true; realBtn.click();
    }}
}});

// Esconde st.audio_input nativo
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

// Resize iframe — dvh para mobile
(function resizeIframe(){{
    try{{
        var par=window.parent;
        var h=par.innerHeight;
        try{{if(par.visualViewport) h=par.visualViewport.height;}}catch(e){{}}
        var iframes=par.document.querySelectorAll('iframe');
        for(var i=0;i<iframes.length;i++){{
            try{{
                if(iframes[i].contentWindow===window){{
                    iframes[i].style.cssText=['height:'+h+'px','max-height:'+h+'px','min-height:200px','display:block','border:none','width:100%'].join(';');
                    var p=iframes[i].parentElement;
                    for(var j=0;j<10&&p&&p!==par.document.body;j++){{
                        p.style.margin='0';p.style.padding='0';p.style.overflow='hidden';p.style.maxHeight=h+'px';p=p.parentElement;
                    }}
                    break;
                }}
            }}catch(e){{}}
        }}
    }}catch(e){{}}
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
</body></html>""", height=920, scrolling=False)

    # Botões Streamlit ocultos para navegação pelo JS
    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("chat_mode", lang), key="vm_go_chat"):
            for k in ["_vm_history","_vm_reply","_vm_tts_b64","_vm_user_said","_vm_error","_vm_last_upload"]:
                st.session_state.pop(k, None)
            st.session_state.page = "chat"; st.rerun()
    with col2:
        if st.button("⚙️ " + t("profile", lang), key="vm_go_profile"):
            st.session_state.page = "profile"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# CHAT — modo texto
# ══════════════════════════════════════════════════════════════════════════════
def _render_audio_player(tts_b64, msg_time, player_id):
    return f"""<!DOCTYPE html><html><head><style>
*{{box-sizing:border-box;margin:0;padding:0;}}html,body{{background:transparent;font-family:'Sora',sans-serif;overflow:hidden;}}
.player{{display:flex;align-items:center;gap:8px;padding:3px 0;flex-wrap:wrap;}}
.tl{{font-size:.62rem;color:#8b949e;font-family:monospace;flex-shrink:0;}}
.pb{{background:none;border:1px solid #30363d;border-radius:20px;color:#f0a500;font-size:.75rem;padding:2px 10px;cursor:pointer;white-space:nowrap;flex-shrink:0;}}
.pw{{flex:1;min-width:60px;height:3px;background:#30363d;border-radius:2px;cursor:pointer;}}
.pf{{height:100%;background:linear-gradient(90deg,#f0a500,#e05c2a);border-radius:2px;width:0%;transition:width .1s linear;pointer-events:none;}}
.sw{{display:flex;align-items:center;gap:3px;flex-shrink:0;}}
.sb{{background:none;border:1px solid #30363d;border-radius:4px;color:#8b949e;font-size:.65rem;padding:1px 5px;cursor:pointer;}}
.sb.on{{border-color:#f0a500;color:#f0a500;background:rgba(240,165,0,.08);}}
</style></head><body>
<div class="player"><span class="tl">{msg_time}</span>
  <button class="pb" id="b">▶ Ouvir</button>
  <div class="pw" id="pw"><div class="pf" id="pf"></div></div>
  <div class="sw" id="sw">
    <button class="sb" data-r="0.75">0.75×</button>
    <button class="sb on" data-r="1">1×</button>
    <button class="sb" data-r="1.25">1.25×</button>
    <button class="sb" data-r="1.5">1.5×</button>
  </div>
</div>
<script>
(function(){{
  var audio=new Audio('data:audio/mpeg;base64,{tts_b64}');
  var b=document.getElementById('b'),pf=document.getElementById('pf'),pw=document.getElementById('pw'),sw=document.getElementById('sw');
  b.onclick=function(){{
    if(!audio.paused){{audio.pause();b.textContent='▶ Ouvir';}}
    else{{audio.play().then(function(){{b.textContent='⏸ Pausar';}}).catch(function(){{}});}}
  }};
  audio.onended=function(){{b.textContent='▶ Ouvir';pf.style.width='0%';}};
  audio.ontimeupdate=function(){{if(audio.duration)pf.style.width=(audio.currentTime/audio.duration*100)+'%';}};
  pw.onclick=function(e){{var r=pw.getBoundingClientRect();if(audio.duration)audio.currentTime=((e.clientX-r.left)/r.width)*audio.duration;}};
  sw.querySelectorAll('.sb').forEach(function(btn){{
    btn.onclick=function(){{sw.querySelectorAll('.sb').forEach(function(x){{x.classList.remove('on');}});this.classList.add('on');audio.playbackRate=parseFloat(this.dataset.r);}};
  }});
}})();
</script></body></html>"""


def _process_file(username, user, conv_id, raw, filename, extra_text=""):
    result = extract_file(raw, filename)
    kind = result["kind"]
    if kind == "audio":
        with st.spinner("Transcrevendo..."):
            text = transcribe_bytes(raw, suffix=Path(filename).suffix.lower(), language="en")
        if text.startswith("❌") or text.startswith("⚠️"): st.error(text); return False
        disp = f"{extra_text}\n\n[Áudio: {text}]" if extra_text else text
        msg  = f"{extra_text}\n\n[Áudio: '{filename}']\n{text}" if extra_text else f"[Áudio: '{filename}']\n{text}"
        append_message(username, conv_id, "user", disp, audio=True)
        st.session_state.speaking = True
        try: send_to_claude(username, user, conv_id, msg)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False; return True
    elif kind == "text":
        ext = result["text"]
        if ext.startswith("❌"): st.error(ext); return False
        if not ext: st.warning("Sem texto no arquivo."); return False
        disp = (f"{extra_text}\n\n📄 {result['label']}: '{filename}' — {ext[:200]}…" if extra_text
                else f"📄 {result['label']}: '{filename}' — {ext[:200]}…")
        append_message(username, conv_id, "user", disp)
        st.session_state.speaking = True
        try: send_to_claude(username, user, conv_id, f"📄 '{filename}':\n{ext}\n\nPlease help me understand this.")
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False; return True
    elif kind == "image":
        disp = f"{extra_text}\n\n📸 '{filename}'" if extra_text else f"📸 '{filename}'"
        append_message(username, conv_id, "user", disp)
        st.session_state.speaking = True
        try: send_to_claude(username, user, conv_id, f"📸 '{filename}'\nHelp me learn English from this image.",
                            image_b64=result["b64"], image_media_type=result["media_type"])
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False; return True
    st.warning(f"Formato não suportado: {result['label']}"); return False


def show_chat() -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")
    conv_id  = get_or_create_conv(username)
    messages = cached_load_conversation(username, conv_id)

    _ac = profile.get("accent_color", "#f0a500")
    _ub = profile.get("user_bubble_color", "#2d6a4f")
    _ab = profile.get("ai_bubble_color", "#1a1f2e")
    components.html(f"""<!DOCTYPE html><html><head><style>html,body{{margin:0;padding:0;overflow:hidden;}}</style></head><body><script>
(function(){{
  function hexToRgb(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];var n=parseInt(h,16);return[(n>>16)&255,(n>>8)&255,n&255].join(',');}}
  function lum(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];var n=parseInt(h,16);return 0.299*((n>>16)&255)+0.587*((n>>8)&255)+0.114*(n&255);}}
  var ac="{_ac}",ub="{_ub}",ab="{_ab}";var rgb=hexToRgb(ac);
  var r=window.parent.document.documentElement;
  r.style.setProperty('--accent-full',ac);r.style.setProperty('--accent-30','rgba('+rgb+',.3)');
  r.style.setProperty('--bubble-bg','rgba('+rgb+',.12)');r.style.setProperty('--bubble-border','rgba('+rgb+',.3)');
  r.style.setProperty('--user-bubble-bg',ub);r.style.setProperty('--user-bubble-text',lum(ub)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-bg',ab);r.style.setProperty('--ai-bubble-text',lum(ab)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-border','rgba('+hexToRgb(ab)+',.6)');
}})();
</script></body></html>""", height=1)

    with st.sidebar:
        st.markdown(f"""<div style="padding:14px 14px 10px;border-bottom:1px solid #21262d;">
            <div style="display:flex;align-items:center;gap:10px;">{avatar_html(40)}<div>
            <div style="font-weight:600;font-size:.88rem;">{PROF_NAME}</div>
            <div style="font-size:.68rem;color:#8b949e;">● Online</div></div></div></div>""", unsafe_allow_html=True)
        if st.button(t("new_conv",ui_lang), use_container_width=True, key="btn_new"):
            st.session_state.conv_id = new_conversation(username); st.rerun()
        if st.button(t("voice_mode",ui_lang), use_container_width=True, key="btn_voice"):
            st.session_state.page = "voice"; st.rerun()
        st.markdown('<div style="font-size:.68rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px;padding:10px 4px 4px;">Conversas</div>', unsafe_allow_html=True)
        for c in list_conversations(username):
            is_active = c["id"] == conv_id
            col_c, col_d = st.columns([5,1])
            with col_c:
                if st.button(("▶ " if is_active else "") + c["title"], key=f"conv_{c['id']}", use_container_width=True):
                    st.session_state.conv_id = c["id"]; st.rerun()
            with col_d:
                if st.button("🗑", key=f"del_{c['id']}"):
                    delete_conversation(username, c["id"])
                    if st.session_state.conv_id == c["id"]: st.session_state.conv_id = None
                    st.rerun()
        st.markdown("<hr style='border-color:#21262d;margin:8px 0 0'>", unsafe_allow_html=True)
        st.markdown(f"""<div style="padding:8px 12px;display:flex;align-items:center;gap:10px;">
            {user_avatar_html(username,34)}<div>
            <div style="font-weight:600;font-size:.82rem;">{user['name'].split()[0]}</div>
            <div style="color:#8b949e;font-size:.68rem;">{user['level']}</div></div></div>""", unsafe_allow_html=True)
        if user["role"] == "professor":
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("dashboard",ui_lang), use_container_width=True, key="btn_dash"):
                    st.session_state.page = "dashboard"; st.rerun()
            with c2:
                if st.button(t("profile",ui_lang), use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
        else:
            if st.button(t("profile",ui_lang), use_container_width=True, key="btn_profile"):
                st.session_state.page = "profile"; st.rerun()
        if st.button(t("logout",ui_lang), use_container_width=True, key="btn_sair"):
            _logout(); st.rerun()

    st.markdown("""<style>
.msg-row{display:flex;align-items:flex-end;gap:10px;margin:6px 0;}
.msg-row.user-row{flex-direction:row-reverse;}
.msg-row.user-row>div,.msg-row.bot-row>div{display:flex;flex-direction:column;}
.msg-row.user-row>div{align-items:flex-end;}
.msg-row.bot-row>div{align-items:flex-start;}
.msg-bubble{padding:10px 15px;border-radius:18px;font-size:.88rem;line-height:1.6;word-break:break-word;white-space:pre-wrap;}
.msg-bubble.user{max-width:clamp(200px,75%,700px);background:var(--user-bubble-bg,#2d6a4f);color:var(--user-bubble-text,#fff);border-bottom-right-radius:4px;}
.msg-bubble.bot{max-width:clamp(200px,75%,700px);background:var(--ai-bubble-bg,#1a1f2e);color:var(--ai-bubble-text,#e6edf3);border:1px solid var(--ai-bubble-border,#252d3d);border-bottom-left-radius:4px;}
.msg-av{width:30px;height:30px;border-radius:50%;overflow:hidden;flex-shrink:0;margin-bottom:2px;}
.msg-time{font-size:.6rem;color:#4a5a6a;margin:2px 4px 0;}
.bot-row .msg-time{text-align:left;}.msg-row.user-row .msg-time{text-align:right;}
.ouvir-row{padding:2px 0 0 40px;}
.ouvir-btn{background:none;border:1px solid #30363d;border-radius:16px;color:#8b949e;font-size:.68rem;padding:2px 10px;cursor:pointer;font-family:inherit;white-space:nowrap;}
.ouvir-btn:hover{border-color:#f0a500;color:#f0a500;}
@media(max-width:768px){.msg-bubble{max-width:88%!important;font-size:.82rem!important;}}
</style>""", unsafe_allow_html=True)

    st.markdown(f"""<div style="display:flex;align-items:center;gap:14px;padding:14px 0 10px;border-bottom:1px solid #1e2a3a;margin-bottom:8px;">
        {avatar_html(52)}<div><div style="font-size:1rem;font-weight:700;color:#e6edf3;">{PROF_NAME}</div>
        <div style="font-size:.7rem;color:#8b949e;">● Online · {user['level']} · {user['focus']}</div></div></div>""", unsafe_allow_html=True)

    _mini = get_tati_mini_b64()
    tati_av = (f'<div class="msg-av" style="background:url({_mini}) center top/cover no-repeat;"></div>'
               if _mini else '<div class="msg-av" style="background:#1e2a3a;display:flex;align-items:center;justify-content:center;font-size:14px;">🧑‍🏫</div>')

    for i, msg in enumerate(messages):
        content  = msg["content"].replace("\n", "<br>")
        msg_time = msg.get("time", "")
        if msg["role"] == "assistant":
            tts_b64 = msg.get("tts_b64", "")
            is_file = msg.get("is_file", False)
            st.markdown(f'<div class="msg-row bot-row">{tati_av}<div><div class="msg-bubble bot">{content}</div><div class="msg-time">{msg_time}</div></div></div>', unsafe_allow_html=True)
            if tts_b64:
                components.html(_render_audio_player(tts_b64, msg_time, f"p{i}"), height=44, scrolling=False)
            elif not is_file:
                clean = (msg["content"].replace("\\","").replace("`","").replace('"',"&quot;")
                    .replace("'","&#39;").replace("\n"," ").replace("*","").replace("#",""))[:600]
                st.markdown(f'<div class="ouvir-row"><button class="ouvir-btn" data-pav-tts data-text="{clean}">▶ Ouvir</button></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="msg-row user-row"><div><div class="msg-bubble user">{content}</div><div class="msg-time">{msg_time}</div></div></div>', unsafe_allow_html=True)

    if st.session_state.get("speaking"):
        components.html("""<!DOCTYPE html><html><head><style>*{margin:0;padding:0;}html,body{background:transparent;overflow:hidden;font-family:sans-serif;}
.row{display:flex;align-items:center;gap:10px;padding:6px 0;}
.av{width:30px;height:30px;border-radius:50%;background:#1e2a3a;display:flex;align-items:center;justify-content:center;font-size:14px;}
.bbl{display:flex;align-items:center;gap:8px;background:#1a1f2e;border:1px solid #252d3d;border-radius:18px;border-bottom-left-radius:4px;padding:8px 14px;}
.spin{color:#e05c2a;font-size:16px;animation:sp 1.2s linear infinite;display:inline-block;}
@keyframes sp{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
.txt{font-size:.75rem;color:#8b949e;font-style:italic;}
</style></head><body><div class="row"><div class="av">🧑‍🏫</div><div class="bbl"><span class="spin">✳</span><span class="txt">Pensando…</span></div></div></body></html>""", height=52, scrolling=False)

    # Anexo staged
    staged = st.session_state.get("staged_file")
    if staged:
        sl = staged if isinstance(staged, list) else [staged]
        icons = {"audio":"🎵","text":"📄","image":"📸"}
        items = "".join(f'<span style="background:rgba(255,255,255,.06);border-radius:6px;padding:3px 8px;font-size:.8rem;color:#e6edf3;">{icons.get(f["kind"],"📎")} {f["name"]}</span>' for f in sl)
        st.markdown(f'<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.25);border-radius:10px;padding:10px 14px;margin:6px 0;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;"><div style="display:flex;gap:6px;flex-wrap:wrap;">{items}<span style="color:#8b949e;font-size:.75rem;">· {len(sl)} arquivo(s)</span></div></div>', unsafe_allow_html=True)
        if st.button(t("remove_attachment", ui_lang), key="rm_staged"):
            st.session_state.staged_file = None; st.session_state.pop("_last_files_key", None); st.rerun()

    # Download pendente
    pd = st.session_state.get("_pending_download")
    if pd:
        st.markdown(f'<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.35);border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;align-items:center;justify-content:space-between;gap:12px;"><span style="font-size:.85rem;color:#e6edf3;">📎 <b>{pd["filename"]}</b></span><a href="data:{pd["mime"]};base64,{pd["b64"]}" download="{pd["filename"]}" style="background:linear-gradient(135deg,#f0a500,#e05c2a);color:#060a10;font-weight:700;font-size:.78rem;padding:6px 16px;border-radius:20px;text-decoration:none;">⬇ Baixar</a></div>', unsafe_allow_html=True)

    prompt = st.chat_input(t("type_message", ui_lang))
    if prompt:
        if not API_KEY: st.error("Configure ANTHROPIC_API_KEY"); st.stop()
        staged = st.session_state.get("staged_file")
        if staged:
            sl = staged if isinstance(staged, list) else [staged]
            for i, sf in enumerate(sl):
                _process_file(username, user, conv_id, sf["raw"], sf["name"], extra_text=prompt if i==0 else "")
            st.session_state.staged_file = None; st.session_state.pop("_last_files_key", None)
        else:
            append_message(username, conv_id, "user", prompt)
            st.session_state.speaking = True
            try: send_to_claude(username, user, conv_id, prompt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
        st.rerun()

    audio_val = st.audio_input(" ", key=f"voice_input_{st.session_state.audio_key}", label_visibility="collapsed")
    if audio_val and audio_val != st.session_state.get("_last_audio"):
        st.session_state["_last_audio"] = audio_val
        with st.spinner("Transcrevendo..."):
            txt = transcribe_bytes(audio_val.read(), ".wav", None)
        if txt and not txt.startswith("❌") and not txt.startswith("⚠️"):
            append_message(username, conv_id, "user", txt, audio=True)
            st.session_state.speaking = True
            try: send_to_claude(username, user, conv_id, txt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
            st.session_state.audio_key += 1; st.rerun()
        elif txt: st.error(txt)

    uploaded = st.file_uploader("📎", key="file_upload", label_visibility="collapsed", accept_multiple_files=True,
        type=["mp3","wav","ogg","m4a","webm","flac","pdf","doc","docx","txt","png","jpg","jpeg","webp"])
    if uploaded:
        names_key = ",".join(sorted(f.name for f in uploaded))
        if names_key != st.session_state.get("_last_files_key"):
            st.session_state["_last_files_key"] = names_key
            sl = []
            for uf in uploaded:
                raw = uf.read(); res = extract_file(raw, uf.name)
                sl.append({"raw":raw,"name":uf.name,"kind":res["kind"]})
            st.session_state.staged_file = sl; st.rerun()

    # TTS via Web Speech API para mensagens sem tts_b64
    components.html("""<!DOCTYPE html><html><body><script>
(function(){var par=window.parent?window.parent.document:document;var cur=null;
function init(){par.querySelectorAll('[data-pav-tts]').forEach(function(btn){
  if(btn._pi)return;btn._pi=true;
  btn.addEventListener('click',function(){
    if(cur&&cur!==btn){speechSynthesis.cancel();cur.textContent='▶ Ouvir';cur=null;}
    if(btn.classList.contains('speaking')){speechSynthesis.cancel();btn.textContent='▶ Ouvir';cur=null;return;}
    var u=new SpeechSynthesisUtterance(btn.getAttribute('data-text')||'');u.lang='en-US';u.rate=0.95;
    u.onstart=function(){btn.textContent='⏹ Parar';cur=btn;};
    u.onend=u.onerror=function(){btn.textContent='▶ Ouvir';cur=null;};
    speechSynthesis.cancel();speechSynthesis.speak(u);
  });
});}
init();new MutationObserver(init).observe(par.body,{childList:true,subtree:true});
})();
</script></body></html>""", height=1)

# ══════════════════════════════════════════════════════════════════════════════
# PERFIL
# ══════════════════════════════════════════════════════════════════════════════
def show_profile() -> None:
    user = st.session_state.user; username = user["username"]
    profile = user.get("profile", {}); ui_lang = profile.get("language","pt-BR")
    is_prof = user.get("role") == "professor"

    st.markdown("## ⚙️ Perfil"); st.markdown("---")
    level_opts = ["Beginner","Pre-Intermediate","Intermediate","Business English","Advanced","Native"]
    focus_opts = ["General Conversation","Business English","Travel","Academic","Pronunciation","Grammar","Vocabulary","Exam Prep"]
    def si(lst, val):
        try: return lst.index(val)
        except: return 0

    t1, t2, t3 = st.tabs(["🎨 Geral","🧠 Personalização","👤 Conta"])

    with t1:
        c1, c2 = st.columns(2)
        with c1:
            lang   = st.selectbox(t("interface_lang",ui_lang),["pt-BR","en-US"],index=si(["pt-BR","en-US"],profile.get("language","pt-BR")),key="pf_l")
            accent = st.color_picker("Cor de destaque",value=profile.get("accent_color","#f0a500"),key="pf_a")
        with c2:
            ub = st.color_picker("Balão usuário",value=profile.get("user_bubble_color","#2d6a4f"),key="pf_ub")
            ab = st.color_picker("Balão IA",value=profile.get("ai_bubble_color","#1a1f2e"),key="pf_ab")
        c3, c4 = st.columns(2)
        with c3: vl=st.selectbox(t("transcription_lang",ui_lang),["auto (pt+en)","en","pt"],index=si(["auto (pt+en)","en","pt"],profile.get("voice_lang","auto (pt+en)")),key="pf_vl")
        with c4: sl=st.selectbox(t("tts_accent",ui_lang),["en-US","en-UK","pt-BR"],index=si(["en-US","en-UK","pt-BR"],profile.get("speech_lang","en-US")),key="pf_sl")
        if st.button(t("save_general",ui_lang),key="sg"):
            update_profile(username,{"language":lang,"accent_color":accent,"user_bubble_color":ub,"ai_bubble_color":ab,"voice_lang":vl,"speech_lang":sl})
            st.session_state.user={"username":username,**load_students().get(username,{})}; st.success("✅ Salvo!")

    with t2:
        c1, c2 = st.columns(2)
        with c1:
            nick = st.text_input(t("nickname",ui_lang),value=profile.get("nickname",""),key="pf_n")
            occ  = st.text_input(t("occupation",ui_lang),value=profile.get("occupation",""),key="pf_o")
        with c2:
            level = st.selectbox(t("english_level",ui_lang),level_opts,index=si(level_opts,user.get("level","Beginner")),key="pf_lv")
            focus = st.selectbox(t("focus",ui_lang),focus_opts,index=si(focus_opts,user.get("focus","General Conversation")),key="pf_f")
        ai_style = profile.get("ai_style","Warm & Encouraging"); ai_tone = profile.get("ai_tone","Teacher"); custom = profile.get("custom_instructions","")
        if not is_prof:
            c3, c4 = st.columns(2)
            with c3: ai_style=st.selectbox(t("conv_tone",ui_lang),["Warm & Encouraging","Formal","Fun & Casual","Strict"],index=si(["Warm & Encouraging","Formal","Fun & Casual","Strict"],ai_style),key="pf_as")
            with c4: ai_tone=st.selectbox(t("ai_role",ui_lang),["Teacher","Partner","Tutor","Coach"],index=si(["Teacher","Partner","Tutor","Coach"],ai_tone),key="pf_at")
            custom=st.text_area("Instruções personalizadas",value=custom,height=80,key="pf_cu")
        if st.button(t("save_custom",ui_lang),key="sc"):
            update_profile(username,{"nickname":nick,"occupation":occ,"ai_style":ai_style,"ai_tone":ai_tone,"custom_instructions":custom,"level":level,"focus":focus})
            st.session_state.user={"username":username,**load_students().get(username,{})}; st.success("✅ Salvo!")

    with t3:
        st.markdown("### 📸 Foto")
        cur_av = get_user_avatar_b64(username, st.session_state.get("_avatar_v",0))
        st.markdown(_avatar_circle_html(cur_av, 80)+'<div style="height:8px"></div>', unsafe_allow_html=True)
        st.markdown("""<style>[data-testid="stFileUploader"]{position:static!important;top:auto!important;left:auto!important;width:auto!important;height:auto!important;overflow:visible!important;opacity:1!important;pointer-events:auto!important;}</style>""", unsafe_allow_html=True)
        pf = st.file_uploader("JPG, PNG ou WEBP (máx 15MB)",type=["jpg","jpeg","png","webp"],key="pf_ph")
        if pf:
            fid = f"{pf.name}::{pf.size}"
            if st.session_state.get("_last_ph") != fid:
                raw = pf.read()
                if len(raw) > 15*1024*1024: st.error("❌ Máximo 15MB.")
                else:
                    suffix = Path(pf.name).suffix.lstrip(".")
                    mime = "image/jpeg" if suffix in ("jpg","jpeg") else f"image/{suffix}"
                    save_user_avatar_db(username, raw, mime)
                    _bump_avatar(); st.session_state["_last_ph"] = fid; st.success("✅ Foto salva!"); st.rerun()
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1: fname=st.text_input(t("full_name",ui_lang),value=user.get("name",""),key="pf_fn")
        with c2: email=st.text_input(t("email",ui_lang),value=user.get("email",""),key="pf_em")
        st.markdown(f"**Username:** `{username}`")
        if st.button(t("save_data",ui_lang),key="sd"):
            update_profile(username,{"name":fname,"email":email})
            st.session_state.user={"username":username,**load_students().get(username,{})}; st.success("✅ Salvo!")
        st.markdown("---"); st.markdown("### Senha")
        c3, c4 = st.columns(2)
        with c3: np_=st.text_input(t("new_password",ui_lang),type="password",key="pf_np")
        with c4: cp_=st.text_input(t("confirm_password",ui_lang),type="password",key="pf_cp")
        if st.button(t("change_password",ui_lang),key="spw"):
            if len(np_)<6: st.error("Muito curta.")
            elif np_!=cp_: st.error("Não coincidem.")
            else: update_password(username,np_); st.success("✅ Senha alterada!")

    st.markdown("---")
    if st.button(t("back",ui_lang),key="bk"):
        st.session_state.page = "dashboard" if is_prof else "chat"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def show_dashboard() -> None:
    user = st.session_state.user; ui_lang = user.get("profile",{}).get("language","pt-BR")
    with st.sidebar:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div><div style="font-weight:600;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#8b949e;">● Professora</div></div></div><hr style="border-color:#30363d;">""", unsafe_allow_html=True)
        if st.button("📊 Dashboard",use_container_width=True,type="primary"): pass
        if st.button(t("voice_mode",ui_lang),use_container_width=True,key="dv"):
            st.session_state.page="voice"; st.rerun()
        if st.button(t("use_as_student",ui_lang),use_container_width=True,key="dc"):
            st.session_state.page="chat"; st.rerun()
            st.session_state.page="profile"; st.rerun()
        if st.button(t("logout",ui_lang),use_container_width=True,key="dl"):
            _logout(); st.rerun()

    st.markdown("## 📊 Painel do Professor"); st.markdown("---")
    stats = get_all_students_stats(); today = datetime.now().strftime("%Y-%m-%d")
    c1,c2,c3,c4 = st.columns(4)
    for col,val,lbl in zip([c1,c2,c3,c4],
        [len(stats), sum(s["messages"] for s in stats), sum(s["corrections"] for s in stats),
         sum(1 for s in stats if s["last_active"][:10]==today)],
        ["Alunos","Mensagens","Correções","Ativos Hoje"]):
        col.metric(lbl, val)
    st.markdown("---"); st.markdown("### 👥 Alunos")
    if not stats:
        st.info("Nenhum aluno ainda.")
    else:
        for s in sorted(stats, key=lambda x: x["messages"], reverse=True):
            with st.expander(f"**{s['name']}** (@{s['username']}) — {s['level']}"):
                st.write(f"Foco: {s['focus']} | Msgs: {s['messages']} | Correções: {s['corrections']} | Último: {s['last_active']}")

# ══════════════════════════════════════════════════════════════════════════════
# ROTEADOR
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    show_login()
else:
    _tok = st.session_state.get("_session_token","")
    if _tok and not st.session_state.get("_session_saved"):
        js_save_session(_tok); st.session_state["_session_saved"] = True

    _page = st.session_state.page
    if   _page == "profile":   show_profile()
    elif _page == "dashboard": show_dashboard()
    elif _page == "chat":      show_chat()
    else:                      show_chat()    # padrão: modo chat