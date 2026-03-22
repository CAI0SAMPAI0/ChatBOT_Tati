import os
import streamlit as st
from datetime import datetime, date

import anthropic

from core.database import (
    get_all_students_stats, delete_session,
    list_conversations, load_conversation,
    load_students, update_profile,
)
from utils.helpers import avatar_html, PROF_NAME
from utils.i18n import t
from ui.session import js_clear_session


# ── Labels i18n locais ────────────────────────────────────────────────────────
_L = {
    "pt-BR": {
        "title":        "Painel Pedagógico",
        "students":     "ALUNOS",
        "messages":     "MENSAGENS",
        "errors":       "ERROS",
        "corrections":  "CORREÇÕES",
        "class_insights":"Insights da Turma",
        "click_expand": "Clique no aluno para expandir",
        "student_mgmt": "Gerenciamento de Alunos",
        "class_summary":"Resumo da Turma",
        "active":       "Ativo",
        "inactive":     "Inativo",
        "new":          "Novo",
        "level":        "Nível",
        "focus":        "Foco",
        "last_active":  "Último acesso",
        "msgs":         "Msgs",
        "corr":         "Correções",
        "msgs_day":     "Msgs/dia",
        "change_level": "Alterar nível",
        "save":         "💾 Salvar",
        "saved_ok":     "✅ Salvo!",
        "level_saved":  "✅ Nível atualizado!",
        "remove":       "🗑 Remover aluno",
        "confirm_rm":   "Confirmar remoção de",
        "confirm":      "✅ Confirmar",
        "cancel":       "❌ Cancelar",
        "removed_ok":   "removido com sucesso.",
        "select_std":   "Selecionar aluno",
        "no_students":  "Nenhum aluno ainda.",
        "avg_msgs":     "Msgs/Aluno",
        "total_convs":  "Total de conversas",
        "active_today": "Ativos hoje",
        "corr_rate":    "Taxa de correção",
        "most_active":  "Mais ativo",
        "ai_insight":   "✨ AI Insight",
        "gen_insight":  "✨ Gerar Insight com IA",
        "analyzing":    "Analisando...",
        "no_data":      "Sem conversa suficiente para gerar insight.",
        "errors_lbl":   "Erros detectados",
        "hits_lbl":     "Acertos / Elogios",
        "no_errs":      "Nenhum erro registrado.",
        "no_hits":      "Nenhum acerto registrado.",
        "cust_prompt":  "🎯 Prompt personalizado para IA",
        "prompt_hint":  "Ex: Foque em erros de passado simples.",
        "prompt_saved": "✅ Prompt salvo!",
        "enter_chat":   "Entrar no Chat",
        "voice_mode":   "Modo Voz",
        "my_profile":   "Meu Perfil",
        "logout":       "Sair",
        "use_student":  "Usar como Aluno",
        "err_rate":     "Taxa de Erro",
        "total_err":    "Total Erros",
        "msgs_per_std": "Msgs/Aluno",
    },
    "en-US": {
        "title":        "Pedagogical Dashboard",
        "students":     "STUDENTS",
        "messages":     "MESSAGES",
        "errors":       "ERRORS",
        "corrections":  "CORRECTIONS",
        "class_insights":"Class Insights",
        "click_expand": "Click on a student to expand",
        "student_mgmt": "Student Management",
        "class_summary":"Class Summary",
        "active":       "Active",
        "inactive":     "Inactive",
        "new":          "New",
        "level":        "Level",
        "focus":        "Focus",
        "last_active":  "Last active",
        "msgs":         "Msgs",
        "corr":         "Corrections",
        "msgs_day":     "Msgs/day",
        "change_level": "Change level",
        "save":         "💾 Save",
        "saved_ok":     "✅ Saved!",
        "level_saved":  "✅ Level updated!",
        "remove":       "🗑 Remove student",
        "confirm_rm":   "Confirm removal of",
        "confirm":      "✅ Confirm",
        "cancel":       "❌ Cancel",
        "removed_ok":   "removed successfully.",
        "select_std":   "Select student",
        "no_students":  "No students yet.",
        "avg_msgs":     "Msgs/Student",
        "total_convs":  "Total conversations",
        "active_today": "Active today",
        "corr_rate":    "Correction rate",
        "most_active":  "Most active",
        "ai_insight":   "✨ AI Insight",
        "gen_insight":  "✨ Generate AI Insight",
        "analyzing":    "Analyzing...",
        "no_data":      "Not enough conversation history.",
        "errors_lbl":   "Detected errors",
        "hits_lbl":     "Hits / Praise",
        "no_errs":      "No errors recorded.",
        "no_hits":      "No hits recorded.",
        "cust_prompt":  "🎯 Custom AI prompt",
        "prompt_hint":  "E.g.: Focus on past simple errors.",
        "prompt_saved": "✅ Prompt saved!",
        "enter_chat":   "Enter Chat",
        "voice_mode":   "Voice Mode",
        "my_profile":   "My Profile",
        "logout":       "Logout",
        "use_student":  "Use as Student",
        "err_rate":     "Error Rate",
        "total_err":    "Total Errors",
        "msgs_per_std": "Msgs/Student",
    },
}


