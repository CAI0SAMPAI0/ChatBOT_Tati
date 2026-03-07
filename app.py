import os
import base64
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import streamlit.components.v1 as components
import anthropic
from datetime import datetime
from database import (
    init_db, authenticate, register_student, load_students,
    new_conversation, list_conversations, load_conversation,
    append_message, get_all_students_stats
)
from transcriber import transcribe_bytes
from tts import text_to_speech, tts_available
from file_reader import extract_file

init_db()
API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
PHOTO_PATH   = os.getenv("PROFESSOR_PHOTO", "assets/professor.jpg")
PROF_NAME    = os.getenv("PROFESSOR_NAME", "Professor Avatar")

# ── Foto ─────────────────────────────────────────────────────────────────────
def get_photo_b64():
    path = Path(PHOTO_PATH)
    if path.exists():
        ext = path.suffix.lower().replace(".","")
        mime = "jpeg" if ext in ("jpg","jpeg") else ext
        return f"data:image/{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    return None

PHOTO_B64 = get_photo_b64()

def avatar_html(size=52, speaking=False):
    cls = "speaking" if speaking else ""
    if PHOTO_B64:
        return f'<div class="avatar-wrap {cls}" style="width:{size}px;height:{size}px"><img src="{PHOTO_B64}" class="avatar-img"/><div class="avatar-ring"></div></div>'
    return f'<div class="avatar-circle {cls}" style="width:{size}px;height:{size}px;font-size:{int(size*.48)}px">🧑‍🏫</div>'

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title=f"{PROF_NAME} · English", page_icon="🎓", layout="wide")

def load_css(path: str):
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

