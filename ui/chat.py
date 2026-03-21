'''"""
ui/chat.py — Tela principal de chat do Teacher Tati.
"""

import base64
import html
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core.database import (
    new_conversation, list_conversations, load_conversation,
    cached_load_conversation, append_message, delete_conversation, delete_session,
)
from core.ai import send_to_claude
from core.audio import transcribe_bytes
from core.file_handler import extract_file
from utils.helpers import (
    avatar_html, get_tati_mini_b64, _avatar_circle_html,
    get_user_avatar_b64, PROF_NAME,
)
from utils.i18n import t
from ui.session import js_clear_session, js_save_session


# ── Helpers internos ──────────────────────────────────────────────────────────

def get_or_create_conv(username: str) -> str:
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id


def user_avatar_html(username: str, size: int = 36) -> str:
    return _avatar_circle_html(
        get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v", 0)), size
    )


def _logout():
    token = st.session_state.get("_session_token", "")
    if token:
        delete_session(token)
    js_clear_session()
    st.session_state.pop("_session_token", None)
    st.session_state.pop("_session_saved", None)
    st.session_state.update(logged_in=False, user=None, conv_id=None)


def _process_and_send_file(
    username: str, user: dict, conv_id: str,
    raw: bytes, filename: str, extra_text: str = "",
) -> bool:
    result = extract_file(raw, filename)
    kind   = result["kind"]

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
        if not extracted: st.warning(f"Sem texto em '{filename}'."); return False
        preview      = extracted[:200].replace('\n', ' ')
        user_display = f"[{result['label']}: '{filename}'] — {preview}{'…' if len(extracted) > 200 else ''}"
        if extra_text: user_display = f"{extra_text}\n\n{user_display}"
        claude_msg   = f"[{result['label']}: '{filename}']\n\n{extracted}\n\nPlease help me understand this content."
        if extra_text: claude_msg = f"{extra_text}\n\n{claude_msg}"
        append_message(username, conv_id, "user", user_display)
        st.session_state.speaking = True
        try:   send_to_claude(username, user, conv_id, claude_msg)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        return True

    elif kind == "image":
        user_display = f"[Imagem: '{filename}']"
        if extra_text: user_display = f"{extra_text}\n\n{user_display}"
        claude_msg = f"[Imagem: '{filename}']\nPlease look at this image and help me learn English from it."
        if extra_text: claude_msg = f"{extra_text}\n\n{claude_msg}"
        append_message(username, conv_id, "user", user_display)
        st.session_state.speaking = True
        try:
            send_to_claude(username, user, conv_id, claude_msg,
                           image_b64=result["b64"], image_media_type=result["media_type"])
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        return True

    st.warning(f"⚠️ Formato '{result['label']}' não suportado.")
    return False


def render_audio_player(tts_b64: str, msg_time: str, player_id: str) -> str:
    return f"""<!DOCTYPE html><html><head>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:transparent;font-family:'Sora',sans-serif;overflow:hidden;}}
.player{{display:flex;align-items:center;gap:8px;padding:3px 0;flex-wrap:nowrap;}}
.tl{{font-size:.62rem;color:#8b949e;font-family:'JetBrains Mono',monospace;flex-shrink:0;}}
.pb{{background:none;border:1px solid #30363d;border-radius:20px;color:#f0a500;font-size:.75rem;padding:2px 10px;cursor:pointer;transition:background .15s;white-space:nowrap;flex-shrink:0;}}
.pb:hover{{background:rgba(240,165,0,.12);border-color:#f0a500;}}
.pw{{flex:1;min-width:60px;height:3px;background:#30363d;border-radius:2px;cursor:pointer;}}
.pf{{height:100%;background:linear-gradient(90deg,#f0a500,#e05c2a);border-radius:2px;width:0%;transition:width .1s linear;pointer-events:none;}}
.sw{{display:flex;align-items:center;gap:3px;flex-shrink:0;}}
.sb{{background:none;border:1px solid #30363d;border-radius:4px;color:#8b949e;font-size:.65rem;padding:1px 5px;cursor:pointer;transition:all .15s;}}
.sb:hover,.sb.on{{border-color:#f0a500;color:#f0a500;background:rgba(240,165,0,.08);}}
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
</div>
<script>
(function(){{
  var audio=new Audio('data:audio/mpeg;base64,{tts_b64}');
  audio.preload='metadata';
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


# ══════════════════════════════════════════════════════════════════════════════
# SHOW CHAT
# ══════════════════════════════════════════════════════════════════════════════

def show_chat() -> None:
    from ui.voice import show_voice

    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")
    conv_id  = get_or_create_conv(username)
    messages = cached_load_conversation(username, conv_id)
    speaking = st.session_state.speaking

    if st.session_state.voice_mode:
        show_voice(); return

    _ac = profile.get("accent_color", "#f0a500")
    _ub = profile.get("user_bubble_color", "#2d6a4f")
    _ab = profile.get("ai_bubble_color", "#1a1f2e")
    _inject_colors(_ac, _ub, _ab)

    st.markdown("""<style>
[data-testid="stChatInput"] textarea{max-height:120px!important;min-height:44px!important;font-size:.88rem!important;}
[data-testid="stChatInputContainer"]{padding:6px 10px!important;}
.main .block-container{padding-bottom:80px!important;}
.msg-row{display:flex;align-items:flex-end;gap:10px;margin:6px 0;}
.msg-row.user-row{flex-direction:row-reverse;}
.msg-row.user-row>div{display:flex;flex-direction:column;align-items:flex-end;}
.msg-row.bot-row>div{display:flex;flex-direction:column;align-items:flex-start;}
.msg-bubble{padding:10px 15px;border-radius:18px;font-size:.88rem;line-height:1.6;word-break:normal;overflow-wrap:break-word;white-space:pre-wrap;}
.msg-bubble.user{max-width:75%;background:var(--user-bubble-bg,#2d6a4f);color:var(--user-bubble-text,#d8f3dc);border-bottom-right-radius:4px;}
.msg-bubble.bot{max-width:75%;background:var(--ai-bubble-bg,#1a1f2e);color:var(--ai-bubble-text,#e6edf3);border:1px solid var(--ai-bubble-border,#252d3d);border-bottom-left-radius:4px;}
.msg-av{width:30px;height:30px;border-radius:50%;overflow:hidden;flex-shrink:0;margin-bottom:2px;}
.msg-time{font-size:.6rem;color:#4a5a6a;margin:2px 4px 0;text-align:right;}
.bot-row .msg-time{text-align:left;}
.msg-ouvir-row{padding:2px 0 0 40px;}
.msg-ouvir-btn{background:none;border:1px solid #30363d;border-radius:16px;color:#8b949e;font-size:.68rem;padding:2px 10px;cursor:pointer;transition:all .15s;white-space:nowrap;font-family:inherit;}
.msg-ouvir-btn:hover{border-color:#f0a500;color:#f0a500;}
.conv-picker{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:6px 8px;margin:2px 0 6px 0;}
@media(max-width:768px){.msg-bubble{max-width:88%!important;font-size:.82rem!important;}}
</style>""", unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""<div style="padding:14px 14px 10px;border-bottom:1px solid #21262d;flex-shrink:0;">
            <div style="display:flex;align-items:center;gap:10px;">
                {avatar_html(40)}<div>
                <div style="font-weight:600;font-size:.88rem;">{PROF_NAME}</div>
                <div style="font-size:.68rem;color:#8b949e;">Online</div>
                </div></div></div>""", unsafe_allow_html=True)

        if st.button(t("new_conv", ui_lang), use_container_width=True, key="btn_new"):
            st.session_state.conv_id = new_conversation(username)
            st.session_state.pop("_conv_pick", None)
            st.rerun()
        if st.button(t("voice_mode", ui_lang), use_container_width=True, key="btn_voice"):
            st.session_state.voice_mode = True; st.rerun()

        st.markdown('<div style="font-size:.68rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px;padding:10px 4px 4px;">Conversas</div>', unsafe_allow_html=True)

        convs = list_conversations(username)
        if not convs:
            st.markdown('<div style="font-size:.78rem;color:#8b949e;padding:6px 4px;">Nenhuma conversa ainda.</div>', unsafe_allow_html=True)

        for c in convs:
            is_active = c["id"] == conv_id
            is_picked = st.session_state.get("_conv_pick") == c["id"]
            label     = ("▶ " if is_active else "") + c["title"]

            col_conv, col_del = st.columns([5, 1])
            with col_conv:
                if st.button(label, key=f"conv_{c['id']}", use_container_width=True):
                    if is_picked:
                        # segundo clique fecha o picker
                        st.session_state.pop("_conv_pick", None)
                    else:
                        st.session_state["_conv_pick"] = c["id"]
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{c['id']}"):
                    delete_conversation(username, c["id"])
                    if st.session_state.conv_id == c["id"]:
                        st.session_state.conv_id = None
                    st.session_state.pop("_conv_pick", None)
                    st.rerun()

            st.markdown(
                f'<div style="font-size:.62rem;color:#6e7681;margin:-10px 0 2px 6px;">'
                f'{c["date"]} · {c["count"]} msg</div>',
                unsafe_allow_html=True,
            )

            # ── Picker Chat / Voz ─────────────────────────────────────────
            if is_picked:
                st.markdown('<div class="conv-picker">', unsafe_allow_html=True)
                pc1, pc2 = st.columns(2)
                with pc1:
                    if st.button("💬 Chat", key=f"pick_chat_{c['id']}", use_container_width=True):
                        st.session_state.conv_id    = c["id"]
                        st.session_state.voice_mode = False
                        st.session_state.pop("_conv_pick", None)
                        st.rerun()
                with pc2:
                    if st.button("🎙 Voz", key=f"pick_voice_{c['id']}", use_container_width=True):
                        st.session_state.conv_id    = c["id"]
                        st.session_state.voice_mode = True
                        st.session_state.pop("_vm_history", None)
                        st.session_state.pop("_conv_pick", None)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        # ── Rodapé sidebar ────────────────────────────────────────────────
        user_msgs   = len([m for m in messages if m["role"] == "user"])
        uav_sidebar = user_avatar_html(username, size=34)
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
                if st.button(t("dashboard", ui_lang), use_container_width=True, key="btn_dash"):
                    st.session_state.page = "dashboard"; st.rerun()
            with col_b:
                if st.button(t("profile", ui_lang), use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            if st.button(t("logout", ui_lang), use_container_width=True, key="btn_sair"):
                _logout(); st.rerun()
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(t("profile", ui_lang), use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            with col_b:
                if st.button(t("logout", ui_lang), use_container_width=True, key="btn_sair"):
                    _logout(); st.rerun()

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(f"""<div class="prof-header">
        {avatar_html(56, speaking)}
        <div class="prof-info">
            <h1>{PROF_NAME}</h1>
            <p>Online · {user['level']} · {user['focus']}</p>
        </div></div>""", unsafe_allow_html=True)

    # ── Mensagens ─────────────────────────────────────────────────────────────
    _tati_mini   = get_tati_mini_b64()
    tati_av_html = (
        f'<div class="msg-av" style="background:url({_tati_mini}) center top/cover no-repeat;"></div>'
        if _tati_mini else
        '<div class="msg-av"><div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;font-size:14px;">🧑‍🏫</div></div>'
    )

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for i, msg in enumerate(messages):
        safe_content = html.escape(msg["content"]).replace("\n", "<br>")
        msg_time     = msg.get("time", "")

        if msg["role"] == "assistant":
            tts_b64 = msg.get("tts_b64", "")
            is_file = msg.get("is_file", False)
            st.markdown(
                f'<div class="msg-row bot-row">{tati_av_html}'
                f'<div><div class="msg-bubble bot">{safe_content}</div>'
                f'<div class="msg-time">{msg_time}</div></div></div>',
                unsafe_allow_html=True)
            if tts_b64:
                components.html(
                    render_audio_player(tts_b64, msg_time, f"msg_{i}_{conv_id}"),
                    height=44, scrolling=False)
            elif not is_file:
                clean_text = (html.escape(msg["content"])
                    .replace("\n", " ").replace("*", "").replace("#", ""))[:600]
                st.markdown(
                    f'<div class="msg-ouvir-row">'
                    f'<button class="msg-ouvir-btn" data-pav-tts data-text="{clean_text}">▶ Ouvir</button>'
                    f'</div>', unsafe_allow_html=True)
        else:
            is_audio = msg.get("audio", False)
            extra    = " audio-msg" if is_audio else ""
            st.markdown(
                f'<div class="msg-row user-row">'
                f'<div><div class="msg-bubble user{extra}">{safe_content}</div>'
                f'<div class="msg-time">{msg_time}</div></div></div>',
                unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Indicador "digitando"
    if st.session_state.get("speaking"):
        components.html("""<!DOCTYPE html><html><head>
<style>*{margin:0;padding:0;box-sizing:border-box;}html,body{background:transparent;overflow:hidden;font-family:'Sora',sans-serif;}
.typing-row{display:flex;align-items:center;gap:10px;padding:6px 0 4px 0;}
.av{width:30px;height:30px;border-radius:50%;background:#1e2a3a;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}
.typing-bubble{display:flex;align-items:center;gap:8px;background:#1a1f2e;border:1px solid #252d3d;border-radius:18px;border-bottom-left-radius:4px;padding:8px 14px;}
.spin{color:#e05c2a;font-size:16px;line-height:1;animation:spinme 1.2s linear infinite;display:inline-block;flex-shrink:0;}
@keyframes spinme{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
.typing-text{font-size:.75rem;color:#8b949e;font-style:italic;letter-spacing:.2px;}
</style></head><body>
<div class="typing-row">
  <div class="av">🧑‍🏫</div>
  <div class="typing-bubble"><span class="spin">✳</span><span class="typing-text">Pensando…</span></div>
</div>
</body></html>""", height=52, scrolling=False)

    # Anexo staged
    staged = st.session_state.get("staged_file")
    if staged:
        staged_list = staged if isinstance(staged, list) else [staged]
        icons = {"audio": "🎵", "text": "📄", "image": "📸"}
        items_html = "".join(
            f'<span style="background:rgba(255,255,255,.06);border-radius:6px;padding:3px 8px;font-size:.8rem;color:#e6edf3;">'
            f'{icons.get(f["kind"],"📎")} {html.escape(f["name"])}</span>'
            for f in staged_list
        )
        st.markdown(f"""
<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.25);border-radius:10px;padding:10px 14px;margin:6px 0;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
  <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">{items_html}<span style="color:#8b949e;font-size:.75rem;">· {len(staged_list)} arquivo(s)</span></div>
  <span style="font-size:.7rem;color:#f0a500;">↩ Digite uma mensagem ou envie</span>
</div>""", unsafe_allow_html=True)
        if st.button(t("remove_attachment", ui_lang), key="remove_staged"):
            st.session_state.staged_file = None
            st.session_state.pop("_last_files_key", None); st.rerun()

    # Download pendente
    pending_dl = st.session_state.get("_pending_download")
    if pending_dl:
        b64_data = pending_dl["b64"]
        fname    = pending_dl["filename"]
        mime     = pending_dl["mime"]
        st.markdown(f"""
<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.35);border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;align-items:center;justify-content:space-between;gap:12px;">
  <span style="font-size:.85rem;color:#e6edf3;">📎 <b>{html.escape(fname)}</b> pronto para download</span>
  <a href="data:{mime};base64,{b64_data}" download="{html.escape(fname)}" style="background:linear-gradient(135deg,#f0a500,#e05c2a);color:#060a10;font-weight:700;font-size:.78rem;padding:6px 16px;border-radius:20px;text-decoration:none;white-space:nowrap;">⬇ Baixar arquivo</a>
</div>""", unsafe_allow_html=True)

    # Chat input
    prompt = st.chat_input(t("type_message", ui_lang))
    if prompt:
        staged = st.session_state.get("staged_file")
        if staged:
            staged_list = staged if isinstance(staged, list) else [staged]
            for i, sf in enumerate(staged_list):
                _process_and_send_file(username, user, conv_id, sf["raw"], sf["name"],
                                       extra_text=prompt if i == 0 else "")
            st.session_state.staged_file = None
            st.session_state.pop("_last_files_key", None)
        else:
            append_message(username, conv_id, "user", prompt)
            st.session_state.speaking = True
            try:   send_to_claude(username, user, conv_id, prompt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
        st.rerun()

    # Gravador de áudio
    audio_val = st.audio_input(" ", key=f"voice_input_{st.session_state.audio_key}",
                               label_visibility="collapsed")
    if audio_val and audio_val != st.session_state.get("_last_audio"):
        st.session_state["_last_audio"] = audio_val
        with st.spinner("Transcrevendo..."):
            txt = transcribe_bytes(audio_val.read(), ".wav", None)
        if txt and not txt.startswith("❌") and not txt.startswith("⚠️"):
            append_message(username, conv_id, "user", txt, audio=True)
            st.session_state.speaking = True
            try:   send_to_claude(username, user, conv_id, txt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
            st.session_state.audio_key += 1; st.rerun()
        elif txt:
            st.error(txt)

    # File uploader
    uploaded_list = st.file_uploader(
        "📎", key="file_upload", label_visibility="collapsed",
        accept_multiple_files=True,
        type=["mp3", "wav", "ogg", "m4a", "webm", "flac",
              "pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "webp"])
    if uploaded_list:
        names_key = ",".join(sorted(f.name for f in uploaded_list))
        if names_key != st.session_state.get("_last_files_key"):
            st.session_state["_last_files_key"] = names_key
            staged_list = []
            for uf in uploaded_list:
                raw    = uf.read()
                result = extract_file(raw, uf.name)
                staged_list.append({"raw": raw, "name": uf.name, "kind": result["kind"]})
            st.session_state.staged_file = staged_list; st.rerun()

    # Botões TTS via Web Speech API
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;background:transparent;}</style>
</head><body><script>
(function(){
  var par=window.parent?window.parent.document:document;
  var cur=null;
  function initBtns(){
    par.querySelectorAll('[data-pav-tts]').forEach(function(btn){
      if(btn._pavInit)return; btn._pavInit=true;
      btn.addEventListener('click',function(){
        if(cur&&cur!==btn){speechSynthesis.cancel();cur.textContent='▶ Ouvir';cur=null;}
        if(btn.classList.contains('speaking')){speechSynthesis.cancel();btn.textContent='▶ Ouvir';btn.classList.remove('speaking');cur=null;return;}
        var txt=btn.getAttribute('data-text')||'';
        var u=new SpeechSynthesisUtterance(txt);u.lang='en-US';u.rate=0.95;
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
  new MutationObserver(initBtns).observe(par.body,{childList:true,subtree:true});
})();
</script></body></html>""", height=1)

    # Botões mic e clipe
    _btn_css  = Path("static/pav_buttons.css")
    _btn_html = Path("static/pav_buttons.html")
    if _btn_css.exists():
        st.markdown(f"<style>{_btn_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    if _btn_html.exists():
        components.html(_btn_html.read_text(encoding="utf-8"), height=1, scrolling=False)


def _inject_colors(ac: str, ub: str, ab: str) -> None:
    components.html(f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;background:transparent;}}</style>
</head><body><script>
(function(){{
  function hexToRgb(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];var n=parseInt(h,16);return[(n>>16)&255,(n>>8)&255,n&255].join(',');}}
  function luminance(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];var n=parseInt(h,16);var r=(n>>16)&255,g=(n>>8)&255,b=n&255;return 0.299*r+0.587*g+0.114*b;}}
  var ac="{ac}",ub="{ub}",ab="{ab}",rgb=hexToRgb(ac),r=window.parent.document.documentElement;
  r.style.setProperty('--accent-full',ac);
  r.style.setProperty('--accent-70','rgba('+rgb+',.7)');
  r.style.setProperty('--user-bubble-bg',ub);
  r.style.setProperty('--user-bubble-text',luminance(ub)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-bg',ab);
  r.style.setProperty('--ai-bubble-text',luminance(ab)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-border','rgba('+hexToRgb(ab)+',.6)');
  var par=window.parent;
  if(par)par.document.querySelectorAll('audio').forEach(function(a){{a.pause();a.currentTime=0;}});
}})();
</script></body></html>""", height=1)'''

