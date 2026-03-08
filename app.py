# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# app.py — Teacher Tati · English Learning AI
# Autor: Caio (programador) · Arquitetura: Streamlit + Claude + ElevenLabs TTS
# ══════════════════════════════════════════════════════════════════════════════

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
    create_session, validate_session, delete_session   # sessões persistentes
)
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from file_reader import extract_file

# ── Font Awesome (ícones de anexo, etc.) ─────────────────────────────────────
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">',
    unsafe_allow_html=True
)

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

# ── Avatares individuais dos alunos ───────────────────────────────────────────
AVATARS_DIR = Path("data/avatars")
AVATARS_DIR.mkdir(parents=True, exist_ok=True)

def get_user_avatar_b64(username: str) -> str | None:
    """Retorna a foto de perfil do usuário como data-URI, ou None."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = AVATARS_DIR / f"{username}.{ext}"
        if p.exists():
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None

def save_user_avatar(username: str, raw: bytes, suffix: str) -> str:
    """Salva a foto de perfil do usuário e retorna o data-URI."""
    suffix = suffix.lower().lstrip(".")
    if suffix == "jpg":
        suffix = "jpeg"
    # Remove arquivos anteriores de qualquer extensão
    for ext in ("jpg", "jpeg", "png", "webp"):
        old = AVATARS_DIR / f"{username}.{ext}"
        if old.exists():
            old.unlink()
    dest = AVATARS_DIR / f"{username}.{suffix}"
    dest.write_bytes(raw)
    return f"data:image/{suffix};base64,{base64.b64encode(raw).decode()}"

def remove_user_avatar(username: str) -> None:
    """Remove a foto de perfil do usuário."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = AVATARS_DIR / f"{username}.{ext}"
        if p.exists():
            p.unlink()

def user_avatar_html(username: str, size: int = 36, fallback_emoji: str = "🎓") -> str:
    """Retorna HTML de avatar circular do usuário (foto ou emoji fallback)."""
    b64 = get_user_avatar_b64(username)
    if b64:
        return (
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'background:url({b64}) center/cover;border:1.5px solid #f0a500;'
            f'flex-shrink:0;"></div>'
        )
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:linear-gradient(135deg,#1e2a3a,#2a3a50);'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:{int(size*.5)}px;flex-shrink:0;">{fallback_emoji}</div>'
    )

