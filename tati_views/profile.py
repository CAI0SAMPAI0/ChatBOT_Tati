"""
tati_views/profile.py — Teacher Tati · Página de perfil do usuário.
"""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from database import load_students, update_profile, update_password
from ui_helpers import (
    t, get_user_avatar_b64, _avatar_circle_html,
    save_user_avatar, remove_user_avatar, _bump_avatar_version,
)


def show_profile() -> None:
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")

    # File uploader visível nesta página
    st.markdown("""<style>
[data-testid="stFileUploader"] {
    position:static!important; top:auto!important; left:auto!important;
    width:auto!important; height:auto!important;
    overflow:visible!important; opacity:1!important;
    pointer-events:auto!important;
}
[data-testid="stFileUploaderDropzone"] { display:flex!important; visibility:visible!important; }
</style>""", unsafe_allow_html=True)

    # Injeta cores de destaque
    _ac = profile.get("accent_color",      "#f0a500")
    _ub = profile.get("user_bubble_color", "#2d6a4f")
    _ab = profile.get("ai_bubble_color",   "#1a1f2e")
    components.html(f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function(){{
  function hexToRgb(h){{
    h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);return [(n>>16)&255,(n>>8)&255,n&255].join(',');
  }}
  function luminance(h){{
    h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);var r=(n>>16)&255,g=(n>>8)&255,b=n&255;
    return 0.299*r+0.587*g+0.114*b;
  }}
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
    level_opts = ["Beginner","Pre-Intermediate","Intermediate","Business English","Advanced","Native"]
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
            lang = st.selectbox(
                t("interface_lang", ui_lang), ["pt-BR","en-US","en-UK"],
                index=safe_index(["pt-BR","en-US","en-UK"], profile.get("language","pt-BR")),
                key="pf_lang",
            )
        with col2:
            accent = st.color_picker(
                "Cor de destaque (anel / botões)",
                value=profile.get("accent_color","#f0a500"), key="pf_accent",
            )
        col5, col6 = st.columns(2)
        with col5:
            user_bubble_color = st.color_picker(
                "Balão do usuário",
                value=profile.get("user_bubble_color","#2d6a4f"), key="pf_user_bubble",
            )
        with col6:
            ai_bubble_color = st.color_picker(
                "Balão da IA",
                value=profile.get("ai_bubble_color","#1a1f2e"), key="pf_ai_bubble",
            )
        st.markdown("### Voz")
        col3, col4 = st.columns(2)
        with col3:
            voice_lang = st.selectbox(
                t("transcription_lang", ui_lang),
                ["auto (pt+en)","en","pt","es","fr","de"],
                index=safe_index(
                    ["auto (pt+en)","en","pt","es","fr","de"],
                    profile.get("voice_lang","auto (pt+en)"),
                ),
                key="pf_vlang",
            )
        with col4:
            speech_lang = st.selectbox(
                t("tts_accent", ui_lang), ["en-US","en-UK","pt-BR"],
                index=safe_index(["en-US","en-UK","pt-BR"], profile.get("speech_lang","en-US")),
                key="pf_slang",
            )
        if st.button(t("save_general", ui_lang), key="save_geral"):
            update_profile(username, {
                "language": lang, "accent_color": accent,
                "user_bubble_color": user_bubble_color,
                "ai_bubble_color": ai_bubble_color,
                "voice_lang": voice_lang, "speech_lang": speech_lang,
            })
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Settings saved!")

    # ── Aba Personalização ────────────────────────────────────────────────────
    with tab_pers:
        st.markdown("### Sobre Você")
        col1, col2 = st.columns(2)
        with col1:
            nickname   = st.text_input(t("nickname",   ui_lang), value=profile.get("nickname",""),   key="pf_nick")
            occupation = st.text_input(t("occupation", ui_lang), value=profile.get("occupation",""),
                                       placeholder="ex: Professora, Desenvolvedor",              key="pf_occ")
        with col2:
            level = st.selectbox(
                t("english_level", ui_lang), level_opts,
                index=safe_index(level_opts, user.get("level","Beginner")), key="pf_level",
            )
            focus = st.selectbox(
                t("focus", ui_lang), focus_opts,
                index=safe_index(focus_opts, user.get("focus","General Conversation")), key="pf_focus",
            )
        if not is_prof:
            st.markdown("### Estilo da IA")
            col3, col4 = st.columns(2)
            ai_style_opts = ["Warm & Encouraging","Formal & Professional","Fun & Casual","Strict & Direct"]
            ai_tone_opts  = ["Teacher","Conversation Partner","Tutor","Business Coach"]
            with col3:
                ai_style = st.selectbox(
                    t("conv_tone", ui_lang), ai_style_opts,
                    index=safe_index(ai_style_opts, profile.get("ai_style","Warm & Encouraging")),
                    key="pf_aistyle",
                )
            with col4:
                ai_tone = st.selectbox(
                    t("ai_role", ui_lang), ai_tone_opts,
                    index=safe_index(ai_tone_opts, profile.get("ai_tone","Teacher")),
                    key="pf_aitone",
                )
            custom = st.text_area(
                "Instruções personalizadas para a IA",
                value=profile.get("custom_instructions",""),
                placeholder="ex: Sempre me corrija quando eu errar o Past Simple.",
                height=100, key="pf_custom",
            )
        else:
            ai_style = profile.get("ai_style","Warm & Encouraging")
            ai_tone  = profile.get("ai_tone","Teacher")
            custom   = profile.get("custom_instructions","")

        if st.button(t("save_custom", ui_lang), key="save_pers"):
            update_profile(username, {
                "nickname": nickname, "occupation": occupation,
                "ai_style": ai_style, "ai_tone": ai_tone,
                "custom_instructions": custom, "level": level, "focus": focus,
            })
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
                _avatar_circle_html(cur_avatar, size=88) + '<div style="height:8px"></div>',
                unsafe_allow_html=True,
            )
        with col_btns:
            photo_file = st.file_uploader(
                "Alterar foto — JPG, PNG ou WEBP (máx 15 MB)",
                type=["jpg","jpeg","png","webp"], key="pf_photo_upload",
            )
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
            if cur_avatar:
                if st.button(t("remove_photo", ui_lang), key="pf_remove_photo"):
                    remove_user_avatar(username)
                    _bump_avatar_version()
                    st.session_state.pop("_last_photo_saved", None)
                    st.session_state["_photo_msg"] = "removed"
                    st.rerun()

        st.markdown("---")
        st.markdown("### Informações da Conta")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input(t("full_name", ui_lang), value=user.get("name",""), key="pf_fname")
        with col2:
            email = st.text_input(t("email", ui_lang), value=user.get("email",""), key="pf_email")
        st.markdown(f"**Username:** `{username}`")
        st.markdown(f"**Conta criada em:** {user.get('created_at','')[:10]}")
        if st.button(t("save_data", ui_lang), key="save_conta"):
            update_profile(username, {"name": full_name, "email": email})
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Dados atualizados!")

        st.markdown("---")
        st.markdown("### Alterar Senha")
        col3, col4 = st.columns(2)
        with col3:
            new_pw  = st.text_input(t("new_password",     ui_lang), type="password", key="pf_newpw")
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
    is_prof   = user.get("role") == "professor"
    back_page = "dashboard" if is_prof else "chat"
    back_lbl  = "← Voltar ao Dashboard" if is_prof else "← Voltar ao Chat"
    if st.button(back_lbl, key="back_chat"):
        st.session_state.page = back_page; st.rerun()
