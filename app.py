"""
app.py — Teacher Tati · Roteador principal.

Toda a lógica de UI foi movida para:
  ui_helpers.py            helpers compartilhados (i18n, avatares, Claude, etc.)
  tati_views/login.py      tela de login / registro
  tati_views/chat.py       chat principal + geração de arquivos
  tati_views/voice.py      modo voz com avatar animado (7 frames)
  tati_views/profile.py    perfil do usuário
  tati_views/dashboard.py  painel do professor
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import streamlit.components.v1 as components

# ── Banco de dados ────────────────────────────────────────────────────────────
from database import init_db, validate_session, load_students, create_session

# ── Helpers compartilhados ────────────────────────────────────────────────────
from ui_helpers import (
    PROF_NAME, PHOTO_PATH,
    get_photo_b64, js_save_session, js_clear_session,
)

# ── Views ─────────────────────────────────────────────────────────────────────
from tati_views.login     import show_login
from tati_views.chat      import show_chat
from tati_views.profile   import show_profile
from tati_views.dashboard import show_dashboard

# ── Font Awesome ──────────────────────────────────────────────────────────────
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">',
    unsafe_allow_html=True,
)

# ── Inicialização do banco ────────────────────────────────────────────────────
init_db()

# ── Página Streamlit ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{PROF_NAME} · English",
    page_icon=str(Path(PHOTO_PATH)) if Path(PHOTO_PATH).exists() else "🎓",
    layout="wide",
)

# ── CSS global ────────────────────────────────────────────────────────────────
def _load_css(path: str) -> None:
    p = Path(path)
    if p.exists():
        st.markdown(f"<style>{p.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

_load_css("styles/style.css")

st.markdown("""<style>
[data-testid="stAppViewBlockContainer"] { opacity:1!important; }
div[data-stale="true"]  { opacity:1!important; transition:none!important; }
div[data-stale="false"] { opacity:1!important; transition:none!important; }
.stSpinner,[data-testid="stSpinner"],
div[class*="StatusWidget"],div[class*="stStatusWidget"] { display:none!important; }
.stApp > div { opacity:1!important; }
.main .block-container {
    max-width:100%!important;
    padding-left:clamp(10px,2vw,40px)!important;
    padding-right:clamp(10px,2vw,40px)!important;
    padding-top:1rem!important;
}
section[data-testid="stSidebar"] { min-width:220px!important; max-width:340px!important; }
div[data-testid="stButton"] button { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stFileUploader"] {
    position:fixed!important; bottom:-999px!important; left:-9999px!important;
    opacity:0!important; width:1px!important; height:1px!important;
    pointer-events:none!important; overflow:hidden!important;
}
[data-testid="stFileUploader"] input[type="file"] { pointer-events:auto!important; }
[data-testid="stAudioInput"] {
    position:fixed!important; bottom:-9999px!important; left:-9999px!important;
    opacity:0!important; pointer-events:none!important;
    width:1px!important; height:1px!important; overflow:hidden!important;
}
[data-testid="stAudioInput"] button { pointer-events:auto!important; }
@media (max-width:768px) {
    .main .block-container { padding-left:8px!important; padding-right:8px!important; padding-bottom:80px!important; }
    div.bubble { max-width:92%!important; font-size:.82rem!important; }
    div.prof-header h1 { font-size:1rem!important; }
    .bav-s,.bav-u { display:none!important; }
}
</style>""", unsafe_allow_html=True)

# ── Contador de áudio ─────────────────────────────────────────────────────────
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0

# ── Session state padrão ──────────────────────────────────────────────────────
_defaults = {
    "logged_in":        False,
    "user":             None,
    "page":             "chat",
    "speaking":         False,
    "conv_id":          None,
    "voice_mode":       False,
    "staged_file":      None,
    "staged_file_name": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auto-login via query param ?s=<token> ─────────────────────────────────────
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
                st.session_state.page              = "dashboard" if _udata["role"] == "professor" else "chat"
                st.session_state.conv_id           = None
                st.session_state["_session_token"] = _s
        else:
            st.query_params.pop("s", None)

# ── Salva token uma única vez por sessão ──────────────────────────────────────
if st.session_state.logged_in:
    _tok = st.session_state.get("_session_token", "")
    if _tok and not st.session_state.get("_session_saved"):
        js_save_session(_tok)
        st.session_state["_session_saved"] = True

# ══════════════════════════════════════════════════════════════════════════════
# ROTEADOR
# ══════════════════════════════════════════════════════════════════════════════

if not st.session_state.logged_in:
    show_login()
else:
    page = st.session_state.page
    if page == "profile":
        show_profile()
    elif page == "dashboard":
        show_dashboard()
    else:
        show_chat()