# teste 

"""
ui/chat.py — Tela principal de chat do Teacher Tati.
Refatorado com st.fragment para eliminar reruns globais.

MUDANÇAS vs versão anterior:
  - @st.fragment na sidebar  → troca de conversa sem recarregar o chat
  - @st.fragment no chat      → envio de mensagem sem recarregar a sidebar
  - @st.fragment nos inputs   → mic/arquivo sem recarregar as mensagens
  - Resultado: reruns isolados por região, página ~3-4x mais responsiva
"""
"""
ui/chat.py — Tela principal de chat do Teacher Tati.
Refatorado com st.fragment para eliminar reruns globais.
"""

import base64
import html
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core.database import (
    new_conversation, list_conversations, load_conversation,
    cached_load_conversation, append_message, delete_conversation, delete_session,
)
from core.ai import send_to_claude
from core.audio import transcribe_bytes
from core.file_handler import extract_file
from utils.helpers import (
    avatar_html, get_tati_mini_b64, _avatar_circle_html,
    get_user_avatar_b64, PROF_NAME,
)
from utils.i18n import t
from ui.session import js_clear_session


# ── Helpers internos ──────────────────────────────────────────────────────────

def get_or_create_conv(username: str) -> str:
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id


def user_avatar_html(username: str, size: int = 36) -> str:
    return _avatar_circle_html(
        get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v", 0)), size
    )


