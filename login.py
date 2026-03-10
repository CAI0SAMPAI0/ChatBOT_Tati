"""
tati_views/login.py — Tela de login / cadastro.
Layout 100% centralizado, sem st.columns, funciona mobile e desktop.
Integra auto-login via ?s= token (compatível com app.py).
"""

import streamlit as st
import streamlit.components.v1 as components

from database import authenticate, register_student, create_session, validate_session, load_students
from ui_helpers import PROF_NAME, get_photo_b64, t, js_save_session, js_clear_session


def show_login() -> None:
    photo_src = get_photo_b64() or ""

    # ── Auto-login via ?s= token na URL (compatível com app.py) ─────────────
    params = st.query_params
    if "s" in params:
        token = params["s"]
        udata = validate_session(token)
        if udata:
            uname = udata.get("_resolved_username") or next(
                (k for k, v in load_students().items() if v.get("password") == udata.get("password")),
                None,
            )
            if uname:
                st.session_state.update(
                    logged_in=True,
                    user={"username": uname, **udata},
                    page="dashboard" if udata.get("role") == "professor" else "voice",
                    conv_id=None,
                )
                st.session_state["_session_token"] = token
                st.session_state["_session_saved"] = True
                st.query_params.clear()
                st.rerun()
        else:
            js_clear_session()
            st.query_params.clear()

    # ── CSS global da tela de login ──────────────────────────────────────────
    st.markdown("""<style>
[data-testid='stSidebar']{display:none!important;}
#MainMenu,footer,header{display:none!important;}
[data-testid="stToolbar"]{display:none!important;}
[data-testid="stDecoration"]{display:none!important;}
.stApp{background:#060a10!important;}
section[data-testid="stMain"],
section[data-testid="stMain"]>div,
.main .block-container{
    padding:0!important;margin:0!important;
    max-width:100%!important;width:100%!important;
}
/* Botões de aba secundários */
div[data-testid="stButton"]>button{
    border-radius:10px!important;font-weight:600!important;
    border:1px solid #2a2a4a!important;
    background:transparent!important;color:#6b7280!important;
    transition:all .2s!important;
}
/* Botão de aba ativo (primary) */
div[data-testid="stButton"]>button[kind="primary"],
div[data-testid="stButton"]>button[data-testid="baseButton-primary"]{
    background:linear-gradient(135deg,#6c3fc5,#8b5cf6)!important;
    border-color:#7c4dcc!important;color:#fff!important;
    box-shadow:0 0 14px rgba(139,92,246,.35)!important;
}
/* Botão submit do form */
div[data-testid="stFormSubmitButton"]>button{
    background:linear-gradient(135deg,#6c3fc5,#8b5cf6)!important;
    border:1px solid #7c4dcc!important;color:#fff!important;
    border-radius:10px!important;font-weight:700!important;
    box-shadow:0 0 14px rgba(139,92,246,.3)!important;
    width:100%!important;padding:12px!important;
    transition:all .25s!important;
}
div[data-testid="stFormSubmitButton"]>button:hover{
    background:linear-gradient(135deg,#7c4dcc,#9d6ff7)!important;
    box-shadow:0 0 22px rgba(139,92,246,.5)!important;
    transform:translateY(-1px)!important;
}
/* Inputs */
.stTextInput label{
    font-size:.7rem!important;color:#4a5a6a!important;
    font-weight:700!important;text-transform:uppercase!important;
    letter-spacing:1px!important;
}
.stTextInput input{
    background:rgba(255,255,255,.04)!important;
    border:1px solid #1e2a3a!important;border-radius:10px!important;
    color:#e6edf3!important;font-size:.88rem!important;
    transition:border-color .2s,box-shadow .2s!important;
}
.stTextInput input:focus{
    border-color:#8b5cf6!important;
    box-shadow:0 0 0 3px rgba(139,92,246,.12)!important;
}
/* Iframes fantasma */
iframe[height="1"]{
    position:fixed!important;opacity:0!important;
    pointer-events:none!important;bottom:0!important;left:0!important;
}
/* Centraliza bloco verticalmente */
section[data-testid="stMain"]>div>div>div{
    display:flex!important;
    flex-direction:column!important;
    align-items:center!important;
}
div[data-testid="stVerticalBlock"]{
    width:100%!important;
    max-width:420px!important;
    margin:0 auto!important;
    padding:0 16px!important;
}
[data-testid="InputInstructions"]{display:none!important;}
</style>""", unsafe_allow_html=True)

    # ── Auto-login via localStorage / cookie ─────────────────────────────────
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
(function(){
    function readToken(){
        try{var s=window.parent.localStorage.getItem('pav_session');if(s&&s.length>10)return s;}catch(e){}
        try{var s2=localStorage.getItem('pav_session');if(s2&&s2.length>10)return s2;}catch(e){}
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

    # ── Avatar HTML ──────────────────────────────────────────────────────────
    if photo_src:
        av_html = (
            f'<div class="av" style="background:url({photo_src}) center top/cover no-repeat;'
            f'width:90px;height:90px;border-radius:50%;display:block;margin-bottom:12px;'
            f'border:2.5px solid #8b5cf6;'
            f'box-shadow:0 0 0 6px rgba(139,92,246,.12),0 0 28px rgba(139,92,246,.25);'
            f'flex-shrink:0;"></div>'
        )
    else:
        av_html = '<div class="av-emoji" id="avE">&#129489;&#8203;&#127979;</div>'

    # ── Card visual animado (avatar + nome) ──────────────────────────────────
    components.html(f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;700;800&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{
    background:#060a10;font-family:'Sora',sans-serif;
    width:100%;height:100%;overflow:hidden;
    display:flex;align-items:center;justify-content:center;
}}
/* Orbs de fundo */
.bg{{position:fixed;inset:0;background:#060a10;overflow:hidden;pointer-events:none;}}
.orb1{{position:absolute;width:400px;height:400px;border-radius:50%;
       background:radial-gradient(circle,rgba(139,92,246,.12),transparent 70%);
       top:-120px;right:-100px;animation:d1 12s ease-in-out infinite alternate;}}
.orb2{{position:absolute;width:320px;height:320px;border-radius:50%;
       background:radial-gradient(circle,rgba(108,63,197,.08),transparent 70%);
       bottom:-80px;left:-80px;animation:d2 12s ease-in-out infinite alternate;}}
@keyframes d1{{from{{transform:translate(0,0);}}to{{transform:translate(20px,14px) scale(1.04);}}}}
@keyframes d2{{from{{transform:translate(0,0);}}to{{transform:translate(-14px,10px) scale(1.03);}}}}
.card{{
    position:relative;z-index:1;
    background:linear-gradient(180deg,#0f1824,#0a1020);
    border:1px solid #1a2535;border-radius:24px;
    padding:28px 24px 20px;width:100%;max-width:420px;
    box-shadow:0 24px 64px rgba(0,0,0,.7);
    display:flex;flex-direction:column;align-items:center;
}}
.av-emoji{{
    width:90px;height:90px;border-radius:50%;
    background:linear-gradient(135deg,#6c3fc5,#8b5cf6);
    display:flex;align-items:center;justify-content:center;
    font-size:38px;margin-bottom:12px;
    box-shadow:0 0 0 6px rgba(139,92,246,.12),0 0 28px rgba(139,92,246,.25);
}}
h2{{
    font-size:1.35rem;font-weight:800;text-align:center;margin:0 0 3px;
    background:linear-gradient(135deg,#8b5cf6 30%,#c084fc 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}}
p{{font-size:.7rem;color:#3a4e5e;text-align:center;}}
.line{{width:36px;height:2px;background:linear-gradient(90deg,#8b5cf6,#c084fc);
       border-radius:2px;margin:10px auto 0;opacity:.5;}}
</style></head><body>
<div class="bg"><div class="orb1"></div><div class="orb2"></div></div>
<div class="card">
    {av_html}
    <h2>{PROF_NAME}</h2>
    <p>Voice English Coach</p>
    <div class="line"></div>
</div>
</body></html>""", height=220, scrolling=False)

    # ── Mensagens de feedback ────────────────────────────────────────────────
    login_err = st.session_state.pop("_login_err", "")
    reg_err   = st.session_state.pop("_reg_err",   "")
    reg_ok    = st.session_state.pop("_reg_ok",    False)
    reg_name  = st.session_state.pop("_reg_name",  "")
    if login_err: st.error(f"❌ {login_err}")
    if reg_err:   st.error(f"❌ {reg_err}")
    if reg_ok:    st.success(f"✅ Conta criada! Bem-vindo(a), {reg_name}!")

    # ── Abas Entrar / Criar Conta ────────────────────────────────────────────
    tab = st.session_state["_login_tab"]
    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("enter"), use_container_width=True, key="tab_login",
                     type="primary" if tab == "login" else "secondary"):
            st.session_state["_login_tab"] = "login"
            st.rerun()
    with c2:
        if st.button(t("create_account"), use_container_width=True, key="tab_reg",
                     type="primary" if tab == "reg" else "secondary"):
            st.session_state["_login_tab"] = "reg"
            st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Formulário LOGIN ─────────────────────────────────────────────────────
    if tab == "login":
        with st.form("form_login", clear_on_submit=True):
            u = st.text_input(t("username"), placeholder="seu.usuario")
            p = st.text_input(t("password"), type="password", placeholder="••••••••")
            if st.form_submit_button(t("enter"), use_container_width=True):
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
                            page="dashboard" if user["role"] == "professor" else "voice",
                            conv_id=None,
                        )
                        token = create_session(real_u)
                        st.session_state["_session_token"] = token
                        st.session_state["_session_saved"] = True
                        js_save_session(token)
                        st.rerun()
                    else:
                        st.session_state["_login_err"] = "Usuário ou senha incorretos."
                        st.rerun()

    # ── Formulário REGISTRO ──────────────────────────────────────────────────
    else:
        with st.form("form_reg", clear_on_submit=True):
            rn  = st.text_input(t("full_name"),  placeholder="João Silva")
            re_ = st.text_input(t("email"),      placeholder="joao@email.com")
            ru  = st.text_input(t("username"),   placeholder="joao.silva")
            rp  = st.text_input("Senha", type="password", placeholder="mínimo 6 caracteres")
            if st.form_submit_button(t("create_account"), use_container_width=True):
                if not rn or not re_ or not ru or not rp:
                    st.session_state["_reg_err"] = "Preencha todos os campos."
                    st.rerun()
                elif "@" not in re_:
                    st.session_state["_reg_err"] = "E-mail inválido."
                    st.rerun()
                elif len(rp) < 6:
                    st.session_state["_reg_err"] = "Senha muito curta (mínimo 6)."
                    st.rerun()
                else:
                    ok, msg = register_student(ru, rn, rp, email=re_)
                    if ok:
                        st.session_state["_reg_ok"]    = True
                        st.session_state["_reg_name"]  = rn
                        st.session_state["_login_tab"] = "login"
                        st.rerun()
                    else:
                        st.session_state["_reg_err"] = msg
                        st.rerun()

    st.markdown(
        f'<p style="text-align:center;font-size:.6rem;color:#1a2535;margin-top:14px;">'
        f'2025 © {PROF_NAME}</p>',
        unsafe_allow_html=True,
    )
