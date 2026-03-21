"""
core/database.py — Teacher Tati · Supabase (PostgreSQL) backend.

Correções aplicadas vs versão anterior:
  - load_students() não retorna senha por padrão (include_password=False)
  - authenticate() faz query direta por username (sem SELECT * completo)
  - authenticate() remove senha do retorno antes de chegar ao session_state
  - Logging estruturado em vez de print()
  - Sessões com expiração em 30 dias
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
import streamlit as st
from supabase import create_client, Client

logger = logging.getLogger(__name__)

AVATAR_BUCKET = "avatars"
SESSION_DAYS  = 30


# ── Cliente Supabase ──────────────────────────────────────────────────────────

def get_client() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("❌ SUPABASE_URL e SUPABASE_KEY não encontrados.")
    return create_client(url, key)


# ── Senha (bcrypt + migração SHA-256) ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Gera hash bcrypt com 12 rounds."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(plain: str, hashed: str) -> bool:
    """Verifica senha aceitando bcrypt (novo) e SHA-256 hex (legado)."""
    if not plain or not hashed:
        return False
    if hashed.startswith("$2"):
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False
    if len(hashed) == 64:
        sha = hashlib.sha256(plain.encode()).hexdigest()
        return secrets.compare_digest(sha, hashed)
    return False


def _migrate_password_to_bcrypt(username: str, plain: str) -> None:
    """Migra hash SHA-256 para bcrypt silenciosamente após login bem-sucedido."""
    try:
        db = get_client()
        db.table("users").update(
            {"password": hash_password(plain)}
        ).eq("username", username).execute()
    except Exception:
        logger.warning("Falha ao migrar senha de '%s'", username, exc_info=True)


# ── Init DB ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    db = get_client()
    _ensure_default_users(db)


def _ensure_default_users(db: Client) -> None:
    now = datetime.now().isoformat()
    defaults = [
        {
            "username":   "professor",
            "name":       "Professor",
            "password":   hash_password("prof123"),
            "role":       "professor",
            "level":      "Advanced",
            "focus":      "General Conversation",
            "email":      "",
            "created_at": now,
            "profile":    {},
        },
        {
            "username":   "programador",
            "name":       "Programador",
            "password":   hash_password("cai0_based"),
            "role":       "programador",
            "level":      "Advanced",
            "focus":      "General Conversation",
            "email":      "",
            "created_at": now,
            "profile":    {},
        },
    ]
    for u in defaults:
        existing = (
            db.table("users").select("username").eq("username", u["username"]).execute().data
        )
        if not existing:
            db.table("users").insert(u).execute()


# ── Usuários ──────────────────────────────────────────────────────────────────

def load_students(include_password: bool = False) -> dict:
    """
    Carrega usuários. Por padrão NÃO inclui hash de senha.
    Use include_password=True apenas internamente no authenticate().
    """
    db   = get_client()
    cols = "username, name, role, email, level, focus, created_at, profile"
    if include_password:
        cols = "*"

    rows = db.table("users").select(cols).execute().data or []
    result: dict = {}
    for r in rows:
        entry = {
            "name":       r["name"],
            "role":       r["role"],
            "email":      r.get("email", ""),
            "level":      r["level"],
            "focus":      r["focus"],
            "created_at": r["created_at"],
            "profile":    r.get("profile") or {},
        }
        if include_password:
            entry["password"] = r.get("password", "")
        result[r["username"]] = entry
    return result


def authenticate(username: str, password: str) -> dict | None:
    """
    Autentica usuário com query direta (sem carregar todos os usuários).
    Retorna dados do usuário SEM senha, ou None.
    """
    db = get_client()

    def _fetch(uname: str) -> dict | None:
        rows = (
            db.table("users")
            .select("username, name, password, role, email, level, focus, created_at, profile")
            .eq("username", uname)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    # Tenta username exato, depois lowercase
    row = _fetch(username) or _fetch(username.lower())
    if not row:
        return None

    if not check_password(password, row["password"]):
        return None

    # Migração automática SHA-256 → bcrypt
    if not row["password"].startswith("$2"):
        _migrate_password_to_bcrypt(row["username"], password)

    # Remove a senha antes de retornar — nunca vai para session_state
    return {
        "_resolved_username": row["username"],
        "name":       row["name"],
        "role":       row["role"],
        "email":      row.get("email", ""),
        "level":      row["level"],
        "focus":      row["focus"],
        "created_at": row["created_at"],
        "profile":    row.get("profile") or {},
    }


def register_student(
    username: str,
    name: str,
    password: str,
    email: str = "",
    level: str = "Beginner",
    focus: str = "General Conversation",
) -> tuple[bool, str]:
    db = get_client()
    existing = (
        db.table("users").select("username").eq("username", username.lower()).execute().data
    )
    if existing:
        return False, "Username já existe."

    now     = datetime.now().isoformat()
    profile = {
        "theme": "dark", "accent_color": "#f0a500", "language": "pt-BR",
        "nickname": "", "occupation": "",
        "ai_style": "Warm & Encouraging", "ai_tone": "Teacher",
        "custom_instructions": "", "voice_lang": "en", "speech_lang": "en-US",
    }
    db.table("users").insert({
        "username":   username.lower(),
        "name":       name,
        "password":   hash_password(password),
        "role":       "student",
        "email":      email,
        "level":      level,
        "focus":      focus,
        "created_at": now,
        "profile":    profile,
    }).execute()
    return True, "Conta criada!"


def update_profile(username: str, patch: dict) -> bool:
    db  = get_client()
    row = (
        db.table("users").select("profile, level, focus").eq("username", username).execute().data
    )
    if not row:
        return False

    top_fields: dict = {}
    for f in ("name", "email", "level", "focus"):
        if f in patch:
            top_fields[f] = patch.pop(f)

    profile = row[0].get("profile") or {}
    profile.update(patch)
    db.table("users").update({"profile": profile, **top_fields}).eq("username", username).execute()
    return True


def update_password(username: str, new_pw: str) -> bool:
    db = get_client()
    db.table("users").update(
        {"password": hash_password(new_pw)}
    ).eq("username", username).execute()
    return True


# ── Sessões persistentes ──────────────────────────────────────────────────────

def create_session(username: str) -> str:
    token      = secrets.token_urlsafe(32)
    now        = datetime.now()
    expires_at = (now + timedelta(days=SESSION_DAYS)).isoformat()
    db         = get_client()
    db.table("sessions").insert({
        "token":      token,
        "username":   username,
        "created_at": now.isoformat(),
        "last_seen":  now.isoformat(),
        "expires_at": expires_at,
    }).execute()
    return token


def validate_session(token: str) -> dict | None:
    """Valida token, atualiza last_seen. Retorna dados do usuário sem senha."""
    if not token:
        return None
    db  = get_client()
    now = datetime.now()

    try:
        result   = db.rpc("validate_session", {"p_token": token}).execute()
        username = result.data
        if not username:
            return None
    except Exception:
        row = (
            db.table("sessions")
            .select("username, expires_at")
            .eq("token", token)
            .execute()
            .data
        )
        if not row:
            return None
        sess     = row[0]
        username = sess["username"]
        expires  = sess.get("expires_at")
        if expires and datetime.fromisoformat(expires) < now:
            db.table("sessions").delete().eq("token", token).execute()
            return None
        db.table("sessions").update(
            {"last_seen": now.isoformat()}
        ).eq("token", token).execute()

    return load_students().get(username)


def delete_session(token: str) -> None:
    get_client().table("sessions").delete().eq("token", token).execute()


# ── Conversas ─────────────────────────────────────────────────────────────────

def new_conversation(username: str) -> str:
    cid = datetime.now().strftime("%Y%m%d_%H%M%S")
    now = datetime.now().isoformat()
    db  = get_client()
    db.table("conversations").upsert(
        {"id": cid, "username": username, "created_at": now},
        on_conflict="id,username",
        ignore_duplicates=True,
    ).execute()
    return cid


def delete_conversation(username: str, conv_id: str) -> None:
    db = get_client()
    try:
        db.rpc("delete_conversation", {
            "p_username": username, "p_conv_id": conv_id,
        }).execute()
    except Exception:
        db.table("messages").delete().eq("username", username).eq("conv_id", conv_id).execute()
        db.table("conversations").delete().eq("username", username).eq("id", conv_id).execute()


def list_conversations(username: str) -> list[dict]:
    db = get_client()
    try:
        rows = db.rpc("list_conversations", {"p_username": username}).execute().data or []
    except Exception:
        return _list_conversations_fallback(username, db)

    result = []
    for r in rows:
        if not r.get("title"):
            continue
        title = r["title"]
        if len(title) == 45:
            title += "..."
        try:
            date = datetime.strptime(r["id"], "%Y%m%d_%H%M%S").strftime("%d/%m %H:%M")
        except Exception:
            date = r["id"][:13]
        result.append({
            "id":    r["id"],
            "title": title,
            "date":  date,
            "count": r.get("msg_count", 0),
        })
    return result


def _list_conversations_fallback(username: str, db: Client) -> list[dict]:
    convs = (
        db.table("conversations").select("id, created_at")
        .eq("username", username).order("created_at", desc=True)
        .execute().data or []
    )
    result = []
    for c in convs:
        msgs = (
            db.table("messages").select("content")
            .eq("username", username).eq("conv_id", c["id"]).eq("role", "user")
            .order("id").limit(1).execute().data or []
        )
        if not msgs:
            continue
        count = (
            db.table("messages").select("id", count="exact")
            .eq("username", username).eq("conv_id", c["id"]).eq("role", "user")
            .execute().count or 0
        )
        first = msgs[0]["content"]
        title = first[:45] + ("..." if len(first) > 45 else "")
        try:
            date = datetime.strptime(c["id"], "%Y%m%d_%H%M%S").strftime("%d/%m %H:%M")
        except Exception:
            date = c["id"][:13]
        result.append({"id": c["id"], "title": title, "date": date, "count": count})
    return result


def load_conversation(username: str, conv_id: str) -> list[dict]:
    db = get_client()
    try:
        rows = db.rpc("load_conversation", {
            "p_username": username, "p_conv_id": conv_id,
        }).execute().data or []
        for r in rows:
            if "msg_time" in r:
                r["time"]      = r.pop("msg_time")
                r["date"]      = r.pop("msg_date")
                r["timestamp"] = r.pop("msg_timestamp")
    except Exception:
        rows = (
            db.table("messages").select("*")
            .eq("username", username).eq("conv_id", conv_id).order("id")
            .execute().data or []
        )
    return rows


@st.cache_data(show_spinner=False, ttl=10)
def cached_load_conversation(username: str, conv_id: str) -> list[dict]:
    return load_conversation(username, conv_id)


def append_message(
    username:  str,
    conv_id:   str,
    role:      str,
    content:   str,
    audio:     bool = False,
    tts_b64:   str | None = None,
    is_file:   bool = False,
) -> None:
    now = datetime.now()
    db  = get_client()
    try:
        db.rpc("append_message", {
            "p_username":      username,
            "p_conv_id":       conv_id,
            "p_role":          role,
            "p_content":       content,
            "p_audio":         bool(audio),
            "p_is_file":       bool(is_file),
            "p_tts_b64":       tts_b64 or "",
            "p_msg_time":      now.strftime("%H:%M"),
            "p_msg_date":      now.strftime("%Y-%m-%d"),
            "p_msg_timestamp": now.isoformat(),
        }).execute()
    except Exception:
        db.table("conversations").upsert(
            {"id": conv_id, "username": username, "created_at": now.isoformat()},
            on_conflict="id,username",
            ignore_duplicates=True,
        ).execute()
        db.table("messages").insert({
            "conv_id":   conv_id,
            "username":  username,
            "role":      role,
            "content":   content,
            "audio":     bool(audio),
            "is_file":   bool(is_file),
            "tts_b64":   tts_b64 or "",
            "time":      now.strftime("%H:%M"),
            "date":      now.strftime("%Y-%m-%d"),
            "timestamp": now.isoformat(),
        }).execute()


# ── Avatar (Supabase Storage) ─────────────────────────────────────────────────

def save_user_avatar_db(username: str, raw: bytes, mime: str) -> bool:
    db   = get_client()
    path = f"{username}/avatar"
    try:
        try:
            db.storage.from_(AVATAR_BUCKET).remove([path])
        except Exception:
            pass
        db.storage.from_(AVATAR_BUCKET).upload(
            path, raw,
            file_options={"content-type": mime, "upsert": "true"},
        )
        return True
    except Exception:
        logger.error("Falha no upload de avatar para '%s'", username, exc_info=True)
        return False


def get_user_avatar_db(username: str) -> tuple[bytes, str] | None:
    db   = get_client()
    path = f"{username}/avatar"
    try:
        raw  = db.storage.from_(AVATAR_BUCKET).download(path)
        mime = "image/jpeg"
        if raw[:4] == b"\x89PNG":
            mime = "image/png"
        elif raw[:4] == b"RIFF":
            mime = "image/webp"
        return raw, mime
    except Exception:
        return None


def remove_user_avatar_db(username: str) -> bool:
    db   = get_client()
    path = f"{username}/avatar"
    try:
        db.storage.from_(AVATAR_BUCKET).remove([path])
        return True
    except Exception:
        logger.error("Falha ao remover avatar de '%s'", username, exc_info=True)
        return False


# ── Stats do professor ─────────────────────────────────────────────────────────

def get_all_students_stats() -> list[dict]:
    db = get_client()
    try:
        rows = db.rpc("get_students_stats").execute().data or []
        return [
            {
                "username":    r["username"],
                "name":        r["name"],
                "level":       r["level"],
                "focus":       r["focus"],
                "messages":    r.get("total_msgs", 0),
                "corrections": r.get("corrections", 0),
                "last_active": r.get("last_active", "---"),
                "created_at":  (r.get("created_at") or "")[:10],
            }
            for r in rows
        ]
    except Exception:
        return _get_students_stats_fallback(db)


def _get_students_stats_fallback(db: Client) -> list[dict]:
    students = load_students()
    result   = []
    for username, data in students.items():
        if data["role"] != "student":
            continue
        msgs  = db.table("messages").select("id", count="exact").eq("username", username).eq("role", "user").execute()
        total = msgs.count or 0
        ai_msgs = (
            db.table("messages").select("content")
            .eq("username", username).eq("role", "assistant")
            .execute().data or []
        )
        keywords = ["Quick check", "we say", "instead of", "should be", "Try saying"]
        fixes = sum(1 for m in ai_msgs if any(kw in m["content"] for kw in keywords))
        last_row = (
            db.table("messages").select("date")
            .eq("username", username).order("id", desc=True).limit(1)
            .execute().data
        )
        last = last_row[0]["date"] if last_row else "---"
        result.append({
            "username":    username,
            "name":        data["name"],
            "level":       data["level"],
            "focus":       data["focus"],
            "messages":    total,
            "corrections": fixes,
            "last_active": last,
            "created_at":  data["created_at"][:10],
        })
    return result