def _logout():
    token = st.session_state.get("_session_token", "")
    if token:
        delete_session(token)
    js_clear_session()
    st.session_state.pop("_session_token", None)
    st.session_state.pop("_session_saved", None)
    st.session_state.update(logged_in=False, user=None, conv_id=None)


def _process_and_send_file(
    username: str, user: dict, conv_id: str,
    raw: bytes, filename: str, extra_text: str = "",
) -> bool:
    result = extract_file(raw, filename)
    kind   = result["kind"]

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
        if not extracted: st.warning(f"Sem texto em '{filename}'."); return False
        preview      = extracted[:200].replace('\n', ' ')
        user_display = f"[{result['label']}: '{filename}'] — {preview}{'…' if len(extracted) > 200 else ''}"
        if extra_text: user_display = f"{extra_text}\n\n{user_display}"
        claude_msg   = f"[{result['label']}: '{filename}']\n\n{extracted}\n\nPlease help me understand this content."
        if extra_text: claude_msg = f"{extra_text}\n\n{claude_msg}"
        append_message(username, conv_id, "user", user_display)
        st.session_state.speaking = True
        try:   send_to_claude(username, user, conv_id, claude_msg)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        return True

    elif kind == "image":
        user_display = f"[Imagem: '{filename}']"
        if extra_text: user_display = f"{extra_text}\n\n{user_display}"
        claude_msg = f"[Imagem: '{filename}']\nPlease look at this image and help me learn English from it."
        if extra_text: claude_msg = f"{extra_text}\n\n{claude_msg}"
        append_message(username, conv_id, "user", user_display)
        st.session_state.speaking = True
        try:
            send_to_claude(username, user, conv_id, claude_msg,
                           image_b64=result["b64"], image_media_type=result["media_type"])
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        return True

    st.warning(f"⚠️ Formato '{result['label']}' não suportado.")
    return False