load_css("styles/style.css")

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, and encouraging.
Students: teenagers (False Beginner/Pre-Intermediate) and adults focused on Business/News.
Teaching Style:
- Neuro-learning: guide students to discover their own errors. Never just give the answer.
  Example: If they say "he go" → "Quick check — what ending do we add for he/she/it? 😊"
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT responses. **Bold** grammar points. End with ONE engaging question.
Rules: Simple English. Teens→Fortnite/Netflix/TikTok. Adults→LinkedIn/news.
Celebrate progress 🎉. Portuguese → acknowledge briefly, switch to English."""

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {"logged_in":False,"user":None,"page":"chat","speaking":False,"conv_id":None}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ── Auto-login via localStorage ───────────────────────────────────────────────
# JS lê localStorage e injeta query param ?_u=username apenas se não estiver logado
if not st.session_state.logged_in:
    components.html("""
    <script>
    const u = localStorage.getItem("pav_user");
    if (u) {
        const url = new URL(window.parent.location.href);
        if (url.searchParams.get("_u") !== u) {
            url.searchParams.set("_u", u);
            window.parent.location.replace(url.toString());
        }
    }
    </script>""", height=0)

    params = st.query_params
    if "_u" in params:
        uname = params["_u"]
        students = load_students()
        if uname in students:
            udata = students[uname]
            st.session_state.logged_in = True
            st.session_state.user = {"username": uname, **udata}
            st.session_state.page = "dashboard" if udata["role"] == "professor" else "chat"
            st.session_state.conv_id = None  # nova conversa ao abrir
            st.query_params.clear()
            st.rerun()

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_or_create_conv(username):
    """Garante que há uma conversa ativa na sessão."""
    if not st.session_state.conv_id:
        st.session_state.conv_id = new_conversation(username)
    return st.session_state.conv_id

def send_to_claude(username, user, conv_id, text, image_b64=None, image_media_type=None):
    """Envia mensagem para Claude (texto ou imagem), salva resposta e gera TTS."""
    import base64 as b64
    client  = anthropic.Anthropic(api_key=API_KEY)
    context = f"\n\nStudent: Name={user['name']}, Level={user['level']}, Focus={user['focus']}."
    msgs    = load_conversation(username, conv_id)

    # Monta histórico
    api_msgs = []
    for m in msgs:
        api_msgs.append({
            "role": "user" if m["role"] == "user" else "assistant",
            "content": m["content"]
        })

    # Se tiver imagem, substitui a última mensagem do usuário por conteúdo multimodal
    if image_b64 and image_media_type and api_msgs and api_msgs[-1]["role"] == "user":
        api_msgs[-1]["content"] = [
            {"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": image_b64}},
            {"type": "text",  "text": text}
        ]

    resp = client.messages.create(
        model="claude-haiku-4-5", max_tokens=400,
        system=SYSTEM_PROMPT + context,
        messages=api_msgs
    )
    reply_text = resp.content[0].text
    append_message(username, conv_id, "assistant", reply_text)

    # ── TTS ───────────────────────────────────────────────────────────────────
    st.session_state.pop("_tts_audio", None)
    if tts_available():
        audio_bytes = text_to_speech(reply_text)
        if audio_bytes:
            st.session_state["_tts_audio"] = b64.b64encode(audio_bytes).decode()

    # ── TTS automático (comentado — descomentar para ativar) ──────────────────
    # if tts_available():
    #     audio_bytes = text_to_speech(reply_text)
    #     if audio_bytes:
    #         st.audio(audio_bytes, format="audio/mp3", autoplay=True)

    return reply_text

# ── JS helpers ────────────────────────────────────────────────────────────────
def js_save_user(username):
    components.html(f"<script>localStorage.setItem('pav_user','{username}');</script>", height=0)

def js_clear_user():
    components.html("<script>localStorage.removeItem('pav_user');</script>", height=0)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
def show_login():
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="login-avatar">{avatar_html(100)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="login-title">{PROF_NAME}</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Your personal English practice companion</div>', unsafe_allow_html=True)

    t1,t2 = st.tabs(["🔑 Login","✨ Criar Conta"])
    with t1:
        u = st.text_input("Username", key="li_u", placeholder="seu.usuario")
        p = st.text_input("Password", type="password", key="li_p", placeholder="••••••••")
        if st.button("Entrar →", key="btn_login"):
            user = authenticate(u,p)
            if user:
                st.session_state.update(logged_in=True, user={"username":u,**user},
                                        page="dashboard" if user["role"]=="professor" else "chat",
                                        conv_id=None)
                js_save_user(u)
                st.rerun()
            else: st.error("❌ Username ou senha incorretos.")
    with t2:
        rn=st.text_input("Nome completo",key="r_n",placeholder="João Silva")
        ru=st.text_input("Username",key="r_u",placeholder="joao.silva")
        rp=st.text_input("Senha",type="password",key="r_p",placeholder="mínimo 6 caracteres")
        rl=st.selectbox("Nível",["False Beginner","Pre-Intermediate","Intermediate","Business English"],key="r_l")
        rf=st.selectbox("Foco",["General Conversation","Sports & Games","Business & News","Series & Pop Culture"],key="r_f")
        if st.button("Criar Conta →",key="btn_reg"):
            if len(rp)<6: st.error("Senha muito curta.")
            elif not rn or not ru: st.error("Preencha todos os campos.")
            else:
                ok,msg=register_student(ru,rn,rp,rl,rf)
                st.success(f"✅ {msg} Faça login!") if ok else st.error(f"❌ {msg}")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════════════════
def show_chat():
    user     = st.session_state.user
    username = user["username"]
    conv_id  = get_or_create_conv(username)
    messages = load_conversation(username, conv_id)
    speaking = st.session_state.speaking

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        # Avatar + nome
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div>
            <div style="font-weight:600;font-size:.9rem;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#8b949e;"><span class="status-dot"></span>Online</div>
            </div></div><hr style="border-color:#30363d;margin:6px 0 12px">""", unsafe_allow_html=True)

        # Stats rápidas
        user_msgs = len([m for m in messages if m["role"]=="user"])
        st.markdown(f"""<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
            padding:10px 12px;margin-bottom:10px;font-size:.82rem;">
            <div style="color:#8b949e;font-size:.68rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
                👤 {user['name'].split()[0]} · {user['level']}</div>
            <div style="display:flex;justify-content:space-between;padding:2px 0;">
                <span>Msgs hoje</span>
                <span style="color:#f0a500;font-family:'JetBrains Mono',monospace">{user_msgs}</span>
            </div></div>""", unsafe_allow_html=True)

        # ── Histórico de conversas ────────────────────────────────────────────
        st.markdown("""<div style="font-size:.72rem;color:#8b949e;text-transform:uppercase;
            letter-spacing:1px;margin-bottom:8px;">🕘 Conversas</div>""", unsafe_allow_html=True)

        if st.button("➕ Nova conversa", use_container_width=True, key="btn_new"):
            st.session_state.conv_id = new_conversation(username)
            st.rerun()

        convs = list_conversations(username)
        if not convs:
            st.markdown('<div style="font-size:.78rem;color:#8b949e;padding:6px 2px;">Nenhuma conversa ainda.<br>Digite algo para começar!</div>', unsafe_allow_html=True)
        for c in convs:
            is_active = c["id"] == conv_id
            border = "1px solid #f0a500" if is_active else "1px solid #30363d"
            bg     = "#1a2332" if is_active else "#0d1117"
            prefix = "▶ " if is_active else ""
            if st.button(
                f"{prefix}{c['title']}",
                key=f"conv_{c['id']}",
                use_container_width=True,
                help=f"📅 {c['date']} · 💬 {c['count']} msg{'s' if c['count']!=1 else ''}"
            ):
                st.session_state.conv_id = c["id"]
                st.rerun()
            st.markdown(f'<div style="font-size:.65rem;color:#8b949e;margin:-10px 0 4px 4px;">📅 {c["date"]} · 💬 {c["count"]} msg</div>', unsafe_allow_html=True)

        st.markdown("<hr style='border-color:#30363d;margin:10px 0'>", unsafe_allow_html=True)

        if user["role"]=="professor":
            if st.button("📊 Painel", use_container_width=True):
                st.session_state.page="dashboard"; st.rerun()
        if st.button("🚪 Sair", use_container_width=True):
            js_clear_user()
            st.session_state.update(logged_in=False, user=None, conv_id=None)
            st.rerun()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"""<div class="prof-header">
        {avatar_html(56, speaking)}
        <div class="prof-info">
            <h1>{PROF_NAME}</h1>
            <p><span class="status-dot"></span>Online · {user['level']} · {user['focus']}</p>
        </div></div>""", unsafe_allow_html=True)

    # ── Boas-vindas se conversa vazia ─────────────────────────────────────────
    if not messages:
        greeting = f"Hey, {user['name'].split()[0]}! 👋 Great to see you!\n\nReady to practice? **What have you been up to lately?** Tell me in English — no worries about mistakes! 😊"
        append_message(username, conv_id, "assistant", greeting)
        messages = load_conversation(username, conv_id)

    # ── Mensagens ─────────────────────────────────────────────────────────────
    tts_b64 = st.session_state.get("_tts_audio", "")
    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    last_bot = max((i for i,m in enumerate(messages) if m["role"]=="assistant"), default=-1)
    for i, msg in enumerate(messages):
        content = msg["content"].replace("\n","<br>")
        t = msg.get("time","")
        if msg["role"] == "assistant":
            av = avatar_html(36, speaking and i == last_bot)
            if i == last_bot and tts_b64:
                # Última bolha da professora: renderiza via components.html
                # para ter botão ▶ funcional com áudio no mesmo iframe
                st.markdown(
                    f'<div class="bubble-row bot"><div class="bav-s">{av}</div><div>'
                    f'<div class="bubble bot">{content}</div></div></div>',
                    unsafe_allow_html=True
                )
                components.html(f"""<!DOCTYPE html><html><head>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:transparent;font-family:'Sora',sans-serif;}}
#wrap{{display:flex;align-items:center;gap:8px;padding:2px 0;}}
#play{{
  background:none;
  border:1px solid #30363d;
  border-radius:20px;
  color:#f0a500;
  font-size:.78rem;
  padding:2px 12px;
  cursor:pointer;
  transition:background .15s,border-color .15s;
  white-space:nowrap;
}}
#play:hover{{background:rgba(240,165,0,.12);border-color:#f0a500;}}
#time{{font-size:.65rem;color:#8b949e;font-family:'JetBrains Mono',monospace;}}
</style></head><body>
<div id="wrap">
  <span id="time">{t}</span>
  <button id="play">▶ Ouvir</button>
</div>
<script>
const b64 = "{tts_b64}";
const btn = document.getElementById('play');
const audio = new Audio('data:audio/mpeg;base64,' + b64);
btn.onclick = function() {{
  if (!audio.paused) {{
    audio.pause(); audio.currentTime = 0;
    btn.textContent = '▶ Ouvir';
  }} else {{
    audio.play();
    btn.textContent = '⏸ Pausar';
    audio.onended = () => btn.textContent = '▶ Ouvir';
  }}
}};
</script>
</body></html>""", height=36, scrolling=False)
            else:
                st.markdown(
                    f'<div class="bubble-row bot"><div class="bav-s">{av}</div><div>'
                    f'<div class="bubble bot">{content}</div>'
                    f'<div class="btime">{t}</div></div></div>',
                    unsafe_allow_html=True
                )
        else:
            extra = " audio-msg" if msg.get("audio") else ""
            icon  = "🎙️ " if msg.get("audio") else ""
            st.markdown(
                f'<div class="bubble-row user"><div class="bav-u">🎓</div><div>'
                f'<div class="bubble user{extra}">{icon}{content}</div>'
                f'<div class="btime">{t}</div></div></div>',
                unsafe_allow_html=True
            )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Input principal: chat_input fixo no rodapé ────────────────────────────
    prompt = st.chat_input("Type your message in English... 💬")
    if prompt:
        if not API_KEY: st.error("⚠️ Configure ANTHROPIC_API_KEY no .env"); st.stop()
        append_message(username, conv_id, "user", prompt)
        st.session_state.speaking = True
        try: send_to_claude(username, user, conv_id, prompt)
        except Exception as e: st.error(f"❌ {e}")
        st.session_state.speaking = False
        st.rerun()

    # ── Microfone: st.audio_input dentro do stBottom via CSS ─────────────────
    # Fica oculto visualmente mas funcional; o botão 🎤 no rodapé o aciona via JS
    audio_val = st.audio_input("🎤", key="voice_input", label_visibility="collapsed")
    if audio_val and audio_val != st.session_state.get("_last_audio"):
        st.session_state["_last_audio"] = audio_val
        with st.spinner("🔄 Transcrevendo..."):
            txt = transcribe_bytes(audio_val.read(), ".wav", "en")
        if txt and not txt.startswith("❌") and not txt.startswith("⚠️"):
            if not API_KEY: st.error("⚠️ Configure ANTHROPIC_API_KEY"); st.stop()
            append_message(username, conv_id, "user", txt, audio=True)
            st.session_state.speaking = True
            try: send_to_claude(username, user, conv_id, txt)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
            st.rerun()
        elif txt:
            st.error(txt)

    # ── Upload de arquivo ─────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "📎", key="file_upload", label_visibility="collapsed",
        type=["mp3","wav","ogg","m4a","webm","flac","pdf","doc","docx","txt","png","jpg","jpeg","webp"]
    )
    if uploaded and uploaded.name != st.session_state.get("_last_file"):
        st.session_state["_last_file"] = uploaded.name
        fname = uploaded.name
        raw   = uploaded.read()
        if not API_KEY: st.error("⚠️ Configure ANTHROPIC_API_KEY"); st.stop()

        result = extract_file(raw, fname)
        kind   = result["kind"]
        label  = result["label"]

        if kind == "audio":
            with st.spinner("🔄 Transcrevendo áudio..."):
                text = transcribe_bytes(raw, suffix=Path(fname).suffix.lower(), language="en")
            if text.startswith("❌") or text.startswith("⚠️"):
                st.error(text)
            else:
                msg = f"🎙️ [Áudio: '{fname}']\n{text}"
                append_message(username, conv_id, "user", msg, audio=True)
                st.session_state.speaking = True
                try: send_to_claude(username, user, conv_id, msg)
                except Exception as e: st.error(f"❌ {e}")
                st.session_state.speaking = False
                st.rerun()

        elif kind == "text":
            extracted = result["text"]
            if extracted.startswith("❌"):
                st.error(extracted)
            elif not extracted:
                st.warning(f"⚠️ Não foi possível extrair texto de '{fname}'.")
            else:
                preview = extracted[:200].replace('\n',' ')
                msg = (f"📄 [{label}: '{fname}']\n\n{extracted}\n\n"
                       f"Please help me understand this content — explain vocabulary, grammar, "
                       f"and key ideas. Teach me from it.")
                append_message(username, conv_id, "user",
                               f"📄 [{label}: '{fname}'] — {preview}{'…' if len(extracted)>200 else ''}")
                st.session_state.speaking = True
                try: send_to_claude(username, user, conv_id, msg)
                except Exception as e: st.error(f"❌ {e}")
                st.session_state.speaking = False
                st.rerun()

        elif kind == "image":
            b64_img    = result["b64"]
            media_type = result["media_type"]
            msg_text   = (f"📸 [Imagem: '{fname}']\n"
                          f"Please look at this image and help me learn English from it. "
                          f"Describe what you see, point out useful vocabulary and any text visible.")
            append_message(username, conv_id, "user", f"📸 [Imagem: '{fname}']")
            st.session_state.speaking = True
            try: send_to_claude(username, user, conv_id, msg_text,
                                image_b64=b64_img, image_media_type=media_type)
            except Exception as e: st.error(f"❌ {e}")
            st.session_state.speaking = False
            st.rerun()

        else:
            st.warning(f"⚠️ Formato '{label}' não suportado ainda.")

    # ── JS: move audio_input e file_uploader para dentro do stBottom ─────────
    st.markdown("""
<script>
(function moveToChatBar() {
  const bottom = window.parent.document.querySelector('[data-testid="stBottom"]');
  if (!bottom) { setTimeout(moveToChatBar, 300); return; }

  // Já foi feito
  if (bottom.querySelector('.pav-extras')) return;

  // Encontra os widgets no body principal
  const audioWidget = window.parent.document.querySelector('[data-testid="stAudioInput"]');
  const fileWidget  = window.parent.document.querySelector('[data-testid="stFileUploader"]');

  if (!audioWidget || !fileWidget) { setTimeout(moveToChatBar, 300); return; }

  // Cria container de botões extras
  const extras = window.parent.document.createElement('div');
  extras.className = 'pav-extras';

  // Botão microfone — aciona o st.audio_input oculto
  const micBtn = window.parent.document.createElement('button');
  micBtn.className = 'pav-icon-btn';
  micBtn.title = 'Gravar voz';
  micBtn.innerHTML = '🎤';
  micBtn.onclick = () => {
    const btn = audioWidget.querySelector('button');
    if (btn) btn.click();
  };

  // Botão anexar — aciona o st.file_uploader oculto
  const attachBtn = window.parent.document.createElement('button');
  attachBtn.className = 'pav-icon-btn';
  attachBtn.title = 'Anexar arquivo';
  attachBtn.innerHTML = '＋';
  attachBtn.onclick = () => {
    const inp = fileWidget.querySelector('input[type="file"]');
    if (inp) inp.click();
  };

  extras.appendChild(attachBtn);
  extras.appendChild(micBtn);

  // Insere antes do campo de texto no stBottom
  bottom.insertBefore(extras, bottom.firstChild);

  // Oculta os widgets originais (mas mantém funcionais)
  audioWidget.style.cssText = 'position:fixed;bottom:-999px;left:-9999px;width:1px;height:1px;overflow:hidden;opacity:0';
  fileWidget.style.cssText  = 'position:fixed;bottom:-999px;left:-9999px;width:1px;height:1px;overflow:hidden;opacity:0';
  fileWidget.querySelector('input[type="file"]').style.pointerEvents = 'auto';
})();
</script>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def show_dashboard():
    with st.sidebar:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div style="font-weight:600">{PROF_NAME}</div></div>
            <hr style="border-color:#30363d;margin:6px 0 12px">""", unsafe_allow_html=True)
        if st.button("💬 Chat", use_container_width=True): st.session_state.page="chat"; st.rerun()
        if st.button("🚪 Sair", use_container_width=True):
            js_clear_user()
            st.session_state.update(logged_in=False,user=None); st.rerun()

    st.markdown("## 📊 Painel do Professor")
    st.markdown("---")
    stats = get_all_students_stats()
    today = datetime.now().strftime("%Y-%m-%d")

    c1,c2,c3,c4 = st.columns(4)
    for col,val,lbl in zip([c1,c2,c3,c4],
        [len(stats),sum(s["messages"] for s in stats),sum(s["corrections"] for s in stats),
         sum(1 for s in stats if s["last_active"][:10]==today)],
        ["Alunos","Mensagens","Correções","Ativos Hoje"]):
        col.markdown(f'<div class="stat-card"><div class="val">{val}</div><div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>")
    st.markdown("### 👥 Alunos")
    if not stats: st.info("Nenhum aluno ainda.")
    else:
        badge={"False Beginner":"badge-blue","Pre-Intermediate":"badge-green","Intermediate":"badge-gold","Business English":"badge-gold"}
        rows="".join(f"""<tr>
            <td><b>{s['name']}</b><br><span style="color:#8b949e;font-size:.75rem">@{s['username']}</span></td>
            <td><span class="badge {badge.get(s['level'],'badge-blue')}">{s['level']}</span></td>
            <td>{s['focus']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['messages']}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:#f0a500">{s['corrections']}</td>
            <td style="color:#8b949e">{s['last_active']}</td>
        </tr>""" for s in sorted(stats,key=lambda x:x["messages"],reverse=True))
        st.markdown(f'<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden"><table class="dash-table"><thead><tr><th>Aluno</th><th>Nível</th><th>Foco</th><th>Msgs</th><th>Correções</th><th>Último Acesso</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

    st.markdown("<br>")
    st.markdown("### 💬 Histórico do Aluno")
    students = load_students()
    opts = {u:d["name"] for u,d in students.items() if d["role"]=="student"}
    if opts:
        sel  = st.selectbox("Selecione",list(opts.keys()),format_func=lambda u:f"{opts[u]} (@{u})")
        convs = list_conversations(sel)
        if convs:
            csel = st.selectbox("Conversa",convs,format_func=lambda c:f"{c['date']} — {c['title']} ({c['count']} msgs)")
            hist = load_conversation(sel, csel["id"])
            with st.expander(f"📖 {len(hist)} mensagens"):
                for m in hist:
                    who = PROF_NAME if m["role"]=="assistant" else opts[sel]
                    icon = "🧑‍🏫" if m["role"]=="assistant" else "🎓"
                    audio_tag = " 🎙️" if m.get("audio") else ""
                    st.markdown(f"**{icon} {who}{audio_tag}** `{m.get('date','')} {m.get('time','')}`\n\n{m['content']}\n\n---")
        else: st.info("Aluno ainda não conversou.")

# ══════════════════════════════════════════════════════════════════════════════
# ROTEADOR
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:       show_login()
elif st.session_state.page=="dashboard": show_dashboard()
else:                                    show_chat()