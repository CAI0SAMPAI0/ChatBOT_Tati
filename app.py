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

# ── Imports do banco e serviços ───────────────────────────────────────────────
from database import (
    init_db, authenticate, register_student, load_students,
    new_conversation, list_conversations, load_conversation,
    append_message, get_all_students_stats, delete_conversation,
    update_profile, update_password,
    create_session, validate_session, delete_session,
    save_user_avatar_db, get_user_avatar_db, remove_user_avatar_db, get_client, AVATAR_BUCKET,
)
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from file_reader import extract_file

# ── Telas externas (login e modo voz) ────────────────────────────────────────
from login import show_login        # tela de login responsiva (roxo)
from voice import show_voice        # modo voz imersivo com dvh

# ── Wav2Lip (opcional) ────────────────────────────────────────────────────────
try:
    from wav2lip_avatar import generate_talking_video, wav2lip_available
    _WAV2LIP_LOADED = True
except ImportError:
    _WAV2LIP_LOADED = False
    def wav2lip_available(): return False
    def generate_talking_video(_): return None

# ── Font Awesome ──────────────────────────────────────────────────────────────
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">',
    unsafe_allow_html=True,
)

# ── Inicialização ─────────────────────────────────────────────────────────────
init_db()

API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
PHOTO_PATH = os.getenv("PROFESSOR_PHOTO", "assets/tati.png")
PROF_NAME  = os.getenv("PROFESSOR_NAME",  "Professor Avatar")

if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0


# ══════════════════════════════════════════════════════════════════════════════
# INTERNACIONALIZAÇÃO (i18n)
# ══════════════════════════════════════════════════════════════════════════════

_STRINGS = {
    "pt-BR": {
        "type_message":       "Digite uma mensagem…",
        "new_conv":           "➕  Nova conversa",
        "voice_mode":         "🎙️  Modo Conversa",
        "dashboard":          "📊 Painel",
        "profile":            "⚙️ Perfil",
        "logout":             "🚪 Sair",
        "delete_conv":        "Excluir conversa",
        "username":           "Usuário",
        "password":           "Senha",
        "full_name":          "Nome completo",
        "email":              "E-mail",
        "enter":              "Entrar",
        "create_account":     "Criar Conta",
        "save_general":       "💾 Salvar Alterações",
        "save_custom":        "💾 Salvar Personalização",
        "save_data":          "💾 Salvar Dados",
        "change_password":    "🔒 Alterar Senha",
        "remove_photo":       "🗑️ Remover foto",
        "remove_attachment":  "✕ Remover anexo",
        "close_voice":        "✕ Fechar Modo Voz",
        "close":              "✕ Fechar",
        "back":               "← Voltar ao Chat",
        "use_as_student":     "Usar como Aluno",
        "enter_chat":         "Entrar no Chat",
        "my_profile":         "⚙️ Meu Perfil",
        "interface_lang":     "Idioma da interface",
        "theme":              "Tema",
        "transcription_lang": "Idioma da transcrição (Whisper)",
        "tts_accent":         "Sotaque (TTS fallback)",
        "nickname":           "Apelido",
        "occupation":         "Ocupação",
        "english_level":      "Nível de inglês",
        "focus":              "Foco",
        "conv_tone":          "Tom das conversas",
        "ai_role":            "Papel da IA",
        "new_password":       "Nova senha",
        "confirm_password":   "Confirmar senha",
        "speaking":           "🗣 Falando...",
        "listening":          "🎙 Ouvindo...",
        "processing":         "⏳ Processando...",
        "tap_to_speak":       "Toque no microfone para falar",
        "tap_to_record":      "Toque para gravar",
        "tap_to_stop":        "Toque para parar",
        "wait":               "Aguarde...",
        "speaking_ai":        "IA falando...",
        "error_mic":          "Erro ao processar áudio.",
        "error_api":          "API não configurada.",
    },
    "en-US": {
        "type_message":       "Type a message…",
        "new_conv":           "➕  New conversation",
        "voice_mode":         "🎙️  Voice Mode",
        "dashboard":          "📊 Dashboard",
        "profile":            "⚙️ Profile",
        "logout":             "🚪 Logout",
        "delete_conv":        "Delete conversation",
        "username":           "Username",
        "password":           "Password",
        "full_name":          "Full name",
        "email":              "E-mail",
        "enter":              "Sign In",
        "create_account":     "Create Account",
        "save_general":       "💾 Save Changes",
        "save_custom":        "💾 Save Customization",
        "save_data":          "💾 Save Data",
        "change_password":    "🔒 Change Password",
        "remove_photo":       "🗑️ Remove photo",
        "remove_attachment":  "✕ Remove attachment",
        "close_voice":        "✕ Close Voice Mode",
        "close":              "✕ Close",
        "back":               "← Back to Chat",
        "use_as_student":     "Use as Student",
        "enter_chat":         "Enter Chat",
        "my_profile":         "⚙️ My Profile",
        "interface_lang":     "Interface language",
        "theme":              "Theme",
        "transcription_lang": "Transcription language (Whisper)",
        "tts_accent":         "Accent (TTS fallback)",
        "nickname":           "Nickname",
        "occupation":         "Occupation",
        "english_level":      "English level",
        "focus":              "Focus",
        "conv_tone":          "Conversation tone",
        "ai_role":            "AI role",
        "new_password":       "New password",
        "confirm_password":   "Confirm password",
        "speaking":           "🗣 Speaking...",
        "listening":          "🎙 Listening...",
        "processing":         "⏳ Processing...",
        "tap_to_speak":       "Tap the mic to speak",
        "tap_to_record":      "Tap to record",
        "tap_to_stop":        "Tap to stop",
        "wait":               "Please wait...",
        "speaking_ai":        "AI speaking...",
        "error_mic":          "Could not process audio.",
        "error_api":          "API not configured.",
    },
    "en-UK": {
        "type_message":       "Type a message…",
        "new_conv":           "➕  New conversation",
        "voice_mode":         "🎙️  Voice Mode",
        "dashboard":          "📊 Dashboard",
        "profile":            "⚙️ Profile",
        "logout":             "🚪 Log out",
        "delete_conv":        "Delete conversation",
        "username":           "Username",
        "password":           "Password",
        "full_name":          "Full name",
        "email":              "E-mail",
        "enter":              "Sign In",
        "create_account":     "Create Account",
        "save_general":       "💾 Save Changes",
        "save_custom":        "💾 Save Customisation",
        "save_data":          "💾 Save Data",
        "change_password":    "🔒 Change Password",
        "remove_photo":       "🗑️ Remove photo",
        "remove_attachment":  "✕ Remove attachment",
        "close_voice":        "✕ Close Voice Mode",
        "close":              "✕ Close",
        "back":               "← Back to Chat",
        "use_as_student":     "Use as Student",
        "enter_chat":         "Enter Chat",
        "my_profile":         "⚙️ My Profile",
        "interface_lang":     "Interface language",
        "theme":              "Theme",
        "transcription_lang": "Transcription language (Whisper)",
        "tts_accent":         "Accent (TTS fallback)",
        "nickname":           "Nickname",
        "occupation":         "Occupation",
        "english_level":      "English level",
        "focus":              "Focus",
        "conv_tone":          "Conversation tone",
        "ai_role":            "AI role",
        "new_password":       "New password",
        "confirm_password":   "Confirm password",
        "speaking":           "🗣 Speaking...",
        "listening":          "🎙 Listening...",
        "processing":         "⏳ Processing...",
        "tap_to_speak":       "Tap the mic to speak",
        "tap_to_record":      "Tap to record",
        "tap_to_stop":        "Tap to stop",
        "wait":               "Please wait...",
        "speaking_ai":        "AI speaking...",
        "error_mic":          "Could not process audio.",
        "error_api":          "API not configured.",
    },
}