def render_audio_player(tts_b64: str, msg_time: str, player_id: str) -> str:
    return f"""<!DOCTYPE html><html><head>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:transparent;font-family:'Sora',sans-serif;overflow:hidden;}}
.player{{display:flex;align-items:center;gap:8px;padding:3px 0;flex-wrap:nowrap;}}
.tl{{font-size:.62rem;color:#8b949e;font-family:'JetBrains Mono',monospace;flex-shrink:0;}}
.pb{{background:none;border:1px solid #30363d;border-radius:20px;color:#f0a500;font-size:.75rem;padding:2px 10px;cursor:pointer;transition:background .15s;white-space:nowrap;flex-shrink:0;}}
.pb:hover{{background:rgba(240,165,0,.12);border-color:#f0a500;}}
.pw{{flex:1;min-width:60px;height:3px;background:#30363d;border-radius:2px;cursor:pointer;}}
.pf{{height:100%;background:linear-gradient(90deg,#f0a500,#e05c2a);border-radius:2px;width:0%;transition:width .1s linear;pointer-events:none;}}
.sw{{display:flex;align-items:center;gap:3px;flex-shrink:0;}}
.sb{{background:none;border:1px solid #30363d;border-radius:4px;color:#8b949e;font-size:.65rem;padding:1px 5px;cursor:pointer;transition:all .15s;}}
.sb:hover,.sb.on{{border-color:#f0a500;color:#f0a500;background:rgba(240,165,0,.08);}}
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
</div>
<script>
(function(){{
  var audio=new Audio('data:audio/mpeg;base64,{tts_b64}');
  audio.preload='metadata';
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


# ══════════════════════════════════════════════════════════════════════════════
# FRAGMENT: SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

@st.fragment
def _render_sidebar(user: dict, conv_id: str, messages: list, ui_lang: str):
    username = user["username"]

    st.markdown(f"""<div style="padding:14px 14px 10px;border-bottom:1px solid #21262d;flex-shrink:0;">
        <div style="display:flex;align-items:center;gap:10px;">
            {avatar_html(40)}<div>
            <div style="font-weight:600;font-size:.88rem;">{PROF_NAME}</div>
            <div style="font-size:.68rem;color:#8b949e;">Online</div>
            </div></div></div>""", unsafe_allow_html=True)

    if st.button(t("new_conv", ui_lang), use_container_width=True, key="btn_new"):
        st.session_state.conv_id = new_conversation(username)
        st.session_state.pop("_conv_pick", None)
        st.rerun()

    if st.button(t("voice_mode", ui_lang), use_container_width=True, key="btn_voice"):
        st.session_state.voice_mode = True
        st.rerun()

    st.markdown(
        '<div style="font-size:.68rem;color:#8b949e;text-transform:uppercase;'
        'letter-spacing:1px;padding:10px 4px 4px;">Conversas</div>',
        unsafe_allow_html=True,
    )

    convs = list_conversations(username)
    if not convs:
        st.markdown(
            '<div style="font-size:.78rem;color:#8b949e;padding:6px 4px;">Nenhuma conversa ainda.</div>',
            unsafe_allow_html=True,
        )

    for c in convs:
        is_active = c["id"] == conv_id
        is_picked = st.session_state.get("_conv_pick") == c["id"]
        label     = ("▶ " if is_active else "") + c["title"]

        col_conv, col_del = st.columns([5, 1])
        with col_conv:
            if st.button(label, key=f"conv_{c['id']}", use_container_width=True):
                if is_picked:
                    st.session_state.pop("_conv_pick", None)
                else:
                    st.session_state["_conv_pick"] = c["id"]
                st.rerun(scope="fragment")

        with col_del:
            if st.button("🗑", key=f"del_{c['id']}"):
                delete_conversation(username, c["id"])
                if st.session_state.conv_id == c["id"]:
                    st.session_state.conv_id = None
                st.session_state.pop("_conv_pick", None)
                st.rerun(scope="fragment")

        st.markdown(
            f'<div style="font-size:.62rem;color:#6e7681;margin:-10px 0 2px 6px;">'
            f'{c["date"]} · {c["count"]} msg</div>',
            unsafe_allow_html=True,
        )

        if is_picked:
            st.markdown('<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:6px 8px;margin:2px 0 6px 0;">', unsafe_allow_html=True)
            pc1, pc2 = st.columns(2)
            with pc1:
                if st.button("💬 Chat", key=f"pick_chat_{c['id']}", use_container_width=True):
                    st.session_state.conv_id    = c["id"]
                    st.session_state.voice_mode = False
                    st.session_state.pop("_conv_pick", None)
                    st.rerun()
            with pc2:
                if st.button("🎙 Voz", key=f"pick_voice_{c['id']}", use_container_width=True):
                    st.session_state.conv_id    = c["id"]
                    st.session_state.voice_mode = True
                    st.session_state.pop("_vm_history", None)
                    st.session_state.pop("_conv_pick", None)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # Rodapé sidebar
    user_msgs   = len([m for m in messages if m["role"] == "user"])
    uav_sidebar = user_avatar_html(username, size=34)
    st.markdown("<hr style='border-color:#21262d;margin:8px 0 0'>", unsafe_allow_html=True)
    st.markdown(
        f"""<div style="padding:8px 12px;display:flex;align-items:center;gap:10px;">
            {uav_sidebar}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:600;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user['name'].split()[0]}</div>
              <div style="color:#8b949e;font-size:.68rem;">{user['level']} · {user_msgs} msgs</div>
            </div></div>""",
        unsafe_allow_html=True,
    )

    if user["role"] in ("professor", "professora", "programador"):
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(t("dashboard", ui_lang), use_container_width=True, key="btn_dash"):
                st.session_state.page = "dashboard"; st.rerun()
        with col_b:
            if st.button(t("profile", ui_lang), use_container_width=True, key="btn_profile"):
                st.session_state.page = "profile"; st.rerun()
        if st.button(t("logout", ui_lang), use_container_width=True, key="btn_sair"):
            _logout(); st.rerun()
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(t("profile", ui_lang), use_container_width=True, key="btn_profile"):
                st.session_state.page = "profile"; st.rerun()
        with col_b:
            if st.button(t("logout", ui_lang), use_container_width=True, key="btn_sair"):
                _logout(); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# FRAGMENT: HISTÓRICO DE MENSAGENS
# ══════════════════════════════════════════════════════════════════════════════

@st.fragment
def _render_messages(username: str, conv_id: str):
    messages = cached_load_conversation(username, conv_id)

    _tati_mini   = get_tati_mini_b64()
    tati_av_html = (
        f'<div class="msg-av" style="background:url({_tati_mini}) center top/cover no-repeat;"></div>'
        if _tati_mini else
        '<div class="msg-av"><div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;font-size:14px;">🧑‍🏫</div></div>'
    )

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for i, msg in enumerate(messages):
        safe_content = html.escape(msg["content"]).replace("\n", "<br>")
        msg_time     = msg.get("time", "")

        if msg["role"] == "assistant":
            tts_b64 = msg.get("tts_b64", "")
            is_file = msg.get("is_file", False)
            st.markdown(
                f'<div class="msg-row bot-row">{tati_av_html}'
                f'<div><div class="msg-bubble bot">{safe_content}</div>'
                f'<div class="msg-time">{msg_time}</div></div></div>',
                unsafe_allow_html=True)
            if tts_b64:
                components.html(
                    render_audio_player(tts_b64, msg_time, f"msg_{i}_{conv_id}"),
                    height=44, scrolling=False)
            elif not is_file:
                clean_text = (html.escape(msg["content"])
                    .replace("\n", " ").replace("*", "").replace("#", ""))[:600]
                st.markdown(
                    f'<div class="msg-ouvir-row">'
                    f'<button class="msg-ouvir-btn" data-pav-tts data-text="{clean_text}">▶ Ouvir</button>'
                    f'</div>', unsafe_allow_html=True)
        else:
            is_audio = msg.get("audio", False)
            extra    = " audio-msg" if is_audio else ""
            st.markdown(
                f'<div class="msg-row user-row">'
                f'<div><div class="msg-bubble user{extra}">{safe_content}</div>'
                f'<div class="msg-time">{msg_time}</div></div></div>',
                unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Indicador "digitando"
    if st.session_state.get("speaking"):
        components.html("""<!DOCTYPE html><html><head>