def avatar_html(size: int = 52, speaking: bool = False) -> str:
    """Avatar da professora com anel de 'speaking' animado."""
    cls   = "speaking" if speaking else ""
    photo = get_photo_b64()   # sempre fresco — pega upload recente
    if photo:
        return (
            f'<div class="avatar-wrap {cls}" style="width:{size}px;height:{size}px">'
            f'<img src="{photo}" class="avatar-img"/>'
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
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

load_css("styles/style.css")

# ── CSS responsivo global ──────────────────────────────────────────────────────
st.markdown("""<style>
section[data-testid="stMain"] > div {
    transition: all .25s ease;
    max-width: 100% !important;
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

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, and encouraging.
Students: teenagers (False Beginner/Pre-Intermediate) and adults focused on Business/News.

TEACHING STYLE:
- Neuro-learning: guide students to discover errors. Never just give the answer.
  Example: "he go" → "What ending do we add for he/she/it?"
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT conversational responses. Bold grammar points when appropriate.
- End responses with ONE engaging question.
- Use emojis and formatting (bold, etc.) ONLY if the student uses them or explicitly asks.
  Otherwise respond in plain, natural text.

RULES:
- Simple English. Teens→Fortnite/Netflix/TikTok refs. Adults→LinkedIn/news.
- Portuguese → acknowledge briefly, switch to English.
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


# ══════════════════════════════════════════════════════════════════════════════
# SESSÃO PERSISTENTE — funções de salvar/limpar no localStorage
# ══════════════════════════════════════════════════════════════════════════════

def js_save_session(token: str) -> None:
    """
    Persiste o token no localStorage + cookie via iframe com height=1.
    height=0 é descartado pelo Streamlit Cloud — height=1 garante execução.
    """
    components.html(
        f"""<!DOCTYPE html><html><body><script>
        (function() {{
            var token = '{token}';
            var maxAge = 60 * 60 * 24 * 30;
            try {{
                window.parent.document.cookie = 'pav_session=' + encodeURIComponent(token)
                    + ';max-age=' + maxAge + ';path=/;SameSite=Lax';
            }} catch(e) {{}}
            try {{ window.parent.localStorage.setItem('pav_session', token); }} catch(e) {{}}
            try {{ localStorage.setItem('pav_session', token); }} catch(e) {{}}
        }})();
        </script></body></html>""",
        height=1
    )

def js_clear_session() -> None:
    """Remove o token de sessão de cookie e localStorage."""
    components.html(
        """<!DOCTYPE html><html><body><script>
        (function() {
            try {
                window.parent.document.cookie = 'pav_session=;max-age=0;path=/;SameSite=Lax';
            } catch(e) {}
            try { window.parent.localStorage.removeItem('pav_session'); } catch(e) {}
            try { window.parent.localStorage.removeItem('pav_user'); } catch(e) {}
            try { localStorage.removeItem('pav_session'); } catch(e) {}
            try { localStorage.removeItem('pav_user'); } catch(e) {}
        })();
        </script></body></html>""",
        height=1
    )

# ── PATCH 2: Auto-login (bloco completo — substitui o bloco "AUTO-LOGIN" atual)
# Substitua o bloco que começa com "if not st.session_state.logged_in:"
# e termina antes de "HELPERS DE CONVERSA" pelo código abaixo:

if not st.session_state.logged_in:

    # JS lê token do cookie/localStorage e injeta na URL como query param
    # height=1 garante execução no Streamlit Cloud (height=0 é descartado)
    components.html("""<!DOCTYPE html><html><body><script>
    (function() {
        function readToken() {
            // Tenta cookie do parent
            try {
                var match = window.parent.document.cookie.split(';')
                    .map(function(c) { return c.trim(); })
                    .find(function(c) { return c.startsWith('pav_session='); });
                if (match) {
                    var val = decodeURIComponent(match.split('=')[1]);
                    if (val && val.length > 5) return val;
                }
            } catch(e) {}
            // Tenta localStorage do parent
            try {
                var v = window.parent.localStorage.getItem('pav_session');
                if (v && v.length > 5) return v;
            } catch(e) {}
            // Tenta localStorage local
            try {
                var v2 = localStorage.getItem('pav_session')
                      || localStorage.getItem('pav_user') || '';
                if (v2 && v2.length > 5) return v2;
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
                st.session_state.logged_in          = True
                st.session_state.user               = {"username": uname, **udata}
                st.session_state.page               = "dashboard" if udata["role"] == "professor" else "chat"
                st.session_state.conv_id            = None
                st.session_state["_session_token"]  = token
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


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE CONVERSA / CLAUDE
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_conv(username: str) -> str:
    """Retorna o conv_id ativo ou cria uma nova conversa."""
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id


def send_to_claude(username: str, user: dict, conv_id: str,
                   text: str, image_b64: str = None, image_media_type: str = None) -> str:
    """
    Envia a mensagem ao Claude Haiku, obtém a resposta,
    gera TTS opcional e salva no banco.
    Retorna o texto da resposta.
    """
    client  = anthropic.Anthropic(api_key=API_KEY)
    context = f"\n\nStudent: Name={user['name']}, Level={user['level']}, Focus={user['focus']}."

    # Monta histórico da conversa para a API
    msgs     = load_conversation(username, conv_id)
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
        return display_msg

    except Exception as e:
        err = f"Desculpe, não consegui gerar o arquivo: {e}"
        append_message(username, conv_id, "assistant", err)
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
            if st.button("🔑 Entrar", use_container_width=True, key="tab_btn_login",
                         type="primary" if st.session_state["_login_tab"] == "login" else "secondary"):
                st.session_state["_login_tab"] = "login"; st.rerun()
        with c2:
            if st.button("✨ Criar Conta", use_container_width=True, key="tab_btn_reg",
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
            with st.form("form_login", clear_on_submit=False):
                u = st.text_input("Username", placeholder="seu.usuario", key="li_u")
                p = st.text_input("Senha", type="password", placeholder="••••••••", key="li_p")
                submitted = st.form_submit_button("Entrar →", use_container_width=True)
                if submitted:
                    if not u or not p:
                        st.error("❌ Preencha todos os campos.")
                    else:
                        user = authenticate(u, p)
                        if user:
                            real_u = user.get("_resolved_username", u.lower())

                            # Atualiza session state
                            st.session_state.update(
                                logged_in=True,
                                user={"username": real_u, **user},
                                page="dashboard" if user["role"] == "professor" else "chat",
                                conv_id=None
                            )

                            # ── Cria sessão persistente ───────────────────────
                            token = create_session(real_u)
                            st.session_state["_session_token"] = token
                            js_save_session(token)  # persiste no localStorage
                            # ─────────────────────────────────────────────────

                            st.rerun()
                        else:
                            st.error("❌ Usuário ou senha incorretos.")

        # ── Aba REGISTRO ──────────────────────────────────────────────────────
        else:
            with st.form("form_reg", clear_on_submit=False):
                rn = st.text_input("Nome completo", placeholder="João Silva",     key="r_n")
                re = st.text_input("E-mail",        placeholder="joao@email.com", key="r_e")
                ru = st.text_input("Username",       placeholder="joao.silva",    key="r_u")
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

    st.markdown("## ⚙️ Configurações do Perfil")
    st.markdown("---")

    is_prof    = user.get("role") == "professor"
    level_opts = ["False Beginner", "Pre-Intermediate", "Intermediate", "Business English", "Advanced", "Native"]
    focus_opts = ["General Conversation", "Sports & Games", "Business & News", "Series & Pop Culture", "Teaching"]

    def safe_index(lst, val, default=0):
        try:    return lst.index(val)
        except: return default

    tab_geral, tab_pers, tab_conta = st.tabs(["🎨 Geral", "🧠 Personalização", "👤 Conta"])

    # ── Aba Geral ─────────────────────────────────────────────────────────────
    with tab_geral:
        st.markdown("### Aparência")
        col1, col2 = st.columns(2)
        with col1:
            theme = st.selectbox("Tema", ["dark", "light", "system"],
                index=safe_index(["dark", "light", "system"], profile.get("theme", "dark")), key="pf_theme")
            lang  = st.selectbox("Idioma da interface", ["pt-BR", "en-US", "en-UK"],
                index=safe_index(["pt-BR", "en-US", "en-UK"], profile.get("language", "pt-BR")), key="pf_lang")
        with col2:
            accent = st.color_picker("Cor de destaque",
                value=profile.get("accent_color", "#f0a500"), key="pf_accent")

        st.markdown("### Voz")
        col3, col4 = st.columns(2)
        with col3:
            voice_lang = st.selectbox("Idioma da transcrição (Whisper)", ["en", "pt", "es", "fr", "de"],
                index=safe_index(["en", "pt", "es", "fr", "de"], profile.get("voice_lang", "en")), key="pf_vlang")
        with col4:
            speech_lang = st.selectbox("Sotaque (TTS fallback)", ["en-US", "en-UK", "pt-BR"],
                index=safe_index(["en-US", "en-UK", "pt-BR"], profile.get("speech_lang", "en-US")), key="pf_slang")

        if st.button("💾 Salvar Geral", key="save_geral"):
            update_profile(username, {"theme": theme, "language": lang,
                "accent_color": accent, "voice_lang": voice_lang, "speech_lang": speech_lang})
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Configurações salvas!")

    # ── Aba Personalização ────────────────────────────────────────────────────
    with tab_pers:
        st.markdown("### Sobre Você")
        col1, col2 = st.columns(2)
        with col1:
            nickname   = st.text_input("Apelido", value=profile.get("nickname", ""), key="pf_nick")
            occupation = st.text_input("Ocupação", value=profile.get("occupation", ""),
                placeholder="ex: Professora, Desenvolvedor", key="pf_occ")
        with col2:
            level = st.selectbox("Nível de inglês", level_opts,
                index=safe_index(level_opts, user.get("level", "False Beginner")), key="pf_level")
            focus = st.selectbox("Foco", focus_opts,
                index=safe_index(focus_opts, user.get("focus", "General Conversation")), key="pf_focus")

        if not is_prof:
            st.markdown("### Estilo da IA")
            col3, col4 = st.columns(2)
            ai_style_opts = ["Warm & Encouraging", "Formal & Professional", "Fun & Casual", "Strict & Direct"]
            ai_tone_opts  = ["Teacher", "Conversation Partner", "Tutor", "Business Coach"]
            with col3:
                ai_style = st.selectbox("Tom das conversas", ai_style_opts,
                    index=safe_index(ai_style_opts, profile.get("ai_style", "Warm & Encouraging")), key="pf_aistyle")
            with col4:
                ai_tone = st.selectbox("Papel da IA", ai_tone_opts,
                    index=safe_index(ai_tone_opts, profile.get("ai_tone", "Teacher")), key="pf_aitone")
            custom = st.text_area("Instruções personalizadas para a IA",
                value=profile.get("custom_instructions", ""),
                placeholder="ex: Sempre me corrija quando eu errar o Past Simple.",
                height=100, key="pf_custom")
        else:
            ai_style = profile.get("ai_style", "Warm & Encouraging")
            ai_tone  = profile.get("ai_tone",  "Teacher")
            custom   = profile.get("custom_instructions", "")

        if st.button("💾 Salvar Personalização", key="save_pers"):
            update_profile(username, {"nickname": nickname, "occupation": occupation,
                "ai_style": ai_style, "ai_tone": ai_tone, "custom_instructions": custom,
                "level": level, "focus": focus})
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Perfil salvo!")

    # ── Aba Conta ─────────────────────────────────────────────────────────────
    with tab_conta:
        st.markdown("### 📸 Foto de Perfil")
        cur_avatar = get_user_avatar_b64(username)
        MAX_BYTES  = 15 * 1024 * 1024

        col_av, col_btns = st.columns([1, 3])
        with col_av:
            if cur_avatar:
                st.markdown(
                    f'<div style="width:88px;height:88px;border-radius:50%;'
                    f'background:url({cur_avatar}) center/cover;'
                    f'border:2.5px solid #f0a500;'
                    f'box-shadow:0 0 0 4px rgba(240,165,0,.15);"></div>',
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="width:88px;height:88px;border-radius:50%;'
                    'background:linear-gradient(135deg,#1e2a3a,#2a3a50);'
                    'display:flex;align-items:center;justify-content:center;'
                    'font-size:36px;border:2px solid #30363d;">🎓</div>',
                    unsafe_allow_html=True)
        with col_btns:
            photo_file = st.file_uploader(
                "Alterar foto — JPG, PNG ou WEBP (máx 15 MB)",
                type=["jpg", "jpeg", "png", "webp"], key="pf_photo_upload")
            if photo_file:
                file_id = f"{photo_file.name}_{photo_file.size}"
                if st.session_state.get("_last_photo_saved") != file_id:
                    raw_photo = photo_file.read()
                    if len(raw_photo) > MAX_BYTES:
                        st.error("❌ Foto muito grande. Máximo 15 MB.")
                    else:
                        suffix = Path(photo_file.name).suffix.lstrip(".")
                        save_user_avatar(username, raw_photo, suffix)
                        st.session_state["_last_photo_saved"] = file_id
                        st.success("✅ Foto salva! Ela aparecerá no chat.")
            if cur_avatar:
                if st.button("🗑️ Remover foto", key="pf_remove_photo"):
                    remove_user_avatar(username)
                    st.session_state.pop("_last_photo_saved", None)
                    st.success("Foto removida."); st.rerun()

        st.markdown("---")
        st.markdown("### Informações da Conta")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Nome completo", value=user.get("name", ""), key="pf_fname")
        with col2:
            email = st.text_input("E-mail", value=user.get("email", ""), key="pf_email")

        st.markdown(f"**Username:** `{username}`")
        st.markdown(f"**Conta criada em:** {user.get('created_at', '')[:10]}")

        if st.button("💾 Salvar Dados", key="save_conta"):
            update_profile(username, {"name": full_name, "email": email})
            u = load_students().get(username, {})
            st.session_state.user = {"username": username, **u}
            st.success("✅ Dados atualizados!")

        st.markdown("---")
        st.markdown("### Alterar Senha")
        col3, col4 = st.columns(2)
        with col3:
            new_pw  = st.text_input("Nova senha", type="password", key="pf_newpw")
        with col4:
            conf_pw = st.text_input("Confirmar senha", type="password", key="pf_confpw")

        if st.button("🔒 Alterar Senha", key="save_pw"):
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
    txt = transcribe_bytes(raw, suffix=".webm", language=lang)
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
    if tts_available():
        ab = text_to_speech(reply)
        if ab:
            tts_b64 = base64.b64encode(ab).decode()

    st.session_state["_vm_reply"]   = reply
    st.session_state["_vm_tts_b64"] = tts_b64

    # Persiste no histórico da conversa atual
    append_message(username, conv_id, "user",      txt,   audio=True)
    append_message(username, conv_id, "assistant", reply, tts_b64=tts_b64 or None)


def show_voice_mode() -> None:
    """
    Renderiza o modo de conversa por voz com:
    - Avatar animado (morph de 3 imagens: closed/mid/open)
    - VAD (detecção automática de silêncio)
    - Animações: respiração, piscar, inclinação de cabeça
    - Painel de debug para o usuário 'programador'
    """
    user     = st.session_state.user
    username = user["username"]
    profile  = user.get("profile", {})
    whisper_lang    = profile.get("voice_lang",  "en")
    speech_lang_val = profile.get("speech_lang", "en-US")
    is_dev   = (username == "programador")

    conv_id = get_or_create_conv(username)

    if st.button("✕ Fechar Modo Voz", key="close_voice_inner"):
        st.session_state.voice_mode = False
        for k in ["_vm_history", "_vm_reply", "_vm_tts_b64", "_vm_user_said",
                  "_vm_error", "_vm_last_upload"]:
            st.session_state.pop(k, None)
        st.rerun()

    # Uploader oculto — recebe o blob de áudio enviado pelo JS
    audio_upload = st.file_uploader(
        "vm_audio", key="vm_audio_upload", label_visibility="collapsed",
        type=["webm", "wav", "ogg", "mp4", "m4a"])
    if audio_upload:
        uid = f"{audio_upload.name}_{audio_upload.size}"
        if uid != st.session_state.get("_vm_last_upload"):
            st.session_state["_vm_last_upload"] = uid
            for k in ["_vm_reply", "_vm_tts_b64", "_vm_user_said", "_vm_error"]:
                st.session_state.pop(k, None)
            _vm_process_audio(audio_upload.read(), whisper_lang, conv_id)
            st.rerun()

    user_said = st.session_state.get("_vm_user_said", "")
    reply     = st.session_state.get("_vm_reply",     "")
    tts_b64   = st.session_state.get("_vm_tts_b64",   "")
    vm_error  = st.session_state.get("_vm_error",     "")

    # ── Carrega as 3 imagens do avatar (closed / mid / open) ─────────────────
    def load_avatar(filename: str) -> str:
        p = Path(f"data/avatars/{filename}")
        if p.exists():
            b64  = base64.b64encode(p.read_bytes()).decode()
            ext  = p.suffix.lstrip(".")
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            return f"data:image/{mime};base64,{b64}"
        return ""

    src_closed = load_avatar("avatar_closed.png") or load_avatar("avatar.png") or PHOTO_B64 or ""
    src_mid    = load_avatar("avatar_mid.png")    or src_closed
    src_open   = load_avatar("avatar_open.png")   or src_closed

    # Serializa dados Python → JS com json.dumps para evitar problemas de aspas
    us_js     = json.dumps(user_said)
    rep_js    = json.dumps(reply)
    tts_js    = json.dumps(tts_b64)
    err_js    = json.dumps(vm_error)
    pnm_js    = json.dumps(PROF_NAME)
    sl_js     = json.dumps(speech_lang_val)
    is_dev_js = json.dumps(is_dev)
    role_js   = json.dumps(user.get("role", "student"))

    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
:root{{--bg:#080c12;--surface:#0f1419;--border:#1e2530;
       --accent:#f0a500;--accent2:#e05c2a;--text:#e6edf3;--muted:#8b949e;
       --green:#3fb950;--red:#f85149;--blue:#58a6ff;}}
html,body{{background:var(--bg);font-family:'Sora',sans-serif;color:var(--text);height:100%;overflow:hidden;}}
#three-canvas{{display:block;}}

.vm{{display:flex;flex-direction:column;align-items:center;justify-content:center;
     height:100vh;gap:16px;padding:20px;
     background:radial-gradient(ellipse at 50% 25%,rgba(240,165,0,.07) 0%,transparent 60%);}}

.avatar-wrap{{
  position:relative;width:220px;height:220px;
  border-radius:50%;overflow:hidden;flex-shrink:0;
  box-shadow:0 0 40px rgba(240,165,0,.2);
}}

/* Painel debug */
#debug-panel{{
  position:fixed;top:10px;right:10px;
  background:rgba(10,16,24,.95);border:1px solid var(--accent);
  border-radius:10px;padding:12px 16px;font-size:.72rem;z-index:9999;
  min-width:220px;display:none;
}}
#debug-toggle{{
  position:fixed;top:10px;right:10px;
  background:rgba(240,165,0,.15);border:1px solid var(--accent);
  border-radius:6px;color:var(--accent);font-size:.65rem;
  padding:3px 8px;cursor:pointer;z-index:10000;display:none;
}}

.info{{text-align:center;}}
.prof-name{{font-size:1rem;font-weight:700;color:var(--accent);margin-bottom:3px;}}
.status{{font-size:.78rem;color:var(--muted);transition:color .3s;}}
.status.s-listening{{color:var(--green);}}.status.s-speaking{{color:var(--accent);}}.status.s-processing{{color:var(--blue);}}

.transcript{{max-width:480px;width:100%;background:var(--surface);border:1px solid var(--border);
             border-radius:14px;padding:12px 16px;font-size:.84rem;line-height:1.65;min-height:60px;}}
.t-label{{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}}
.t-user{{color:#adbac7;margin-bottom:6px;display:none;}}
.t-sep{{border:none;border-top:1px solid var(--border);margin:6px 0;display:none;}}
.t-ai{{color:var(--text);display:none;}}.t-wait{{color:#3d4a5c;font-style:italic;}}

.sil{{width:130px;height:3px;background:var(--border);border-radius:2px;overflow:hidden;visibility:hidden;margin:0 auto;}}
.sil-fill{{height:100%;background:linear-gradient(90deg,var(--green),var(--accent));border-radius:2px;width:0%;}}
.sil.show{{visibility:visible;}}

.mic-btn{{width:64px;height:64px;border-radius:50%;border:none;cursor:pointer;font-size:26px;
          display:flex;align-items:center;justify-content:center;
          background:linear-gradient(135deg,var(--green),#2ea043);
          box-shadow:0 0 20px rgba(63,185,80,.3);transition:all .2s;}}
.mic-btn:hover{{transform:scale(1.07);}}
.mic-btn.active{{background:linear-gradient(135deg,var(--red),#c03030);
                 box-shadow:0 0 26px rgba(248,81,73,.5);
                 animation:mpulse .8s ease-in-out infinite alternate;}}
@keyframes mpulse{{from{{box-shadow:0 0 14px rgba(248,81,73,.3);}}to{{box-shadow:0 0 32px rgba(248,81,73,.7);}}}}
.hint{{font-size:.65rem;color:#2d3a4a;text-align:center;}}
.err{{font-size:.74rem;color:var(--red);text-align:center;max-width:340px;min-height:18px;}}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head><body>

<button id="debug-toggle" onclick="toggleDebug()" style="display:none">⚙ Debug</button>
<div id="debug-panel"></div>

<div class="vm" id="vm">
  <div class="avatar-wrap" id="avatarWrap"></div>
  <div class="info">
    <div class="prof-name">{PROF_NAME}</div>
    <div class="status" id="status">Clique no microfone para falar</div>
  </div>
  <div class="transcript">
    <div class="t-label" id="tLabel">Aguardando...</div>
    <div class="t-user" id="tUser"></div>
    <hr class="t-sep" id="tSep">
    <div class="t-ai" id="tAi"></div>
    <div class="t-wait" id="tWait">—</div>
  </div>
  <div class="sil" id="sil"><div class="sil-fill" id="silFill"></div></div>
  <button class="mic-btn" id="micBtn">🎤</button>
  <div class="hint">Detecção automática de silêncio (1.5s)</div>
  <div class="err" id="errBox"></div>
</div>

<script>
const PY_USER_SAID = {us_js};
const PY_REPLY     = {rep_js};
const PY_TTS_B64   = {tts_js};
const PY_ERROR     = {err_js};
const SPEECH_LANG  = {sl_js};
const PROF_NAME    = {pnm_js};
const IS_DEV       = {is_dev_js};
const USER_ROLE    = {role_js};

// ── Three.js Avatar ──────────────────────────────────────────────────────────
const wrap = document.getElementById('avatarWrap');
const W = 220, H = 220;

const renderer = new THREE.WebGLRenderer({{antialias:true, alpha:true}});
renderer.setSize(W, H);
renderer.domElement.style.width = '100%';   
renderer.domElement.style.height = '100%';  
renderer.setPixelRatio(window.devicePixelRatio || 1);
renderer.shadowMap.enabled = true;
renderer.domElement.id = 'three-canvas';
wrap.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, W/H, 0.1, 100);
camera.position.set(0, 0.3, 4.2);
camera.lookAt(0, 0.3, 0);

// Lighting
const ambient = new THREE.AmbientLight(0xffeedd, 0.7);
scene.add(ambient);
const keyLight = new THREE.DirectionalLight(0xfff5e0, 1.2);
keyLight.position.set(2, 4, 3);
scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(0xe0eeff, 0.4);
fillLight.position.set(-3, 1, 2);
scene.add(fillLight);
const rimLight = new THREE.DirectionalLight(0xf0a500, 0.3);
rimLight.position.set(0, -2, -3);
scene.add(rimLight);

// ── Avatar builder ───────────────────────────────────────────────────────────
// Builds a cartoon avatar based on role: 'professor' = female Teacher Tati
// any other role = male student avatar

const isFemale = (USER_ROLE === 'professor');

function buildAvatar(female) {{
  const g = new THREE.Group();
  scene.add(g);

  // ── Shared helpers ──────────────────────────────────────────────────────────
  function mat(hex, opts={{}}) {{
    return new THREE.MeshToonMaterial({{color: hex, ...opts}});
  }}

  // ── Color palette ───────────────────────────────────────────────────────────
  const skinColor   = female ? 0xf0d0b8 : 0x8b5c3a;
  const hairColor   = female ? 0x3a2010 : 0x1a0d00;
  const irisColor   = female ? 0x5a3a20 : 0x3a2810;
  const lipColor    = female ? 0xc05060 : 0x8a5048;
  const glassColor  = female ? 0x2a2a8a : 0xb0883a;
  const shirtColor  = female ? 0xf0f0f0 : 0x101418;
  const blushColor  = female ? 0xf0a0b0 : 0x7a3a2a;
  const earringColor= female ? 0xb08040 : 0xd4a030;

  const skinMat   = mat(skinColor);
  const hairMat   = mat(hairColor);
  const eyeWMat   = mat(0xffffff);
  const irisMat   = mat(irisColor);
  const pupilMat  = mat(0x0a0808);
  const lipMat    = mat(lipColor);
  const mouthMat  = mat(0x1a0505);
  const teethMat  = mat(0xfaf8f5);
  const blushMat  = mat(blushColor, {{transparent:true, opacity:0.3}});
  const glassMat  = mat(glassColor);
  const glassFrm  = mat(female ? 0x1a1a6a : 0x8a6828);
  const shirtMat  = mat(shirtColor);
  const darkMat   = mat(hairColor);

  // ── HEAD ────────────────────────────────────────────────────────────────────
  const head = new THREE.Group();
  g.add(head);

  // Face shape — female rounder, male slightly squarer
  const faceGeo = new THREE.SphereGeometry(1, 32, 32);
  faceGeo.scale(female ? 1.0 : 1.05, female ? 1.1 : 1.08, 0.88);
  head.add(new THREE.Mesh(faceGeo, skinMat));

  // Jaw
  const jawGeo = new THREE.SphereGeometry(female ? 0.52 : 0.58, 16, 16);
  jawGeo.scale(female ? 0.95 : 1.05, female ? 0.55 : 0.62, 0.85);
  const jaw = new THREE.Mesh(jawGeo, skinMat);
  jaw.position.set(0, -0.9, 0.08);
  head.add(jaw);

  // Neck
  const neckGeo = new THREE.CylinderGeometry(
    female ? 0.26 : 0.32, female ? 0.30 : 0.36, 0.5, 16);
  const neck = new THREE.Mesh(neckGeo, skinMat);
  neck.position.set(0, -1.5, 0);
  head.add(neck);

  // Shoulders
  const shGeo = new THREE.SphereGeometry(1, 16, 8);
  shGeo.scale(female ? 1.5 : 1.7, 0.45, 0.65);
  const shoulders = new THREE.Mesh(shGeo, shirtMat);
  shoulders.position.set(0, -2.1, -0.1);
  head.add(shoulders);

  // Collar / shirt detail
  if (female) {{
    // White blouse collar
    const colGeo = new THREE.TorusGeometry(0.28, 0.09, 8, 16);
    const col = new THREE.Mesh(colGeo, mat(0xffffff));
    col.position.set(0, -1.72, 0.16);
    col.rotation.x = 0.4;
    head.add(col);
  }} else {{
    // Open shirt collar — two small panels
    [[-0.18, 0.08], [0.18, -0.08]].forEach(([x, rz]) => {{
      const panelGeo = new THREE.BoxGeometry(0.18, 0.3, 0.04);
      const panel = new THREE.Mesh(panelGeo, mat(0x101418));
      panel.position.set(x, -1.8, 0.25);
      panel.rotation.z = rz;
      head.add(panel);
    }});
    // Chain necklace (gold line)
    const chainGeo = new THREE.TorusGeometry(0.3, 0.015, 6, 24);
    const chain = new THREE.Mesh(chainGeo, mat(earringColor));
    chain.position.set(0, -1.88, 0.1);
    chain.rotation.x = 0.5;
    head.add(chain);
  }}

  // ── HAIR ────────────────────────────────────────────────────────────────────
  if (female) {{
    // Short brown hair, slightly wavy — Teacher Tati style
    const topGeo = new THREE.SphereGeometry(1.06, 32, 32);
    topGeo.scale(1.0, 0.62, 0.9);
    const topMesh = new THREE.Mesh(topGeo, hairMat);
    topMesh.position.set(0, 0.42, -0.05);
    head.add(topMesh);

    // Side wisps
    [[-0.92, 0.08], [0.92, 0.08]].forEach(([x, z]) => {{
      const sg = new THREE.SphereGeometry(0.38, 16, 16);
      sg.scale(0.5, 1.1, 0.55);
      const sm = new THREE.Mesh(sg, hairMat);
      sm.position.set(x, -0.1, z);
      head.add(sm);
    }});

    // Back
    const bgeo = new THREE.SphereGeometry(0.88, 16, 16);
    bgeo.scale(0.95, 1.05, 0.55);
    const bm = new THREE.Mesh(bgeo, hairMat);
    bm.position.set(0, -0.05, -0.85);
    head.add(bm);

  }} else {{
    // Very short black hair — close-cropped
    const topGeo = new THREE.SphereGeometry(1.04, 32, 32);
    topGeo.scale(1.05, 0.45, 0.92);
    const topMesh = new THREE.Mesh(topGeo, hairMat);
    topMesh.position.set(0, 0.62, -0.04);
    head.add(topMesh);

    // Temple sides — very thin
    [-1, 1].forEach(side => {{
      const sg = new THREE.SphereGeometry(0.3, 12, 12);
      sg.scale(0.38, 0.9, 0.5);
      const sm = new THREE.Mesh(sg, hairMat);
      sm.position.set(side * 1.0, 0.1, -0.05);
      head.add(sm);
    }});
  }}

  // ── EYEBROWS ────────────────────────────────────────────────────────────────
  const browY = female ? 0.5 : 0.48;
  [[-0.38, female ? 0.06 : 0.04], [0.38, female ? -0.06 : -0.04]].forEach(([x, rz]) => {{
    const bg = new THREE.BoxGeometry(female ? 0.28 : 0.32, female ? 0.04 : 0.05, 0.04);
    const bm = new THREE.Mesh(bg, darkMat);
    bm.position.set(x, browY, 0.87);
    bm.rotation.z = rz;
    head.add(bm);
  }});

  // ── EYES ────────────────────────────────────────────────────────────────────
  const eyeGroups = [];
  const eyelids = [];
  [-0.37, 0.37].forEach(x => {{
    const eg = new THREE.Group();
    eg.position.set(x, 0.24, 0.86);
    head.add(eg);

    const white = new THREE.Mesh(new THREE.SphereGeometry(0.165, 16, 16), eyeWMat);
    white.scale(1, 0.82, 0.58);
    eg.add(white);

    const iris = new THREE.Mesh(new THREE.CircleGeometry(0.095, 16), irisMat);
    iris.position.set(0, 0, 0.096);
    eg.add(iris);

    const pupil = new THREE.Mesh(new THREE.CircleGeometry(0.052, 16), pupilMat);
    pupil.position.set(0, 0, 0.098);
    eg.add(pupil);

    // Eye shine
    const shine = new THREE.Mesh(new THREE.CircleGeometry(0.022, 8), mat(0xffffff));
    shine.position.set(0.03, 0.03, 0.1);
    eg.add(shine);

    // Eyelid for blinking
    const lidGeo = new THREE.SphereGeometry(0.175, 16, 8, 0, Math.PI*2, 0, Math.PI/2);
    const lid = new THREE.Mesh(lidGeo, skinMat);
    lid.position.set(0, 0.01, 0);
    lid.rotation.x = -Math.PI;
    lid.scale.set(1, 0.82, 0.6);
    eg.add(lid);
    eyelids.push(lid);
    eyeGroups.push(eg);
  }});

  // ── GLASSES ─────────────────────────────────────────────────────────────────
  if (female) {{
    // Cat-eye glasses — blue/purple thick frames
    [-0.37, 0.37].forEach((x, i) => {{
      // Frame shape — slightly angled cat-eye
      const frameGeo = new THREE.TorusGeometry(0.22, 0.04, 8, 20);
      frameGeo.scale(1, female ? 0.78 : 0.82, 0.3);
      const frame = new THREE.Mesh(frameGeo, glassMat);
      frame.position.set(x, 0.25, 0.86);
      // Cat-eye: tilt outer corner up
      frame.rotation.z = i === 0 ? 0.18 : -0.18;
      head.add(frame);
    }});
    // Bridge
    const bridgeGeo = new THREE.CylinderGeometry(0.015, 0.015, 0.22, 8);
    const bridge = new THREE.Mesh(bridgeGeo, glassMat);
    bridge.rotation.z = Math.PI / 2;
    bridge.position.set(0, 0.27, 0.9);
    head.add(bridge);
    // Temples
    [-0.6, 0.6].forEach(x => {{
      const tempGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.35, 8);
      const temp = new THREE.Mesh(tempGeo, glassMat);
      temp.rotation.z = Math.PI / 2;
      temp.position.set(x * 0.88, 0.25, 0.7);
      temp.rotation.y = x > 0 ? -0.5 : 0.5;
      head.add(temp);
    }});
  }} else {{
    // Thin rose-gold rectangular glasses
    [-0.38, 0.38].forEach((x, i) => {{
      const frameGeo = new THREE.TorusGeometry(0.19, 0.025, 6, 20);
      frameGeo.scale(1.1, 0.72, 0.25);
      const frame = new THREE.Mesh(frameGeo, glassFrm);
      frame.position.set(x, 0.24, 0.88);
      head.add(frame);
    }});
    // Bridge
    const bGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.2, 6);
    const bridge = new THREE.Mesh(bGeo, glassFrm);
    bridge.rotation.z = Math.PI / 2;
    bridge.position.set(0, 0.26, 0.92);
    head.add(bridge);
    // Temples
    [-0.58, 0.58].forEach(x => {{
      const tGeo = new THREE.CylinderGeometry(0.01, 0.01, 0.32, 6);
      const temp = new THREE.Mesh(tGeo, glassFrm);
      temp.rotation.z = Math.PI / 2;
      temp.position.set(x * 0.86, 0.24, 0.72);
      temp.rotation.y = x > 0 ? -0.45 : 0.45;
      head.add(temp);
    }});
  }}

  // ── NOSE ────────────────────────────────────────────────────────────────────
  const noseGeo = new THREE.SphereGeometry(female ? 0.1 : 0.13, 8, 8);
  noseGeo.scale(1, 0.7, 1.1);
  const nose = new THREE.Mesh(noseGeo, skinMat);
  nose.position.set(0, -0.07, 0.94);
  head.add(nose);

  // ── GOATEE (male only) ──────────────────────────────────────────────────────
  if (!female) {{
    // Light goatee/stubble under lip
    const goateeGeo = new THREE.SphereGeometry(0.22, 12, 8);
    goateeGeo.scale(0.9, 0.6, 0.5);
    const goatee = new THREE.Mesh(goateeGeo, hairMat);
    goatee.position.set(0, -0.62, 0.78);
    head.add(goatee);
    // Mustache area dots
    const mustGeo = new THREE.SphereGeometry(0.28, 12, 8);
    mustGeo.scale(1.1, 0.22, 0.4);
    const must = new THREE.Mesh(mustGeo, mat(0x2a1a0a, {{transparent:true, opacity:0.4}}));
    must.position.set(0, -0.33, 0.9);
    head.add(must);
  }}

  // ── BLUSH ────────────────────────────────────────────────────────────────────
  [-0.52, 0.52].forEach(x => {{
    const bg = new THREE.CircleGeometry(female ? 0.18 : 0.14, 16);
    const bm = new THREE.Mesh(bg, blushMat);
    bm.position.set(x, 0.04, 0.88);
    head.add(bm);
  }});

  // ── EARRINGS / EARS ──────────────────────────────────────────────────────────
  [-1.0, 1.0].forEach(x => {{
    if (female) {{
      // Round drop earrings
      const earGeo = new THREE.SphereGeometry(0.1, 8, 8);
      const earMesh = new THREE.Mesh(earGeo, mat(earringColor));
      earMesh.position.set(x, -0.35, 0);
      head.add(earMesh);
    }} else {{
      // No earrings — just ear shape
      const earGeo = new THREE.SphereGeometry(0.15, 8, 8);
      earGeo.scale(0.4, 0.6, 0.4);
      const earMesh = new THREE.Mesh(earGeo, skinMat);
      earMesh.position.set(x * 1.0, 0.0, 0.0);
      head.add(earMesh);
    }}
  }});

  // ── MOUTH ────────────────────────────────────────────────────────────────────
  const mouthGroup = new THREE.Group();
  mouthGroup.position.set(0, female ? -0.36 : -0.38, 0.89);
  head.add(mouthGroup);

  const upperLip = new THREE.Mesh(
    new THREE.TorusGeometry(female ? 0.17 : 0.19, female ? 0.038 : 0.042, 8, 16, Math.PI),
    lipMat
  );
  upperLip.rotation.x = -0.3;
  mouthGroup.add(upperLip);

  const lowerLip = new THREE.Mesh(
    new THREE.TorusGeometry(female ? 0.18 : 0.20, female ? 0.048 : 0.052, 8, 16, Math.PI),
    lipMat
  );
  lowerLip.rotation.x = Math.PI + 0.3;
  lowerLip.position.y = -0.01;
  mouthGroup.add(lowerLip);

  const innerMouth = new THREE.Mesh(
    new THREE.SphereGeometry(0.13, 16, 8), mouthMat
  );
  innerMouth.scale.set(1.1, 0.28, 0.65);
  innerMouth.position.set(0, -0.01, 0.02);
  innerMouth.visible = false;
  mouthGroup.add(innerMouth);

  const upperTeeth = new THREE.Mesh(
    new THREE.BoxGeometry(0.26, 0.055, 0.055), teethMat
  );
  upperTeeth.position.set(0, 0.035, 0.055);
  upperTeeth.visible = false;
  mouthGroup.add(upperTeeth);

  const lowerTeeth = new THREE.Mesh(
    new THREE.BoxGeometry(0.22, 0.045, 0.045), teethMat
  );
  lowerTeeth.position.set(0, -0.055, 0.055);
  lowerTeeth.visible = false;
  mouthGroup.add(lowerTeeth);

  return {{ head, mouthGroup, lowerLip, upperLip, innerMouth, upperTeeth, lowerTeeth, eyelids }};
}}

const {{ head, mouthGroup, lowerLip, upperLip, innerMouth, upperTeeth, lowerTeeth, eyelids }} = buildAvatar(isFemale);
// ── Animation state ──────────────────────────────────────────────────────────
let mouthOpen   = 0;
let mouthTarget = 0;
let blinkT      = 0;
let nextBlink   = 3 + Math.random() * 4;
let breathe     = 0;
let headTilt    = 0;
let headTiltTarget = 0;
let isRecording = false;
let isSpeaking  = false;
let clock = new THREE.Clock();

function animateAvatar() {{
  requestAnimationFrame(animateAvatar);
  const dt = clock.getDelta();

  breathe += dt;
  head.position.y = Math.sin(breathe * 0.8) * 0.015;
  const breathScale = 1 + Math.sin(breathe * 0.8) * 0.004;
  head.scale.set(breathScale, breathScale, breathScale);

  // Blink
  blinkT += dt;
  if (blinkT > nextBlink) {{
    blinkT = 0;
    nextBlink = 3 + Math.random() * 4;
    let bt = 0;
    const blinkAnim = setInterval(() => {{
      bt += 0.05;
      const v = bt < 0.5 ? bt * 2 : (1 - bt) * 2;
      eyelids.forEach(lid => {{ lid.scale.y = 0.85 + v * 1.5; }});
      if (bt >= 1) clearInterval(blinkAnim);
    }}, 16);
  }}

  // Head tilt
  headTiltTarget = isRecording ? -0.04 : (isSpeaking ? mouthOpen * 0.06 : 0);
  headTilt += (headTiltTarget - headTilt) * 0.05;
  head.rotation.z = headTilt;

  // Mouth open/close
  mouthOpen += (mouthTarget - mouthOpen) * 0.12;

  const open = mouthOpen;
  lowerLip.position.y    = -open * 0.22;
  lowerLip.rotation.x    = Math.PI + 0.3 + open * 0.4;
  upperLip.rotation.x    = -0.3 - open * 0.15;
  innerMouth.visible     = open > 0.08;
  upperTeeth.visible     = open > 0.08;
  lowerTeeth.visible     = open > 0.08;
  if (open > 0.08) {{
    innerMouth.scale.y   = 0.3 + open * 0.5;
    lowerTeeth.position.y = -0.06 - open * 0.15;
  }}

  renderer.render(scene, camera);
}}

animateAvatar();

// ── Audio lip sync ────────────────────────────────────────────────────────────
let ttsAnalyser = null;

function getTTSAmplitude() {{
  if (!ttsAnalyser) return 0;
  const d = new Uint8Array(ttsAnalyser.fftSize);
  ttsAnalyser.getByteTimeDomainData(d);
  let sum = 0;
  for (let i = 0; i < d.length; i++) sum += Math.abs(d[i] - 128);
  return Math.min(sum / d.length / 8, 1.0);
}}

function updateMouthFromTTS() {{
  if (!isSpeaking) {{ mouthTarget = 0; return; }}
  mouthTarget = mouthTarget * 0.5 + getTTSAmplitude() * 0.5;
  requestAnimationFrame(updateMouthFromTTS);
}}

// ── VAD + Recording ───────────────────────────────────────────────────────────
const SILENCE_MS = 1500, MIN_DB = -42;
let mediaRec=null,chunks=[],audioCtx=null,analyser=null,micStream=null;
let vadActive=false,speechHit=false;
let silTimer=null,silStart=null,curAudio=null;

const statusEl = document.getElementById('status');
const tLabel=document.getElementById('tLabel'),tUser=document.getElementById('tUser');
const tSep=document.getElementById('tSep'),tAi=document.getElementById('tAi');
const tWait=document.getElementById('tWait');
const sil=document.getElementById('sil'),silFill=document.getElementById('silFill');
const micBtn=document.getElementById('micBtn'),errBox=document.getElementById('errBox');

function setStatus(t,c=''){{statusEl.textContent=t;statusEl.className='status '+c;}}
function showErr(m){{errBox.textContent=m;setTimeout(()=>errBox.textContent='',5000);}}
function showSil(p){{sil.classList.add('show');silFill.style.width=p+'%';}}
function hideSil(){{sil.classList.remove('show');silFill.style.width='0%';}}
function showTranscript(u,a){{
  tWait.style.display='none';
  if(u){{tLabel.textContent='Você disse:';tUser.textContent=u;tUser.style.display='block';}}
  if(a){{tSep.style.display='block';tAi.textContent=a;tAi.style.display='block';}}
}}

function getMicRMS(){{
  if(!analyser) return -100;
  const d=new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(d);
  let s=0; for(let i=0;i<d.length;i++) s+=d[i]*d[i];
  const r=Math.sqrt(s/d.length); return r>0?20*Math.log10(r):-100;
}}

function runVAD(){{
  if(!vadActive) return;
  const loud=getMicRMS()>MIN_DB;
  if(loud){{
    speechHit=true;clearTimeout(silTimer);silStart=null;hideSil();
    if(isSpeaking&&curAudio){{curAudio.pause();curAudio=null;isSpeaking=false;mouthTarget=0;}}
  }}else if(speechHit){{
    if(!silStart){{silStart=Date.now();animSil();}}
    clearTimeout(silTimer);
    silTimer=setTimeout(()=>{{
      if(vadActive&&speechHit){{
        vadActive=false;speechHit=false;mediaRec.stop();
        setStatus('Processando...','s-processing');
        tLabel.textContent='Transcrevendo...';
      }}
    }},SILENCE_MS);
  }}
  requestAnimationFrame(runVAD);
}}

function animSil(){{
  if(!silStart) return;
  const p=Math.min((Date.now()-silStart)/SILENCE_MS*100,100);
  showSil(p);if(p<100&&silStart)requestAnimationFrame(animSil);
}}

async function startRec(){{
  if(isRecording) return;
  try{{micStream=await navigator.mediaDevices.getUserMedia({{audio:{{echoCancellation:true,noiseSuppression:true,sampleRate:16000}}}});}}
  catch(e){{showErr('Permissão de microfone negada.');return;}}
  audioCtx=new(window.AudioContext||window.webkitAudioContext)();
  analyser=audioCtx.createAnalyser();analyser.fftSize=512;
  audioCtx.createMediaStreamSource(micStream).connect(analyser);
  const mime=['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/ogg'].find(m=>MediaRecorder.isTypeSupported(m))||'';
  try{{mediaRec=new MediaRecorder(micStream,mime?{{mimeType:mime}}:{{}});}}
  catch(e){{mediaRec=new MediaRecorder(micStream);}}
  chunks=[];
  mediaRec.ondataavailable=e=>{{if(e.data&&e.data.size>0)chunks.push(e.data);}};
  mediaRec.onstop=()=>uploadAudio(new Blob(chunks,{{type:mediaRec.mimeType||'audio/webm'}}));
  mediaRec.onerror=e=>{{showErr('Erro: '+e.error);resetToIdle();}};
  mediaRec.start(100);
  isRecording=true;vadActive=true;speechHit=false;
  micBtn.classList.add('active');micBtn.textContent='⏹';
  setStatus('Ouvindo...','s-listening');
  tWait.style.display='block';tWait.textContent='—';
  tUser.style.display='none';tSep.style.display='none';tAi.style.display='none';
  tLabel.textContent='Aguardando sua fala...';
  mouthTarget=0;runVAD();
}}

function stopRec(){{
  vadActive=false;isRecording=false;speechHit=false;
  clearTimeout(silTimer);silStart=null;hideSil();
  if(mediaRec&&mediaRec.state!=='inactive')try{{mediaRec.stop();}}catch(e){{}}
  if(micStream)micStream.getTracks().forEach(t=>t.stop());micStream=null;
  if(audioCtx)try{{audioCtx.close();}}catch(e){{}}audioCtx=null;analyser=null;
  micBtn.classList.remove('active');micBtn.textContent='🎤';mouthTarget=0;
}}

function uploadAudio(blob){{
  if(blob.size<1500){{resetToIdle();return;}}
  const par=window.parent.document;
  function tryInject(attempt){{
    let input=par.querySelector('[data-testid="stFileUploader"] input[type="file"]')
           ||par.querySelector('[data-testid="stFileUploaderDropzone"] input[type="file"]')
           ||Array.from(par.querySelectorAll('input[type="file"]')).find(i=>i.accept&&i.accept.includes('webm'));
    if(!input){{
      if(attempt<8){{setTimeout(()=>tryInject(attempt+1),300);return;}}
      showErr('Input não encontrado.');resetToIdle();return;
    }}
    const ext=blob.type.includes('ogg')?'ogg':(blob.type.includes('mp4')?'mp4':'webm');
    const file=new File([blob],`vm_${{Date.now()}}.${{ext}}`,{{type:blob.type||'audio/webm'}});
    const dt=new DataTransfer();dt.items.add(file);
    input.files=dt.files;
    input.dispatchEvent(new Event('change',{{bubbles:true}}));
    input.dispatchEvent(new Event('input',{{bubbles:true}}));
  }}
  tryInject(0);
}}

function resetToIdle(){{
  stopRec();mouthTarget=0;
  setStatus('Clique no microfone para continuar','');
}}

function playTTS(b64,txt){{
  isSpeaking=true;setStatus('Falando...','s-speaking');
  if(b64&&b64.length>20){{
    const ttsCtx=new(window.AudioContext||window.webkitAudioContext)();
    ttsAnalyser=ttsCtx.createAnalyser();ttsAnalyser.fftSize=256;
    curAudio=new Audio('data:audio/mpeg;base64,'+b64);
    curAudio.crossOrigin='anonymous';
    curAudio.oncanplaythrough=()=>{{
      try{{const src=ttsCtx.createMediaElementSource(curAudio);
            src.connect(ttsAnalyser);ttsAnalyser.connect(ttsCtx.destination);}}catch(e){{}}
      curAudio.play().catch(()=>fallbackTTS(txt));
      updateMouthFromTTS();
    }};
    curAudio.onended=()=>{{
      isSpeaking=false;curAudio=null;mouthTarget=0;ttsAnalyser=null;
      try{{ttsCtx.close();}}catch(e){{}}
      resetToIdle();startRec();
    }};
    curAudio.onerror=()=>{{isSpeaking=false;mouthTarget=0;fallbackTTS(txt);}};
  }}else{{fallbackTTS(txt);}}
}}

function fallbackTTS(text){{
  isSpeaking=true;setStatus('Falando...','s-speaking');
  let t0=Date.now();
  function synthMouth(){{
    if(!isSpeaking){{mouthTarget=0;return;}}
    mouthTarget=0.25+0.5*Math.abs(Math.sin((Date.now()-t0)/200));
    requestAnimationFrame(synthMouth);
  }}
  synthMouth();
  const u=new SpeechSynthesisUtterance(text.substring(0,500));
  u.lang=SPEECH_LANG;u.rate=0.95;u.pitch=1.05;
  speechSynthesis.getVoices();
  setTimeout(()=>{{
    const vv=speechSynthesis.getVoices();
    const pick=vv.find(v=>v.lang===SPEECH_LANG)||vv.find(v=>v.lang.startsWith(SPEECH_LANG.split('-')[0]));
    if(pick)u.voice=pick;
    u.onend=u.onerror=()=>{{isSpeaking=false;mouthTarget=0;resetToIdle();startRec();}};
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  }},100);
}}

micBtn.onclick=()=>{{
  if(curAudio){{curAudio.pause();curAudio=null;}}
  try{{speechSynthesis.cancel();}}catch(e){{}}
  isSpeaking=false;mouthTarget=0;ttsAnalyser=null;
  if(isRecording) resetToIdle();
  else startRec();
}};

window.addEventListener('load',()=>{{
  if(PY_ERROR&&PY_ERROR.length>1){{showErr(PY_ERROR);setStatus('Erro','');return;}}
  if(PY_REPLY&&PY_REPLY.length>1){{showTranscript(PY_USER_SAID,PY_REPLY);playTTS(PY_TTS_B64,PY_REPLY);return;}}
  if(PY_USER_SAID&&PY_USER_SAID.length>1) showTranscript(PY_USER_SAID,'');
}});

function toggleDebug(){{}}
</script></body></html>""", height=720, scrolling=False)


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
    conv_id  = get_or_create_conv(username)
    messages = load_conversation(username, conv_id)
    speaking = st.session_state.speaking

    # Redireciona para o modo voz se ativo
    if st.session_state.voice_mode:
        show_voice_mode()
        return

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

        if st.button("➕  Nova conversa", use_container_width=True, key="btn_new"):
            st.session_state.conv_id = new_conversation(username); st.rerun()
        if st.button("🎙️  Modo Conversa", use_container_width=True, key="btn_voice"):
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
                if st.button("🗑", key=f"del_{c['id']}", help="Excluir conversa"):
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
                if st.button("📊 Painel", use_container_width=True, key="btn_dash"):
                    st.session_state.page = "dashboard"; st.rerun()
            with col_b:
                if st.button("⚙️ Perfil", use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            # Logout da professora: apaga sessão persistente
            if st.button("🚪 Sair", use_container_width=True, key="btn_sair"):
                _logout(); st.rerun()
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("⚙️ Perfil", use_container_width=True, key="btn_profile"):
                    st.session_state.page = "profile"; st.rerun()
            with col_b:
                # Logout do aluno: apaga sessão persistente
                if st.button("🚪 Sair", use_container_width=True, key="btn_sair"):
                    _logout(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── CSS do chat ───────────────────────────────────────────────────────────
    st.markdown("""<style>
[data-testid="stChatInput"] textarea {
    max-height: 120px !important; min-height: 44px !important; font-size: .88rem !important;
}
[data-testid="stChatInputContainer"] { padding: 6px 10px !important; }
.main .block-container { padding-bottom: 80px !important; }
section[data-testid="stMain"] { transition: margin-left .3s ease !important; }
@media (max-width: 768px) {
    .main .block-container { padding: 0 8px 80px !important; }
    [data-testid="stChatInput"] textarea { font-size: .82rem !important; }
    div.bubble { max-width: 90% !important; font-size: .82rem !important; }
}
@media (max-width: 480px) {
    div.bubble { max-width: 96% !important; }
    [data-testid="stChatInput"] textarea { font-size: .78rem !important; }
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
    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for i, msg in enumerate(messages):
        content  = msg["content"].replace("\n", "<br>")
        t        = msg.get("time", "")

        if msg["role"] == "assistant":
            av      = avatar_html(36, speaking and i == len(messages)-1)
            tts_b64 = msg.get("tts_b64", "")
            is_file = msg.get("is_file", False)
            st.markdown(
                f'<div class="bubble-row bot"><div class="bav-s">{av}</div><div>'
                f'<div class="bubble bot">{content}</div></div></div>',
                unsafe_allow_html=True)
            if tts_b64:
                # Player de áudio pré-gerado pelo ElevenLabs
                components.html(render_audio_player(tts_b64, t, f"msg_{i}_{conv_id}"),
                                height=44, scrolling=False)
            elif not is_file:
                # Fallback: Web Speech API via JS
                clean_text = (msg["content"]
                    .replace("\\", "").replace("`", "")
                    .replace("'", "\\'").replace('"', '\\"')
                    .replace("\n", " ").replace("\r", "")
                    .replace("*", "").replace("#", ""))[:600]
                components.html(f"""<!DOCTYPE html><html><head>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{background:transparent;overflow:hidden;}}
.row{{display:flex;align-items:center;gap:8px;padding:2px 0 0 46px;}}
.ts{{font-size:.6rem;color:#8b949e;font-family:'JetBrains Mono',monospace;}}
.btn{{background:none;border:1px solid #30363d;border-radius:16px;
      color:#8b949e;font-size:.68rem;padding:2px 10px;cursor:pointer;
      transition:all .15s;white-space:nowrap;}}
.btn:hover,.btn.on{{border-color:#f0a500;color:#f0a500;}}
</style></head><body>
<div class="row">
  <span class="ts">{t}</span>
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
                st.markdown(f'<div class="btime" style="margin-left:46px;">{t}</div>',
                            unsafe_allow_html=True)
        else:
            is_audio = msg.get("audio", False)
            extra    = " audio-msg" if is_audio else ""
            uav_html = user_avatar_html(username, size=36, fallback_emoji="🎓")
            st.markdown(
                f'<div class="bubble-row user" style="justify-content:flex-end;padding-left:50%;">'
                f'<div class="bav-u" style="margin-right:8px;flex-shrink:0;">{uav_html}</div>'
                f'<div style="display:flex;flex-direction:column;align-items:flex-end;">'
                f'<div class="bubble user{extra}">{content}</div>'
                f'<div class="btime" style="text-align:right;">{t}</div></div></div>',
                unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Banner de arquivo em staging (aguardando envio) ───────────────────────
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
        if st.button("✕ Remover anexo", key="remove_staged"):
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
    prompt = st.chat_input("Type a message…")
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
            txt = transcribe_bytes(audio_val.read(), ".wav", "en")
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
    components.html("""<!DOCTYPE html><html><body>
<script>
function pavMoveToChatBar() {
  const parent = window.parent ? window.parent.document : document;
  const chatInputContainer = parent.querySelector('[data-testid="stChatInput"]');
  if (!chatInputContainer) return;
  if (chatInputContainer.querySelector('.pav-extras')) return;

  const extras = parent.createElement('div');
  extras.className = 'pav-extras';

  const ab = parent.createElement('button');
  ab.className = 'pav-icon-btn';
  ab.title = 'Anexar arquivo';
  ab.innerHTML = '<i class="fa-solid fa-paperclip"></i>';
  ab.onclick = () => {
    const fw = parent.querySelector('[data-testid="stFileUploader"]');
    if (fw) {
      const fileInput = fw.querySelector('input[type="file"]');
      if (fileInput) fileInput.click();
    }
  };

  extras.appendChild(ab);
  const chatInner = chatInputContainer.querySelector('div');
  if (chatInner) chatInner.style.position = 'relative';
  chatInputContainer.appendChild(extras);

  const fw = parent.querySelector('[data-testid="stFileUploader"]');
  if (fw) {
    fw.style.cssText = 'position:fixed!important;bottom:-999px!important;left:-9999px!important;opacity:0!important;width:1px!important;height:1px!important;pointer-events:none!important;';
    const fi = fw.querySelector('input[type="file"]');
    if (fi) fi.style.pointerEvents = 'auto';
  }
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

setInterval(pavMoveToChatBar, 1000);
setInterval(pavFixAudioInput, 500);
</script>
</body></html>""", height=1)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD DA PROFESSORA
# ══════════════════════════════════════════════════════════════════════════════

def show_dashboard() -> None:
    """Painel administrativo com estatísticas de todos os alunos."""
    with st.sidebar:
        user = st.session_state.user
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div>
            <div style="font-weight:600;font-size:.9rem;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#8b949e;"><span class="status-dot"></span>Professora</div>
            </div></div>
            <hr style="border-color:#30363d;margin:6px 0 12px">""", unsafe_allow_html=True)
        if st.button("📊 Dashboard",      use_container_width=True, type="primary"): pass
        if st.button("💬 Usar como Aluno", use_container_width=True, key="dash_chat"):
            st.session_state.page = "chat"; st.rerun()
        if st.button("⚙️ Meu Perfil",     use_container_width=True, key="dash_profile"):
            st.session_state.page = "profile"; st.rerun()
        # Logout da professora via dashboard — apaga sessão persistente
        if st.button("🚪 Sair",           use_container_width=True):
            _logout(); st.rerun()

    st.markdown("## 📊 Painel do Professor")
    st.markdown("---")
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button("💬 Entrar no Chat", use_container_width=True):
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
        badge = {"False Beginner": "badge-blue", "Pre-Intermediate": "badge-green",
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
elif st.session_state.page == "profile":
    show_profile()
elif st.session_state.page == "dashboard":
    show_dashboard()
else:
    show_chat()