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
    save_user_avatar_db, get_user_avatar_db, remove_user_avatar_db # sessões persistentes
)
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from file_reader import extract_file

# ── Wav2Lip (avatar realista — opcional, requer Colab rodando) ────────────────
try:
    from wav2lip_avatar import generate_talking_video, wav2lip_available
    _WAV2LIP_LOADED = True
except ImportError:
    _WAV2LIP_LOADED = False
    def wav2lip_available(): return False
    def generate_talking_video(_): return None

# ── Font Awesome (ícones de anexo, etc.) ─────────────────────────────────────
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">',
    unsafe_allow_html=True
)

# login lendo o cookie

def _try_autologin_from_cookie() -> bool:
    """
    Tenta fazer login automático lendo o cookie pav_session do header HTTP.
    Retorna True se o login foi restaurado com sucesso.

    Requer Streamlit >= 1.31 (st.context.headers).
    Funciona em todos os browsers, inclusive Safari e iOS.
    """
    if st.session_state.logged_in:
        return True  # já logado

    # Tenta ler os headers HTTP da requisição atual
    try:
        headers = st.context.headers
        cookie_header = headers.get("Cookie", "") or headers.get("cookie", "")
    except AttributeError:
        # Streamlit < 1.31 — st.context não existe, usa fallback JS
        return False

    if not cookie_header:
        return False

    # Extrai pav_session do header Cookie
    token = None
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("pav_session="):
            import urllib.parse
            token = urllib.parse.unquote(part.split("=", 1)[1].strip())
            break

    if not token or len(token) < 10:
        return False

    # Valida o token no banco
    udata = validate_session(token)
    if not udata:
        return False

    # Resolve o username
    uname = udata.get("_resolved_username")
    if not uname:
        students = load_students()
        uname = next(
            (k for k, v in students.items() if v.get("password") == udata.get("password")),
            None
        )
    if not uname:
        return False

    # Restaura a sessão
    st.session_state.logged_in         = True
    st.session_state.user              = {"username": uname, **udata}
    st.session_state.page              = "dashboard" if udata.get("role") == "professor" else "chat"
    st.session_state.conv_id           = None
    st.session_state["_session_token"] = token
    return True

# ── Inicialização do banco de dados (SQLite) ──────────────────────────────────
init_db()

# ── Variáveis de ambiente ─────────────────────────────────────────────────────
API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
PHOTO_PATH = os.getenv("PROFESSOR_PHOTO", "assets/professor.jpg")
PROF_NAME  = os.getenv("PROFESSOR_NAME",  "Professor Avatar")

# ── Contador de áudio — força re-render do widget nativo ─────────────────────
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
    },
}

def t(key: str, lang: str = "pt-BR") -> str:
    """Retorna string traduzida. Fallback: pt-BR."""
    return _STRINGS.get(lang, _STRINGS["pt-BR"]).get(key, _STRINGS["pt-BR"].get(key, key))


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE IMAGEM / AVATAR
# ══════════════════════════════════════════════════════════════════════════════

def get_photo_b64() -> str | None:
    """Lê a foto da professora e devolve como data-URI base64."""
    p = Path(PHOTO_PATH)
    if p.exists():
        ext  = p.suffix.lower().replace(".", "")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None

PHOTO_B64 = get_photo_b64()

# ── Cache da foto mini da Tati (evita re-leitura de disco a cada render) ──────
@st.cache_data(show_spinner=False)
def get_tati_mini_b64() -> str:
    """Lê a foto da Tati uma única vez e reutiliza em todo o app."""
    for _p in [Path("assets/tati.png"), Path("assets/tati.jpg"),
               Path(__file__).parent / "assets" / "tati.png",
               Path(__file__).parent / "assets" / "tati.jpg"]:
        if _p.exists():
            _ext  = _p.suffix.lstrip(".").lower()
            _mime = "jpeg" if _ext in ("jpg", "jpeg") else _ext
            return f"data:image/{_mime};base64,{base64.b64encode(_p.read_bytes()).decode()}"
    return get_photo_b64() or ""

# ── Cache dos 4 frames do avatar animado do modo voz ─────────────────────────
@st.cache_data(show_spinner=False)
def get_avatar_frames() -> dict:
    """Carrega os frames do avatar animado uma única vez."""
    _base = Path(__file__).parent
    def _load(candidates):
        for p in candidates:
            p = Path(p)
            if p.exists():
                return f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"
        return ""
    return {
        "base":   _load([_base/"assets"/"avatar_tati_normal.png",      "assets/avatar_tati_normal.png"]),
        "closed": _load([_base/"assets"/"avatar_tati_closed.png",      "assets/avatar_tati_closed.png"]),
        "mid":    _load([_base/"assets"/"avatar_tati_meio.png",        "assets/avatar_tati_meio.png"]),
        "open":   _load([_base/"assets"/"avatar_tati_bem_aberta.png",  "assets/avatar_tati_bem_aberta.png",
                         _base/"assets"/"avatar_tati_aberta.png",      "assets/avatar_tati_aberta.png"]),
    }

# ── Avatares individuais dos alunos ───────────────────────────────────────────
def get_user_avatar_b64(username: str, _bust: int = 0) -> str | None:
    """Busca foto do usuário direto do banco, sem cache."""
    result = get_user_avatar_db(username)
    if not result:
        return None
    raw, mime = result
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

# alias usado internamente
_get_avatar = lambda u: get_user_avatar_b64(u, _bust=st.session_state.get("_avatar_v", 0))

def _avatar_circle_html(b64: str | None, size: int, border: str = "#f0a500") -> str:
    """Retorna HTML de avatar circular — foto, sem_foto.png ou ícone FA."""
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
    """Salva a foto de perfil no Supabase Storage."""
    suffix = suffix.lower().lstrip(".")
    mime   = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    save_user_avatar_db(username, raw, mime)
    _bump_avatar_version()

def remove_user_avatar(username: str) -> None:
    """Remove a foto de perfil do Supabase Storage."""
    remove_user_avatar_db(username)
    _bump_avatar_version()

def _bump_avatar_version() -> None:
    """Incrementa o contador de versão do avatar para forçar re-fetch."""
    st.session_state["_avatar_v"] = st.session_state.get("_avatar_v", 0) + 1