def t(key: str, lang: str = "pt-BR") -> str:
    return _STRINGS.get(lang, _STRINGS["pt-BR"]).get(key, _STRINGS["pt-BR"].get(key, key))


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE IMAGEM / AVATAR
# ══════════════════════════════════════════════════════════════════════════════

def get_photo_b64() -> str | None:
    p = Path(PHOTO_PATH)
    if p.exists():
        ext  = p.suffix.lower().replace(".", "")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None

PHOTO_B64 = get_photo_b64()

@st.cache_data(show_spinner=False)
def get_tati_mini_b64() -> str:
    for _p in [Path("assets/tati.png"), Path("assets/tati.jpg"),
               Path(__file__).parent / "assets" / "tati.png",
               Path(__file__).parent / "assets" / "tati.jpg"]:
        if _p.exists():
            _ext  = _p.suffix.lstrip(".").lower()
            _mime = "jpeg" if _ext in ("jpg", "jpeg") else _ext
            return f"data:image/{_mime};base64,{base64.b64encode(_p.read_bytes()).decode()}"
    return get_photo_b64() or ""

@st.cache_data(show_spinner=False)
def get_avatar_frames() -> dict:
    _base = Path(__file__).parent
    def _load(candidates):
        for p in candidates:
            p = Path(p)
            if p.exists():
                return f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"
        return ""
    return {
        "base":   _load([_base/"assets"/"avatar_tati_normal.png",     "assets/avatar_tati_normal.png"]),
        "closed": _load([_base/"assets"/"avatar_tati_closed.png",     "assets/avatar_tati_closed.png"]),
        "mid":    _load([_base/"assets"/"avatar_tati_meio.png",       "assets/avatar_tati_meio.png"]),
        "open":   _load([_base/"assets"/"avatar_tati_bem_aberta.png", "assets/avatar_tati_bem_aberta.png",
                         _base/"assets"/"avatar_tati_aberta.png",     "assets/avatar_tati_aberta.png"]),
    }

def get_user_avatar_b64(username: str, _bust: int = 0) -> str | None:
    result = get_user_avatar_db(username)
    if not result:
        return None
    raw, mime = result
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

_get_avatar = lambda u: get_user_avatar_b64(u, _bust=st.session_state.get("_avatar_v", 0))

def _avatar_circle_html(b64: str | None, size: int, border: str = "#8800f0") -> str:
    if not b64:
        for _p in [Path("assets/sem_foto.png"), Path(__file__).parent / "assets" / "sem_foto.png"]:
            if _p.exists():
                b64 = f"data:image/png;base64,{base64.b64encode(_p.read_bytes()).decode()}"
                break
    if b64:
        return (
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'background:url({b64}) center/cover no-repeat;'
            f'border:2px solid {border};flex-shrink:0;"></div>'
        )
    icon_px = int(size * 0.50)
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:linear-gradient(135deg,#1e2a3a,#2a3a50);'
        f'display:flex;align-items:center;justify-content:center;'
        f'border:2px solid #1e2a3a;flex-shrink:0;">'
        f'<i class="fa-duotone fa-solid fa-user-graduate" '
        f'style="font-size:{icon_px}px;--fa-primary-color:#f0a500;--fa-secondary-color:#c87800;--fa-secondary-opacity:0.6;"></i>'
        f'</div>'
    )

def save_user_avatar(username: str, raw: bytes, suffix: str) -> None:
    suffix = suffix.lower().lstrip(".")
    mime   = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    save_user_avatar_db(username, raw, mime)
    _bump_avatar_version()

def remove_user_avatar(username: str) -> None:
    remove_user_avatar_db(username)
    _bump_avatar_version()

def _bump_avatar_version() -> None:
    st.session_state["_avatar_v"] = st.session_state.get("_avatar_v", 0) + 1

