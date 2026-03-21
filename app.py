import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import streamlit.components.v1 as components

# ── Core & UI ─────────────────────────────────────────────────────────────────
from core.database import init_db, validate_session, load_students, create_session
from ui.login import show_login
from ui.chat import show_chat
from ui.profile import show_profile
from ui.dashboard import show_dashboard
from ui.session import js_save_session
from utils.helpers import PHOTO_PATH, PROF_NAME

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{PROF_NAME} · English",
    page_icon=str(Path(PHOTO_PATH)) if Path(PHOTO_PATH).exists() else "🎓",
    layout="wide",
)

# ── Font Awesome ──────────────────────────────────────────────────────────────
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">',
    unsafe_allow_html=True,
)

# ── CSS global ────────────────────────────────────────────────────────────────
_css_path = Path("styles/style.css")
if _css_path.exists():
    st.markdown(f"<style>{_css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

st.markdown("""<style>
[data-testid="stAppViewBlockContainer"]{opacity:1!important;}
div[data-stale="true"]{opacity:1!important;transition:none!important;}
.stSpinner,[data-testid="stSpinner"]{display:none!important;}
.main .block-container{max-width:100%!important;padding-left:clamp(10px,2vw,40px)!important;padding-right:clamp(10px,2vw,40px)!important;padding-top:1rem!important;}
section[data-testid="stSidebar"]{min-width:220px!important;max-width:340px!important;}
[data-testid="stFileUploader"]{position:fixed!important;bottom:-999px!important;left:-9999px!important;opacity:0!important;width:1px!important;height:1px!important;pointer-events:none!important;overflow:hidden!important;}
[data-testid="stFileUploader"] input[type="file"]{pointer-events:auto!important;}
[data-testid="stAudioInput"]{position:fixed!important;bottom:-9999px!important;left:-9999px!important;opacity:0!important;pointer-events:none!important;width:1px!important;height:1px!important;overflow:hidden!important;}
[data-testid="stAudioInput"] button{pointer-events:auto!important;}
@media(max-width:768px){
    .main .block-container{padding-left:8px!important;padding-right:8px!important;padding-bottom:80px!important;}
    div.bubble{max-width:92%!important;font-size:.82rem!important;}
}
</style>""", unsafe_allow_html=True)

# ── Fix do botão collapsar sidebar ───────────────────────────────────────────
components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
(function(){
  function inject(){
    var doc=window.parent.document;
    if(!doc.getElementById('pav-toggle-style')){
      var s=doc.createElement('style');s.id='pav-toggle-style';
      s.textContent='[data-testid="collapsedControl"]{position:fixed!important;top:10px!important;left:10px!important;z-index:99999!important;}';
      doc.head.appendChild(s);
    }
  }
  inject();setTimeout(inject,500);setTimeout(inject,1500);setInterval(inject,3000);
})();
</script></body></html>""", height=1)

# ── Banco de dados ────────────────────────────────────────────────────────────
init_db()

# ── Roles que têm acesso ao dashboard ────────────────────────────────────────
_DASHBOARD_ROLES = ("professor", "professora", "programador")

# ── Session state defaults ────────────────────────────────────────────────────
_DEFAULTS = {
    "logged_in":        False,
    "user":             None,
    "page":             "chat",
    "speaking":         False,
    "conv_id":          None,
    "voice_mode":       False,
    "staged_file":      None,
    "staged_file_name": None,
    "audio_key":        0,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Restaura sessão via query param (?s=TOKEN) ────────────────────────────────
if not st.session_state.logged_in:
    _s = st.query_params.get("s", "")
    if _s and len(_s) > 10:
        _udata = validate_session(_s)
        if _udata:
            _uname = _udata.get("_resolved_username") or next(
                (k for k, v in load_students().items() if v.get("name") == _udata.get("name")), None
            )
            if _uname:
                st.session_state.logged_in         = True
                st.session_state.user              = {"username": _uname, **_udata}
                # ← CORRIGIDO: usa `in` ao invés de `==`
                st.session_state.page              = "dashboard" if _udata.get("role") in _DASHBOARD_ROLES else "chat"
                st.session_state.conv_id           = None
                st.session_state["_session_token"] = _s
        else:
            st.query_params.pop("s", None)

# ── Mantém token na URL após login ────────────────────────────────────────────
_tok = st.session_state.get("_session_token", "")
if _tok and st.session_state.logged_in:
    if st.query_params.get("s") != _tok:
        st.query_params["s"] = _tok

# ── Salva sessão no localStorage (apenas uma vez por sessão) ──────────────────
if _tok and st.session_state.logged_in and not st.session_state.get("_session_saved"):
    js_save_session(_tok)
    st.session_state["_session_saved"] = True

# ══════════════════════════════════════════════════════════════════════════════
# ROTEAMENTO
# ══════════════════════════════════════════════════════════════════════════════

if not st.session_state.logged_in:
    show_login()
elif st.session_state.page == "profile":
    show_profile()
elif st.session_state.page == "dashboard":
    show_dashboard()
else:
    show_chat()