"""
ui_helpers.py — Teacher Tati · Helpers compartilhados entre todas as views.

Contém: i18n, PROF_NAME, SYSTEM_PROMPT, avatares, sessão JS,
        player de áudio, send_to_claude, do_logout.

Importado por app.py e por todos os módulos em tati_views/.
"""

import os
import base64
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import anthropic

# ── Variáveis de ambiente ─────────────────────────────────────────────────────
API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
PHOTO_PATH = os.getenv("PROFESSOR_PHOTO", "assets/tati.png")
PROF_NAME  = os.getenv("PROFESSOR_NAME",  "Professor Avatar")


# ══════════════════════════════════════════════════════════════════════════════
# INTERNACIONALIZAÇÃO
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
    return _STRINGS.get(lang, _STRINGS["pt-BR"]).get(key, _STRINGS["pt-BR"].get(key, key))


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, very intelligent and encouraging. You help adults speak English with more confidence, over 25 years of experience, Advanced English Hunter College NY, and passionate about teaching.
Students: teenagers (Beginner/Pre-Intermediate) and adults focused on Business/News.

BILINGUAL POLICY (VERY IMPORTANT)
BEGINNER / PRE-INTERMEDIATE:
  • Student writes/speaks in Portuguese → respond in simple English AND provide Portuguese translation of key words in parentheses.
  • Student mixes PT and EN → Celebrate English parts, supply missing English for Portuguese parts.
  • Always end with an easy encouraging question in English.

INTERMEDIATE:
  • Respond primarily in English. Use Portuguese ONLY to clarify specific words.
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

RULES:
- Simple English. Teens→Fortnite/Netflix/TikTok refs. Adults→LinkedIn/news/geopolitics.
- NEVER start a conversation uninvited. Wait for the student to speak first.

ACTIVITY GENERATION:
- When the student asks for a FILE (PDF, Word/DOCX), respond ONLY with:
  <<<GENERATE_FILE>>>
  {{"format":"pdf","filename":"activity.pdf","title":"Exercise Title","content":"Full content here with \\n for line breaks"}}
  <<<END_FILE>>>"""


# ══════════════════════════════════════════════════════════════════════════════
# IMAGENS / AVATARES
# ══════════════════════════════════════════════════════════════════════════════

def get_photo_b64() -> str | None:
    p = Path(PHOTO_PATH)
    if p.exists():
        ext  = p.suffix.lower().replace(".", "")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None


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
    """Carrega os 7 frames do avatar animado uma única vez."""
    _base = Path(__file__).parent
    def _load(candidates):
        for p in candidates:
            p = Path(p)
            if p.exists():
                return f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"
        return ""
    return {
        "base":     _load([_base/"assets"/"avatar_tati_normal.png",     "assets/avatar_tati_normal.png"]),
        "closed":   _load([_base/"assets"/"avatar_tati_closed.png",     "assets/avatar_tati_closed.png"]),
        "mid":      _load([_base/"assets"/"avatar_tati_meio.png",       "assets/avatar_tati_meio.png"]),
        "open":     _load([_base/"assets"/"avatar_tati_bem_aberta.png", "assets/avatar_tati_bem_aberta.png",
                           _base/"assets"/"avatar_tati_aberta.png",     "assets/avatar_tati_aberta.png"]),
        "smile":    _load([_base/"assets"/"avatar_tati_aberta.png",     "assets/avatar_tati_aberta.png"]),
        "wink":     _load([_base/"assets"/"tati_piscando.png",          "assets/tati_piscando.png"]),
        "surprise": _load([_base/"assets"/"tati_surpresa.png",          "assets/tati_surpresa.png"]),
    }


def get_user_avatar_b64(username: str, _bust: int = 0) -> str | None:
    from database import get_user_avatar_db
    result = get_user_avatar_db(username)
    if not result:
        return None
    raw, mime = result
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


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
        f'style="font-size:{icon_px}px;--fa-primary-color:#f0a500;'
        f'--fa-secondary-color:#c87800;--fa-secondary-opacity:0.6;"></i>'
        f'</div>'
    )


def save_user_avatar(username: str, raw: bytes, suffix: str) -> None:
    from database import save_user_avatar_db
    suffix = suffix.lower().lstrip(".")
    mime   = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    save_user_avatar_db(username, raw, mime)
    _bump_avatar_version()


def remove_user_avatar(username: str) -> None:
    from database import remove_user_avatar_db
    remove_user_avatar_db(username)
    _bump_avatar_version()


def _bump_avatar_version() -> None:
    st.session_state["_avatar_v"] = st.session_state.get("_avatar_v", 0) + 1


def user_avatar_html(username: str, size: int = 36, **_) -> str:
    return _avatar_circle_html(
        get_user_avatar_b64(username, _bust=st.session_state.get("_avatar_v", 0)),
        size,
    )


def avatar_html(size: int = 52, speaking: bool = False) -> str:
    photo = get_photo_b64()
    cls   = "speaking" if speaking else ""
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
# SESSÃO PERSISTENTE
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
.pf{{height:100%;background:linear-gradient(90deg,#f0a500,#e05c2a);border-radius:2px;width:0%;
     transition:width .1s linear;pointer-events:none;}}
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
    try{{var AC=window.AudioContext||window.webkitAudioContext;
        if(!AC)return;var ctx=new AC();
        var buf=ctx.createBuffer(1,1,22050);var src=ctx.createBufferSource();
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
# CLAUDE — envio de mensagens
# ══════════════════════════════════════════════════════════════════════════════

def send_to_claude(
    username: str, user: dict, conv_id: str,
    text: str, image_b64: str = None, image_media_type: str = None,
) -> str:
    from database import load_conversation, append_message, cached_load_conversation
    from tts import text_to_speech, tts_available

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

    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2000 if is_activity else 400,
        system=SYSTEM_PROMPT + context,
        messages=api_msgs,
    )
    reply_text = resp.content[0].text

    # Remove emojis
    reply_text = re.sub(
        r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF'
        r'\u2600-\u26FF\u2700-\u27BF\U0001FA00-\U0001FA6F'
        r'\U0001FA70-\U0001FAFF\u200d\ufe0f]',
        '', reply_text,
    ).strip()

    if "<<<GENERATE_FILE>>>" in reply_text:
        from tati_views.chat import _intercept_file_generation
        return _intercept_file_generation(reply_text, username, conv_id)

    tts_b64_str = None
    if tts_available():
        audio_bytes = text_to_speech(reply_text)
        if audio_bytes:
            import base64 as _b64
            tts_b64_str = _b64.b64encode(audio_bytes).decode()
            st.session_state["_tts_audio"] = tts_b64_str

    append_message(username, conv_id, "assistant", reply_text, tts_b64=tts_b64_str)
    cached_load_conversation.clear()
    return reply_text


# ══════════════════════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════════════════════

def do_logout() -> None:
    from database import delete_session
    token = st.session_state.get("_session_token", "")
    if token:
        delete_session(token)
    js_clear_session()
    st.session_state.pop("_session_token", None)
    st.session_state.pop("_session_saved", None)
    st.session_state.update(logged_in=False, user=None, conv_id=None)