def user_avatar_html(username: str, size: int = 36, **_) -> str:
    return _avatar_circle_html(get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v", 0)), size)

def avatar_html(size: int = 52, speaking: bool = False) -> str:
    cls   = "speaking" if speaking else ""
    photo = PHOTO_B64
    if photo:
        return (
            f'<div class="avatar-wrap {cls}" style="'
            f'width:{size}px;height:{size}px;border-radius:50%;flex-shrink:0;'
            f'background:url({photo}) center top/cover no-repeat;'
            f'position:relative;overflow:hidden;">'
            f'<div class="avatar-ring"></div></div>'
        )
    return (
        f'<div class="avatar-circle {cls}" '
        f'style="width:{size}px;height:{size}px;font-size:{int(size*.48)}px">🧑‍🏫</div>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title=f"{PROF_NAME} · English",
    page_icon=str(Path(PHOTO_PATH)) if Path(PHOTO_PATH).exists() else "🎓",
    layout="wide",
)

def load_css(path: str) -> None:
    p = Path(path)
    if p.exists():
        st.markdown(f"<style>{p.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

load_css("styles/style.css")

# ── CSS responsivo global ──────────────────────────────────────────────────────
st.markdown("""<style>
/* ── Anti-flash / anti-dim durante rerun ── */
[data-testid="stAppViewBlockContainer"] { opacity: 1 !important; }
div[data-stale="true"]  { opacity: 1 !important; transition: none !important; }
div[data-stale="false"] { opacity: 1 !important; transition: none !important; }
.stSpinner, [data-testid="stSpinner"],
div[class*="StatusWidget"], div[class*="stStatusWidget"] { display: none !important; }
.stApp > div { opacity: 1 !important; }
iframe[title="streamlit_loading"] { display: none !important; }

/* ── Layout responsivo ── */
html, body {
    height: 100%;
    height: 100dvh;
}
section[data-testid="stMain"] > div {
    transition: all .25s ease;
    max-width: 100% !important;
}
.main .block-container {
    max-width: 100% !important;
    padding-left:  clamp(8px, 2vw, 40px) !important;
    padding-right: clamp(8px, 2vw, 40px) !important;
    padding-top:   clamp(8px, 1vh, 24px) !important;
    padding-bottom: clamp(60px, 8vh, 100px) !important;
}
section[data-testid="stSidebar"] {
    min-width: 220px !important;
    max-width: 340px !important;
}
div[data-testid="stButton"] button {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ── File uploader oculto ── */
[data-testid="stFileUploader"] {
    position: fixed !important;
    bottom: -999px !important;
    left: -9999px !important;
    opacity: 0 !important;
    width: 1px !important;
    height: 1px !important;
    pointer-events: none !important;
    overflow: hidden !important;
}
[data-testid="stFileUploader"] input[type="file"] {
    pointer-events: auto !important;
}

/* ── Audio input oculto (nativo) ── */
[data-testid="stAudioInput"] {
    position: fixed !important;
    bottom: -9999px !important;
    left: -9999px !important;
    opacity: 0 !important;
    pointer-events: none !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
}
[data-testid="stAudioInput"] button {
    pointer-events: auto !important;
}

/* ── Responsivo mobile ── */
@media (max-width: 1024px) {
    .main .block-container {
        padding-left: 12px !important;
        padding-right: 12px !important;
    }
}
@media (max-width: 768px) {
    section[data-testid="stSidebar"] { min-width: 0 !important; }
    .main .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
        padding-bottom: 80px !important;
    }
    div.bubble { max-width: 92% !important; font-size: .82rem !important; }
    div.prof-header h1 { font-size: 1rem !important; }
    div.prof-header { padding: 10px 8px !important; }
    .bav-s, .bav-u { display: none !important; }
}
@media (max-width: 380px) {
    .main .block-container {
        padding-left: 4px !important;
        padding-right: 4px !important;
    }
}
img { max-width: 100%; }
</style>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT DO SISTEMA
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, very intelligent and encouraging. You help adults speak English with more confidence, over 25 years of experience, Advanced English Hunter College NY, and passionate about teaching.
Students: teenagers (Beginner/Pre-Intermediate) and adults focused on Business/News.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BILINGUAL POLICY (VERY IMPORTANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BEGINNER / PRE-INTERMEDIATE:
  • Student writes/speaks in Portuguese → Respond in simple English AND provide Portuguese translation of key words in parentheses.
  • Always end your reply with an easy, encouraging question in English.

INTERMEDIATE:
  • Respond primarily in English. Use Portuguese ONLY to clarify a specific word.
  • If student writes in Portuguese: "I understood! Now, how would you say that in English?"

ADVANCED / BUSINESS ENGLISH:
  • Respond exclusively in English.
  • If student writes in Portuguese: "Let's keep it in English — you've got this!"

TRANSLATION REQUESTS (any level):
  • When asked "como se diz X?" or "what does Y mean?", always provide translation + example sentence.

TEACHING STYLE:
- Neuro-learning: guide students to discover errors. Never just give the answer.
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT conversational responses. Bold grammar points when appropriate.
- End responses with ONE engaging question.
- NEVER use emojis. Not a single one. Ever. Plain text only, always.
- NEVER start uninvited. Wait for the student to speak first.

ACTIVITY GENERATION:
- When the student asks for a FILE (PDF, Word/DOCX), respond ONLY with:
  <<<GENERATE_FILE>>>
  {{"format":"pdf","filename":"activity.pdf","title":"Exercise Title","content":"Full content here with \\n for line breaks"}}
  <<<END_FILE>>>"""


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE — valores padrão
# ══════════════════════════════════════════════════════════════════════════════

_defaults = {
    "logged_in":        False,
    "user":             None,
    "page":             "voice",     # padrão: modo voz (alunos vão direto para voz)
    "speaking":         False,
    "conv_id":          None,
    "voice_mode":       False,
    "staged_file":      None,
    "staged_file_name": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auto-login via token na URL (?s=...) ──────────────────────────────────────
_session_token = st.session_state.get("_session_token", "")
if _session_token and st.session_state.logged_in:
    if st.query_params.get("s") != _session_token:
        st.query_params["s"] = _session_token

if not st.session_state.logged_in:
    _s = st.query_params.get("s", "")
    if _s and len(_s) > 10:
        _udata = validate_session(_s)
        if _udata:
            _uname = _udata.get("_resolved_username") or next(
                (k for k, v in load_students().items() if v["password"] == _udata["password"]),
                None,
            )
            if _uname:
                st.session_state.logged_in         = True
                st.session_state.user              = {"username": _uname, **_udata}
                st.session_state.page              = "dashboard" if _udata["role"] == "professor" else "voice"
                st.session_state.conv_id           = None
                st.session_state["_session_token"] = _s
        else:
            st.query_params.pop("s", None)


# ══════════════════════════════════════════════════════════════════════════════
# SESSÃO PERSISTENTE — localStorage + cookie
# ══════════════════════════════════════════════════════════════════════════════

def js_save_session(token: str) -> None:
    components.html(
        f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function(){{
    var t='{token}';
    try{{window.parent.localStorage.setItem('pav_session',t);}}catch(e){{}}
    try{{localStorage.setItem('pav_session',t);}}catch(e){{}}
    try{{var exp=new Date(Date.now()+2592000000).toUTCString();
        window.parent.document.cookie='pav_session='+encodeURIComponent(t)+';expires='+exp+';path=/;SameSite=Lax';}}catch(e){{}}
    try{{var exp2=new Date(Date.now()+2592000000).toUTCString();
        document.cookie='pav_session='+encodeURIComponent(t)+';expires='+exp2+';path=/;SameSite=Lax';}}catch(e){{}}
}})();
</script></body></html>""",
        height=1,
    )

def js_clear_session() -> None:
    components.html(
        """<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
(function(){
    try{window.parent.localStorage.removeItem('pav_session');}catch(e){}
    try{localStorage.removeItem('pav_session');}catch(e){}
    try{window.parent.document.cookie='pav_session=;expires=Thu,01 Jan 1970 00:00:00 GMT;path=/';}catch(e){}
    try{document.cookie='pav_session=;expires=Thu,01 Jan 1970 00:00:00 GMT;path=/';}catch(e){}
})();
</script></body></html>""",
        height=1,
    )


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE CONVERSA / CLAUDE
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_conv(username: str) -> str:
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id

@st.cache_data(ttl=10, show_spinner=False)
def cached_load_conversation(username: str, conv_id: str) -> list:
    return load_conversation(username, conv_id)

def send_to_claude(username: str, user: dict, conv_id: str,
                   text: str, image_b64: str = None, image_media_type: str = None) -> str:
    client  = anthropic.Anthropic(api_key=API_KEY)
    context = (
        f"\n\nStudent profile — Name: {user['name']} | "
        f"Level: {user['level']} | Focus: {user['focus']} | "
        f"Native language: Brazilian Portuguese.\n"
        f"Apply the bilingual policy for level '{user['level']}' as instructed."
    )
    msgs     = load_conversation(username, conv_id)
    api_msgs = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in msgs
    ]
    if not api_msgs or api_msgs[-1]["role"] != "user" or api_msgs[-1]["content"] != text:
        api_msgs.append({"role": "user", "content": text})

    if image_b64 and image_media_type and api_msgs and api_msgs[-1]["role"] == "user":
        api_msgs[-1]["content"] = [
            {"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": image_b64}},
            {"type": "text",  "text": text},
        ]

    is_activity = any(w in text.lower() for w in [
        "pdf", "word", "docx", "atividade", "exercício", "exercicio",
        "worksheet", "activity", "exercise", "generate", "criar arquivo", "crie um", "make a",
    ])
    max_tok = 2000 if is_activity else 400

    resp       = client.messages.create(
        model="claude-haiku-4-5", max_tokens=max_tok,
        system=SYSTEM_PROMPT + context, messages=api_msgs,
    )
    reply_text = resp.content[0].text

    import re as _re
    reply_text = _re.sub(
        r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF'
        r'\u2600-\u26FF\u2700-\u27BF\U0001FA00-\U0001FA6F'
        r'\U0001FA70-\U0001FAFF\u200d\ufe0f]',
        '', reply_text,
    ).strip()

    if "<<<GENERATE_FILE>>>" in reply_text:
        return _intercept_file_generation(reply_text, username, conv_id)

    tts_b64_str = None
    if tts_available():
        audio_bytes = text_to_speech(reply_text)
        if audio_bytes:
            tts_b64_str = base64.b64encode(audio_bytes).decode()
            st.session_state["_tts_audio"] = tts_b64_str

    append_message(username, conv_id, "assistant", reply_text, tts_b64=tts_b64_str)
    cached_load_conversation.clear()
    return reply_text


def _intercept_file_generation(reply_text: str, username: str, conv_id: str) -> str:
    import re
    try:
        match = re.search(
            r'<<<GENERATE_FILE>>>\s*(\{.*?\})\s*<<<END_FILE>>>',
            reply_text, re.DOTALL,
        )
        if not match:
            append_message(username, conv_id, "assistant", reply_text)
            return reply_text
        meta     = json.loads(match.group(1))
        fmt      = meta.get("format", "pdf").lower()
        title    = meta.get("title", "Activity")
        content  = meta.get("content", "")
        filename = meta.get("filename", f"activity.{fmt}")
        if not filename.endswith(f".{fmt}"):
            filename = f"{filename}.{fmt}"
        out_dir  = Path("data/generated")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename
        if fmt == "pdf":
            _generate_pdf(title, content, out_path)
        else:
            _generate_docx(title, content, out_path)
        with open(out_path, "rb") as f:
            file_bytes = f.read()
        st.session_state["_pending_download"] = {
            "b64":      base64.b64encode(file_bytes).decode(),
            "filename": filename,
            "mime":     "application/pdf" if fmt == "pdf" else
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        display_msg = (
            f"📎 Arquivo gerado: **{filename}**\n\n_{title}_\n\n"
            "Clique em **⬇ Baixar arquivo** abaixo para salvar."
        )
        append_message(username, conv_id, "assistant", display_msg, is_file=True)
        cached_load_conversation.clear()
        return display_msg
    except Exception as e:
        err = f"Desculpe, não consegui gerar o arquivo: {e}"
        append_message(username, conv_id, "assistant", err)
        cached_load_conversation.clear()
        return err


def _generate_pdf(title: str, content: str, out_path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units    import cm
    from reportlab.lib          import colors
    from reportlab.platypus     import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums    import TA_CENTER
    doc    = SimpleDocTemplate(str(out_path), pagesize=A4,
                               leftMargin=2.5*cm, rightMargin=2.5*cm,
                               topMargin=2.5*cm, bottomMargin=2.5*cm)
    styles = getSampleStyleSheet()
    story  = []
    t_style = ParagraphStyle("t", parent=styles["Title"],  fontSize=18, spaceAfter=6,
                              textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER)
    s_style = ParagraphStyle("s", parent=styles["Normal"], fontSize=9,  spaceAfter=14,
                              textColor=colors.HexColor("#888888"), alignment=TA_CENTER)
    b_style = ParagraphStyle("b", parent=styles["Normal"], fontSize=11, leading=18, spaceAfter=8)
    story.append(Paragraph(title, t_style))
    story.append(Paragraph(f"Teacher {PROF_NAME}", s_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#f0a500")))
    story.append(Spacer(1, 0.4*cm))
    for line in content.split("\\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), b_style))
        else:
            story.append(Spacer(1, 0.2*cm))
    doc.build(story)


def _generate_docx(title: str, content: str, out_path: Path) -> None:
    from docx           import Document
    from docx.shared    import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    doc = Document()
    for sec in doc.sections:
        sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Cm(2.5)
    h = doc.add_heading(title, 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)
    sub = doc.add_paragraph(f"Teacher {PROF_NAME}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size = Pt(9)
    sub.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    doc.add_paragraph()
    for line in content.split("\\n"):
        if line.strip():
            p = doc.add_paragraph(line.strip())
            p.style.font.size = Pt(11)
        else:
            doc.add_paragraph()
    doc.save(str(out_path))


# ══════════════════════════════════════════════════════════════════════════════
# PLAYER DE ÁUDIO TTS
# ══════════════════════════════════════════════════════════════════════════════

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
  var audio=new Audio('data:audio/mpeg;base64,{tts_b64}');
  audio.preload='metadata';
  var b=document.getElementById('b'),pf=document.getElementById('pf'),
      pw=document.getElementById('pw'),vs=document.getElementById('vs'),
      vi=document.getElementById('vi'),sw=document.getElementById('sw');
  function unlockAudio(){{
    try{{var AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;
        var ctx=new AC();var buf=ctx.createBuffer(1,1,22050);var src=ctx.createBufferSource();
        src.buffer=buf;src.connect(ctx.destination);src.start(0);
        if(ctx.state==='suspended')ctx.resume();}}catch(e){{}}
  }}
  b.onclick=function(){{
    unlockAudio();
    if(!audio.paused){{audio.pause();b.textContent='▶ Ouvir';}}
    else{{var p=audio.play();
      if(p!==undefined){{p.then(function(){{b.textContent='⏸ Pausar';}})
        .catch(function(){{b.textContent='▶ Ouvir';}});}}
    }}
  }};
  audio.onended=function(){{b.textContent='▶ Ouvir';pf.style.width='0%';}};
  audio.ontimeupdate=function(){{
    if(audio.duration)pf.style.width=(audio.currentTime/audio.duration*100)+'%';
  }};
  pw.onclick=function(e){{
    var r=pw.getBoundingClientRect();
    if(audio.duration)audio.currentTime=((e.clientX-r.left)/r.width)*audio.duration;
  }};
  sw.querySelectorAll('.sb').forEach(function(btn){{
    btn.onclick=function(){{
      sw.querySelectorAll('.sb').forEach(function(x){{x.classList.remove('on');}});
      this.classList.add('on');audio.playbackRate=parseFloat(this.dataset.r);
    }};
  }});
  vs.oninput=function(){{
    audio.volume=parseFloat(vs.value);
    vi.textContent=audio.volume===0?'🔇':audio.volume<0.5?'🔉':'🔊';
  }};
  vi.onclick=function(){{
    if(audio.volume>0){{audio._v=audio.volume;audio.volume=0;vs.value=0;vi.textContent='🔇';}}
    else{{audio.volume=audio._v||1;vs.value=audio.volume;vi.textContent='🔊';}}
  }};
}})();
</script></body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL DO USUÁRIO
# ══════════════════════════════════════════════════════════════════════════════

def show_profile() -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")

    st.markdown("""<style>
[data-testid="stFileUploader"] {
    position: static !important; top: auto !important; left: auto !important;
    width: auto !important; height: auto !important;
    overflow: visible !important; opacity: 1 !important;
    pointer-events: auto !important;
}
[data-testid="stFileUploaderDropzone"] { display: flex !important; visibility: visible !important; }
</style>""", unsafe_allow_html=True)

    _ac = profile.get("accent_color", "#f0a500")
    _ub = profile.get("user_bubble_color", "#2d6a4f")
    _ab = profile.get("ai_bubble_color", "#1a1f2e")
    components.html(f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function(){{
  function hexToRgb(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);return[(n>>16)&255,(n>>8)&255,n&255].join(',');}}
  function luminance(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);var r=(n>>16)&255,g=(n>>8)&255,b=n&255;return 0.299*r+0.587*g+0.114*b;}}
  var ac="{_ac}",ub="{_ub}",ab="{_ab}";
  var rgb=hexToRgb(ac);
  var r=window.parent.document.documentElement;
  r.style.setProperty('--accent-full',ac);
  r.style.setProperty('--accent-70','rgba('+rgb+',.7)');
  r.style.setProperty('--accent-40','rgba('+rgb+',.4)');
  r.style.setProperty('--accent-30','rgba('+rgb+',.3)');
  r.style.setProperty('--accent-15','rgba('+rgb+',.15)');
  r.style.setProperty('--bubble-bg','rgba('+rgb+',.12)');
  r.style.setProperty('--bubble-border','rgba('+rgb+',.3)');
  r.style.setProperty('--bubble-text','#e6edf3');
  r.style.setProperty('--user-bubble-bg',ub);
  r.style.setProperty('--user-bubble-text',luminance(ub)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-bg',ab);
  r.style.setProperty('--ai-bubble-text',luminance(ab)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-border','rgba('+hexToRgb(ab)+',.6)');
}})();
</script></body></html>""", height=1)

    st.markdown("## ⚙️ Configurações do Perfil")
    st.markdown("---")

    is_prof    = user.get("role") == "professor"
    level_opts = ["Beginner", "Pre-Intermediate", "Intermediate", "Business English", "Advanced", "Native"]
    focus_opts = ["General Conversation","Business English","Travel","Academic",
                  "Pronunciation","Grammar","Vocabulary","Exam Prep"]

    def safe_index(lst, val, default=0):
        try:    return lst.index(val)
        except: return default

    tab_geral, tab_pers, tab_conta = st.tabs(["🎨 Geral", "🧠 Personalização", "👤 Conta"])

    with tab_geral:
        st.markdown("### Aparência")
        col1, col2 = st.columns(2)
        with col1:
            lang = st.selectbox(t("interface_lang", ui_lang), ["pt-BR","en-US","en-UK"],
                index=safe_index(["pt-BR","en-US","en-UK"], profile.get("language","pt-BR")), key="pf_lang")
        with col2:
            accent = st.color_picker("Cor de destaque", value=profile.get("accent_color","#f0a500"), key="pf_accent")
        col5, col6 = st.columns(2)
        with col5:
            user_bubble_color = st.color_picker("Balão do usuário", value=profile.get("user_bubble_color","#2d6a4f"), key="pf_user_bubble")
        with col6:
            ai_bubble_color = st.color_picker("Balão da IA", value=profile.get("ai_bubble_color","#1a1f2e"), key="pf_ai_bubble")
        st.markdown("### Voz")
        col3, col4 = st.columns(2)
        with col3:
            voice_lang = st.selectbox(t("transcription_lang",ui_lang),
                ["auto (pt+en)","en","pt","es","fr","de"],
                index=safe_index(["auto (pt+en)","en","pt","es","fr","de"],profile.get("voice_lang","auto (pt+en)")),key="pf_vlang")
        with col4:
            speech_lang = st.selectbox(t("tts_accent",ui_lang),["en-US","en-UK","pt-BR"],
                index=safe_index(["en-US","en-UK","pt-BR"],profile.get("speech_lang","en-US")),key="pf_slang")
        if st.button(t("save_general",ui_lang), key="save_geral"):
            update_profile(username,{"language":lang,"accent_color":accent,
                "user_bubble_color":user_bubble_color,"ai_bubble_color":ai_bubble_color,
                "voice_lang":voice_lang,"speech_lang":speech_lang})
            u = load_students().get(username,{})
            st.session_state.user = {"username":username,**u}
            st.success("✅ Settings saved!")

    with tab_pers:
        st.markdown("### Sobre Você")
        col1, col2 = st.columns(2)
        with col1:
            nickname   = st.text_input(t("nickname",ui_lang), value=profile.get("nickname",""), key="pf_nick")
            occupation = st.text_input(t("occupation",ui_lang), value=profile.get("occupation",""), key="pf_occ")
        with col2:
            level = st.selectbox(t("english_level",ui_lang), level_opts,
                index=safe_index(level_opts,user.get("level","Beginner")),key="pf_level")
            focus = st.selectbox(t("focus",ui_lang), focus_opts,
                index=safe_index(focus_opts,user.get("focus","General Conversation")),key="pf_focus")
        if not is_prof:
            st.markdown("### Estilo da IA")
            col3, col4 = st.columns(2)
            ai_style_opts = ["Warm & Encouraging","Formal & Professional","Fun & Casual","Strict & Direct"]
            ai_tone_opts  = ["Teacher","Conversation Partner","Tutor","Business Coach"]
            with col3:
                ai_style = st.selectbox(t("conv_tone",ui_lang), ai_style_opts,
                    index=safe_index(ai_style_opts,profile.get("ai_style","Warm & Encouraging")),key="pf_aistyle")
            with col4:
                ai_tone = st.selectbox(t("ai_role",ui_lang), ai_tone_opts,
                    index=safe_index(ai_tone_opts,profile.get("ai_tone","Teacher")),key="pf_aitone")
            custom = st.text_area("Instruções personalizadas para a IA",
                value=profile.get("custom_instructions",""),
                placeholder="ex: Sempre me corrija quando eu errar o Past Simple.",
                height=100,key="pf_custom")
        else:
            ai_style = profile.get("ai_style","Warm & Encouraging")
            ai_tone  = profile.get("ai_tone","Teacher")
            custom   = profile.get("custom_instructions","")
        if st.button(t("save_custom",ui_lang), key="save_pers"):
            update_profile(username,{"nickname":nickname,"occupation":occupation,
                "ai_style":ai_style,"ai_tone":ai_tone,"custom_instructions":custom,
                "level":level,"focus":focus})
            u = load_students().get(username,{})
            st.session_state.user = {"username":username,**u}
            st.success("✅ Perfil salvo!")

    with tab_conta:
        st.markdown("### 📸 Foto de Perfil")
        msg = st.session_state.pop("_photo_msg", None)
        if msg == "saved":   st.success("✅ Foto salva!")
        elif msg == "removed": st.success("Foto removida.")
        cur_avatar = get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v",0))
        MAX_BYTES  = 15 * 1024 * 1024
        col_av, col_btns = st.columns([1, 3])
        with col_av:
            st.markdown(_avatar_circle_html(cur_avatar, size=88) + '<div style="height:8px"></div>', unsafe_allow_html=True)
        with col_btns:
            photo_file = st.file_uploader("Alterar foto — JPG, PNG ou WEBP (máx 15 MB)",
                type=["jpg","jpeg","png","webp"], key="pf_photo_upload")
            if photo_file:
                file_id = f"{photo_file.name}::{photo_file.size}"
                if st.session_state.get("_last_photo_saved") != file_id:
                    raw_photo = photo_file.read()
                    if len(raw_photo) > MAX_BYTES:
                        st.error("❌ Foto muito grande. Máximo 15 MB.")
                    else:
                        suffix = Path(photo_file.name).suffix.lstrip(".")
                        save_user_avatar(username, raw_photo, suffix)
                        st.session_state["_last_photo_saved"] = file_id
                        _bump_avatar_version()
                        st.session_state["_photo_msg"] = "saved"
                        st.rerun()
        st.markdown("---")
        st.markdown("### Informações da Conta")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input(t("full_name",ui_lang), value=user.get("name",""), key="pf_fname")
        with col2:
            email = st.text_input(t("email",ui_lang), value=user.get("email",""), key="pf_email")
        st.markdown(f"**Username:** `{username}`")
        if st.button(t("save_data",ui_lang), key="save_conta"):
            update_profile(username,{"name":full_name,"email":email})
            u = load_students().get(username,{})
            st.session_state.user = {"username":username,**u}
            st.success("✅ Dados atualizados!")
        st.markdown("---")
        st.markdown("### Alterar Senha")
        col3, col4 = st.columns(2)
        with col3:
            new_pw  = st.text_input(t("new_password",ui_lang), type="password", key="pf_newpw")
        with col4:
            conf_pw = st.text_input(t("confirm_password",ui_lang), type="password", key="pf_confpw")
        if st.button(t("change_password",ui_lang), key="save_pw"):
            if len(new_pw) < 6:
                st.error("Senha muito curta.")
            elif new_pw != conf_pw:
                st.error("As senhas não coincidem.")
            else:
                update_password(username, new_pw)
                st.success("✅ Senha alterada!")

    st.markdown("---")
    back_label = "← Voltar ao Dashboard" if is_prof else "← Voltar"
    back_page  = "dashboard" if is_prof else "voice"
    if st.button(back_label, key="back_from_profile"):
        st.session_state.page = back_page
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CHAT — tela de conversa por texto
# ══════════════════════════════════════════════════════════════════════════════

def _logout() -> None:
    token = st.session_state.get("_session_token", "")
    if token:
        delete_session(token)
    js_clear_session()
    st.session_state.pop("_session_token", None)
    st.session_state.pop("_session_saved", None)
    st.session_state.update(logged_in=False, user=None, conv_id=None)

def _process_and_send_file(username, user, conv_id, raw, filename, extra_text="") -> bool:
    result = extract_file(raw, filename)
    kind, label = result["kind"], result["label"]
    if kind == "audio":
        with st.spinner("🔄 Transcrevendo áudio..."):
            text = transcribe_bytes(raw, suffix=Path(filename).suffix.lower(), language="en")
        if text.startswith("❌") or text.startswith("⚠️"):
            st.error(text); return False
        user_display = f"{extra_text}\n\n[Áudio transcrito: {text}]" if extra_text else text
        claude_msg   = f"{extra_text}\n\n[Áudio: '{filename}']\n{text}" if extra_text else f"[Áudio: '{filename}']\n{text}"
        append_message(username, conv_id, "user", user_display, audio=True)
        st.session_state.speaking = True
        try:   send_to_claude(username, user, conv_id, claude_msg)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        return True
    elif kind == "text":
        extracted = result["text"]
        if extracted.startswith("❌"):  st.error(extracted);  return False
        if not extracted:               st.warning(f"Sem texto em '{filename}'."); return False
        preview      = extracted[:200].replace('\n', ' ')
        user_display = f"📄 [{label}: '{filename}'] — {preview}{'…' if len(extracted)>200 else ''}"
        if extra_text: user_display = f"{extra_text}\n\n{user_display}"
        claude_msg   = (f"📄 [{label}: '{filename}']\n\n{extracted}\n\n"
                        "Please help me understand this content.")
        if extra_text: claude_msg = f"{extra_text}\n\n{claude_msg}"
        append_message(username, conv_id, "user", user_display)
        st.session_state.speaking = True
        try:   send_to_claude(username, user, conv_id, claude_msg)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        return True
    elif kind == "image":
        user_display = f"📸 [Imagem: '{filename}']"
        if extra_text: user_display = f"{extra_text}\n\n{user_display}"
        claude_msg   = f"📸 [Imagem: '{filename}']\nPlease look at this image and help me learn English from it."
        if extra_text: claude_msg = f"{extra_text}\n\n{claude_msg}"
        append_message(username, conv_id, "user", user_display)
        st.session_state.speaking = True
        try:
            send_to_claude(username, user, conv_id, claude_msg,
                           image_b64=result["b64"], image_media_type=result["media_type"])
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        return True
    else:
        st.warning(f"⚠️ Formato '{label}' não suportado.")
        return False


def show_chat() -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")
    conv_id  = get_or_create_conv(username)
    messages = cached_load_conversation(username, conv_id)
    speaking = st.session_state.speaking

    _ac = profile.get("accent_color", "#f0a500")
    _ub = profile.get("user_bubble_color", "#2d6a4f")
    _ab = profile.get("ai_bubble_color", "#1a1f2e")
    components.html(f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function(){{
  function hexToRgb(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);return[(n>>16)&255,(n>>8)&255,n&255].join(',');}}
  function luminance(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);var r=(n>>16)&255,g=(n>>8)&255,b=n&255;return 0.299*r+0.587*g+0.114*b;}}
  var ac="{_ac}",ub="{_ub}",ab="{_ab}";var rgb=hexToRgb(ac);
  var r=window.parent.document.documentElement;
  r.style.setProperty('--accent-full',ac);r.style.setProperty('--accent-70','rgba('+rgb+',.7)');
  r.style.setProperty('--accent-40','rgba('+rgb+',.4)');r.style.setProperty('--accent-30','rgba('+rgb+',.3)');
  r.style.setProperty('--accent-15','rgba('+rgb+',.15)');r.style.setProperty('--bubble-bg','rgba('+rgb+',.12)');
  r.style.setProperty('--bubble-border','rgba('+rgb+',.3)');r.style.setProperty('--bubble-text','#e6edf3');
  r.style.setProperty('--user-bubble-bg',ub);r.style.setProperty('--user-bubble-text',luminance(ub)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-bg',ab);r.style.setProperty('--ai-bubble-text',luminance(ab)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-border','rgba('+hexToRgb(ab)+',.6)');
  var par=window.parent;
  if(par){{par.document.querySelectorAll('audio').forEach(function(a){{a.pause();a.currentTime=0;}});
    if(par.speechSynthesis)par.speechSynthesis.cancel();}}
}})();
</script></body></html>""", height=1)

    with st.sidebar:
        st.markdown("""<style>
        section[data-testid="stSidebar"] { overflow: hidden; }
        section[data-testid="stSidebar"] > div:first-child {
            height: 100vh; display: flex; flex-direction: column; padding: 0 !important; gap: 0;
        }
        div.sidebar-footer { margin-top: auto; }
        </style>""", unsafe_allow_html=True)
        st.markdown(f"""<div style="padding:14px 14px 10px;border-bottom:1px solid #21262d;flex-shrink:0;">
            <div style="display:flex;align-items:center;gap:10px;">
                {avatar_html(40)}<div>
                <div style="font-weight:600;font-size:.88rem;">{PROF_NAME}</div>
                <div style="font-size:.68rem;color:#8b949e;">● Online</div>
                </div></div></div>""", unsafe_allow_html=True)
        if st.button(t("new_conv",ui_lang), use_container_width=True, key="btn_new"):
            st.session_state.conv_id = new_conversation(username); st.rerun()
        if st.button(t("voice_mode",ui_lang), use_container_width=True, key="btn_voice"):
            st.session_state.page = "voice"; st.rerun()
        st.markdown('<div style="font-size:.68rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px;padding:10px 4px 4px;">Conversas</div>', unsafe_allow_html=True)
        convs = list_conversations(username)
        if not convs:
            st.markdown('<div style="font-size:.78rem;color:#8b949e;padding:6px 4px;">Nenhuma conversa ainda.</div>', unsafe_allow_html=True)
        for c in convs:
            is_active = c["id"] == conv_id
            label = ("▶ " if is_active else "") + c["title"]
            col_conv, col_del = st.columns([5, 1])
            with col_conv:
                if st.button(label, key=f"conv_{c['id']}", use_container_width=True):
                    st.session_state.conv_id = c["id"]; st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{c['id']}"):
                    delete_conversation(username, c["id"])
                    if st.session_state.conv_id == c["id"]: st.session_state.conv_id = None
                    st.rerun()
        user_msgs = len([m for m in messages if m["role"] == "user"])
        uav_sidebar = user_avatar_html(username, size=34)
        st.markdown('<div class="sidebar-footer">', unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#21262d;margin:8px 0 0'>", unsafe_allow_html=True)
        st.markdown(f"""<div style="padding:8px 12px;display:flex;align-items:center;gap:10px;">
            {uav_sidebar}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:600;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user['name'].split()[0]}</div>
              <div style="color:#8b949e;font-size:.68rem;">{user['level']} · {user_msgs} msgs</div>
            </div></div>""", unsafe_allow_html=True)
        if user["role"] == "professor":
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(t("dashboard",ui_lang), use_container_width=True, key="btn_dash"):
                    st.session_state.page = "dashboard"; st.rerun()
            with col_b:
                if st.button(t("profile",ui_lang), use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            if st.button(t("logout",ui_lang), use_container_width=True, key="btn_sair"):
                _logout(); st.rerun()
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(t("profile",ui_lang), use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            with col_b:
                if st.button(t("logout",ui_lang), use_container_width=True, key="btn_sair"):
                    _logout(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""<style>
[data-testid="stChatInput"] textarea { max-height:120px!important;min-height:44px!important;font-size:.88rem!important; }
[data-testid="stChatInputContainer"] { padding:6px 10px!important; }
.main .block-container { padding-bottom:80px!important; }
.msg-row { display:flex;align-items:flex-end;gap:10px;margin:6px 0; }
.msg-row.user-row { flex-direction:row-reverse; }
.msg-row.user-row>div { display:flex;flex-direction:column;align-items:flex-end; }
.msg-row.bot-row>div  { display:flex;flex-direction:column;align-items:flex-start; }
.msg-bubble { padding:10px 15px;border-radius:18px;font-size:.88rem;line-height:1.6;
    word-break:normal;overflow-wrap:break-word;white-space:pre-wrap; }
.msg-bubble.user { max-width:clamp(200px,75%,700px);background:var(--user-bubble-bg,#2d6a4f);
    color:var(--user-bubble-text,#d8f3dc);border-bottom-right-radius:4px; }
.msg-bubble.bot  { max-width:clamp(200px,75%,700px);background:var(--ai-bubble-bg,#1a1f2e);
    color:var(--ai-bubble-text,#e6edf3);border:1px solid var(--ai-bubble-border,#252d3d);border-bottom-left-radius:4px; }
.msg-time { font-size:.6rem;color:#4a5a6a;margin:2px 4px 0;text-align:right; }
.bot-row .msg-time { text-align:left; }
.msg-ouvir-row { padding:2px 0 0 40px; }
.msg-ouvir-btn { background:none;border:1px solid #30363d;border-radius:16px;
    color:#8b949e;font-size:.68rem;padding:2px 10px;cursor:pointer;
    transition:all .15s;white-space:nowrap;font-family:inherit; }
.msg-ouvir-btn:hover,.msg-ouvir-btn.speaking { border-color:#f0a500;color:#f0a500; }
@media(max-width:768px){
    .msg-bubble{max-width:88%!important;font-size:.82rem!important;}
}
@media(max-width:480px){
    .msg-bubble{max-width:94%!important;}
}
</style>""", unsafe_allow_html=True)

    st.markdown(f"""<div class="prof-header">
        {avatar_html(56, speaking)}
        <div class="prof-info">
            <h1>{PROF_NAME}</h1>
            <p><span class="status-dot"></span>Online · {user['level']} · {user['focus']}</p>
        </div></div>""", unsafe_allow_html=True)

    _tati_mini   = get_tati_mini_b64()
    tati_av_html = (f'<div class="msg-av" style="background:url({_tati_mini}) center top/cover no-repeat;"></div>'
                    if _tati_mini else '<div class="msg-av"><div class="av-emoji">🧑‍🏫</div></div>')

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for i, msg in enumerate(messages):
        content  = msg["content"].replace("\n", "<br>")
        msg_time = msg.get("time", "")
        if msg["role"] == "assistant":
            tts_b64 = msg.get("tts_b64", "")
            is_file = msg.get("is_file", False)
            st.markdown(
                f'<div class="msg-row bot-row">{tati_av_html}'
                f'<div><div class="msg-bubble bot">{content}</div>'
                f'<div class="msg-time">{msg_time}</div></div></div>',
                unsafe_allow_html=True)
            if tts_b64:
                components.html(render_audio_player(tts_b64, msg_time, f"msg_{i}_{conv_id}"), height=44, scrolling=False)
            elif not is_file:
                clean_text = (msg["content"].replace("\\","").replace("`","")
                    .replace('"',"&quot;").replace("'","&#39;")
                    .replace("\n"," ").replace("\r","")
                    .replace("*","").replace("#",""))[:600]
                st.markdown(
                    f'<div class="msg-ouvir-row">'
                    f'<button class="msg-ouvir-btn" data-pav-tts data-text="{clean_text}">▶ Ouvir</button>'
                    f'</div>', unsafe_allow_html=True)
        else:
            is_audio = msg.get("audio", False)
            extra    = " audio-msg" if is_audio else ""
            st.markdown(
                f'<div class="msg-row user-row">'
                f'<div><div class="msg-bubble user{extra}">{content}</div>'
                f'<div class="msg-time">{msg_time}</div></div></div>',
                unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.get("speaking"):
        components.html("""<!DOCTYPE html><html><head>
<style>*{margin:0;padding:0;box-sizing:border-box;}
html,body{background:transparent;overflow:hidden;font-family:'Sora',sans-serif;}
.typing-row{display:flex;align-items:center;gap:10px;padding:6px 0 4px 0;}
.av{width:30px;height:30px;border-radius:50%;background:#1e2a3a;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}
.typing-bubble{display:flex;align-items:center;gap:8px;background:#1a1f2e;border:1px solid #252d3d;border-radius:18px;border-bottom-left-radius:4px;padding:8px 14px;}
.spin{color:#e05c2a;font-size:16px;animation:spinme 1.2s linear infinite;display:inline-block;flex-shrink:0;}
@keyframes spinme{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
.typing-text{font-size:.75rem;color:#8b949e;font-style:italic;}
</style></head><body>
<div class="typing-row">
  <div class="av">🧑‍🏫</div>
  <div class="typing-bubble"><span class="spin">✳</span><span class="typing-text">Pensando…</span></div>
</div>
</body></html>""", height=52, scrolling=False)

    staged = st.session_state.get("staged_file")
    if staged:
        staged_list = staged if isinstance(staged, list) else [staged]
        icons = {"audio":"🎵","text":"📄","image":"📸"}
        items_html = "".join(
            f'<span style="background:rgba(255,255,255,.06);border-radius:6px;padding:3px 8px;font-size:.8rem;color:#e6edf3;">'
            f'{icons.get(f["kind"],"📎")} {f["name"]}</span>'
            for f in staged_list)
        st.markdown(f"""<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.25);
     border-radius:10px;padding:10px 14px;margin:6px 0;display:flex;align-items:center;
     justify-content:space-between;gap:10px;flex-wrap:wrap;">
  <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">{items_html}
    <span style="color:#8b949e;font-size:.75rem;">· {len(staged_list)} arquivo(s)</span></div>
  <span style="font-size:.7rem;color:#f0a500;">↩ Digite uma mensagem ou envie</span>
</div>""", unsafe_allow_html=True)
        if st.button(t("remove_attachment",ui_lang), key="remove_staged"):
            st.session_state.staged_file = None
            st.session_state.staged_file_name = None
            st.session_state.pop("_last_files_key", None)
            st.rerun()

    pending_dl = st.session_state.get("_pending_download")
    if pending_dl:
        b64_data = pending_dl["b64"]
        fname    = pending_dl["filename"]
        mime     = pending_dl["mime"]
        st.markdown(f"""<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.35);
     border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;align-items:center;
     justify-content:space-between;gap:12px;">
  <span style="font-size:.85rem;color:#e6edf3;">📎 <b>{fname}</b> pronto para download</span>
  <a href="data:{mime};base64,{b64_data}" download="{fname}"
     style="background:linear-gradient(135deg,#f0a500,#e05c2a);color:#060a10;
     font-weight:700;font-size:.78rem;padding:6px 16px;border-radius:20px;
     text-decoration:none;white-space:nowrap;">⬇ Baixar arquivo</a>
</div>""", unsafe_allow_html=True)

    prompt = st.chat_input(t("type_message", ui_lang))
    if prompt:
        if not API_KEY:
            st.error("Configure ANTHROPIC_API_KEY no .env"); st.stop()
        staged = st.session_state.get("staged_file")
        if staged:
            staged_list = staged if isinstance(staged, list) else [staged]
            for i, sf in enumerate(staged_list):
                extra = prompt if i == 0 else ""
                _process_and_send_file(username, user, conv_id, sf["raw"], sf["name"], extra_text=extra)
            st.session_state.staged_file = None
            st.session_state.staged_file_name = None
            st.session_state.pop("_last_files_key", None)
        else:
            append_message(username, conv_id, "user", prompt)
            st.session_state.speaking = True
            try:   send_to_claude(username, user, conv_id, prompt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
        st.rerun()

    audio_val = st.audio_input(" ", key=f"voice_input_{st.session_state.audio_key}", label_visibility="collapsed")
    if audio_val and audio_val != st.session_state.get("_last_audio"):
        st.session_state["_last_audio"] = audio_val
        with st.spinner("Transcrevendo..."):
            txt = transcribe_bytes(audio_val.read(), ".wav", None)
        if txt and not txt.startswith("❌") and not txt.startswith("⚠️"):
            if not API_KEY: st.error("Configure ANTHROPIC_API_KEY"); st.stop()
            append_message(username, conv_id, "user", txt, audio=True)
            st.session_state.speaking = True
            try:   send_to_claude(username, user, conv_id, txt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
            st.session_state.audio_key += 1
            st.rerun()
        elif txt:
            st.error(txt)

    uploaded_list = st.file_uploader("📎", key="file_upload", label_visibility="collapsed",
        accept_multiple_files=True,
        type=["mp3","wav","ogg","m4a","webm","flac","pdf","doc","docx","txt","png","jpg","jpeg","webp"])
    if uploaded_list:
        names_key = ",".join(sorted(f.name for f in uploaded_list))
        if names_key != st.session_state.get("_last_files_key"):
            st.session_state["_last_files_key"] = names_key
            staged_list = []
            for uf in uploaded_list:
                raw    = uf.read()
                result = extract_file(raw, uf.name)
                staged_list.append({"raw":raw,"name":uf.name,"kind":result["kind"],"result":result})
            st.session_state.staged_file = staged_list
            st.session_state.staged_file_name = ", ".join(f["name"] for f in staged_list)
            st.rerun()

    components.html("""<!DOCTYPE html><html><body><script>
(function(){
  var par=window.parent?window.parent.document:document;
  var cur=null;
  function initBtns(){
    par.querySelectorAll('[data-pav-tts]').forEach(function(btn){
      if(btn._pavInit)return;btn._pavInit=true;
      btn.addEventListener('click',function(){
        if(cur&&cur!==btn){speechSynthesis.cancel();cur.textContent='▶ Ouvir';cur.classList.remove('speaking');cur=null;}
        if(btn.classList.contains('speaking')){speechSynthesis.cancel();btn.textContent='▶ Ouvir';btn.classList.remove('speaking');cur=null;return;}
        var txt=btn.getAttribute('data-text')||'';
        var u=new SpeechSynthesisUtterance(txt);u.lang='en-US';u.rate=0.95;u.pitch=1.05;
        speechSynthesis.getVoices();
        setTimeout(function(){
          var vv=speechSynthesis.getVoices();
          var pick=vv.find(function(v){return v.lang==='en-US';})||vv.find(function(v){return v.lang.startsWith('en');});
          if(pick)u.voice=pick;
          u.onstart=function(){btn.textContent='⏹ Parar';btn.classList.add('speaking');cur=btn;};
          u.onend=u.onerror=function(){btn.textContent='▶ Ouvir';btn.classList.remove('speaking');cur=null;};
          speechSynthesis.cancel();speechSynthesis.speak(u);
        },80);
      });
    });
  }
  initBtns();
  var obs=new MutationObserver(initBtns);
  obs.observe(par.body,{childList:true,subtree:true});
})();
</script></body></html>""", height=1)

    _btn_html = Path("static/pav_buttons.html")
    _btn_css  = Path("static/pav_buttons.css")
    if _btn_css.exists():
        st.markdown(f"<style>{_btn_css.read_text()}</style>", unsafe_allow_html=True)
    if _btn_html.exists():
        components.html(_btn_html.read_text(), height=1)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD DA PROFESSORA
# ══════════════════════════════════════════════════════════════════════════════

def show_dashboard() -> None:
    user    = st.session_state.user
    profile = user.get("profile", {})
    ui_lang = profile.get("language", "pt-BR")

    with st.sidebar:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div>
            <div style="font-weight:600;font-size:.9rem;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#8b949e;">● Professora</div>
            </div></div>
            <hr style="border-color:#30363d;margin:6px 0 12px">""", unsafe_allow_html=True)
        if st.button("📊 Dashboard", use_container_width=True, type="primary"): pass
        if st.button(t("voice_mode",ui_lang), use_container_width=True, key="dash_voice"):
            st.session_state.page = "voice"; st.rerun()
        if st.button(t("use_as_student",ui_lang), use_container_width=True, key="dash_chat"):
            st.session_state.page = "chat"; st.rerun()
        if st.button(t("my_profile",ui_lang), use_container_width=True, key="dash_profile"):
            st.session_state.page = "profile"; st.rerun()
        if st.button(t("logout",ui_lang), use_container_width=True, key="dash_logout"):
            _logout(); st.rerun()

    st.markdown("## 📊 Painel do Professor")
    st.markdown("---")
    _, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button(t("voice_mode",ui_lang), use_container_width=True, key="dash_voice2"):
            st.session_state.page = "voice"; st.rerun()
    st.markdown("---")
    stats = get_all_students_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in zip(
        [c1,c2,c3,c4],
        [len(stats), sum(s["messages"] for s in stats),
         sum(s["corrections"] for s in stats),
         sum(1 for s in stats if s["last_active"][:10]==today)],
        ["Alunos","Mensagens","Correções","Ativos Hoje"],
    ):
        col.markdown(
            f'<div class="stat-card"><div class="val">{val}</div><div class="lbl">{lbl}</div></div>',
            unsafe_allow_html=True)
    st.markdown("<br>")
    st.markdown("### 👥 Alunos")
    if not stats:
        st.info("Nenhum aluno ainda.")
    else:
        badge = {"Beginner":"badge-blue","Pre-Intermediate":"badge-green",
                 "Intermediate":"badge-gold","Business English":"badge-gold"}
        rows = "".join(f"""<tr>
            <td><b>{s['name']}</b><br><span style="color:#8b949e;font-size:.75rem">@{s['username']}</span></td>
            <td><span class="badge {badge.get(s['level'],'badge-blue')}">{s['level']}</span></td>
            <td>{s['focus']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['messages']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['corrections']}</td>
            <td style="color:#8b949e">{s['last_active']}</td>
        </tr>""" for s in sorted(stats, key=lambda x: x["messages"], reverse=True))
        st.markdown(
            f'<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden">'
            f'<table class="dash-table"><thead>'
            f'<tr><th>Aluno</th><th>Nível</th><th>Foco</th><th>Msgs</th><th>Correções</th><th>Último Acesso</th></tr>'
            f'</thead><tbody>{rows}</tbody></table></div>',
            unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ROTEADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

if not st.session_state.logged_in:
    show_login()
else:
    # Salva token apenas uma vez por sessão
    _tok = st.session_state.get("_session_token", "")
    if _tok and not st.session_state.get("_session_saved"):
        js_save_session(_tok)
        st.session_state["_session_saved"] = True

    _page = st.session_state.page

    if _page == "profile":
        show_profile()
    elif _page == "dashboard":
        show_dashboard()
    elif _page == "chat":
        show_chat()
    else:
        # "voice" é o padrão — modo voz imersivo
        show_voice()