def user_avatar_html(username: str, size: int = 36, **_) -> str:
    """Retorna HTML de avatar circular do usuário."""
    return _avatar_circle_html(get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v", 0)), size)

def avatar_html(size: int = 52, speaking: bool = False) -> str:
    """Avatar da professora com anel de 'speaking' animado."""
    cls   = "speaking" if speaking else ""
    photo = PHOTO_B64  # usa cache — evita re-leitura e flash
    if photo:
        return (
            f'<div class="avatar-wrap {cls}" style="width:{size}px;height:{size}px;'
            f'overflow:hidden;border-radius:50%;">'
            f'<img src="{photo}" class="avatar-img" style="width:100%;height:100%;'
            f'object-fit:cover;object-position:top;display:block;"/>'
            f'<div class="avatar-ring"></div></div>'
        )
    return (
        f'<div class="avatar-circle {cls}" '
        f'style="width:{size}px;height:{size}px;font-size:{int(size*.48)}px">🧑‍🏫</div>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title=f"{PROF_NAME} · English", page_icon="🎓", layout="wide")

def load_css(path: str) -> None:
    p = Path(path)
    if p.exists():
        css = p.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

load_css("styles/style.css")

# ── CSS responsivo global ──────────────────────────────────────────────────────
st.markdown("""<style>
section[data-testid="stMain"] > div {
    transition: all .25s ease;
    max-width: 100% !important;
}
/* Evita flash de imagem desestilizada */
img { max-width: 100%; }
.avatar-wrap img, .avatar-ring img { display: block; }
/* Esconde conteúdo do st.markdown durante re-render */
[data-testid="stMarkdownContainer"] img {
    opacity: 1;
    transition: opacity .15s;
}
.main .block-container {
    max-width: 100% !important;
    padding-left: clamp(10px, 2vw, 40px) !important;
    padding-right: clamp(10px, 2vw, 40px) !important;
    padding-top: 1rem !important;
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
/* Esconde file uploader nativo imediatamente — o JS depois move o clipe */
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
@media (max-width: 1024px) {
    .main .block-container { padding-left: 12px !important; padding-right: 12px !important; }
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
</style>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT DO SISTEMA
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, very intelligent and encouraging. You help adults speak English with more confidence, over 25 years of experience, Advanced English Hunter College NY, and passionate about teaching.
Students: teenagers (Beginner/Pre-Intermediate) and adults focused on Business/News.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BILINGUAL POLICY (VERY IMPORTANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The student's messages may arrive in English, Portuguese, or a mix.
Adapt your language policy according to the student's level:

BEGINNER / PRE-INTERMEDIATE:
  • Student writes/speaks in Portuguese → Fully acceptable. Respond in simple English
    AND provide the Portuguese translation of key words in parentheses.
    Example: "Great question! The word is 'homework' (tarefa)."
  • Student mixes PT and EN → Celebrate the English parts, gently supply the missing
    English for the Portuguese parts. Never make them feel bad for using Portuguese.
  • Always end your reply with an easy, encouraging question in English.
  • Provide Portuguese support freely when they seem lost or frustrated.

INTERMEDIATE:
  • Respond primarily in English. Use Portuguese ONLY to clarify a specific word
    or resolve a genuine comprehension block — keep it brief.
  • If the student writes in Portuguese, acknowledge briefly in English and invite
    them to try saying the same thing in English:
    "I understood! Now, how would you say that in English? 😊"
  • Encourage them to push further; celebrate every English sentence they produce.

ADVANCED / BUSINESS ENGLISH:
  • Respond exclusively in English.
  • If the student writes in Portuguese, reply in English and say something like:
    "Let's keep it in English — you've got this! 💪"
  • You may add a brief Portuguese gloss ONLY for highly technical or idiomatic
    terms where the meaning is genuinely ambiguous.

TRANSLATION REQUESTS (any level):
  • When the student asks "como se diz X?", "what does Y mean?", or similar,
    always provide the translation + an example sentence in English.
  • For Beginners/Pre-Intermediate: also include the Portuguese example.

TEACHING STYLE:
- Neuro-learning: guide students to discover errors. Never just give the answer.
  Example: "he go" → "What ending do we add for he/she/it?"
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT conversational responses. Bold grammar points when appropriate.
- End responses with ONE engaging question.
- Use emojis and formatting (bold, etc.) ONLY if the student uses them or explicitly asks.
  Otherwise respond in plain, natural text.

RULES:
- Simple English. Teens→Fortnite/Netflix/TikTok/Movies and series refs. Adults→LinkedIn/news/geopolitics.
- Portuguese → briefly acknowledge, when asked to speak Portuguese, speak, but switch to English.
- NEVER start a conversation uninvited. Wait for the student to speak first.

ACTIVITY GENERATION:
- When asked to create exercises, worksheets or activities, generate complete, well-structured content.
- Support: fill-in-the-blank, multiple choice, reading comprehension, dialogue writing,
  grammar drills, vocabulary lists, translation, error correction, etc.
- When the student asks for a FILE (PDF, Word/DOCX), respond ONLY with a special JSON block
  on its own line, no other text, in this exact format:
  <<<GENERATE_FILE>>>
  {{"format":"pdf","filename":"activity.pdf","title":"Exercise Title","content":"Full content here with \\n for line breaks"}}
  <<<END_FILE>>>
  Use "pdf" or "docx" as format. Put ALL the exercise content inside "content".
  The system will intercept this and generate the real file for download."""


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE — valores padrão na primeira execução
# ══════════════════════════════════════════════════════════════════════════════

_defaults = {
    "logged_in":        False,
    "user":             None,
    "page":             "chat",
    "speaking":         False,
    "conv_id":          None,
    "voice_mode":       False,
    "staged_file":      None,   # arquivo anexado aguardando envio
    "staged_file_name": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

_session_token = st.session_state.get("_session_token", "")
if _session_token and st.session_state.logged_in:
    # Mantém o token na URL para que o reload funcione
    if st.query_params.get("s") != _session_token:
        st.query_params["s"] = _session_token

if not st.session_state.logged_in:
    _s = st.query_params.get("s", "")
    if _s and len(_s) > 10:
        _udata = validate_session(_s)
        if _udata:
            _uname = _udata.get("_resolved_username") or next(
                (k for k, v in load_students().items() if v["password"] == _udata["password"]),
                None
            )
            if _uname:
                st.session_state.logged_in         = True
                st.session_state.user              = {"username": _uname, **_udata}
                st.session_state.page              = "dashboard" if _udata["role"] == "professor" else "chat"
                st.session_state.conv_id           = None
                st.session_state["_session_token"] = _s
        else:
            # Token inválido — limpa
            st.query_params.pop("s", None)

# ══════════════════════════════════════════════════════════════════════════════
# SESSÃO PERSISTENTE — funções de salvar/limpar no localStorage
# ══════════════════════════════════════════════════════════════════════════════

def js_save_session(token: str) -> None:
    """Salva token no localStorage E cookie (30 dias) para persistência total."""
    components.html(
        f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
        (function() {{
            var t = '{token}';
            try {{ window.parent.localStorage.setItem('pav_session', t); }} catch(e) {{}}
            try {{ localStorage.setItem('pav_session', t); }} catch(e) {{}}
            try {{
                var exp = new Date(Date.now()+2592000000).toUTCString();
                window.parent.document.cookie = 'pav_session='+encodeURIComponent(t)+';expires='+exp+';path=/;SameSite=Lax';
            }} catch(e) {{}}
            try {{
                var exp2 = new Date(Date.now()+2592000000).toUTCString();
                document.cookie = 'pav_session='+encodeURIComponent(t)+';expires='+exp2+';path=/;SameSite=Lax';
            }} catch(e) {{}}
        }})();
        </script></body></html>""",
        height=1,
    )

def js_clear_session() -> None:
    components.html(
        """<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
        (function() {
            try { window.parent.localStorage.removeItem('pav_session'); } catch(e) {}
            try { localStorage.removeItem('pav_session'); } catch(e) {}
            try { window.parent.document.cookie='pav_session=;expires=Thu,01 Jan 1970 00:00:00 GMT;path=/'; } catch(e) {}
            try { document.cookie='pav_session=;expires=Thu,01 Jan 1970 00:00:00 GMT;path=/'; } catch(e) {}
        })();
        </script></body></html>""",
        height=1,
    )

# Auto-login via token movido para dentro do show_login()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE CONVERSA / CLAUDE
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_conv(username: str) -> str:
    """Retorna o conv_id ativo ou cria uma nova conversa."""
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id


@st.cache_data(ttl=10, show_spinner=False)
def cached_load_conversation(username: str, conv_id: str) -> list:
    """Cache de 10s do histórico — evita re-leitura do banco a cada render."""
    return load_conversation(username, conv_id)


def send_to_claude(username: str, user: dict, conv_id: str,
                   text: str, image_b64: str = None, image_media_type: str = None) -> str:
    """
    Envia a mensagem ao Claude Haiku, obtém a resposta,
    gera TTS opcional e salva no banco.
    Retorna o texto da resposta.
    """
    client  = anthropic.Anthropic(api_key=API_KEY)
    #context = f"\n\nStudent: Name={user['name']}, Level={user['level']}, Focus={user['focus']}."
    context = (
       f"\n\nStudent profile — Name: {user['name']} | "
       f"Level: {user['level']} | Focus: {user['focus']} | "
       f"Native language: Brazilian Portuguese.\n"
       f"Apply the bilingual policy for level '{user['level']}' as instructed."
   )


    # Monta histórico da conversa para a API
    msgs     = cached_load_conversation(username, conv_id)
    api_msgs = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in msgs
    ]

    # Adiciona imagem à última mensagem do usuário, se houver
    if image_b64 and image_media_type and api_msgs and api_msgs[-1]["role"] == "user":
        api_msgs[-1]["content"] = [
            {"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": image_b64}},
            {"type": "text",  "text": text}
        ]

    # Mais tokens para pedidos de atividade/arquivo
    is_activity = any(w in text.lower() for w in [
        "pdf", "word", "docx", "atividade", "exercício", "exercicio",
        "worksheet", "activity", "exercise", "generate", "criar arquivo", "crie um", "make a"
    ])
    max_tok = 2000 if is_activity else 400

    resp       = client.messages.create(
        model="claude-haiku-4-5", max_tokens=max_tok,
        system=SYSTEM_PROMPT + context, messages=api_msgs
    )
    reply_text = resp.content[0].text

    # Verifica se a IA quer gerar um arquivo (PDF/DOCX)
    if "<<<GENERATE_FILE>>>" in reply_text:
        return _intercept_file_generation(reply_text, username, conv_id)

    # Gera áudio TTS e armazena no banco junto com a mensagem
    tts_b64_str = None
    if tts_available():
        audio_bytes = text_to_speech(reply_text)
        if audio_bytes:
            tts_b64_str = base64.b64encode(audio_bytes).decode()
            st.session_state["_tts_audio"] = tts_b64_str

    append_message(username, conv_id, "assistant", reply_text, tts_b64=tts_b64_str)
    cached_load_conversation.clear()  # invalida cache para próximo render
    return reply_text


def _intercept_file_generation(reply_text: str, username: str, conv_id: str) -> str:
    """
    Intercepta o bloco <<<GENERATE_FILE>>> na resposta da IA
    e cria o arquivo PDF ou DOCX real para download.
    """
    import re

    try:
        match = re.search(
            r'<<<GENERATE_FILE>>>\s*(\{.*?\})\s*<<<END_FILE>>>',
            reply_text, re.DOTALL
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

        # Armazena para exibir o botão de download no chat
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
    """Gera PDF profissional com ReportLab."""
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

    t_style = ParagraphStyle("t", parent=styles["Title"],   fontSize=18, spaceAfter=6,
                              textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER)
    s_style = ParagraphStyle("s", parent=styles["Normal"],  fontSize=9,  spaceAfter=14,
                              textColor=colors.HexColor("#888888"),  alignment=TA_CENTER)
    b_style = ParagraphStyle("b", parent=styles["Normal"],  fontSize=11, leading=18, spaceAfter=8)

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
    """Gera DOCX profissional com python-docx."""
    from docx           import Document
    from docx.shared    import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    for sec in doc.sections:
        sec.top_margin    = Cm(2.5); sec.bottom_margin = Cm(2.5)
        sec.left_margin   = Cm(2.5); sec.right_margin  = Cm(2.5)

    h = doc.add_heading(title, 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)

    sub = doc.add_paragraph(f"Teacher {PROF_NAME}")
    sub.alignment       = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size      = Pt(9)
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
# PLAYER DE ÁUDIO TTS — mini player inline nos balões da IA
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

  // Desbloqueia AudioContext no iOS/Android
  function unlockAudio(){{
    try{{
      var AC=window.AudioContext||window.webkitAudioContext;
      if(!AC)return;
      var ctx=new AC();
      var buf=ctx.createBuffer(1,1,22050);
      var src=ctx.createBufferSource();
      src.buffer=buf; src.connect(ctx.destination); src.start(0);
      if(ctx.state==='suspended')ctx.resume();
    }}catch(e){{}}
    // Também notifica o parent
    try{{
      if(window.parent&&window.parent.pavUnlockAudio)window.parent.pavUnlockAudio();
    }}catch(e){{}}
  }}

  b.onclick=function(){{
    unlockAudio();
    if(!audio.paused){{
      audio.pause(); b.textContent='▶ Ouvir';
    }}else{{
      var p=audio.play();
      if(p!==undefined){{
        p.then(function(){{b.textContent='⏸ Pausar';}})
         .catch(function(err){{
           console.warn('play() bloqueado:', err);
           b.textContent='▶ Ouvir';
           setTimeout(function(){{
             audio.play()
               .then(function(){{b.textContent='⏸ Pausar';}})
               .catch(function(){{}});
           }},300);
         }});
      }}
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
      this.classList.add('on');
      audio.playbackRate=parseFloat(this.dataset.r);
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
# TELA DE LOGIN / REGISTRO
# ══════════════════════════════════════════════════════════════════════════════

def show_login() -> None:
    """Renderiza a tela de login com aba de registro. Cria sessão ao autenticar."""

    # ── Auto-login via token salvo (cookie/localStorage) ──────────────────────
    # height=0 — sem espaço visível, sem duplicação de campos no submit
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
    (function() {
        function readToken() {
            try {
                var v = window.parent.localStorage.getItem('pav_session');
                if (v && v.length > 10) return v;
            } catch(e) {}
            try {
                var v2 = localStorage.getItem('pav_session');
                if (v2 && v2.length > 10) return v2;
            } catch(e) {}
            try {
                var match = window.parent.document.cookie.split(';')
                    .map(function(c) { return c.trim(); })
                    .find(function(c) { return c.startsWith('pav_session='); });
                if (match) {
                    var val = decodeURIComponent(match.split('=')[1]);
                    if (val && val.length > 10) return val;
                }
            } catch(e) {}
            try {
                var match2 = document.cookie.split(';')
                    .map(function(c) { return c.trim(); })
                    .find(function(c) { return c.startsWith('pav_session='); });
                if (match2) {
                    var val2 = decodeURIComponent(match2.split('=')[1]);
                    if (val2 && val2.length > 10) return val2;
                }
            } catch(e) {}
            return '';
        }
        var val = readToken();
        if (!val) return;
        var url      = new URL(window.parent.location.href);
        var isToken  = val.length > 20;
        var paramKey = isToken ? '_token' : '_u';
        if (url.searchParams.get(paramKey) !== val) {
            url.searchParams.set(paramKey, val);
            window.parent.location.replace(url.toString());
        }
    })();
    </script></body></html>""", height=1)

    params = st.query_params
    if "_token" in params:
        token = params["_token"]
        udata = validate_session(token)
        if udata:
            uname = udata.get("_resolved_username") or next(
                (k for k, v in load_students().items() if v["password"] == udata["password"]),
                None
            )
            if uname:
                st.session_state.logged_in         = True
                st.session_state.user              = {"username": uname, **udata}
                st.session_state.page              = "dashboard" if udata["role"] == "professor" else "chat"
                st.session_state.conv_id           = None
                st.session_state["_session_token"] = token
                st.query_params.clear()
                st.rerun()
        else:
            js_clear_session()
            st.query_params.clear()
    elif "_u" in params:
        uname    = params["_u"]
        students = load_students()
        if uname in students:
            udata = students[uname]
            token = create_session(uname)
            st.session_state.logged_in         = True
            st.session_state.user              = {"username": uname, **udata}
            st.session_state.page              = "dashboard" if udata["role"] == "professor" else "chat"
            st.session_state.conv_id           = None
            st.session_state["_session_token"] = token
            js_save_session(token)
            st.query_params.clear()
            st.rerun()

    if "_login_tab" not in st.session_state:
        st.session_state["_login_tab"] = "login"

    # ── CSS exclusivo da página de login ──────────────────────────────────────
    st.markdown("""<style>
[data-testid="stSidebar"]    { display:none!important; }
[data-testid="stHeader"]     { display:none!important; }
[data-testid="stToolbar"]    { display:none!important; }
[data-testid="stDecoration"] { display:none!important; }
footer                       { display:none!important; }
.stApp                       { background:#060a10!important; }
.block-container             { padding-top:0!important; max-width:100%!important; }
section.main > div           { padding:0!important; }
.stTextInput label {
  font-size:.7rem!important; color:#4a5a6a!important;
  font-weight:700!important; text-transform:uppercase!important;
  letter-spacing:1px!important;
}
.stTextInput input {
  background:rgba(255,255,255,.04)!important;
  border:1px solid #1e2a3a!important; border-radius:10px!important;
  color:#e6edf3!important; font-size:.88rem!important;
  transition:border-color .2s,box-shadow .2s!important;
}
.stTextInput input:focus {
  border-color:#f0a500!important;
  box-shadow:0 0 0 3px rgba(240,165,0,.12)!important;
}
.stForm [data-testid="stFormSubmitButton"] button {
  background:linear-gradient(135deg,#f0a500,#e05c2a)!important;
  border:none!important; border-radius:12px!important;
  color:#060a10!important; font-weight:800!important;
  font-size:.9rem!important; padding:14px!important;
  width:100%!important; letter-spacing:.5px!important;
  box-shadow:0 4px 24px rgba(240,165,0,.3)!important;
  transition:all .25s!important; margin-top:8px!important;
}
.stForm [data-testid="stFormSubmitButton"] button:hover {
  transform:translateY(-2px)!important;
  box-shadow:0 8px 32px rgba(240,165,0,.45)!important;
}
div[data-testid="stButton"] button {
  border-radius:10px!important; font-size:.82rem!important;
  font-weight:600!important; transition:all .2s!important;
}
[data-testid="InputInstructions"] { display:none!important; }
small[data-testid="InputInstructions"] { display:none!important; }
</style>""", unsafe_allow_html=True)

    # ── Header visual animado ─────────────────────────────────────────────────
    avatar_src = PHOTO_B64 if PHOTO_B64 else ""
    components.html(f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;700;800&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:#060a10;font-family:'Sora',sans-serif;overflow:hidden;}}
.bg{{position:fixed;inset:0;background:#060a10;overflow:hidden;}}
.orb1{{position:absolute;width:560px;height:560px;border-radius:50%;
       background:radial-gradient(circle,rgba(240,165,0,.12),transparent 70%);
       top:-160px;right:-120px;animation:d1 14s ease-in-out infinite alternate;}}
.orb2{{position:absolute;width:420px;height:420px;border-radius:50%;
       background:radial-gradient(circle,rgba(224,92,42,.09),transparent 70%);
       bottom:-110px;left:-90px;animation:d2 14s ease-in-out infinite alternate;}}
.grid{{position:absolute;inset:0;
       background-image:linear-gradient(rgba(240,165,0,.03) 1px,transparent 1px),
                        linear-gradient(90deg,rgba(240,165,0,.03) 1px,transparent 1px);
       background-size:48px 48px;}}
@keyframes d1{{from{{transform:translate(0,0) scale(1);}}to{{transform:translate(24px,16px) scale(1.06);}}}}
@keyframes d2{{from{{transform:translate(0,0) scale(1);}}to{{transform:translate(-18px,14px) scale(1.04);}}}}
.card{{position:relative;z-index:1;background:linear-gradient(180deg,#0f1824,#0a1020);
       border:1px solid #1a2535;border-radius:24px;
       padding:36px 32px 28px;width:100%;max-width:440px;margin:0 auto;
       box-shadow:0 32px 80px rgba(0,0,0,.65),0 0 0 1px rgba(255,255,255,.03);}}
.wrap{{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;}}
.avatar-img{{width:88px;height:88px;border-radius:50%;
             object-fit:cover;object-position:top;
             border:2.5px solid #f0a500;display:block;margin:0 auto 18px;
             box-shadow:0 0 0 6px rgba(240,165,0,.1),0 0 36px rgba(240,165,0,.22);}}
.avatar-emoji{{width:88px;height:88px;border-radius:50%;
               background:linear-gradient(135deg,#f0a500,#e05c2a);
               display:flex;align-items:center;justify-content:center;
               font-size:40px;margin:0 auto 18px;
               box-shadow:0 0 0 6px rgba(240,165,0,.1),0 0 36px rgba(240,165,0,.22);}}
h2{{font-size:1.55rem;font-weight:800;text-align:center;margin:0 0 5px;
    background:linear-gradient(135deg,#f0a500 30%,#e05c2a 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
p{{font-size:.76rem;color:#3a4e5e;text-align:center;margin:0;letter-spacing:.3px;}}
.line{{width:44px;height:2px;background:linear-gradient(90deg,#f0a500,#e05c2a);
       border-radius:2px;margin:12px auto 0;opacity:.55;}}
</style></head><body>
<div class="bg"><div class="orb1"></div><div class="orb2"></div><div class="grid"></div></div>
<div class="wrap">
  <div class="card">
    {"<img class='avatar-img' src='" + avatar_src + "'/>" if avatar_src else "<div class='avatar-emoji'>🧑‍🏫</div>"}
    <h2>{PROF_NAME}</h2>
    <p>Your personal English practice companion</p>
    <div class="line"></div>
  </div>
</div>
</body></html>""", height=320, scrolling=False)

    # ── Formulários centralizados ─────────────────────────────────────────────
    _, col, _ = st.columns([1, 2.2, 1])
    with col:
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("enter"), use_container_width=True, key="tab_btn_login",
                         type="primary" if st.session_state["_login_tab"] == "login" else "secondary"):
                st.session_state["_login_tab"] = "login"; st.rerun()
        with c2:
            if st.button(t("create_account"), use_container_width=True, key="tab_btn_reg",
                         type="primary" if st.session_state["_login_tab"] == "reg" else "secondary"):
                st.session_state["_login_tab"] = "reg"; st.rerun()

        st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

        # ── Feedback de operações anteriores ──────────────────────────────────
        login_err = st.session_state.pop("_login_err", "")
        reg_err   = st.session_state.pop("_reg_err",   "")
        reg_ok    = st.session_state.pop("_reg_ok",    False)
        reg_name  = st.session_state.pop("_reg_name",  "")
        if login_err: st.error(f"❌ {login_err}")
        if reg_err:   st.error(f"❌ {reg_err}")
        if reg_ok:    st.success(f"✅ Conta criada! Bem-vindo(a), {reg_name}! Faça login.")

        # ── Aba LOGIN ─────────────────────────────────────────────────────────
        if st.session_state["_login_tab"] == "login":
            with st.form("form_login", clear_on_submit=True):
                u = st.text_input(t("username"), placeholder="seu.usuario", key="li_u")
                p = st.text_input(t("password"), type="password", placeholder="••••••••", key="li_p")
                submitted = st.form_submit_button("Entrar →", use_container_width=True)
                if submitted:
                    if not u or not p:
                        st.session_state["_login_err"] = "Preencha todos os campos."
                        st.rerun()
                    else:
                        user = authenticate(u, p)
                        if user:
                            real_u = user.get("_resolved_username", u.lower())
                            st.session_state.update(
                                logged_in=True,
                                user={"username": real_u, **user},
                                page="dashboard" if user["role"] == "professor" else "chat",
                                conv_id=None
                            )
                            token = create_session(real_u)
                            st.session_state["_session_token"] = token
                            js_save_session(token)
                            st.rerun()
                        else:
                            st.session_state["_login_err"] = "Usuário ou senha incorretos."
                            st.rerun()

        # ── Aba REGISTRO ──────────────────────────────────────────────────────
        else:
            with st.form("form_reg", clear_on_submit=False):
                rn = st.text_input(t("full_name"), placeholder="João Silva",     key="r_n")
                re = st.text_input(t("email"),        placeholder="joao@email.com", key="r_e")
                ru = st.text_input(t("username"),       placeholder="joao.silva",    key="r_u")
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
                            st.session_state["_reg_ok"]   = True
                            st.session_state["_reg_name"]  = rn
                            st.session_state["_login_tab"] = "login"
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

        st.markdown(
            f'<p style="text-align:center;font-size:.65rem;color:#1a2535;margin-top:16px;">'
            f'© 2025 · {PROF_NAME} · AI English Coach</p>',
            unsafe_allow_html=True
        )


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL DO USUÁRIO
# ══════════════════════════════════════════════════════════════════════════════

def show_profile() -> None:
    """Página de configurações: aparência, personalização e dados da conta."""
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")

    # Garante que o file uploader de foto seja visível nesta página
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
    st.markdown(f"""<script>
(function(){{
  function hexToRgb(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];var n=parseInt(h,16);return[(n>>16)&255,(n>>8)&255,n&255].join(',');}}
  var ac="{_ac}",rgb=hexToRgb(ac),r=document.documentElement;
  r.style.setProperty('--accent-full',ac);
  r.style.setProperty('--bubble-bg','rgba('+rgb+',.12)');
  r.style.setProperty('--bubble-border','rgba('+rgb+',.3)');
}})();
</script>""", unsafe_allow_html=True)

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

    # ── Aba Geral ─────────────────────────────────────────────────────────────
    with tab_geral:
        st.markdown("### Aparência")
        col1, col2 = st.columns(2)
        with col1:
            lang  = st.selectbox(t("interface_lang", ui_lang), ["pt-BR", "en-US", "en-UK"],
                index=safe_index(["pt-BR", "en-US", "en-UK"], profile.get("language", "pt-BR")), key="pf_lang")
        with col2:
            accent = st.color_picker("Cor de destaque",
                value=profile.get("accent_color", "#f0a500"), key="pf_accent")

        st.markdown("### Voz")
        col3, col4 = st.columns(2)
        with col3:
            voice_lang = st.selectbox(
       t("transcription_lang", ui_lang),
       ["auto (pt+en)", "en", "pt", "es", "fr", "de"],
       index=safe_index(["auto (pt+en)", "en", "pt", "es", "fr", "de"],
                        profile.get("voice_lang", "auto (pt+en)")),
       key="pf_vlang"
   )
        with col4:
            speech_lang = st.selectbox(t("tts_accent", ui_lang), ["en-US", "en-UK", "pt-BR"],
                index=safe_index(["en-US", "en-UK", "pt-BR"], profile.get("speech_lang", "en-US")), key="pf_slang")

        if st.button(t("save_general", ui_lang), key="save_geral"):
            update_profile(username, {"language": lang,
                "accent_color": accent, "voice_lang": voice_lang, "speech_lang": speech_lang})
            u = load_students().get(username, {})
            # Atualiza session_state para refletir cor imediatamente
            st.session_state.user = {"username": username, **u}
            st.success("✅ Settings saved!")

    # ── Aba Personalização ────────────────────────────────────────────────────
    with tab_pers:
        st.markdown("### Sobre Você")
        col1, col2 = st.columns(2)
        with col1:
            nickname   = st.text_input(t("nickname", ui_lang), value=profile.get("nickname", ""), key="pf_nick")
            occupation = st.text_input(t("occupation", ui_lang), value=profile.get("occupation", ""),
                placeholder="ex: Professora, Desenvolvedor", key="pf_occ")
        with col2:
            level = st.selectbox(t("english_level", ui_lang), level_opts,
                index=safe_index(level_opts, user.get("level", "Beginner")), key="pf_level")
            focus = st.selectbox(t("focus", ui_lang), focus_opts,
                index=safe_index(focus_opts, user.get("focus", "General Conversation")), key="pf_focus")

        if not is_prof:
            st.markdown("### Estilo da IA")
            col3, col4 = st.columns(2)
            ai_style_opts = ["Warm & Encouraging", "Formal & Professional", "Fun & Casual", "Strict & Direct"]
            ai_tone_opts  = ["Teacher", "Conversation Partner", "Tutor", "Business Coach"]
            with col3:
                ai_style = st.selectbox(t("conv_tone", ui_lang), ai_style_opts,
                    index=safe_index(ai_style_opts, profile.get("ai_style", "Warm & Encouraging")), key="pf_aistyle")
            with col4:
                ai_tone = st.selectbox(t("ai_role", ui_lang), ai_tone_opts,
                    index=safe_index(ai_tone_opts, profile.get("ai_tone", "Teacher")), key="pf_aitone")
            custom = st.text_area("Instruções personalizadas para a IA",
                value=profile.get("custom_instructions", ""),
                placeholder="ex: Sempre me corrija quando eu errar o Past Simple.",
                height=100, key="pf_custom")
        else:
            ai_style = profile.get("ai_style", "Warm & Encouraging")
            ai_tone  = profile.get("ai_tone",  "Teacher")
            custom   = profile.get("custom_instructions", "")

        if st.button(t("save_custom", ui_lang), key="save_pers"):
            update_profile(username, {"nickname": nickname, "occupation": occupation,
                "ai_style": ai_style, "ai_tone": ai_tone, "custom_instructions": custom,
                "level": level, "focus": focus})
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Perfil salvo!")

    # ── Aba Conta ─────────────────────────────────────────────────────────────
    with tab_conta:
        st.markdown("### 📸 Foto de Perfil")

        msg = st.session_state.pop("_photo_msg", None)
        if msg == "saved":   st.success("✅ Foto salva!")
        elif msg == "removed": st.success("Foto removida.")

        cur_avatar = get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v", 0))
        MAX_BYTES  = 15 * 1024 * 1024

        col_av, col_btns = st.columns([1, 3])
        with col_av:
            st.markdown(
                _avatar_circle_html(cur_avatar, size=88) +
                '<div style="height:8px"></div>',
                unsafe_allow_html=True)
        with col_btns:
            photo_file = st.file_uploader(
                "Alterar foto — JPG, PNG ou WEBP (máx 15 MB)",
                type=["jpg", "jpeg", "png", "webp"], key="pf_photo_upload")
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
                        st.session_state["_photo_msg"] = "saved"
                        st.rerun()
            if cur_avatar:
                if st.button(t("remove_photo", ui_lang), key="pf_remove_photo"):
                    remove_user_avatar(username)
                    get_user_avatar_b64.clear()
                    st.session_state.user.get("profile", {}).pop("avatar_v", None)
                    st.session_state.user["profile"] = {
                        k: v for k, v in st.session_state.user.get("profile", {}).items()
                        if k != "avatar_v"
                    }
                    st.session_state.pop("_last_photo_saved", None)
                    st.session_state["_photo_msg"] = "removed"
                    st.rerun()

        st.markdown("---")
        st.markdown("### Informações da Conta")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input(t("full_name", ui_lang), value=user.get("name", ""), key="pf_fname")
        with col2:
            email = st.text_input(t("email", ui_lang), value=user.get("email", ""), key="pf_email")

        st.markdown(f"**Username:** `{username}`")
        st.markdown(f"**Conta criada em:** {user.get('created_at', '')[:10]}")

        if st.button(t("save_data", ui_lang), key="save_conta"):
            update_profile(username, {"name": full_name, "email": email})
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Dados atualizados!")

        st.markdown("---")
        st.markdown("### Alterar Senha")
        col3, col4 = st.columns(2)
        with col3:
            new_pw  = st.text_input(t("new_password", ui_lang), type="password", key="pf_newpw")
        with col4:
            conf_pw = st.text_input(t("confirm_password", ui_lang), type="password", key="pf_confpw")

        if st.button(t("change_password", ui_lang), key="save_pw"):
            if len(new_pw) < 6:
                st.error("Senha muito curta.")
            elif new_pw != conf_pw:
                st.error("As senhas não coincidem.")
            else:
                update_password(username, new_pw)
                st.success("✅ Senha alterada!")

    st.markdown("---")
    back_label = "← Voltar ao Dashboard" if is_prof else "← Voltar ao Chat"
    back_page  = "dashboard" if is_prof else "chat"
    if st.button(back_label, key="back_chat"):
        st.session_state.page = back_page; st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MODO CONVERSA — avatar animado com microfone contínuo (VAD)
# ══════════════════════════════════════════════════════════════════════════════

def _vm_process_audio(raw: bytes, lang: str, conv_id: str) -> None:
    """
    Transcreve o áudio gravado, envia ao Claude e armazena
    a resposta + TTS no session_state para o JS exibir.
    """
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

    # Gera TTS para o modo voz
    tts_b64 = ""
    tts_bytes = None
    if tts_available():
        ab = text_to_speech(reply)
        if ab:
            tts_bytes = ab
            tts_b64 = base64.b64encode(ab).decode()

    st.session_state["_vm_reply"]   = reply
    st.session_state["_vm_tts_b64"] = tts_b64

    # Gera vídeo Wav2Lip se disponível
    st.session_state["_vm_video_b64"] = ""
    if _WAV2LIP_LOADED and wav2lip_available() and tts_bytes:
        video_b64 = generate_talking_video(tts_bytes)
        if video_b64:
            st.session_state["_vm_video_b64"] = video_b64

    # Persiste no histórico da conversa atual
    append_message(username, conv_id, "user",      txt,   audio=True)
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64 or None)


def show_voice_mode() -> None:
    """
    Modo voz imersivo — estilo ChatGPT Voz.
    Avatar centralizado, histórico de mensagens em bolhas, microfone como ícone FA.
    """
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang         = profile.get("language",    "pt-BR")
    whisper_lang    = profile.get("voice_lang",  "en")
    speech_lang_val = profile.get("speech_lang", "en-US")
    accent_color    = profile.get("accent_color", "#f0a500")

    conv_id = get_or_create_conv(username)

    # Botão fechar — invisível no Streamlit, acionado pelo JS do iframe
    if st.button(t("close_voice", ui_lang), key="close_voice_inner"):
        st.session_state.voice_mode = False
        for k in ["_vm_history", "_vm_reply", "_vm_tts_b64", "_vm_user_said",
                  "_vm_error", "_vm_last_upload", "_vm_video_b64", "_vm_audio_key"]:
            st.session_state.pop(k, None)
        st.rerun()
    st.markdown("""<style>
/* Esconde TODOS os botões Streamlit no modo voz — só usamos o do iframe */
[data-testid="stMain"] button { display: none !important; }
[data-testid="stSidebar"]{display:none!important;}
[data-testid="stHeader"]{display:none!important;}
[data-testid="stToolbar"]{display:none!important;}
footer{display:none!important;}
.main .block-container{padding:0!important;max-width:100%!important;}
section[data-testid="stMain"]>div{padding:0!important;}
/* Oculta o st.audio_input — só usamos ele via JS invisível */
[data-testid="stAudioInput"]{
    position:fixed!important;bottom:-200px!important;
    left:-200px!important;opacity:0!important;
    pointer-events:none!important;width:1px!important;height:1px!important;
}
</style>""", unsafe_allow_html=True)

    # ── Processa áudio quando chega ───────────────────────────────────────────
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

    # ── Dados do estado ───────────────────────────────────────────────────────
    user_said = st.session_state.get("_vm_user_said", "")
    reply     = st.session_state.get("_vm_reply",     "")
    tts_b64   = st.session_state.get("_vm_tts_b64",   "")
    video_b64 = st.session_state.get("_vm_video_b64", "")
    vm_error  = st.session_state.get("_vm_error",     "")
    history   = st.session_state.get("_vm_history",   [])

    # Foto da professora e frames do avatar — via cache (sem re-leitura de disco)
    photo_src = get_tati_mini_b64()

    # ── Avatar animado — 4 estados de boca (cache) ───────────────────────────
    _frames   = get_avatar_frames()
    av_base   = _frames["base"]
    av_closed = _frames["closed"]
    av_mid    = _frames["mid"]
    av_open   = _frames["open"]
    _has_avatar = bool(av_base and av_closed and av_mid and av_open)

    is_speaking  = bool(reply)
    is_processing = bool(user_said and not reply and not vm_error)

    # Serializa para JS
    tts_js       = json.dumps(tts_b64)
    video_js     = json.dumps(video_b64)
    reply_js     = json.dumps(reply)
    us_js        = json.dumps(user_said)
    err_js       = json.dumps(vm_error)
    sl_js        = json.dumps(speech_lang_val)
    pnm_js       = json.dumps(PROF_NAME)
    photo_js     = json.dumps(photo_src)
    av_base_js   = json.dumps(av_base)
    av_closed_js = json.dumps(av_closed)
    av_mid_js    = json.dumps(av_mid)
    av_open_js   = json.dumps(av_open)
    accent_js    = json.dumps(accent_color)
    # UI strings para o modo voz (JS)
    js_speaking   = json.dumps(t("speaking",     ui_lang))
    js_listening  = json.dumps(t("listening",    ui_lang))
    js_processing = json.dumps(t("processing",   ui_lang))
    js_tap_speak  = json.dumps(t("tap_to_speak", ui_lang))
    js_tap_record = json.dumps(t("tap_to_record",ui_lang))
    js_tap_stop   = json.dumps(t("tap_to_stop",  ui_lang))
    js_wait       = json.dumps(t("wait",         ui_lang))
    js_close      = json.dumps(t("close",        ui_lang))

    # Monta bolhas do histórico (pares user/assistant)
    bubbles_html = ""
    msgs = history[:-2] if (reply and len(history) >= 2) else history
    for m in msgs:
        txt = m["content"].replace("<","&lt;").replace(">","&gt;")
        if m["role"] == "user":
            bubbles_html += f'<div class="bubble user-bubble">{txt}</div>'
        else:
            bubbles_html += f'<div class="bubble ai-bubble">{txt}</div>'
    # Adiciona o par mais recente
    if user_said:
        txt_u = user_said.replace("<","&lt;").replace(">","&gt;")
        bubbles_html += f'<div class="bubble user-bubble">{txt_u}</div>'
    if reply:
        txt_r = reply.replace("<","&lt;").replace(">","&gt;")
        bubbles_html += f'<div class="bubble ai-bubble">{txt_r}</div>'
    if vm_error:
        bubbles_html += f'<div class="bubble err-bubble">❌ {vm_error}</div>'
    if is_processing:
        bubbles_html += '<div class="bubble ai-bubble typing"><span></span><span></span><span></span></div>'

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link rel="stylesheet"
  href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{
  background:#080c12;font-family:'Sora',sans-serif;
  color:#e6edf3;height:100vh;overflow:hidden;
  display:flex;flex-direction:column;
}}

/* ── Layout principal ── */
.vm-wrap{{
  display:flex;flex-direction:column;
  height:100vh;position:relative;
  background:radial-gradient(ellipse at 50% 0%,rgba(240,165,0,.06) 0%,transparent 60%);
}}

/* ── Botão fechar ── */
.close-btn{{
  position:absolute;top:14px;left:16px;z-index:100;
  background:rgba(255,255,255,.06);border:1px solid #2a3545;
  color:#8b949e;border-radius:8px;padding:6px 14px;
  font-size:.75rem;font-family:'Sora',sans-serif;cursor:pointer;
  transition:all .2s;
}}
.close-btn:hover{{background:rgba(255,255,255,.12);color:#e6edf3;}}

/* ── Avatar central ── */
.avatar-section{{
  display:flex;flex-direction:column;align-items:center;
  padding-top:36px;gap:8px;flex-shrink:0;
}}

/* Ondas sonoras ao redor do avatar */
.avatar-outer{{
  position:relative;width:220px;height:220px;
  display:flex;align-items:center;justify-content:center;
}}
.wave{{
  position:absolute;border-radius:50%;border:2px solid rgba(240,165,0,0);
  width:100%;height:100%;
  transition:border-color .4s;
}}
.speaking .wave:nth-child(1){{
  animation:wave1 1.4s ease-out infinite;
}}
.speaking .wave:nth-child(2){{
  animation:wave1 1.4s ease-out infinite .35s;
}}
.speaking .wave:nth-child(3){{
  animation:wave1 1.4s ease-out infinite .7s;
}}
@keyframes wave1{{
  0%  {{transform:scale(1);   border-color:var(--accent-70);opacity:1;}}
  100%{{transform:scale(1.55);border-color:transparent;      opacity:0;}}
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

/* ── Área de mensagens ── */
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

/* Typing dots */
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
  box-shadow:0 0 20px rgba(63,185,80,.3);
  color:#fff;transition:all .25s;
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

  <!-- Fechar -->
  <button class="close-btn" onclick="closeModeVoz()">Fechar</button>

  <!-- Avatar -->
  <div class="avatar-section">
    <div class="avatar-outer {"speaking" if is_speaking else ""}">
      <div class="wave"></div>
      <div class="wave"></div>
      <div class="wave"></div>
      <div class="avatar-ring" id="avatarRing">
        <img id="avImg" src="" alt="Tati" style="width:100%;height:100%;object-fit:cover;object-position:top;">
      </div>
    </div>
    <div class="av-name">{PROF_NAME}</div>
    <div class="av-status" id="avStatus">{"🗣 Falando..." if is_speaking else "Toque no microfone para falar"}</div>
  </div>

  <!-- Mensagens -->
  <div class="messages" id="messages">
    {bubbles_html}
  </div>

  <!-- Barra inferior -->
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
const TTS_B64    = {tts_js};
const VIDEO_B64  = {video_js};
const REPLY_TEXT = {reply_js};
const USER_SAID  = {us_js};
const VM_ERROR   = {err_js};
const SPEECH_LANG= {sl_js};
const PROF_NAME  = {pnm_js};
const AV_BASE    = {av_base_js};
const AV_CLOSED  = {av_closed_js};
const AV_MID     = {av_mid_js};
const AV_OPEN    = {av_open_js};
const ACCENT     = {accent_js};
const STR_SPEAKING  = {js_speaking};
const STR_LISTENING = {js_listening};
const STR_PROCESSING= {js_processing};
const STR_TAP_SPEAK = {js_tap_speak};
const STR_TAP_RECORD= {js_tap_record};
const STR_TAP_STOP  = {js_tap_stop};
const STR_WAIT      = {js_wait};
const STR_CLOSE     = {js_close};

// Injeta CSS vars dinamicas baseadas na cor do perfil
(function applyAccent(){{
  function hexToRgb(h){{
    h=h.replace('#','');
    if(h.length===3) h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    const n=parseInt(h,16);
    return [(n>>16)&255,(n>>8)&255,n&255].join(',');
  }}
  const rgb = hexToRgb(ACCENT||'#f0a500');
  const r = document.documentElement;
  r.style.setProperty('--accent-full', ACCENT||'#f0a500');
  r.style.setProperty('--accent-70',  `rgba(${{rgb}},.7)`);
  r.style.setProperty('--accent-40',  `rgba(${{rgb}},.4)`);
  r.style.setProperty('--accent-30',  `rgba(${{rgb}},.3)`);
  r.style.setProperty('--accent-15',  `rgba(${{rgb}},.15)`);
  // Bubble: deriva cor mais escura do accent para background
  r.style.setProperty('--bubble-bg',     `rgba(${{rgb}},.12)`);
  r.style.setProperty('--bubble-border', `rgba(${{rgb}},.3)`);
  r.style.setProperty('--bubble-text',   '#e6edf3');
}})();

// Traduz botão fechar
document.querySelector('.close-btn').textContent = STR_CLOSE;

// ── Scroll mensagens para baixo ───────────────────────────────────────────────
const msgEl = document.getElementById('messages');
function scrollBottom(){{ msgEl.scrollTop = msgEl.scrollHeight; }}
scrollBottom();

// ── Estado do avatar ──────────────────────────────────────────────────────────
const avOuter  = document.querySelector('.avatar-outer');
const avStatus = document.getElementById('avStatus');
const micBtn   = document.getElementById('micBtn');
const micIcon  = document.getElementById('micIcon');
const hintText = document.getElementById('hintText');

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

// ── Avatar animado — sincroniza boca com volume do áudio ─────────────────────
const avImg = document.getElementById('avImg');
let _avAnimFrame = null;

// Inicializa avatar com imagem base
(function initAvatar(){{
  if(AV_BASE) avImg.src = AV_BASE;
  else if({photo_js}) avImg.src = {photo_js};
}})();

function stopMouthAnim(){{
  if(_avAnimFrame){{ cancelAnimationFrame(_avAnimFrame); _avAnimFrame=null; }}
  if(AV_CLOSED) avImg.src = AV_CLOSED;
  else if(AV_BASE) avImg.src = AV_BASE;
}}

function startMouthAnim(audioEl){{
  stopMouthAnim();
  if(!AV_CLOSED || !AV_MID || !AV_OPEN){{ return; }}
  let ctx, analyser, source;
  try{{
    ctx      = new (window.AudioContext||window.webkitAudioContext)();
    analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    source   = ctx.createMediaElementSource(audioEl);
    source.connect(analyser);
    analyser.connect(ctx.destination);
  }}catch(e){{ return; }}

  const data = new Uint8Array(analyser.frequencyBinCount);
  let lastSrc = '', frameCount = 0;

  function loop(){{
    _avAnimFrame = requestAnimationFrame(loop);
    frameCount++;
    if(frameCount % 3 !== 0) return; // ~20fps suficiente
    analyser.getByteFrequencyData(data);
    const vol = data.slice(0,16).reduce((a,b)=>a+b,0)/16;
    let src;
    if     (vol < 8)  src = AV_CLOSED;
    else if(vol < 25) src = AV_MID;
    else              src = AV_OPEN;
    if(src !== lastSrc){{ avImg.src = src; lastSrc = src; }}
  }}
  loop();
}}

// ── Tocar TTS automaticamente ─────────────────────────────────────────────────
function playTTSAuto(b64, text){{
  setAvatarState('speaking');
  if(b64 && b64.length > 20){{
    const audio = new Audio('data:audio/mpeg;base64,' + b64);
    startMouthAnim(audio);
    audio.onended = ()=>{{ stopMouthAnim(); setAvatarState('idle'); }};
    audio.onerror = ()=>{{ stopMouthAnim(); fallbackSpeech(text); }};
    audio.play().catch(()=>{{ stopMouthAnim(); fallbackSpeech(text); }});
  }} else {{
    fallbackSpeech(text);
  }}
}}

function fallbackSpeech(text){{
  const u = new SpeechSynthesisUtterance((text||'').substring(0,500));
  u.lang = SPEECH_LANG; u.rate = 0.95; u.pitch = 1.05;
  speechSynthesis.getVoices();
  setTimeout(()=>{{
    const vv = speechSynthesis.getVoices();
    const pick = vv.find(v=>v.lang===SPEECH_LANG)||vv.find(v=>v.lang.startsWith('en'));
    if(pick) u.voice = pick;
    u.onend = u.onerror = ()=>setAvatarState('idle');
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  }}, 100);
}}

// ── Acionar st.audio_input via parent ────────────────────────────────────────
let isRecording = false;

function triggerAudioInput(){{
  // Clica no botão de gravar do st.audio_input que está oculto
  const par = window.parent ? window.parent.document : document;
  const btn = par.querySelector('[data-testid="stAudioInput"] button')
           || par.querySelector('[data-testid="stAudioInputRecordButton"]')
           || par.querySelector('button[title*="ecord"]')
           || par.querySelector('button[aria-label*="ecord"]');
  if(btn){{
    btn.click();
    return true;
  }}
  return false;
}}

function toggleMic(){{
  if(micBtn.classList.contains('processing')) return;
  if(!isRecording){{
    isRecording = true;
    setAvatarState('recording');
    triggerAudioInput();
  }} else {{
    isRecording = false;
    setAvatarState('processing');
    triggerAudioInput(); // segundo clique para = e envia
    hintText.textContent=STR_PROCESSING;
  }}
}}

// ── Fechar modo voz ───────────────────────────────────────────────────────────
function closeModeVoz(){{
  try{{ speechSynthesis.cancel(); }}catch(e){{}}
  stopMouthAnim();
  // Clica no botão Streamlit com key="close_voice_inner"
  const par = window.parent ? window.parent.document : document;
  // Tenta pelo data-testid key
  let closeBtn = par.querySelector('[data-testid="stButton"][key="close_voice_inner"] button')
               || par.querySelector('button[kind="secondary"]');
  // Fallback: qualquer botão que contenha texto de fechar em qualquer idioma
  if(!closeBtn){{
    const btns = Array.from(par.querySelectorAll('button'));
    closeBtn = btns.find(b=>{{
      const txt = b.textContent.trim();
      return txt.includes('Fechar') || txt.includes('Close') || txt.includes('close_voice');
    }});
  }}
  // Último recurso: primeiro botão visível na página
  if(!closeBtn){{
    closeBtn = par.querySelector('button');
  }}
  if(closeBtn) closeBtn.click();
}}

// ── Auto-play quando há resposta nova ─────────────────────────────────────────
window.addEventListener('load', ()=>{{
  if(REPLY_TEXT && REPLY_TEXT.length > 1){{
    playTTSAuto(TTS_B64, REPLY_TEXT);
  }} else if(USER_SAID && USER_SAID.length > 1){{
    setAvatarState('processing');
  }}
  scrollBottom();
}});
</script>
</body></html>""", height=700, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DO CHAT — processamento de arquivos
# ══════════════════════════════════════════════════════════════════════════════

def _process_and_send_file(username: str, user: dict, conv_id: str,
                            raw: bytes, filename: str, extra_text: str = "") -> bool:
    """
    Processa um arquivo (áudio / texto / imagem) e envia ao Claude
    com um texto adicional opcional do usuário.
    Retorna True se o envio foi bem-sucedido.
    """
    result = extract_file(raw, filename)
    kind, label = result["kind"], result["label"]

    if kind == "audio":
        with st.spinner("🔄 Transcrevendo áudio..."):
            text = transcribe_bytes(raw, suffix=Path(filename).suffix.lower(), language="en")
        if text.startswith("❌") or text.startswith("⚠️"):
            st.error(text); return False
        user_display = f"{extra_text}\n\n[Áudio transcrito: {text}]" if extra_text else text
        claude_msg   = f"{extra_text}\n\n[Áudio: '{filename}']\n{text}" if extra_text else \
                       f"[Áudio: '{filename}']\n{text}"
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
                        "Please help me understand this content — explain vocabulary, grammar, and key ideas.")
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


# ══════════════════════════════════════════════════════════════════════════════
# CHAT — tela principal de conversa
# ══════════════════════════════════════════════════════════════════════════════

def _logout() -> None:
    """
    Encerra a sessão: apaga o token do banco SQLite e do localStorage,
    e limpa o session_state.
    """
    token = st.session_state.get("_session_token", "")
    if token:
        delete_session(token)          # remove do banco SQLite
    js_clear_session()                 # remove do localStorage do browser
    st.session_state.pop("_session_token", None)
    st.session_state.update(logged_in=False, user=None, conv_id=None)


def show_chat() -> None:
    """Tela principal do chat — sidebar com histórico + área de mensagens."""
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")
    conv_id  = get_or_create_conv(username)
    messages = cached_load_conversation(username, conv_id)
    speaking = st.session_state.speaking

    # Redireciona para o modo voz se ativo
    if st.session_state.voice_mode:
        show_voice_mode()
        return

    # ── Injeta cor de destaque do usuário no Streamlit principal ────────────
    _ac = profile.get("accent_color", "#f0a500")
    st.markdown(f"""<script>
(function(){{
  function hexToRgb(h){{
    h=h.replace('#','');
    if(h.length===3) h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);
    return [(n>>16)&255,(n>>8)&255,n&255].join(',');
  }}
  var ac="{_ac}";
  var rgb=hexToRgb(ac);
  var r=document.documentElement;
  r.style.setProperty('--accent-full',ac);
  r.style.setProperty('--accent-70','rgba('+rgb+',.7)');
  r.style.setProperty('--accent-40','rgba('+rgb+',.4)');
  r.style.setProperty('--accent-30','rgba('+rgb+',.3)');
  r.style.setProperty('--accent-15','rgba('+rgb+',.15)');
  r.style.setProperty('--bubble-bg','rgba('+rgb+',.12)');
  r.style.setProperty('--bubble-border','rgba('+rgb+',.3)');
  r.style.setProperty('--bubble-text','#e6edf3');
}})();
</script>""", unsafe_allow_html=True)

    # ── JS: para todo áudio ao trocar de conversa ou recarregar ──────────────
    components.html("""<!DOCTYPE html><html><body><script>
(function() {
  const par = window.parent;
  if (!par) return;
  function stopAllAudio() {
    par.document.querySelectorAll('audio').forEach(function(a) {
      a.pause(); a.currentTime = 0;
    });
    par.document.querySelectorAll('iframe').forEach(function(iframe) {
      try {
        iframe.contentDocument.querySelectorAll('audio').forEach(function(a) {
          a.pause(); a.currentTime = 0;
        });
        iframe.contentDocument.querySelectorAll('#b').forEach(function(b) {
          b.textContent = '\u25b6 Ouvir';
        });
        if (iframe.contentWindow.speechSynthesis) {
          iframe.contentWindow.speechSynthesis.cancel();
        }
      } catch(e) {}
    });
    if (par.speechSynthesis) par.speechSynthesis.cancel();
  }
  stopAllAudio();
  const observer = new MutationObserver(function() { stopAllAudio(); });
  observer.observe(par.document.body, { childList: true, subtree: false });
  window.addEventListener('beforeunload', function() { observer.disconnect(); });
})();
</script></body></html>""", height=1)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""<style>
        section[data-testid="stSidebar"] { overflow: hidden; }
        section[data-testid="stSidebar"] > div:first-child {
            height: 100vh; display: flex; flex-direction: column;
            padding: 0 !important; gap: 0;
        }
        div.sidebar-footer { margin-top: auto; }
        </style>""", unsafe_allow_html=True)

        # Topo com avatar da professora
        st.markdown(f"""<div style="padding:14px 14px 10px;border-bottom:1px solid #21262d;flex-shrink:0;">
            <div style="display:flex;align-items:center;gap:10px;">
                {avatar_html(40)}<div>
                <div style="font-weight:600;font-size:.88rem;">{PROF_NAME}</div>
                <div style="font-size:.68rem;color:#8b949e;"><span class="status-dot"></span>Online</div>
                </div></div></div>""", unsafe_allow_html=True)

        if st.button(t("new_conv", ui_lang), use_container_width=True, key="btn_new"):
            st.session_state.conv_id = new_conversation(username); st.rerun()
        if st.button(t("voice_mode", ui_lang), use_container_width=True, key="btn_voice"):
            st.session_state.voice_mode = True; st.rerun()

        st.markdown('<div style="font-size:.68rem;color:#8b949e;text-transform:uppercase;'
                    'letter-spacing:1px;padding:10px 4px 4px;">Conversas</div>',
                    unsafe_allow_html=True)

        convs = list_conversations(username)
        if not convs:
            st.markdown('<div style="font-size:.78rem;color:#8b949e;padding:6px 4px;">Nenhuma conversa ainda.</div>',
                        unsafe_allow_html=True)
        for c in convs:
            is_active = c["id"] == conv_id
            label     = ("▶ " if is_active else "") + c["title"]
            col_conv, col_del = st.columns([5, 1])
            with col_conv:
                if st.button(label, key=f"conv_{c['id']}", use_container_width=True,
                             help=f"📅 {c['date']} · 💬 {c['count']} msgs"):
                    st.session_state.conv_id = c["id"]; st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{c['id']}", help=t("delete_conv", ui_lang)):
                    delete_conversation(username, c["id"])
                    if st.session_state.conv_id == c["id"]:
                        st.session_state.conv_id = None
                    st.rerun()
            st.markdown(f'<div style="font-size:.62rem;color:#6e7681;margin:-10px 0 2px 6px;">'
                        f'📅 {c["date"]} · 💬 {c["count"]} msg</div>', unsafe_allow_html=True)

        # ── Rodapé da sidebar com botões de ação ──────────────────────────────
        user_msgs   = len([m for m in messages if m["role"] == "user"])
        uav_sidebar = user_avatar_html(username, size=34, fallback_emoji="🎓")
        st.markdown('<div class="sidebar-footer">', unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#21262d;margin:8px 0 0'>", unsafe_allow_html=True)
        st.markdown(f"""<div style="padding:8px 12px;display:flex;align-items:center;gap:10px;">
            {uav_sidebar}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:600;font-size:.82rem;white-space:nowrap;
                overflow:hidden;text-overflow:ellipsis;">{user['name'].split()[0]}</div>
              <div style="color:#8b949e;font-size:.68rem;">{user['level']} · {user_msgs} msgs</div>
            </div></div>""", unsafe_allow_html=True)

        if user["role"] == "professor":
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(t("dashboard", ui_lang), use_container_width=True, key="btn_dash"):
                    st.session_state.page = "dashboard"; st.rerun()
            with col_b:
                if st.button(t("profile", ui_lang), use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            # Logout da professora: apaga sessão persistente
            if st.button(t("logout", ui_lang), use_container_width=True, key="btn_sair"):
                _logout(); st.rerun()
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(t("profile", ui_lang), use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            with col_b:
                # Logout do aluno: apaga sessão persistente
                if st.button(t("logout", ui_lang), use_container_width=True, key="btn_sair"):
                    _logout(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── CSS do chat estilo ChatGPT ────────────────────────────────────────────
    st.markdown("""<style>
[data-testid="stChatInput"] textarea {
    max-height: 120px !important; min-height: 44px !important; font-size: .88rem !important;
}
[data-testid="stChatInputContainer"] { padding: 6px 10px !important; }
.main .block-container { padding-bottom: 80px !important; }
section[data-testid="stMain"] { transition: margin-left .3s ease !important; }

/* Mensagens estilo ChatGPT */
.msg-row { display:flex; align-items:flex-end; gap:10px; margin:6px 0; }
.msg-row.user-row { flex-direction:row-reverse; }
.msg-row.bot-row  { flex-direction:row; }

.msg-bubble {
    max-width: 68%; padding: 10px 15px; border-radius: 18px;
    font-size: .88rem; line-height: 1.6; word-break: break-word;
}
.msg-bubble.user {
    background: #2d6a4f; color: #d8f3dc;
    border-bottom-right-radius: 4px;
}
.msg-bubble.bot {
    background: #1a1f2e; color: #e6edf3;
    border: 1px solid #252d3d;
    border-bottom-left-radius: 4px;
}
.msg-bubble.audio-msg { font-style: italic; opacity: .85; }

.msg-av {
    width: 30px; height: 30px; border-radius: 50%;
    overflow: hidden; flex-shrink: 0; margin-bottom: 2px;
}
.msg-av img { width:100%; height:100%; object-fit:cover; object-position:top; }
.msg-av .av-emoji {
    width:100%; height:100%; background:#1e2a3a;
    display:flex; align-items:center; justify-content:center; font-size:14px;
}
.msg-time {
    font-size: .6rem; color: #4a5a6a;
    margin: 2px 4px 0; text-align: right;
}
.bot-row .msg-time { text-align: left; }

@media (max-width: 768px) {
    .msg-bubble { max-width: 88% !important; font-size: .82rem !important; }
}
@media (max-width: 480px) {
    .msg-bubble { max-width: 94% !important; }
}
</style>""", unsafe_allow_html=True)

    # ── Header do chat ────────────────────────────────────────────────────────
    st.markdown(f"""<div class="prof-header">
        {avatar_html(56, speaking)}
        <div class="prof-info">
            <h1>{PROF_NAME}</h1>
            <p><span class="status-dot"></span>Online · {user['level']} · {user['focus']}</p>
        </div></div>""", unsafe_allow_html=True)

    # ── Histórico de mensagens ────────────────────────────────────────────────
    # Mini-avatar da Tati para o chat (cache — sem re-leitura de disco)
    _tati_mini   = get_tati_mini_b64()
    tati_av_html = (f'<div class="msg-av"><img src="{_tati_mini}"></div>'
                    if _tati_mini else
                    '<div class="msg-av"><div class="av-emoji">🧑‍🏫</div></div>')

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for i, msg in enumerate(messages):
        content  = msg["content"].replace("\n", "<br>")
        msg_time = msg.get("time", "")

        if msg["role"] == "assistant":
            tts_b64 = msg.get("tts_b64", "")
            is_file = msg.get("is_file", False)
            st.markdown(
                f'<div class="msg-row bot-row">'
                f'{tati_av_html}'
                f'<div>'
                f'<div class="msg-bubble bot">{content}</div>'
                f'<div class="msg-time">{msg_time}</div>'
                f'</div></div>',
                unsafe_allow_html=True)
            if tts_b64:
                components.html(render_audio_player(tts_b64, t, f"msg_{i}_{conv_id}"),
                                height=44, scrolling=False)
            elif not is_file:
                clean_text = (msg["content"]
                    .replace("\\", "").replace("`", "")
                    .replace("'", "\\'").replace('"', '\\"')
                    .replace("\n", " ").replace("\r", "")
                    .replace("*", "").replace("#", ""))[:600]
                components.html(f"""<!DOCTYPE html><html><head>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{background:transparent;overflow:hidden;}}
.row{{display:flex;align-items:center;gap:8px;padding:2px 0 0 40px;}}
.btn{{background:none;border:1px solid #30363d;border-radius:16px;
      color:#8b949e;font-size:.68rem;padding:2px 10px;cursor:pointer;
      transition:all .15s;white-space:nowrap;}}
.btn:hover,.btn.on{{border-color:#f0a500;color:#f0a500;}}
</style></head><body>
<div class="row">
  <button class="btn" id="btn">▶ Ouvir</button>
</div>
<script>
(function(){{
  var txt = '{clean_text}';
  var btn = document.getElementById('btn');
  var speaking = false;
  btn.onclick = function() {{
    if (speaking) {{
      speechSynthesis.cancel(); speaking=false;
      btn.textContent='▶ Ouvir'; btn.classList.remove('on'); return;
    }}
    var u = new SpeechSynthesisUtterance(txt);
    u.lang='en-US'; u.rate=0.95; u.pitch=1.05;
    speechSynthesis.getVoices();
    setTimeout(function(){{
      var vv=speechSynthesis.getVoices();
      var pick=vv.find(v=>v.lang==='en-US')||vv.find(v=>v.lang.startsWith('en'));
      if(pick)u.voice=pick;
      u.onstart=function(){{speaking=true;btn.textContent='⏹ Parar';btn.classList.add('on');}};
      u.onend=u.onerror=function(){{speaking=false;btn.textContent='▶ Ouvir';btn.classList.remove('on');}};
      speechSynthesis.cancel(); speechSynthesis.speak(u);
    }},100);
  }};
}})();
</script></body></html>""", height=28, scrolling=False)
            else:
                st.markdown(f'<div class="msg-time" style="margin-left:40px;">{msg_time}</div>',
                            unsafe_allow_html=True)
        else:
            is_audio = msg.get("audio", False)
            extra    = " audio-msg" if is_audio else ""
            st.markdown(
                f'<div class="msg-row user-row">'
                f'<div>'
                f'<div class="msg-bubble user{extra}">{content}</div>'
                f'<div class="msg-time">{msg_time}</div>'
                f'</div></div>',
                unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Indicador "digitando" — aparece enquanto Claude processa ─────────────
    if st.session_state.get("speaking"):
        components.html("""<!DOCTYPE html><html><head>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body{background:transparent;overflow:hidden;font-family:'Sora',sans-serif;}
.typing-row{
  display:flex;align-items:center;gap:10px;
  padding:6px 0 4px 0;
}
.av{
  width:30px;height:30px;border-radius:50%;
  background:#1e2a3a;display:flex;align-items:center;
  justify-content:center;font-size:14px;flex-shrink:0;
}
.typing-bubble{
  display:flex;align-items:center;gap:8px;
  background:#1a1f2e;border:1px solid #252d3d;
  border-radius:18px;border-bottom-left-radius:4px;
  padding:8px 14px;
}
.spin{
  color:#e05c2a;font-size:16px;line-height:1;
  animation:spinme 1.2s linear infinite;
  display:inline-block;flex-shrink:0;
}
@keyframes spinme{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
.typing-text{font-size:.75rem;color:#8b949e;font-style:italic;letter-spacing:.2px;}
</style></head><body>
<div class="typing-row">
  <div class="av">🧑‍🏫</div>
  <div class="typing-bubble">
    <span class="spin">✳</span>
    <span class="typing-text" id="msg">Pensando…</span>
  </div>
</div>
<script>
(function(){
  var msgs = [
    [0,   "Pensando…"],
    [3,   "Elaborando resposta…"],
    [7,   "Demorando mais que o normal. Tentando novamente em breve (tentativa 1)"],
    [14,  "Demorando mais que o normal. Tentando novamente em breve (tentativa 2)"],
    [22,  "Demorando mais que o normal. Tentando novamente em breve (tentativa 3)"],
  ];
  var el    = document.getElementById('msg');
  var start = Date.now();
  function update(){
    var sec = (Date.now()-start)/1000;
    var txt = msgs[0][1];
    for(var i=0;i<msgs.length;i++){ if(sec>=msgs[i][0]) txt=msgs[i][1]; }
    el.textContent = txt;
    setTimeout(update, 800);
  }
  update();
})();
</script>
</body></html>""", height=52, scrolling=False)
    staged = st.session_state.get("staged_file")
    if staged:
        fname = staged.get("name", "arquivo")
        fkind = staged.get("kind", "file")
        icon  = {"audio": "🎵", "text": "📄", "image": "📸"}.get(fkind, "📎")
        st.markdown(f"""
<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.25);
     border-radius:10px;padding:10px 14px;margin:6px 0;
     display:flex;align-items:center;justify-content:space-between;gap:10px;">
  <span style="font-size:.85rem;color:#e6edf3;">{icon} <b>{fname}</b>
    <span style="color:#8b949e;font-size:.75rem;"> · anexado</span></span>
  <span style="font-size:.7rem;color:#f0a500;">↩ Digite uma mensagem ou envie</span>
</div>
""", unsafe_allow_html=True)
        if st.button(t("remove_attachment", ui_lang), key="remove_staged"):
            st.session_state.staged_file      = None
            st.session_state.staged_file_name = None
            st.rerun()

    # ── Botão de download de arquivo gerado pela IA ───────────────────────────
    pending_dl = st.session_state.get("_pending_download")
    if pending_dl:
        b64_data = pending_dl["b64"]
        fname    = pending_dl["filename"]
        mime     = pending_dl["mime"]
        st.markdown(f"""
<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.35);
     border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;
     align-items:center;justify-content:space-between;gap:12px;">
  <span style="font-size:.85rem;color:#e6edf3;">📎 <b>{fname}</b> pronto para download</span>
  <a href="data:{mime};base64,{b64_data}" download="{fname}"
     style="background:linear-gradient(135deg,#f0a500,#e05c2a);color:#060a10;
     font-weight:700;font-size:.78rem;padding:6px 16px;border-radius:20px;
     text-decoration:none;white-space:nowrap;">⬇ Baixar arquivo</a>
</div>""", unsafe_allow_html=True)

    # ── Chat input (texto) ────────────────────────────────────────────────────
    prompt = st.chat_input(t("type_message", ui_lang))
    if prompt:
        if not API_KEY:
            st.error("Configure ANTHROPIC_API_KEY no .env"); st.stop()

        staged = st.session_state.get("staged_file")
        if staged:
            # Envia arquivo + texto juntos
            _process_and_send_file(username, user, conv_id,
                                   staged["raw"], staged["name"], extra_text=prompt)
            st.session_state.staged_file      = None
            st.session_state.staged_file_name = None
        else:
            append_message(username, conv_id, "user", prompt)
            st.session_state.speaking = True
            try:   send_to_claude(username, user, conv_id, prompt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False

        st.rerun()

    # ── Gravador de áudio nativo (st.audio_input) ─────────────────────────────
    audio_val = st.audio_input(" ", key=f"voice_input_{st.session_state.audio_key}",
                               label_visibility="collapsed")
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

    # ── File uploader (oculto — acionado pelo clipe na chat bar) ─────────────
    uploaded = st.file_uploader(
        "📎", key="file_upload", label_visibility="collapsed",
        type=["mp3", "wav", "ogg", "m4a", "webm", "flac",
              "pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "webp"])

    if uploaded and uploaded.name != st.session_state.get("_last_file"):
        st.session_state["_last_file"] = uploaded.name
        raw    = uploaded.read()
        result = extract_file(raw, uploaded.name)
        # Staging: guarda o arquivo sem enviar ainda
        st.session_state.staged_file = {
            "raw":    raw,
            "name":   uploaded.name,
            "kind":   result["kind"],
            "result": result,
        }
        st.session_state.staged_file_name = uploaded.name
        st.rerun()

    # ── JS: move botão de clipe para dentro da chat bar ──────────────────────
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;height:0;}</style>
</head><body>
<script>
(function() {
  var done = false;

  function pavMoveToChatBar() {
    const par = window.parent ? window.parent.document : document;
    const chatInputContainer = par.querySelector('[data-testid="stChatInput"]');
    if (!chatInputContainer) return false;
    if (chatInputContainer.querySelector('.pav-extras')) return true; // já feito

    const extras = par.createElement('div');
    extras.className = 'pav-extras';

    const ab = par.createElement('button');
    ab.className = 'pav-icon-btn';
    ab.title = 'Anexar arquivo';
    ab.innerHTML = '<i class="fa-solid fa-paperclip"></i>';
    ab.onclick = () => {
      const fw = par.querySelector('[data-testid="stFileUploader"]');
      if (fw) {
        const fileInput = fw.querySelector('input[type="file"]');
        if (fileInput) fileInput.click();
      }
    };

    extras.appendChild(ab);
    const chatInner = chatInputContainer.querySelector('div');
    if (chatInner) chatInner.style.position = 'relative';
    chatInputContainer.appendChild(extras);
    return true;
  }

  function pavFixAudioInput() {
    const par = window.parent ? window.parent.document : document;
    const ai  = par.querySelector('[data-testid="stAudioInput"]');
    const ci  = par.querySelector('[data-testid="stChatInput"]');
    if (!ai || !ci) return;

    const rect = ci.getBoundingClientRect();
    ai.style.cssText = `
      position: fixed !important;
      bottom: ${window.parent.innerHeight - rect.top + 42}px !important;
      left: ${rect.left}px !important;
      width: ${rect.width}px !important;
      z-index: 99 !important;
      background: transparent !important;
      border: none !important;
      padding: 0 !important;
      height: 52px !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      box-shadow: none !important;
    `;
    const inners = ai.querySelectorAll('div');
    inners.forEach(d => {
      d.style.background = 'transparent';
      d.style.border = 'none';
      d.style.boxShadow = 'none';
    });
    const lbl = ai.querySelector('label');
    if (lbl) lbl.style.display = 'none';
  }

  function trySetup() {
    const ok = pavMoveToChatBar();
    pavFixAudioInput();
    if (ok) done = true;
    return ok;
  }

  // Tenta imediatamente
  if (!trySetup()) {
    // Observa o DOM do parent para agir assim que o chat input aparecer
    try {
      const par = window.parent ? window.parent.document : document;
      const obs = new MutationObserver(function() {
        if (trySetup()) obs.disconnect();
      });
      obs.observe(par.body, { childList: true, subtree: true });
      // Fallback de segurança: desliga observer após 10s
      setTimeout(() => obs.disconnect(), 10000);
    } catch(e) {
      // Cross-origin fallback
      var t = setInterval(function() {
        if (trySetup()) clearInterval(t);
      }, 200);
      setTimeout(function() { clearInterval(t); }, 10000);
    }
  }

  // Reconecta audio input ao resize
  window.parent.addEventListener('resize', pavFixAudioInput);
})();
</script>
</body></html>""", height=1)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD DA PROFESSORA
# ══════════════════════════════════════════════════════════════════════════════

def show_dashboard() -> None:
    """Painel administrativo com estatísticas de todos os alunos."""
    user    = st.session_state.user
    profile = user.get("profile", {})
    ui_lang = profile.get("language", "pt-BR")

    with st.sidebar:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div>
            <div style="font-weight:600;font-size:.9rem;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#8b949e;"><span class="status-dot"></span>Professora</div>
            </div></div>
            <hr style="border-color:#30363d;margin:6px 0 12px">""", unsafe_allow_html=True)
        if st.button("📊 Dashboard", use_container_width=True, type="primary"): pass
        if st.button(t("voice_mode", ui_lang), use_container_width=True, key="dash_voice"):
            st.session_state.page = "chat"
            st.session_state.voice_mode = True; st.rerun()
        if st.button(t("use_as_student", ui_lang), use_container_width=True, key="dash_chat"):
            st.session_state.page = "chat"; st.rerun()
        if st.button(t("my_profile", ui_lang), use_container_width=True, key="dash_profile"):
            st.session_state.page = "profile"; st.rerun()
        if st.button(t("logout", ui_lang), use_container_width=True, key="dash_logout"):
            _logout(); st.rerun()

    st.markdown("## 📊 Painel do Professor")
    st.markdown("---")
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button(t("enter_chat", ui_lang), use_container_width=True):
            st.session_state.page = "chat"; st.rerun()
    st.markdown("---")

    stats = get_all_students_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in zip(
        [c1, c2, c3, c4],
        [len(stats),
         sum(s["messages"]    for s in stats),
         sum(s["corrections"] for s in stats),
         sum(1 for s in stats if s["last_active"][:10] == today)],
        ["Alunos", "Mensagens", "Correções", "Ativos Hoje"]
    ):
        col.markdown(
            f'<div class="stat-card"><div class="val">{val}</div><div class="lbl">{lbl}</div></div>',
            unsafe_allow_html=True)

    st.markdown("<br>")
    st.markdown("### 👥 Alunos")
    if not stats:
        st.info("Nenhum aluno ainda.")
    else:
        badge = {"Beginner": "badge-blue", "Pre-Intermediate": "badge-green",
                 "Intermediate": "badge-gold",   "Business English": "badge-gold"}
        rows = "".join(f"""<tr>
            <td><b>{s['name']}</b><br><span style="color:#8b949e;font-size:.75rem">@{s['username']}</span></td>
            <td><span class="badge {badge.get(s['level'],'badge-blue')}">{s['level']}</span></td>
            <td>{s['focus']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['messages']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['corrections']}</td>
            <td style="color:#8b949e">{s['last_active']}</td>
        </tr>""" for s in sorted(stats, key=lambda x: x["messages"], reverse=True))
        st.markdown(
            f'<div style="background:var(--surface);border:1px solid var(--border);'
            f'border-radius:12px;overflow:hidden"><table class="dash-table"><thead>'
            f'<tr><th>Aluno</th><th>Nível</th><th>Foco</th><th>Msgs</th>'
            f'<th>Correções</th><th>Último Acesso</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>',
            unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ROTEADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

if not st.session_state.logged_in:
    show_login()
else:
    # Re-salva token a cada render para garantir persistência
    _tok = st.session_state.get("_session_token", "")
    if _tok:
        js_save_session(_tok)

    if st.session_state.page == "profile":
        show_profile()
    elif st.session_state.page == "dashboard":
        show_dashboard()
    else:
        show_chat()