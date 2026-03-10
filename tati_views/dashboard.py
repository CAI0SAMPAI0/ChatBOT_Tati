"""
tati_views/dashboard.py — Teacher Tati · Painel do professor.
"""

from datetime import datetime

import streamlit as st

from database import get_all_students_stats
from ui_helpers import PROF_NAME, t, avatar_html, do_logout


def show_dashboard() -> None:
    user    = st.session_state.user
    profile = user.get("profile", {})
    ui_lang = profile.get("language", "pt-BR")

    with st.sidebar:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            {avatar_html(44)}<div>
            <div style="font-weight:600;font-size:.9rem;">{PROF_NAME}</div>
            <div style="font-size:.7rem;color:#8b949e;"><span class="status-dot"></span>Professora</div>
            </div></div>
            <hr style="border-color:#30363d;margin:6px 0 12px">""", unsafe_allow_html=True)

        if st.button("📊 Dashboard", use_container_width=True, type="primary"): pass
        if st.button(t("voice_mode", ui_lang), use_container_width=True, key="dash_voice"):
            st.session_state.page = "chat"
            st.session_state.voice_mode = True
            st.rerun()
        if st.button(t("use_as_student", ui_lang), use_container_width=True, key="dash_chat"):
            st.session_state.page = "chat"; st.rerun()
        if st.button(t("my_profile", ui_lang), use_container_width=True, key="dash_profile"):
            st.session_state.page = "profile"; st.rerun()
        if st.button(t("logout", ui_lang), use_container_width=True, key="dash_logout"):
            do_logout(); st.rerun()

    st.markdown("## 📊 Painel do Professor")
    st.markdown("---")
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button(t("enter_chat", ui_lang), use_container_width=True):
            st.session_state.page = "chat"; st.rerun()
    st.markdown("---")

    stats = get_all_students_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in zip(
        [c1, c2, c3, c4],
        [
            len(stats),
            sum(s["messages"]    for s in stats),
            sum(s["corrections"] for s in stats),
            sum(1 for s in stats if s["last_active"][:10] == today),
        ],
        ["Alunos", "Mensagens", "Correções", "Ativos Hoje"],
    ):
        col.markdown(
            f'<div class="stat-card"><div class="val">{val}</div><div class="lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>")
    st.markdown("### 👥 Alunos")
    if not stats:
        st.info("Nenhum aluno ainda.")
    else:
        badge = {
            "Beginner":         "badge-blue",
            "Pre-Intermediate": "badge-green",
            "Intermediate":     "badge-gold",
            "Business English": "badge-gold",
        }
        rows = "".join(f"""<tr>
            <td><b>{s['name']}</b><br>
                <span style="color:#8b949e;font-size:.75rem">@{s['username']}</span></td>
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
            unsafe_allow_html=True,
        )
