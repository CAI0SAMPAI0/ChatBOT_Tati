"""
tati_views/login.py — Teacher Tati · Tela de login / cadastro.

Layout 100% centralizado via CSS puro, sem st.columns.
Funciona em mobile e desktop. Tema: dourado/laranja.
"""

import streamlit as st
import streamlit.components.v1 as components

from database import (
    authenticate, register_student, create_session,
    validate_session, load_students,
)
from ui_helpers import PROF_NAME, get_photo_b64, t, js_save_session, js_clear_session


def show_login() -> None:

    # ── CSS: zera padding + estilo dourado/laranja ────────────────────────────
    st.markdown("""<style>
[data-testid="stSidebar"]    { display:none!important; }
[data-testid="stHeader"]     { display:none!important; }
[data-testid="stToolbar"]    { display:none!important; }
[data-testid="stDecoration"] { display:none!important; }
footer                       { display:none!important; }
.stApp                       { background:#060a10!important; }

/* Zera padding do container principal */
.main .block-container,
section[data-testid="stMain"] > div,
section[data-testid="stMain"] > div > div > div {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}

/* Centraliza e limita largura — sem st.columns */
section[data-testid="stMain"] > div > div {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    min-height: 100vh !important;
    justify-content: center !important;
}
div[data-testid="stVerticalBlock"] {
    width: 100% !important;
    max-width: 420px !important;
    margin: 0 auto !important;
    padding: 0 16px !important;
}

/* Inputs */
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

/* Botão submit */
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

/* Botões de aba */
div[data-testid="stButton"] button {
    border-radius:10px!important; font-size:.82rem!important;
    font-weight:600!important; transition:all .2s!important;
    border:1px solid #2a2a3a!important;
}
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stButton"] button[data-testid="baseButton-primary"] {
    background:linear-gradient(135deg,#f0a500,#e05c2a)!important;
    border-color:#e09000!important; color:#060a10!important;
    font-weight:800!important;
    box-shadow:0 0 14px rgba(240,165,0,.35)!important;
}

[data-testid="InputInstructions"] { display:none!important; }
iframe[height="1"] {
    position:fixed!important; opacity:0!important;
    pointer-events:none!important; bottom:0!important; left:0!important;
}
</style>""", unsafe_allow_html=True)

    # ── Auto-login via localStorage / cookie ──────────────────────────────────
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
(function(){
    function readToken(){
        try{var v=window.parent.localStorage.getItem('pav_session');if(v&&v.length>10)return v;}catch(e){}
        try{var v2=localStorage.getItem('pav_session');if(v2&&v2.length>10)return v2;}catch(e){}
        try{var m=window.parent.document.cookie.split(';').map(function(c){return c.trim();})
            .find(function(c){return c.startsWith('pav_session=');});
            if(m){var val=decodeURIComponent(m.split('=')[1]);if(val&&val.length>10)return val;}}catch(e){}
        try{var m2=document.cookie.split(';').map(function(c){return c.trim();})
            .find(function(c){return c.startsWith('pav_session=');});
            if(m2){var val2=decodeURIComponent(m2.split('=')[1]);if(val2&&val2.length>10)return val2;}}catch(e){}
        return '';
    }
    var val=readToken();
    if(!val)return;
    var url=new URL(window.parent.location.href);
    var isToken=val.length>20;
    var paramKey=isToken?'_token':'_u';
    if(url.searchParams.get(paramKey)!==val){
        url.searchParams.set(paramKey,val);
        window.parent.location.replace(url.toString());
    }
})();
</script></body></html>""", height=1)

    # ── Auto-login por query param ────────────────────────────────────────────
    params = st.query_params
    if "_token" in params:
        token = params["_token"]
        udata = validate_session(token)
        if udata:
            uname = udata.get("_resolved_username") or next(
                (k for k, v in load_students().items() if v["password"] == udata["password"]),
                None,
            )
            if uname:
                st.session_state.update(
                    logged_in=True,
                    user={"username": uname, **udata},
                    page="dashboard" if udata["role"] == "professor" else "chat",
                    conv_id=None,
                    _session_token=token,
                    _session_saved=True,
                )
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
            st.session_state.update(
                logged_in=True,
                user={"username": uname, **udata},
                page="dashboard" if udata["role"] == "professor" else "chat",
                conv_id=None,
                _session_token=token,
                _session_saved=True,
            )
            js_save_session(token)
            st.query_params.clear()
            st.rerun()

    if "_login_tab" not in st.session_state:
        st.session_state["_login_tab"] = "login"

    # ── Header visual: card com avatar + nome ─────────────────────────────────
    photo_src   = get_photo_b64() or ""
    avatar_block = (
        f'<div style="background:url({photo_src}) center top/cover no-repeat;'
        f'width:88px;height:88px;border-radius:50%;display:block;margin:0 auto 18px;'
        f'border:2.5px solid #f0a500;flex-shrink:0;'
        f'box-shadow:0 0 0 6px rgba(240,165,0,.1),0 0 36px rgba(240,165,0,.22);"></div>'
        if photo_src else
        '<div style="width:88px;height:88px;border-radius:50%;margin:0 auto 18px;'
        'background:linear-gradient(135deg,#f0a500,#e05c2a);display:flex;'
        'align-items:center;justify-content:center;font-size:40px;'
        'box-shadow:0 0 0 6px rgba(240,165,0,.1),0 0 36px rgba(240,165,0,.22);">🧑‍🏫</div>'
    )

    components.html(f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;700;800&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{
    background:#060a10;font-family:'Sora',sans-serif;
    width:100%;height:100%;overflow:hidden;
    display:flex;align-items:center;justify-content:center;
}}
.bg{{position:fixed;inset:0;background:#060a10;overflow:hidden;pointer-events:none;}}
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
.wrap{{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;width:100%;}}
.card{{position:relative;z-index:1;
       background:linear-gradient(180deg,#0f1824,#0a1020);
       border:1px solid #1a2535;border-radius:24px;
       padding:36px 32px 28px;width:calc(100% - 32px);max-width:420px;
       box-shadow:0 32px 80px rgba(0,0,0,.65),0 0 0 1px rgba(255,255,255,.03);}}
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
    {avatar_block}
    <h2>{PROF_NAME}</h2>
    <p>Your personal English practice companion</p>
    <div class="line"></div>
  </div>
</div>
</body></html>""", height=280, scrolling=False)

    # ── Feedback ──────────────────────────────────────────────────────────────
    login_err = st.session_state.pop("_login_err", "")
    reg_err   = st.session_state.pop("_reg_err",   "")
    reg_ok    = st.session_state.pop("_reg_ok",    False)
    reg_name  = st.session_state.pop("_reg_name",  "")
    if login_err: st.error(f"❌ {login_err}")
    if reg_err:   st.error(f"❌ {reg_err}")
    if reg_ok:    st.success(f"✅ Conta criada! Bem-vindo(a), {reg_name}! Faça login.")

    # ── Abas ──────────────────────────────────────────────────────────────────
    tab = st.session_state["_login_tab"]
    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("enter"), use_container_width=True, key="tab_btn_login",
                     type="primary" if tab == "login" else "secondary"):
            st.session_state["_login_tab"] = "login"; st.rerun()
    with c2:
        if st.button(t("create_account"), use_container_width=True, key="tab_btn_reg",
                     type="primary" if tab == "reg" else "secondary"):
            st.session_state["_login_tab"] = "reg"; st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Formulário Login ──────────────────────────────────────────────────────
    if tab == "login":
        with st.form("form_login", clear_on_submit=True):
            u = st.text_input(t("username"), placeholder="seu.usuario", key="li_u")
            p = st.text_input(t("password"), type="password", placeholder="••••••••", key="li_p")
            if st.form_submit_button("Entrar →", use_container_width=True):
                if not u or not p:
                    st.session_state["_login_err"] = "Preencha todos os campos."
                    st.rerun()
                else:
                    user = authenticate(u, p)
                    if user:
                        real_u = user.get("_resolved_username", u.lower())
                        token  = create_session(real_u)
                        st.session_state.update(
                            logged_in=True,
                            user={"username": real_u, **user},
                            page="dashboard" if user["role"] == "professor" else "chat",
                            conv_id=None,
                            _session_token=token,
                            _session_saved=True,
                        )
                        js_save_session(token)
                        st.rerun()
                    else:
                        st.session_state["_login_err"] = "Usuário ou senha incorretos."
                        st.rerun()

    # ── Formulário Registro ───────────────────────────────────────────────────
    else:
        with st.form("form_reg", clear_on_submit=False):
            rn  = st.text_input(t("full_name"),  placeholder="João Silva",     key="r_n")
            re_ = st.text_input(t("email"),      placeholder="joao@email.com", key="r_e")
            ru  = st.text_input(t("username"),   placeholder="joao.silva",     key="r_u")
            rp  = st.text_input("Senha", type="password",
                                placeholder="mínimo 6 caracteres",             key="r_p")
            if st.form_submit_button("Criar Conta →", use_container_width=True):
                if not rn or not re_ or not ru or not rp:
                    st.error("❌ Preencha todos os campos.")
                elif "@" not in re_:
                    st.error("❌ E-mail inválido.")
                elif len(rp) < 6:
                    st.error("❌ Senha muito curta (mínimo 6 caracteres).")
                else:
                    ok, msg = register_student(ru, rn, rp, email=re_)
                    if ok:
                        st.session_state["_reg_ok"]    = True
                        st.session_state["_reg_name"]  = rn
                        st.session_state["_login_tab"] = "login"
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    st.markdown(
        f'<p style="text-align:center;font-size:.65rem;color:#1a2535;margin-top:16px;">'
        f'© 2025 · {PROF_NAME} · AI English Coach</p>',
        unsafe_allow_html=True,
    )
