import os
import streamlit as st
import streamlit.components.v1 as components
from core.database import authenticate, register_student, create_session
from core.auth import is_rate_limited, register_attempt, clear_attempts, remaining_attempts
from utils.helpers import get_photo_b64, PROF_NAME
from utils.i18n import t


PHOTO_PATH = os.getenv("PROFESSOR_PHOTO", "assets/tati.png")

_DASHBOARD_ROLES = ("professor", "professora", "programador")


def js_save_session(token: str) -> None:
    components.html(
        f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function() {{
    var t = '{token}';
    try {{ window.parent.localStorage.setItem('pav_session', t); }} catch(e) {{}}
    try {{
        var exp = new Date(Date.now()+2592000000).toUTCString();
        window.parent.document.cookie = 'pav_session='+encodeURIComponent(t)+';expires='+exp+';path=/;SameSite=Lax';
    }} catch(e) {{}}
}})();
</script></body></html>""",
        height=1,
    )


def show_login() -> None:
    photo_src = get_photo_b64() or ""

    st.markdown("""<style>
[data-testid='stSidebar']{display:none!important;}
#MainMenu,footer,header{display:none!important;}
[data-testid="stToolbar"],[data-testid="stHeader"],[data-testid="stDecoration"]{display:none!important;}
.stApp{background:#060a10!important;}
section[data-testid="stMain"],
section[data-testid="stMain"]>div,
.main .block-container{padding:0!important;margin:0!important;max-width:100%!important;width:100%!important;}
div[data-testid="stButton"]>button{border-radius:10px!important;font-weight:600!important;border:1px solid #2a2a4a!important;background:transparent!important;color:#6b7280!important;}
div[data-testid="stButton"]>button[kind="primary"],
div[data-testid="stButton"]>button[data-testid="baseButton-primary"]{background:linear-gradient(135deg,#6c3fc5,#8b5cf6)!important;border-color:#7c4dcc!important;color:#fff!important;box-shadow:0 0 14px rgba(139,92,246,.35)!important;}
div[data-testid="stFormSubmitButton"]>button{background:linear-gradient(135deg,#6c3fc5,#8b5cf6)!important;border:1px solid #7c4dcc!important;color:#fff!important;border-radius:10px!important;font-weight:700!important;box-shadow:0 0 14px rgba(139,92,246,.3)!important;}
div[data-testid="stFormSubmitButton"]>button:hover{background:linear-gradient(135deg,#7c4dcc,#9d6ff7)!important;box-shadow:0 0 22px rgba(139,92,246,.5)!important;}
iframe[height="1"]{position:fixed!important;opacity:0!important;pointer-events:none!important;bottom:0!important;left:0!important;}
section[data-testid="stMain"]>div>div>div{display:flex!important;flex-direction:column!important;align-items:center!important;}
div[data-testid="stVerticalBlock"]{width:100%!important;max-width:420px!important;margin:0 auto!important;padding:0 16px!important;}
</style>""", unsafe_allow_html=True)

    # Auto-login via localStorage
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
(function(){
    function readToken(){
        try{var s=window.parent.localStorage.getItem('pav_session');if(s&&s.length>10)return s;}catch(e){}
        try{var m=window.parent.document.cookie.split(';').map(function(c){return c.trim();})
            .find(function(c){return c.startsWith('pav_session=');});
            if(m){var v=decodeURIComponent(m.split('=')[1]);if(v&&v.length>10)return v;}}catch(e){}
        return '';
    }
    var val=readToken();
    if(!val)return;
    var url=new URL(window.parent.location.href);
    if(url.searchParams.get('s')!==val){
        url.searchParams.set('s',val);
        window.parent.location.replace(url.toString());
    }
})();
</script></body></html>""", height=1)

    if "_login_tab" not in st.session_state:
        st.session_state["_login_tab"] = "login"

    # Card visual
    av_html = (
        f'<img class="av" src="{photo_src}" alt="{PROF_NAME}" onerror="this.style.display=\'none\';">'
        if photo_src else '<div class="av-emoji">&#129489;&#8203;&#127979;</div>'
    )

    components.html(f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;700;800&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:#060a10;font-family:'Sora',sans-serif;width:100%;height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center;}}
.card{{background:linear-gradient(180deg,#0f1824,#0a1020);border:1px solid #1a2535;border-radius:24px;padding:28px 24px 20px;width:100%;box-shadow:0 24px 64px rgba(0,0,0,.7);display:flex;flex-direction:column;align-items:center;}}
.av{{width:90px;height:90px;border-radius:50%;object-fit:cover;object-position:top center;border:2.5px solid #8b5cf6;box-shadow:0 0 0 6px rgba(139,92,246,.12),0 0 28px rgba(139,92,246,.25);display:block;margin-bottom:12px;}}
.av-emoji{{width:90px;height:90px;border-radius:50%;background:linear-gradient(135deg,#6c3fc5,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:38px;margin-bottom:12px;}}
h2{{font-size:1.35rem;font-weight:800;text-align:center;margin:0 0 3px;background:linear-gradient(135deg,#8b5cf6 30%,#c084fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
p{{font-size:.7rem;color:#3a4e5e;text-align:center;}}
</style></head><body>
<div class="card">
    {av_html}
    <h2>{PROF_NAME}</h2>
    <p>Voice English Coach</p>
</div>
</body></html>""", height=220, scrolling=False)

    # Feedback
    login_err = st.session_state.pop("_login_err", "")
    reg_err   = st.session_state.pop("_reg_err",   "")
    reg_ok    = st.session_state.pop("_reg_ok",    False)
    reg_name  = st.session_state.pop("_reg_name",  "")
    if login_err: st.error(f"❌ {login_err}")
    if reg_err:   st.error(f"❌ {reg_err}")
    if reg_ok:    st.success(f"✅ Conta criada! Bem-vindo(a), {reg_name}!")

    # Abas
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
                    st.session_state["_login_err"] = "Preencha todos os campos."
                    st.rerun()
                elif is_rate_limited(u.lower()):
                    from core.auth import seconds_until_unlock
                    secs = seconds_until_unlock(u.lower())
                    st.session_state["_login_err"] = f"Muitas tentativas. Aguarde {secs}s."
                    st.rerun()
                else:
                    user = authenticate(u, p)
                    if user:
                        real_u = user.get("_resolved_username", u.lower())
                        clear_attempts(real_u)
                        # ← CORRIGIDO: usa `in` para incluir "programador"
                        page = "dashboard" if user["role"] in _DASHBOARD_ROLES else "chat"
                        st.session_state.update(
                            logged_in=True,
                            user={"username": real_u, **user},
                            page=page,
                            conv_id=None,
                        )
                        token = create_session(real_u)
                        st.session_state["_session_token"] = token
                        st.session_state["_session_saved"] = True
                        js_save_session(token)
                        st.rerun()
                    else:
                        register_attempt(u.lower())
                        rem = remaining_attempts(u.lower())
                        msg = "Usuário ou senha incorretos."
                        MAX_ATTEMPTS = 5
                        if rem < MAX_ATTEMPTS:
                            msg += f" ({rem} tentativa(s) restante(s))"
                        st.session_state["_login_err"] = msg
                        st.rerun()
    else:
        with st.form("form_reg", clear_on_submit=True):
            rn  = st.text_input(t("full_name"),  placeholder="João Silva")
            re_ = st.text_input(t("email"),      placeholder="joao@email.com")
            ru  = st.text_input(t("username"),   placeholder="joao.silva")
            rp  = st.text_input("Senha", type="password", placeholder="mínimo 6 caracteres")
            if st.form_submit_button(t("create_account"), use_container_width=True):
                if not rn or not re_ or not ru or not rp:
                    st.session_state["_reg_err"] = "Preencha todos os campos."
                elif "@" not in re_ or "." not in re_.split("@")[-1]:
                    st.session_state["_reg_err"] = "E-mail inválido."
                elif len(rp) < 6:
                    st.session_state["_reg_err"] = "Senha muito curta (mínimo 6)."
                else:
                    ok, msg = register_student(ru, rn, rp, email=re_)
                    if ok:
                        st.session_state["_reg_ok"]    = True
                        st.session_state["_reg_name"]  = rn
                        st.session_state["_login_tab"] = "login"
                    else:
                        st.session_state["_reg_err"] = msg
                st.rerun()

    st.markdown(
        f'<p style="text-align:center;font-size:.6rem;color:#1a2535;margin-top:14px;">'
        f'2025 © {PROF_NAME}</p>',
        unsafe_allow_html=True)