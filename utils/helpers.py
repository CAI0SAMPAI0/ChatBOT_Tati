import base64
import os
from pathlib import Path

import streamlit as st

PHOTO_PATH = os.getenv("PROFESSOR_PHOTO", "assets/tati.png")
PROF_NAME  = os.getenv("PROFESSOR_NAME",  "Teacher Tati")


# ── Imagens da professora ─────────────────────────────────────────────────────

def get_photo_b64() -> str | None:
    """Lê a foto da professora e devolve como data-URI base64."""
    p = Path(PHOTO_PATH)
    if p.exists():
        ext  = p.suffix.lower().replace(".", "")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None


@st.cache_data(show_spinner=False)
def get_tati_mini_b64() -> str:
    """Lê a foto da Tati uma única vez e reutiliza em todo o app."""
    for _p in [
        Path("assets/tati.png"), Path("assets/tati.jpg"),
        Path(__file__).parent.parent / "assets" / "tati.png",
        Path(__file__).parent.parent / "assets" / "tati.jpg",
    ]:
        if _p.exists():
            _ext  = _p.suffix.lstrip(".").lower()
            _mime = "jpeg" if _ext in ("jpg", "jpeg") else _ext
            return f"data:image/{_mime};base64,{base64.b64encode(_p.read_bytes()).decode()}"
    return get_photo_b64() or ""


@st.cache_data(show_spinner=False)
def get_avatar_frames() -> dict:
    """Carrega os frames do avatar animado uma única vez."""
    _base = Path(__file__).parent.parent

    def _load(candidates):
        for p in candidates:
            p = Path(p)
            if p.exists():
                return f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"
        return ""

    return {
        "normal":     _load([_base / "assets" / "avatar_tati_normal.png",     "assets/avatar_tati_normal.png"]),
        "meio":       _load([_base / "assets" / "avatar_tati_meio.png",       "assets/avatar_tati_meio.png"]),
        "aberta":     _load([_base / "assets" / "avatar_tati_aberta.png",     "assets/avatar_tati_aberta.png"]),
        "bem_aberta": _load([_base / "assets" / "avatar_tati_bem_aberta.png", "assets/avatar_tati_bem_aberta.png"]),
        "ouvindo":    _load([_base / "assets" / "avatar_tati_ouvindo.png",    "assets/avatar_tati_ouvindo.png"]),
        "piscando":   _load([_base / "assets" / "tati_piscando.png",          "assets/tati_piscando.png"]),
        "surpresa":   _load([_base / "assets" / "tati_surpresa.png",          "assets/tati_surpresa.png"]),
    }


# ── Avatares de usuários ──────────────────────────────────────────────────────

def _avatar_circle_html(b64: str | None, size: int, border: str = "#8800f0") -> str:
    """Retorna HTML de avatar circular — foto, sem_foto.png ou ícone FA."""
    if not b64:
        for _p in [
            Path("assets/sem_foto.png"),
            Path(__file__).parent.parent / "assets" / "sem_foto.png",
        ]:
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
        f'style="font-size:{icon_px}px;--fa-primary-color:#f0a500;--fa-secondary-color:#c87800;--fa-secondary-opacity:0.6;"></i>'
        f'</div>'
    )


def avatar_html(size: int = 52, speaking: bool = False) -> str:
    """Avatar da professora com anel de 'speaking' animado."""
    cls   = "speaking" if speaking else ""
    photo = get_photo_b64()
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
        f'style="width:{size}px;height:{size}px;font-size:{int(size * .48)}px">🧑‍🏫</div>'
    )


def get_user_avatar_b64(username: str, _bust: int = 0) -> str | None:
    """Busca foto do usuário direto do banco, sem cache."""
    # Import local para evitar circular
    from core.database import get_user_avatar_db
    result = get_user_avatar_db(username)
    if not result:
        return None
    raw, mime = result
    import base64 as _b64
    return f"data:{mime};base64,{_b64.b64encode(raw).decode()}"


def _bump_avatar_version() -> None:
    st.session_state["_avatar_v"] = st.session_state.get("_avatar_v", 0) + 1


def hex_to_rgb(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    n = int(h, 16)
    return f"{(n >> 16) & 255},{(n >> 8) & 255},{n & 255}"