<style>*{margin:0;padding:0;box-sizing:border-box;}html,body{background:transparent;overflow:hidden;font-family:'Sora',sans-serif;}
.typing-row{display:flex;align-items:center;gap:10px;padding:6px 0 4px 0;}
.av{width:30px;height:30px;border-radius:50%;background:#1e2a3a;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}
.typing-bubble{display:flex;align-items:center;gap:8px;background:#1a1f2e;border:1px solid #252d3d;border-radius:18px;border-bottom-left-radius:4px;padding:8px 14px;}
.spin{color:#e05c2a;font-size:16px;line-height:1;animation:spinme 1.2s linear infinite;display:inline-block;flex-shrink:0;}
@keyframes spinme{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
.typing-text{font-size:.75rem;color:#8b949e;font-style:italic;letter-spacing:.2px;}
</style></head><body>
<div class="typing-row">
  <div class="av">🧑‍🏫</div>
  <div class="typing-bubble"><span class="spin">✳</span><span class="typing-text">Pensando…</span></div>
</div>
</body></html>""", height=52, scrolling=False)

    # Download pendente
    pending_dl = st.session_state.get("_pending_download")
    if pending_dl:
        b64_data = pending_dl["b64"]
        fname    = pending_dl["filename"]
        mime     = pending_dl["mime"]
        st.markdown(f"""
<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.35);border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;align-items:center;justify-content:space-between;gap:12px;">
  <span style="font-size:.85rem;color:#e6edf3;">📎 <b>{html.escape(fname)}</b> pronto para download</span>
  <a href="data:{mime};base64,{b64_data}" download="{html.escape(fname)}" style="background:linear-gradient(135deg,#f0a500,#e05c2a);color:#060a10;font-weight:700;font-size:.78rem;padding:6px 16px;border-radius:20px;text-decoration:none;white-space:nowrap;">⬇ Baixar arquivo</a>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# FRAGMENT: INPUTS (chat + mic + arquivo)
# ══════════════════════════════════════════════════════════════════════════════

@st.fragment
def _render_inputs(user: dict, conv_id: str, ui_lang: str):
    username = user["username"]

    # Anexo staged
    staged = st.session_state.get("staged_file")
    if staged:
        staged_list = staged if isinstance(staged, list) else [staged]
        icons = {"audio": "🎵", "text": "📄", "image": "📸"}
        items_html = "".join(
            f'<span style="background:rgba(255,255,255,.06);border-radius:6px;padding:3px 8px;'
            f'font-size:.8rem;color:#e6edf3;">{icons.get(f["kind"],"📎")} {html.escape(f["name"])}</span>'
            for f in staged_list
        )
        st.markdown(f"""
<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.25);border-radius:10px;
     padding:10px 14px;margin:6px 0;display:flex;align-items:center;
     justify-content:space-between;gap:10px;flex-wrap:wrap;">
  <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
    {items_html}
    <span style="color:#8b949e;font-size:.75rem;">· {len(staged_list)} arquivo(s)</span>
  </div>
  <span style="font-size:.7rem;color:#f0a500;">↩ Digite uma mensagem ou envie</span>
</div>""", unsafe_allow_html=True)
        if st.button(t("remove_attachment", ui_lang), key="remove_staged"):
            st.session_state.staged_file = None
            st.session_state.pop("_last_files_key", None)
            st.rerun()

    # Chat input
    prompt = st.chat_input(t("type_message", ui_lang))
    if prompt:
        staged = st.session_state.get("staged_file")
        if staged:
            staged_list = staged if isinstance(staged, list) else [staged]
            for i, sf in enumerate(staged_list):
                _process_and_send_file(username, user, conv_id, sf["raw"], sf["name"],
                                       extra_text=prompt if i == 0 else "")
            st.session_state.staged_file = None
            st.session_state.pop("_last_files_key", None)
        else:
            append_message(username, conv_id, "user", prompt)
            st.session_state.speaking = True
            try:
                send_to_claude(username, user, conv_id, prompt)
            except Exception as e:
                st.error(f"❌ {e}")
            st.session_state.speaking = False

        cached_load_conversation.clear()
        st.rerun()

    # Gravador de áudio nativo
    audio_val = st.audio_input(
        " ", key=f"voice_input_{st.session_state.audio_key}",
        label_visibility="collapsed",
    )
    if audio_val and audio_val != st.session_state.get("_last_audio"):
        st.session_state["_last_audio"] = audio_val
        with st.spinner("Transcrevendo..."):
            txt = transcribe_bytes(audio_val.read(), ".wav", None)
        if txt and not txt.startswith("❌") and not txt.startswith("⚠️"):
            append_message(username, conv_id, "user", txt, audio=True)
            st.session_state.speaking = True
            try:
                send_to_claude(username, user, conv_id, txt)
            except Exception as e:
                st.error(f"❌ {e}")
            st.session_state.speaking = False
            st.session_state.audio_key += 1
            cached_load_conversation.clear()
            st.rerun()
        elif txt:
            st.error(txt)

    # File uploader (oculto — acionado pelo botão clipe)
    uploaded_list = st.file_uploader(
        "📎", key="file_upload", label_visibility="collapsed",
        accept_multiple_files=True,
        type=["mp3", "wav", "ogg", "m4a", "webm", "flac",
              "pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "webp"],
    )
    if uploaded_list:
        names_key = ",".join(sorted(f.name for f in uploaded_list))
        if names_key != st.session_state.get("_last_files_key"):
            st.session_state["_last_files_key"] = names_key
            staged_list = []
            for uf in uploaded_list:
                raw    = uf.read()
                result = extract_file(raw, uf.name)
                staged_list.append({"raw": raw, "name": uf.name, "kind": result["kind"]})
            st.session_state.staged_file = staged_list
            st.rerun()

    # Web Speech API para os botões "Ouvir" inline
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;background:transparent;}</style>
</head><body><script>
(function(){
  var par=window.parent?window.parent.document:document;
  var cur=null;
  function initBtns(){
    par.querySelectorAll('[data-pav-tts]').forEach(function(btn){
      if(btn._pavInit)return; btn._pavInit=true;
      btn.addEventListener('click',function(){
        if(cur&&cur!==btn){speechSynthesis.cancel();cur.textContent='▶ Ouvir';cur=null;}
        if(btn.classList.contains('speaking')){speechSynthesis.cancel();btn.textContent='▶ Ouvir';btn.classList.remove('speaking');cur=null;return;}
        var txt=btn.getAttribute('data-text')||'';
        var u=new SpeechSynthesisUtterance(txt);u.lang='en-US';u.rate=0.95;
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
  new MutationObserver(initBtns).observe(par.body,{childList:true,subtree:true});
})();
</script></body></html>""", height=1)

    # Botões mic e clipe flutuantes
    _btn_css  = Path("static/pav_buttons.css")
    _btn_html = Path("static/pav_buttons.html")
    if _btn_css.exists():
        st.markdown(f"<style>{_btn_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    if _btn_html.exists():
        components.html(_btn_html.read_text(encoding="utf-8"), height=1, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# SHOW CHAT — orquestrador principal
# ══════════════════════════════════════════════════════════════════════════════

def show_chat() -> None:
    from ui.voice import show_voice

    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    ui_lang  = profile.get("language", "pt-BR")

    if st.session_state.voice_mode:
        show_voice()
        return

    conv_id  = get_or_create_conv(username)
    messages = cached_load_conversation(username, conv_id)
    speaking = st.session_state.get("speaking", False)

    _ac = profile.get("accent_color", "#f0a500")
    _ub = profile.get("user_bubble_color", "#2d6a4f")
    _ab = profile.get("ai_bubble_color", "#1a1f2e")
    _inject_colors(_ac, _ub, _ab)

    st.markdown("""<style>
/* ── Campo de digitação fixo no fundo ── */
[data-testid="stChatInput"] textarea{max-height:120px!important;min-height:44px!important;font-size:.88rem!important;}
[data-testid="stChatInputContainer"]{padding:6px 10px!important;}
/* Fixa o bloco do chat_input na parte inferior */
[data-testid="stBottom"]{
    position:fixed!important;
    bottom:0!important;
    left:var(--sidebar-width,0px)!important;
    right:0!important;
    z-index:999!important;
    background:#0d1117!important;
    border-top:1px solid #21262d!important;
    padding:0!important;
}
/* Compensa o espaço ocupado pelo campo fixo */
.main .block-container{padding-bottom:100px!important;}
.msg-row{display:flex;align-items:flex-end;gap:10px;margin:6px 0;}
.msg-row.user-row{flex-direction:row-reverse;}
.msg-row.user-row>div{display:flex;flex-direction:column;align-items:flex-end;}
.msg-row.bot-row>div{display:flex;flex-direction:column;align-items:flex-start;}
.msg-bubble{padding:10px 15px;border-radius:18px;font-size:.88rem;line-height:1.6;
    word-break:normal;overflow-wrap:break-word;white-space:pre-wrap;}
.msg-bubble.user{max-width:75%;background:var(--user-bubble-bg,#2d6a4f);
    color:var(--user-bubble-text,#d8f3dc);border-bottom-right-radius:4px;}
.msg-bubble.bot{max-width:75%;background:var(--ai-bubble-bg,#1a1f2e);
    color:var(--ai-bubble-text,#e6edf3);border:1px solid var(--ai-bubble-border,#252d3d);
    border-bottom-left-radius:4px;}
.msg-av{width:30px;height:30px;border-radius:50%;overflow:hidden;flex-shrink:0;margin-bottom:2px;}
.msg-time{font-size:.6rem;color:#4a5a6a;margin:2px 4px 0;text-align:right;}
.bot-row .msg-time{text-align:left;}
.msg-ouvir-row{padding:2px 0 0 40px;}
.msg-ouvir-btn{background:none;border:1px solid #30363d;border-radius:16px;color:#8b949e;
    font-size:.68rem;padding:2px 10px;cursor:pointer;transition:all .15s;
    white-space:nowrap;font-family:inherit;}
.msg-ouvir-btn:hover{border-color:#f0a500;color:#f0a500;}
.conv-picker{background:#161b22;border:1px solid #30363d;border-radius:8px;
    padding:6px 8px;margin:2px 0 6px 0;}
@media(max-width:768px){.msg-bubble{max-width:88%!important;font-size:.82rem!important;}}
</style>""", unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""<style>
        section[data-testid="stSidebar"]{overflow:hidden;}
        section[data-testid="stSidebar"]>div:first-child{
            height:100vh;display:flex;flex-direction:column;padding:0!important;gap:0;}
        </style>""", unsafe_allow_html=True)
        _render_sidebar(user, conv_id, messages, ui_lang)

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(f"""<div class="prof-header">
        {avatar_html(56, speaking)}
        <div class="prof-info">
            <h1>{PROF_NAME}</h1>
            <p>Online · {user['level']} · {user['focus']}</p>
        </div></div>""", unsafe_allow_html=True)

    # ── Mensagens ─────────────────────────────────────────────────────────────
    _render_messages(username, conv_id)

    # ── Inputs ────────────────────────────────────────────────────────────────
    _render_inputs(user, conv_id, ui_lang)


# ── Helper: injeção de cores CSS via JS ──────────────────────────────────────

def _inject_colors(ac: str, ub: str, ab: str) -> None:
    components.html(
        f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;background:transparent;}}</style>
</head><body><script>
(function(){{
  function hexToRgb(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);return[(n>>16)&255,(n>>8)&255,n&255].join(',');}}
  function luminance(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n=parseInt(h,16);var r=(n>>16)&255,g=(n>>8)&255,b=n&255;return 0.299*r+0.587*g+0.114*b;}}
  var ac="{ac}",ub="{ub}",ab="{ab}",rgb=hexToRgb(ac),r=window.parent.document.documentElement;
  r.style.setProperty('--accent-full',ac);
  r.style.setProperty('--accent-70','rgba('+rgb+',.7)');
  r.style.setProperty('--user-bubble-bg',ub);
  r.style.setProperty('--user-bubble-text',luminance(ub)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-bg',ab);
  r.style.setProperty('--ai-bubble-text',luminance(ab)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-border','rgba('+hexToRgb(ab)+',.6)');
  var par=window.parent;
  if(par)par.document.querySelectorAll('audio').forEach(function(a){{a.pause();a.currentTime=0;}});
}})();
</script></body></html>""",
        height=1,
    )