def _L_(key: str, lang: str) -> str:
    return _L.get(lang, _L["en-US"]).get(key, key)


def _get_api_key() -> str:
    for k in ["ANTHROPIC_API_KEY"] + [f"ANTHROPIC_API_KEY_{i}" for i in range(2, 6)]:
        v = os.getenv(k, "").strip()
        if v:
            return v
    try:
        for k in ["ANTHROPIC_API_KEY"] + [f"ANTHROPIC_API_KEY_{i}" for i in range(2, 6)]:
            v = st.secrets.get(k, "")
            if v:
                return v
    except Exception:
        pass
    return ""


def _days_inactive(last: str):
    if not last or last in ("---", ""):
        return None
    try:
        return (date.today() - datetime.fromisoformat(last[:10]).date()).days
    except Exception:
        return None


def _student_badge(msgs: int, last: str, lang: str) -> tuple[str, str]:
    """Retorna (label, cor_hex)."""
    if msgs == 0:
        return _L_("new", lang), "#c084fc"
    d = _days_inactive(last)
    if d is None or d <= 5:
        return _L_("active", lang), "#4ade80"
    if d <= 10:
        return f"⚠️ {d}d", "#f0a500"
    return _L_("inactive", lang) + f" · {d}d", "#ff7a5c"


_ERROR_KWS = [
    ("Quick check", "grammar"), ("we say", "grammar"),
    ("instead of", "grammar"), ("should be", "grammar"),
    ("Try saying", "pronunc."), ("not quite", "grammar"),
    ("missing", "grammar"), ("incorrect", "grammar"),
    ("wrong", "grammar"), ("mistake", "grammar"),
]
_HIT_KWS = [
    "great pronunciation", "excellent", "perfect", "well done",
    "spot on", "nailed it", "beautifully", "very clear",
    "ótima pronúncia", "perfeito", "muito bem", "excelente",
    "great job", "well said",
]


def _extract_errors_and_hits(msgs: list) -> tuple[list, list]:
    errors, hits = [], []
    for m in msgs:
        if m.get("role") != "assistant":
            continue
        c  = m.get("content", "")
        cl = c.lower()
        for kw, etype in _ERROR_KWS:
            if kw.lower() in cl:
                for sent in c.replace("\n", " ").split(". "):
                    if kw.lower() in sent.lower() and len(sent) > 10:
                        errors.append({"type": etype, "text": sent.strip()[:120]})
                        break
                break
        for kw in _HIT_KWS:
            if kw in cl:
                for sent in c.replace("\n", " ").split(". "):
                    if kw in sent.lower() and len(sent) > 8:
                        hits.append(sent.strip()[:100])
                        break
                break
    seen_e: set = set()
    seen_h: set = set()
    ue = [e for e in errors if not (e["text"] in seen_e or seen_e.add(e["text"]))]
    uh = [h for h in hits   if not (h in seen_h or seen_h.add(h))]
    return ue[:5], uh[:3]


