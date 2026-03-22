import base64
import html
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core.database import (
    new_conversation, list_conversations,
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


def get_or_create_conv(username):
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id

def user_avatar_html(username, size=36):
    return _avatar_circle_html(
        get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v", 0)), size)

def _logout():
    token = st.session_state.get("_session_token","")
    if token: delete_session(token)
    js_clear_session()
    st.session_state.pop("_session_token",None); st.session_state.pop("_session_saved",None)
    st.session_state.update(logged_in=False, user=None, conv_id=None)

def _send_file(username, user, conv_id, raw, filename, extra=""):
    result = extract_file(raw, filename); kind = result["kind"]
    if kind == "audio":
        with st.spinner("Transcrevendo..."):
            text = transcribe_bytes(raw, suffix=Path(filename).suffix.lower(), language="en")
        if text.startswith("❌") or text.startswith("⚠️"): st.error(text); return False
        ud = f"{extra}\n\n[Audio: {text}]" if extra else text
        cm = f"{extra}\n\n[Audio: '{filename}']\n{text}" if extra else f"[Audio: '{filename}']\n{text}"
        append_message(username, conv_id, "user", ud, audio=True)
        st.session_state.speaking = True
        try:    send_to_claude(username, user, conv_id, cm)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False; return True
    elif kind == "text":
        extracted = result["text"]
        if extracted.startswith("❌"): st.error(extracted); return False
        if not extracted: st.warning(f"Sem texto em '{filename}'."); return False
        preview = extracted[:200].replace('\n',' ')
        ud = f"[{result['label']}: '{filename}'] — {preview}{'…' if len(extracted)>200 else ''}"
        if extra: ud = f"{extra}\n\n{ud}"
        cm = f"[{result['label']}: '{filename}']\n\n{extracted}\n\nPlease help me understand this content."
        if extra: cm = f"{extra}\n\n{cm}"
        append_message(username, conv_id, "user", ud)
        st.session_state.speaking = True
        try:    send_to_claude(username, user, conv_id, cm)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False; return True
    elif kind == "image":
        ud = f"[Imagem: '{filename}']"
        if extra: ud = f"{extra}\n\n{ud}"
        cm = f"[Imagem: '{filename}']\nPlease look at this image and help me learn English from it."
        if extra: cm = f"{extra}\n\n{cm}"
        append_message(username, conv_id, "user", ud)
        st.session_state.speaking = True
        try:    send_to_claude(username, user, conv_id, cm, image_b64=result["b64"], image_media_type=result["media_type"])
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False; return True
    st.warning(f"⚠️ Formato '{result['label']}' não suportado."); return False

def render_audio_player(tts_b64, msg_time, pid):
    return f"""<!DOCTYPE html><html><head>
<style>*{{box-sizing:border-box;margin:0;padding:0;}}html,body{{background:transparent;font-family:'Sora',sans-serif;overflow:hidden;}}
.player{{display:flex;align-items:center;gap:8px;padding:3px 0;flex-wrap:nowrap;}}
.tl{{font-size:.62rem;color:#8b949e;font-family:'JetBrains Mono',monospace;flex-shrink:0;}}
.pb{{background:none;border:1px solid #30363d;border-radius:20px;color:#f0a500;font-size:.75rem;padding:2px 10px;cursor:pointer;transition:background .15s;white-space:nowrap;flex-shrink:0;}}
.pb:hover{{background:rgba(240,165,0,.12);border-color:#f0a500;}}
.pw{{flex:1;min-width:60px;height:3px;background:#30363d;border-radius:2px;cursor:pointer;}}
.pf{{height:100%;background:linear-gradient(90deg,#f0a500,#e05c2a);border-radius:2px;width:0%;transition:width .1s linear;pointer-events:none;}}
.sw{{display:flex;align-items:center;gap:3px;flex-shrink:0;}}
.sb{{background:none;border:1px solid #30363d;border-radius:4px;color:#8b949e;font-size:.65rem;padding:1px 5px;cursor:pointer;transition:all .15s;}}
.sb:hover,.sb.on{{border-color:#f0a500;color:#f0a500;background:rgba(240,165,0,.08);}}</style></head><body>
<div class="player"><span class="tl">{msg_time}</span><button class="pb" id="b">▶ Ouvir</button>
<div class="pw" id="pw"><div class="pf" id="pf"></div></div>
<div class="sw" id="sw"><span style="font-size:.6rem;color:#8b949e;">vel:</span>
<button class="sb" data-r="0.75">0.75×</button><button class="sb on" data-r="1">1×</button>
<button class="sb" data-r="1.25">1.25×</button><button class="sb" data-r="1.5">1.5×</button></div></div>
<script>(function(){{var a=new Audio('data:audio/mpeg;base64,{tts_b64}');a.preload='metadata';
var b=document.getElementById('b'),pf=document.getElementById('pf'),pw=document.getElementById('pw'),sw=document.getElementById('sw');
b.onclick=function(){{if(!a.paused){{a.pause();b.textContent='▶ Ouvir';}}else{{a.play().then(function(){{b.textContent='⏸ Pausar';}}).catch(function(){{}});}}}};
a.onended=function(){{b.textContent='▶ Ouvir';pf.style.width='0%';}};
a.ontimeupdate=function(){{if(a.duration)pf.style.width=(a.currentTime/a.duration*100)+'%';}};
pw.onclick=function(e){{var r=pw.getBoundingClientRect();if(a.duration)a.currentTime=((e.clientX-r.left)/r.width)*a.duration;}};
sw.querySelectorAll('.sb').forEach(function(btn){{btn.onclick=function(){{sw.querySelectorAll('.sb').forEach(function(x){{x.classList.remove('on');}});this.classList.add('on');a.playbackRate=parseFloat(this.dataset.r);}};}}); 
}})();</script></body></html>"""


def show_chat():
    from ui.voice import show_voice
    user=st.session_state.user; username=user["username"]
    profile=user.get("profile",{}); ui_lang=profile.get("language","pt-BR")
    conv_id=get_or_create_conv(username)
    messages=cached_load_conversation(username,conv_id)
    speaking=st.session_state.speaking

    if st.session_state.voice_mode: show_voice(); return

    _ac=profile.get("accent_color","#f0a500")
    _ub=profile.get("user_bubble_color","#2d6a4f")
    _ab=profile.get("ai_bubble_color","#1a1f2e")
    _inject_colors(_ac,_ub,_ab)

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

/* ── File uploader como botão clipe fixo ── */
[data-testid="stFileUploader"] {
    position: fixed !important;
    bottom: 68px !important;
    right: 60px !important;
    width: 38px !important;
    height: 38px !important;
    z-index: 9999 !important;
    overflow: hidden !important;
}
[data-testid="stFileUploaderDropzone"] {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
    min-height: unset !important;
    width: 38px !important;
    height: 38px !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}
[data-testid="stFileUploader"] button {
    width: 34px !important;
    height: 34px !important;
    border-radius: 50% !important;
    border: 1px solid #30363d !important;
    background: #0d1117 !important;
    color: transparent !important;
    font-size: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: unset !important;
    transition: background .15s, border-color .15s !important;
}
[data-testid="stFileUploader"] button:hover {
    background: #1c2128 !important;
    border-color: #484f58 !important;
}
[data-testid="stFileUploader"] button::after {
    content: "";
    display: block;
    width: 15px;
    height: 15px;
    background-color: #8b949e;
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48'/%3E%3C/svg%3E") no-repeat center;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48'/%3E%3C/svg%3E") no-repeat center;
}
[data-testid="stFileUploader"] button:hover::after {
    background-color: #e6edf3;
}
</style>""", unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""<div style="padding:14px 14px 10px;border-bottom:1px solid #21262d;flex-shrink:0;">
            <div style="display:flex;align-items:center;gap:10px;">{avatar_html(40)}<div>
            <div style="font-weight:600;font-size:.88rem;">{PROF_NAME}</div>
            <div style="font-size:.68rem;color:#8b949e;">Online</div></div></div></div>""", unsafe_allow_html=True)
        if st.button(t("new_conv",ui_lang),use_container_width=True,key="btn_new"):
            st.session_state.conv_id=new_conversation(username); st.session_state.pop("_conv_pick",None); st.rerun()
        if st.button(t("voice_mode",ui_lang),use_container_width=True,key="btn_voice"):
            st.session_state.voice_mode=True; st.rerun()
        st.markdown('<div style="font-size:.68rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px;padding:10px 4px 4px;">Conversas</div>',unsafe_allow_html=True)
        convs=list_conversations(username)
        if not convs:
            st.markdown('<div style="font-size:.78rem;color:#8b949e;padding:6px 4px;">Nenhuma conversa ainda.</div>',unsafe_allow_html=True)
        for c in convs:
            is_active=c["id"]==conv_id; is_picked=st.session_state.get("_conv_pick")==c["id"]
            label=("▶ " if is_active else "")+c["title"]
            col_conv,col_del=st.columns([5,1])
            with col_conv:
                if st.button(label,key=f"conv_{c['id']}",use_container_width=True):
                    if is_picked: st.session_state.pop("_conv_pick",None)
                    else: st.session_state["_conv_pick"]=c["id"]
                    st.rerun()
            with col_del:
                if st.button("🗑",key=f"del_{c['id']}"):
                    delete_conversation(username,c["id"])
                    if st.session_state.conv_id==c["id"]: st.session_state.conv_id=None
                    st.session_state.pop("_conv_pick",None); st.rerun()
            st.markdown(f'<div style="font-size:.62rem;color:#6e7681;margin:-10px 0 2px 6px;">{c["date"]} · {c["count"]} msg</div>',unsafe_allow_html=True)
            if is_picked:
                st.markdown('<div class="conv-picker">',unsafe_allow_html=True)
                pc1,pc2=st.columns(2)
                with pc1:
                    if st.button("💬 Chat",key=f"pick_chat_{c['id']}",use_container_width=True):
                        st.session_state.conv_id=c["id"]; st.session_state.voice_mode=False; st.session_state.pop("_conv_pick",None); st.rerun()
                with pc2:
                    if st.button("🎙 Voz",key=f"pick_voice_{c['id']}",use_container_width=True):
                        st.session_state.conv_id=c["id"]; st.session_state.voice_mode=True; st.session_state.pop("_vm_history",None); st.session_state.pop("_conv_pick",None); st.rerun()
                st.markdown('</div>',unsafe_allow_html=True)
        user_msgs=len([m for m in messages if m["role"]=="user"])
        uav_sb=user_avatar_html(username,size=34)
        st.markdown("<hr style='border-color:#21262d;margin:8px 0 0'>",unsafe_allow_html=True)
        st.markdown(f"""<div style="padding:8px 12px;display:flex;align-items:center;gap:10px;">{uav_sb}
            <div style="flex:1;min-width:0;"><div style="font-weight:600;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user['name'].split()[0]}</div>
            <div style="color:#8b949e;font-size:.68rem;">{user['level']} · {user_msgs} msgs</div></div></div>""",unsafe_allow_html=True)
        _DASH=("professor","professora","programador")
        if user["role"] in _DASH:
            col_a,col_b=st.columns(2)
            with col_a:
                if st.button(t("dashboard",ui_lang),use_container_width=True,key="btn_dash"):
                    st.session_state.page="dashboard"; st.rerun()
            with col_b:
                if st.button(t("profile",ui_lang),use_container_width=True,key="btn_profile"):
                    st.session_state.page="profile"; st.rerun()
            if st.button(t("logout",ui_lang),use_container_width=True,key="btn_sair"):
                _logout(); st.rerun()
        else:
            col_a,col_b=st.columns(2)
            with col_a:
                if st.button(t("profile",ui_lang),use_container_width=True,key="btn_profile"):
                    st.session_state.page="profile"; st.rerun()
            with col_b:
                if st.button(t("logout",ui_lang),use_container_width=True,key="btn_sair"):
                    _logout(); st.rerun()

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(f"""<div class="prof-header">{avatar_html(56,speaking)}
        <div class="prof-info"><h1>{PROF_NAME}</h1>
        <p>Online · {user['level']} · {user['focus']}</p></div></div>""",unsafe_allow_html=True)

    # ── Mensagens ─────────────────────────────────────────────────────────────
    _tm=get_tati_mini_b64()
    tav=(f'<div class="msg-av" style="background:url({_tm}) center top/cover no-repeat;"></div>'
         if _tm else '<div class="msg-av"><div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:14px;">🧑‍🏫</div></div>')
    st.markdown('<div class="chat-wrap">',unsafe_allow_html=True)
    for i,msg in enumerate(messages):
        sc=html.escape(msg["content"]).replace("\n","<br>"); mt=msg.get("time","")
        if msg["role"]=="assistant":
            tb=msg.get("tts_b64",""); isf=msg.get("is_file",False)
            st.markdown(f'<div class="msg-row bot-row">{tav}<div><div class="msg-bubble bot">{sc}</div><div class="msg-time">{mt}</div></div></div>',unsafe_allow_html=True)
            if tb: components.html(render_audio_player(tb,mt,f"msg_{i}_{conv_id}"),height=44,scrolling=False)
            elif not isf:
                ct=(html.escape(msg["content"]).replace("\n"," ").replace("*","").replace("#",""))[:600]
                st.markdown(f'<div class="msg-ouvir-row"><button class="msg-ouvir-btn" data-pav-tts data-text="{ct}">▶ Ouvir</button></div>',unsafe_allow_html=True)
        else:
            ex=" audio-msg" if msg.get("audio",False) else ""
            st.markdown(f'<div class="msg-row user-row"><div><div class="msg-bubble user{ex}">{sc}</div><div class="msg-time">{mt}</div></div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    if st.session_state.get("speaking"):
        components.html("""<!DOCTYPE html><html><head><style>*{margin:0;padding:0;box-sizing:border-box;}html,body{background:transparent;overflow:hidden;font-family:'Sora',sans-serif;}
.row{display:flex;align-items:center;gap:10px;padding:6px 0 4px;}
.av{width:30px;height:30px;border-radius:50%;background:#1e2a3a;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}
.bub{display:flex;align-items:center;gap:8px;background:#1a1f2e;border:1px solid #252d3d;border-radius:18px;border-bottom-left-radius:4px;padding:8px 14px;}
.sp{color:#e05c2a;font-size:16px;animation:sp 1.2s linear infinite;display:inline-block;}
@keyframes sp{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
.tx{font-size:.75rem;color:#8b949e;font-style:italic;}
</style></head><body><div class="row"><div class="av">🧑‍🏫</div><div class="bub"><span class="sp">✳</span><span class="tx">Pensando…</span></div></div></body></html>""",height=52,scrolling=False)

    staged=st.session_state.get("staged_file")
    if staged:
        sl=staged if isinstance(staged,list) else [staged]
        icons={"audio":"🎵","text":"📄","image":"📸"}
        ih="".join(f'<span style="background:rgba(255,255,255,.06);border-radius:6px;padding:3px 8px;font-size:.8rem;color:#e6edf3;">{icons.get(f["kind"],"📎")} {html.escape(f["name"])}</span>' for f in sl)
        st.markdown(f"""<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.25);border-radius:10px;padding:10px 14px;margin:6px 0;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
  <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">{ih}<span style="color:#8b949e;font-size:.75rem;">· {len(sl)} arquivo(s)</span></div>
  <span style="font-size:.7rem;color:#f0a500;">↩ Digite uma mensagem ou envie</span></div>""",unsafe_allow_html=True)
        if st.button(t("remove_attachment",ui_lang),key="remove_staged"):
            st.session_state.staged_file=None; st.session_state.pop("_last_files_key",None); st.rerun()

    pending_dl=st.session_state.get("_pending_download")
    if pending_dl:
        b64d=pending_dl["b64"]; fn=pending_dl["filename"]; mime=pending_dl["mime"]
        st.markdown(f"""<div style="background:rgba(240,165,0,.08);border:1px solid rgba(240,165,0,.35);border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;align-items:center;justify-content:space-between;gap:12px;">
  <span style="font-size:.85rem;color:#e6edf3;">📎 <b>{html.escape(fn)}</b> pronto para download</span>
  <a href="data:{mime};base64,{b64d}" download="{html.escape(fn)}" style="background:linear-gradient(135deg,#f0a500,#e05c2a);color:#060a10;font-weight:700;font-size:.78rem;padding:6px 16px;border-radius:20px;text-decoration:none;white-space:nowrap;">⬇ Baixar arquivo</a>
</div>""",unsafe_allow_html=True)

    # Chat input
    prompt=st.chat_input(t("type_message",ui_lang))
    if prompt:
        staged=st.session_state.get("staged_file")
        if staged:
            sl=staged if isinstance(staged,list) else [staged]
            for i,sf in enumerate(sl): _send_file(username,user,conv_id,sf["raw"],sf["name"],extra=prompt if i==0 else "")
            st.session_state.staged_file=None; st.session_state.pop("_last_files_key",None)
        else:
            append_message(username,conv_id,"user",prompt)
            st.session_state.speaking=True
            try:    send_to_claude(username,user,conv_id,prompt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking=False
        st.rerun()

    # Audio input
    audio_val=st.audio_input(" ",key=f"voice_input_{st.session_state.audio_key}",label_visibility="collapsed")
    if audio_val and audio_val!=st.session_state.get("_last_audio"):
        st.session_state["_last_audio"]=audio_val
        with st.spinner("Transcrevendo..."):
            txt=transcribe_bytes(audio_val.read(),".wav",None)
        if txt and not txt.startswith("❌") and not txt.startswith("⚠️"):
            append_message(username,conv_id,"user",txt,audio=True)
            st.session_state.speaking=True
            try:    send_to_claude(username,user,conv_id,txt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking=False; st.session_state.audio_key+=1; st.rerun()
        elif txt: st.error(txt)

    # File uploader — visível como botão clipe fixo via CSS acima
    uploaded_list=st.file_uploader("📎",key="file_upload",label_visibility="collapsed",
        accept_multiple_files=True,
        type=["mp3","wav","ogg","m4a","webm","flac","pdf","doc","docx","txt","png","jpg","jpeg","webp"])
    if uploaded_list:
        nk=",".join(sorted(f.name for f in uploaded_list))
        if nk!=st.session_state.get("_last_files_key"):
            st.session_state["_last_files_key"]=nk; sl=[]
            for uf in uploaded_list:
                raw=uf.read(); res=extract_file(raw,uf.name); sl.append({"raw":raw,"name":uf.name,"kind":res["kind"]})
            st.session_state.staged_file=sl; st.rerun()

    # TTS para botões Ouvir
    components.html("""<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;background:transparent;}</style>
</head><body><script>
(function(){
  var doc = window.parent.document;
  var cur = null;
  function attach() {
    doc.querySelectorAll('[data-pav-tts]').forEach(function(btn) {
      if (btn._pavInit) return; btn._pavInit = true;
      btn.onclick = function() {
        if (cur && cur!==btn) { speechSynthesis.cancel(); cur.textContent='▶ Ouvir'; cur.classList.remove('speaking'); cur=null; }
        if (btn.classList.contains('speaking')) { speechSynthesis.cancel(); btn.textContent='▶ Ouvir'; btn.classList.remove('speaking'); cur=null; return; }
        var u = new SpeechSynthesisUtterance(btn.getAttribute('data-text')||'');
        u.lang='en-US'; u.rate=0.95; speechSynthesis.getVoices();
        setTimeout(function(){
          var vv=speechSynthesis.getVoices();
          var v=vv.find(function(x){return x.lang==='en-US';})||vv.find(function(x){return x.lang.startsWith('en');});
          if(v) u.voice=v;
          u.onstart=function(){ btn.textContent='⏹ Parar'; btn.classList.add('speaking'); cur=btn; };
          u.onend=u.onerror=function(){ btn.textContent='▶ Ouvir'; btn.classList.remove('speaking'); cur=null; };
          speechSynthesis.cancel(); speechSynthesis.speak(u);
        }, 80);
      };
    });
  }
  attach();
  new MutationObserver(attach).observe(doc.body, {childList:true, subtree:true});
})();
</script></body></html>""", height=1)


def _inject_colors(ac, ub, ab):
    components.html(f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;background:transparent;}}</style>
</head><body><script>
(function(){{
  function hexToRgb(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];var n=parseInt(h,16);return[(n>>16)&255,(n>>8)&255,n&255].join(',');}}
  function luminance(h){{h=h.replace('#','');if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]*2;var n=parseInt(h,16);var r=(n>>16)&255,g=(n>>8)&255,b=n&255;return 0.299*r+0.587*g+0.114*b;}}
  var ac="{ac}",ub="{ub}",ab="{ab}",rgb=hexToRgb(ac),r=window.parent.document.documentElement;
  r.style.setProperty('--accent-full',ac);r.style.setProperty('--accent-70','rgba('+rgb+',.7)');
  r.style.setProperty('--user-bubble-bg',ub);r.style.setProperty('--user-bubble-text',luminance(ub)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-bg',ab);r.style.setProperty('--ai-bubble-text',luminance(ab)>128?'#111':'#e6edf3');
  r.style.setProperty('--ai-bubble-border','rgba('+hexToRgb(ab)+',.6)');
  var par=window.parent;
  if(par)par.document.querySelectorAll('audio').forEach(function(a){{a.pause();a.currentTime=0;}});
}})();
</script></body></html>""", height=1)