def _get_ai_insight(student: dict, msgs: list, custom_prompt: str = "", lang: str = "pt-BR") -> tuple[str, str]:
    """Gera um parágrafo de insight sobre o aluno usando Claude."""
    try:
        api_key = _get_api_key()
        if not api_key:
            return "", "ANTHROPIC_API_KEY not found."
        sample = msgs[-30:]
        convo  = "\n".join(
            f"{'Student' if m['role']=='user' else 'Teacher'}: {m.get('content','')[:200]}"
            for m in sample if m.get("content")
        )
        if not convo.strip():
            return "", "no_history"
        if lang == "pt-BR":
            prompt = (
                f"Analise este aluno de inglês e escreva UM parágrafo curto (máximo 3 frases) "
                f"com: 1 ponto forte, 1 dificuldade e 1 sugestão prática. Sem títulos.\n\n"
                f"Aluno: {student.get('name','')} | Nível: {student.get('level','')} | "
                f"Foco: {student.get('focus','')} | Msgs: {student.get('total_messages',0)}\n"
            )
        else:
            prompt = (
                f"Analyse this English student and write ONE short paragraph (max 3 sentences) "
                f"with: 1 strength, 1 difficulty and 1 practical suggestion. No headings.\n\n"
                f"Student: {student.get('name','')} | Level: {student.get('level','')} | "
                f"Focus: {student.get('focus','')} | Messages: {student.get('total_messages',0)}\n"
            )
        if custom_prompt:
            prompt += f"{'Instrução do professor' if lang == 'pt-BR' else 'Teacher instruction'}: {custom_prompt}\n"
        prompt += f"\n{'Conversa' if lang == 'pt-BR' else 'Conversation'}:\n{convo}"

        client = anthropic.Anthropic(api_key=api_key)
        resp   = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=450,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip(), ""
    except Exception as e:
        return "", str(e)




def show_dashboard() -> None:
    user    = st.session_state.user
    profile = user.get("profile", {})
    lang    = profile.get("language", "pt-BR")
    L       = lambda k: _L_(k, lang)  # noqa

    # ── CSS ──────────────────────────────────────────────────────────────────
    st.markdown("""<style>
:root{--db-card:#0f1824;--db-border:#1a2535;--db-acc:#8b5cf6;
  --db-text:#e6edf3;--db-radius:14px;}
.db-title{font-size:1.6rem;font-weight:800;color:var(--db-text);margin-bottom:1.4rem;
  display:flex;align-items:center;gap:10px;}
.m-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:2rem;}
.m-card{background:var(--db-card);border:1px solid var(--db-border);
  border-radius:var(--db-radius);padding:18px 12px;text-align:center;transition:all .2s;}
.m-card:hover{border-color:var(--db-acc);transform:translateY(-2px);
  box-shadow:0 6px 20px rgba(139,92,246,.15);}
.m-icon{font-size:1.5rem;display:block;margin-bottom:4px;}
.m-val{font-size:2rem;font-weight:800;color:var(--db-text);margin:0;}
.m-lbl{font-size:.68rem;color:#4a5a6a;text-transform:uppercase;letter-spacing:.6px;}
.tag-err{display:inline-block;background:rgba(224,92,42,.12);color:#ff7a5c;
  border:1px solid rgba(224,92,42,.3);border-radius:12px;
  padding:2px 8px;font-size:.68rem;margin:2px;}
.tag-hit{display:inline-block;background:rgba(74,222,128,.1);color:#4ade80;
  border:1px solid rgba(74,222,128,.3);border-radius:12px;
  padding:2px 8px;font-size:.7rem;margin:2px;}
.ins-box{background:rgba(139,92,246,.07);border:1px solid rgba(139,92,246,.3);
  border-left:3px solid #8b5cf6;border-radius:10px;
  padding:.8rem 1rem;font-size:.83rem;color:#c084fc;
  font-style:italic;line-height:1.55;margin:.4rem 0 .8rem;}
.ins-label{font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.4px;display:block;margin-bottom:4px;
  color:#8b5cf6;font-style:normal;}
[data-testid="stExpander"]{background:var(--db-card)!important;
  border:1px solid var(--db-border)!important;
  border-radius:var(--db-radius)!important;margin-bottom:10px!important;}
section[data-testid="stSidebar"] div[data-testid="stButton"]>button[kind="primary"]{
  background:linear-gradient(135deg,#6c3fc5,#8b5cf6)!important;
  border:1px solid #7c4dcc!important;color:#fff!important;
  box-shadow:0 0 14px rgba(139,92,246,.35)!important;}
@media(max-width:768px){
  .m-grid{grid-template-columns:repeat(2,1fr);}
  .db-title{font-size:1.2rem;}}
</style>""", unsafe_allow_html=True)

    def _logout():
        token = st.session_state.get("_session_token", "")
        if token:
            delete_session(token)
        js_clear_session()
        st.session_state.pop("_session_token", None)
        st.session_state.pop("_session_saved", None)
        st.session_state.update(logged_in=False, user=None, conv_id=None)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div>
            <div style="font-weight:600;font-size:.9rem;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#4ade80;">&#9679; Online</div>
            </div></div><hr style="border-color:#30363d;margin:4px 0 10px">""",
            unsafe_allow_html=True,
        )
        if st.button("📊 Dashboard", use_container_width=True, type="primary"):
            pass
        if st.button(f"🎙️ {L('voice_mode')}", use_container_width=True, key="db_voice"):
            st.session_state.page = "chat"
            st.session_state.voice_mode = True
            st.rerun()
        if st.button(f"💬 {L('use_student')}", use_container_width=True, key="db_chat"):
            st.session_state.page = "chat"; st.rerun()
        if st.button(f"⚙️ {L('my_profile')}", use_container_width=True, key="db_profile"):
            st.session_state.page = "profile"; st.rerun()
        if st.button(f"🚪 {L('logout')}", use_container_width=True, key="db_logout"):
            _logout(); st.rerun()

    # ── Dados ─────────────────────────────────────────────────────────────────
    all_users = load_students()
    stats     = get_all_students_stats()
    # filtra só alunos
    stats     = [s for s in stats if all_users.get(s.get("username",""), {}).get("role") == "student"]
    today     = datetime.now().strftime("%Y-%m-%d")

    total_students = len(stats)
    total_messages = sum(s.get("messages", 0) for s in stats)
    total_corr     = sum(s.get("corrections", 0) for s in stats)
    active_today   = sum(1 for s in stats
                         if (s.get("last_active", "") or "")[:10] == today)
    corr_rate      = round(total_corr / total_messages * 100, 1) if total_messages else 0

    sorted_stats = sorted(stats, key=lambda x: x.get("messages", 0), reverse=True)
    top          = sorted_stats[0] if sorted_stats else {}

    # ── Título + botão ─────────────────────────────────────────────────────────
    col_t, col_b = st.columns([5, 1])
    with col_t:
        st.markdown(f'<div class="db-title">🎓 {L("title")}</div>', unsafe_allow_html=True)
    with col_b:
        if st.button(f"💬 {L('enter_chat')}", use_container_width=True):
            st.session_state.page = "chat"; st.rerun()

    # ── Metric cards ─────────────────────────────────────────────────────────
    icon_map = ["🎓", "💬", "⚠️", "✅"]
    vals     = [total_students, total_messages, total_corr, total_corr]
    lbls     = [L("students"), L("messages"), L("errors"), L("corrections")]
    cols = st.columns(4)
    for col, icon, val, lbl in zip(cols, icon_map, vals, lbls):
        col.markdown(
            f'<div class="m-card"><span class="m-icon">{icon}</span>'
            f'<div class="m-val">{val}</div><div class="m-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Class Insights ────────────────────────────────────────────────────────
    with st.expander(f"📊 {L('class_insights')}", expanded=False):
        if not stats:
            st.info(L("no_students"))
        else:
            total_convs = 0
            for s in stats:
                try:
                    total_convs += len(list_conversations(s["username"]))
                except Exception:
                    pass
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(L("msgs_per_std"), total_messages // total_students if total_students else 0)
            c2.metric(L("total_convs"),  total_convs)
            c3.metric(L("active_today"), active_today)
            c4.metric(L("err_rate"),     f"{corr_rate:.0f}%")
            if top:
                st.markdown(
                    f"<div style='margin-top:8px;padding:10px;background:#0a1020;"
                    f"border:1px solid #1a2535;border-radius:10px;font-size:.85rem;color:#e6edf3;'>"
                    f"🏆 <b>{L('most_active')}:</b> {top.get('name','—')} "
                    f"({top.get('messages', 0)} msgs)</div>",
                    unsafe_allow_html=True,
                )

    # ── Alunos (expander por aluno) ───────────────────────────────────────────
    level_opts = ["Beginner", "Pre-Intermediate", "Intermediate",
                  "Business English", "Advanced", "Native"]

    st.caption(f"👥 {L('click_expand')}")

    for idx, s in enumerate(sorted_stats):
        name  = s.get("name", "—")
        uname = s.get("username", "")
        level = s.get("level", "—")
        focus = s.get("focus", "—")
        msgs  = s.get("messages", 0)
        corr  = s.get("corrections", 0)
        last  = s.get("last_active", "---")
        mpd   = round(msgs / 30, 1) if msgs > 0 else 0.0

        badge_txt, _  = _student_badge(msgs, last, lang)
        last_fmt      = last[:10] if last and last != "---" else "—"
        insight_key   = f"_insight_{uname}"
        errors_key    = f"_errors_{uname}"
        hits_key      = f"_hits_{uname}"

        # Pré-carrega erros/acertos uma vez
        if errors_key not in st.session_state:
            try:
                convs_list = list_conversations(uname)
                all_msgs: list = []
                for cv in convs_list[:5]:
                    all_msgs.extend(load_conversation(uname, cv["id"]))
                errs, hits = _extract_errors_and_hits(all_msgs)
            except Exception:
                errs, hits = [], []
            st.session_state[errors_key] = errs
            st.session_state[hits_key]   = hits

        errs = st.session_state.get(errors_key, [])
        hits = st.session_state.get(hits_key,   [])

        with st.expander(f"{name}  ·  {level}  ·  {badge_txt}", expanded=False):
            # ── Métricas do aluno ──────────────────────────────────────────
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric(L("msgs"),        msgs)
            mc2.metric(L("corr"),        corr)
            mc3.metric(L("msgs_day"),    mpd)
            mc4.metric(L("last_active"), last_fmt)

            st.markdown(
                f"<p style='font-size:.76rem;color:#8b949e;margin:.2rem 0 .6rem;'>"
                f"<b>{L('focus')}:</b> {focus} &nbsp;|&nbsp; @{uname}</p>",
                unsafe_allow_html=True,
            )
            st.divider()

            # ── Erros e acertos ────────────────────────────────────────────
            col_e, col_h = st.columns(2)
            with col_e:
                st.markdown(f"**⚠️ {L('errors_lbl')}**")
                if errs:
                    for err in errs:
                        st.markdown(
                            f'<span class="tag-err">{err["type"]}</span> '
                            f'<span style="font-size:.76rem;color:#8b949e;">{err["text"]}</span>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        f'<span style="font-size:.75rem;color:#4a5a6a;font-style:italic;">'
                        f'{L("no_errs")}</span>',
                        unsafe_allow_html=True,
                    )
            with col_h:
                st.markdown(f"**✅ {L('hits_lbl')}**")
                if hits:
                    for h in hits:
                        st.markdown(f'<span class="tag-hit">{h}</span>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<span style="font-size:.75rem;color:#4a5a6a;font-style:italic;">'
                        f'{L("no_hits")}</span>',
                        unsafe_allow_html=True,
                    )

            st.divider()

            # ── AI Insight ────────────────────────────────────────────────
            if st.session_state.get(insight_key):
                st.markdown(
                    f'<div class="ins-box"><span class="ins-label">{L("ai_insight")}</span>'
                    f'{st.session_state[insight_key]}</div>',
                    unsafe_allow_html=True,
                )

            if st.button(L("gen_insight"), key=f"ins_{uname}_{idx}"):
                with st.spinner(L("analyzing")):
                    try:
                        convs_list = list_conversations(uname)
                        ml: list = []
                        for cv in convs_list[:3]:
                            ml.extend(load_conversation(uname, cv["id"]))
                        user_profile   = (all_users.get(uname, {}).get("profile") or {})
                        custom_p       = user_profile.get("custom_prompt", "")
                        texto, erro    = _get_ai_insight(s, ml, custom_p)
                    except Exception as e:
                        texto, erro = "", str(e)
                if erro == "no_history":
                    st.warning(L("no_data"))
                elif erro:
                    st.error(f"Error: {erro}")
                elif texto:
                    st.session_state[insight_key] = texto
                    st.rerun()
                else:
                    st.warning(L("no_data"))

            st.divider()

            # ── Alterar nível ──────────────────────────────────────────────
            col_l, _ = st.columns([2, 3])
            with col_l:
                cur_idx   = level_opts.index(level) if level in level_opts else 0
                new_level = st.selectbox(
                    L("change_level"), level_opts, index=cur_idx,
                    key=f"lvl_{uname}_{idx}",
                )
            if new_level != level:
                if st.button(L("save"), key=f"slvl_{uname}_{idx}"):
                    update_profile(uname, {"level": new_level})
                    st.success(L("level_saved"))
                    st.rerun()

            # ── Prompt personalizado ───────────────────────────────────────
            user_profile = (all_users.get(uname, {}).get("profile") or {})
            saved_prompt = user_profile.get("custom_prompt", "")
            st.markdown(f" {L('cust_prompt')}")
            new_prompt = st.text_area(
                "prompt", value=saved_prompt,
                placeholder=L("prompt_hint"),
                key=f"tp_{uname}_{idx}", height=65,
                label_visibility="collapsed",
            )
            if st.button(L("save"), key=f"sp_{uname}_{idx}"):
                update_profile(uname, {"custom_prompt": new_prompt})
                st.session_state.pop(insight_key, None)
                st.success(L("prompt_saved"))
                st.rerun()

    st.divider()

    # ── Student Management ────────────────────────────────────────────────────
    with st.expander(f"⚙️ {L('student_mgmt')}", expanded=False):
        if not sorted_stats:
            st.info(L("no_students"))
        else:
            labels  = [s.get("name", s["username"]) for s in sorted_stats]
            options = [s["username"] for s in sorted_stats]
            sel_label = st.selectbox(L("select_std"), labels, key="mgmt_sel")
            sel_uname = options[labels.index(sel_label)] if sel_label in labels else None
            if sel_uname:
                _, col_b = st.columns([4, 1])
                with col_b:
                    if st.button(L("remove"), key="btn_rm", type="secondary"):
                        st.session_state["_confirm_rm"] = sel_uname
                if st.session_state.get("_confirm_rm") == sel_uname:
                    st.warning(f"{L('confirm_rm')} **{sel_label}**?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(L("confirm"), key="btn_cfm", type="primary"):
                            try:
                                from core.database import get_client
                                db = get_client()
                                for tbl in ("messages", "conversations", "sessions", "users"):
                                    db.table(tbl).delete().eq("username", sel_uname).execute()
                                st.session_state.pop("_confirm_rm", None)
                                st.success(f"{sel_label} {L('removed_ok')}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    with c2:
                        if st.button(L("cancel"), key="btn_cncl"):
                            st.session_state.pop("_confirm_rm", None)
                            st.rerun()

    # ── Class Summary ─────────────────────────────────────────────────────────
    with st.expander(f"📋 {L('class_summary')}", expanded=False):
        if not stats:
            st.info(L("no_students"))
        else:
            avg_msgs = total_messages // total_students if total_students else 0
            st.markdown(
                f"- **{L('msgs_per_std')}:** {avg_msgs}\n"
                f"- **{L('corr_rate')}:** {corr_rate:.1f}%\n"
                f"- **{L('most_active')}:** {top.get('name', 'N/A')} "
                f"({top.get('messages', 0)} msgs)\n"
                f"- **{L('active_today')}:** {active_today}"
            )
            level_dist: dict[str, int] = {}
            for s in stats:
                lv = s.get("level", "Unknown")
                level_dist[lv] = level_dist.get(lv, 0) + 1
            if level_dist:
                st.markdown("**Level distribution:**")
                for lv, count in sorted(level_dist.items(), key=lambda x: x[1], reverse=True):
                    st.markdown(
                        f"<div style='font-size:.8rem;color:#8b949e;margin:2px 0'>"
                        f"<span style='color:#a78bfa;min-width:150px;display:inline-block'>{lv}</span>"
                        f"<span style='color:#f0a500'>{'█' * count}</span>"
                        f" <span style='color:#e6edf3'>{count}</span></div>",
                        unsafe_allow_html=True,
                    )