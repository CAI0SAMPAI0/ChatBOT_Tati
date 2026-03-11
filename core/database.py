"""
core/database.py — Teacher Tati · Supabase (PostgreSQL) backend
Criptografia: bcrypt (rounds=12) com migração automática de hashes SHA-256 legados.
Sessões com expiração em 30 dias.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt
import streamlit as st
from supabase import create_client, Client

AVATAR_BUCKET = "avatars"
SESSION_DAYS  = 30


# ── Cliente Supabase ──────────────────────────────────────────────────────────

def get_client() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("❌ SUPABASE_URL e SUPABASE_KEY não encontrados.")
    return create_client(url, key)


# ── Senha (bcrypt + migração SHA-256) ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Gera hash bcrypt com 12 rounds."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(plain: str, hashed: str) -> bool:
    """
    Verifica senha aceitando bcrypt (novo) e SHA-256 (legado).
    Não faz nenhum output — silencioso.
    """
    if not plain or not hashed:
        return False
    if hashed.startswith("$2"):
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False
    # Fallback SHA-256 legado (hex 64 chars)
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
        pass


# ── Init DB ───────────────────────────────────────────────────────────────────

def init_db():
    """Garante que os usuários padrão existem."""
    db = get_client()
    _ensure_default_users(db)


def _ensure_default_users(db: Client):
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
        existing = db.table("users").select("username").eq("username", u["username"]).execute().data
        if not existing:
            db.table("users").insert(u).execute()


# ── Usuários ──────────────────────────────────────────────────────────────────

def load_students() -> dict:
    """Carrega usuários SEM retornar senhas."""
    db   = get_client()
    rows = db.table("users").select(
        "username, name, role, email, level, focus, created_at, profile"
    ).execute().data or []

    return {
        r["username"]: {
            "name":       r["name"],
            "role":       r["role"],
            "email":      r.get("email", ""),
            "level":      r["level"],
            "focus":      r["focus"],
            "created_at": r["created_at"],
            "profile":    r.get("profile") or {},
        }
        for r in rows
    }


def authenticate(username: str, password: str) -> dict | None:
    """Autentica usuário. Retorna dados sem senha, ou None."""
    db = get_client()

    row = (
        db.table("users")
        .select("username, name, role, email, level, focus, created_at, profile, password")
        .eq("username", username.lower())
        .execute()
        .data
    )
    if not row:
        row = (
            db.table("users")
            .select("username, name, role, email, level, focus, created_at, profile, password")
            .eq("username", username)
            .execute()
            .data
        )
    if not row:
        return None

    u = row[0]

    if not check_password(password, u["password"]):
        return None

    # Migra SHA-256 → bcrypt automaticamente (silencioso)
    if not u["password"].startswith("$2"):
        _migrate_password_to_bcrypt(u["username"], password)

    return {
        "_resolved_username": u["username"],
        "name":       u["name"],
        "role":       u["role"],
        "email":      u.get("email", ""),
        "level":      u["level"],
        "focus":      u["focus"],
        "created_at": u["created_at"],
        "profile":    u.get("profile") or {},
    }


def register_student(
    username: str, name: str, password: str,
    email: str = "", level: str = "Beginner",
    focus: str = "General Conversation",
) -> tuple[bool, str]:
    db = get_client()
    existing = db.table("users").select("username").eq("username", username.lower()).execute().data
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
    row = db.table("users").select("profile, level, focus").eq("username", username).execute().data
    if not row:
        return False

    top_fields = {}
    for f in ("name", "email", "level", "focus"):
        if f in patch:
            top_fields[f] = patch.pop(f)

    profile = row[0].get("profile") or {}
    profile.update(patch)

    db.table("users").update({"profile": profile, **top_fields}).eq("username", username).execute()
    return True


def update_password(username: str, new_pw: str) -> bool:
    db = get_client()
    db.table("users").update({"password": hash_password(new_pw)}).eq("username", username).execute()
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
    """Valida token e atualiza last_seen. Retorna dados do usuário sem senha."""
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
        db.table("sessions").update({"last_seen": now.isoformat()}).eq("token", token).execute()

    return load_students().get(username)


def delete_session(token: str):
    get_client().table("sessions").delete().eq("token", token).execute()


# ── Conversas ─────────────────────────────────────────────────────────────────

def new_conversation(username: str) -> str:
    cid = datetime.now().strftime("%Y%m%d_%H%M%S")
    now = datetime.now().isoformat()
    db  = get_client()
    db.table("conversations").upsert(
        {"id": cid, "username": username, "created_at": now},
        on_conflict="id,username", ignore_duplicates=True,
    ).execute()
    return cid


def delete_conversation(username: str, conv_id: str):
    db = get_client()
    try:
        db.rpc("delete_conversation", {"p_username": username, "p_conv_id": conv_id}).execute()
    except Exception:
        db.table("messages").delete().eq("username", username).eq("conv_id", conv_id).execute()
        db.table("conversations").delete().eq("username", username).eq("id", conv_id).execute()


def list_conversations(username: str) -> list:
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
        result.append({"id": r["id"], "title": title, "date": date, "count": r.get("msg_count", 0)})
    return result


def _list_conversations_fallback(username: str, db: Client) -> list:
    convs = (
        db.table("conversations").select("id, created_at")
        .eq("username", username).order("created_at", desc=True).execute().data or []
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


def load_conversation(username: str, conv_id: str) -> list:
    db = get_client()
    try:
        rows = db.rpc("load_conversation", {"p_username": username, "p_conv_id": conv_id}).execute().data or []
        for r in rows:
            if "msg_time" in r:
                r["time"]      = r.pop("msg_time")
                r["date"]      = r.pop("msg_date")
                r["timestamp"] = r.pop("msg_timestamp")
    except Exception:
        rows = (
            db.table("messages").select("*")
            .eq("username", username).eq("conv_id", conv_id).order("id").execute().data or []
        )
    return rows


@st.cache_data(show_spinner=False, ttl=10)
def cached_load_conversation(username: str, conv_id: str) -> list:
    return load_conversation(username, conv_id)


def append_message(
    username: str, conv_id: str, role: str, content: str,
    audio: bool = False, tts_b64: str = None, is_file: bool = False,
):
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
            on_conflict="id,username", ignore_duplicates=True,
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
            path, raw, file_options={"content-type": mime, "upsert": "true"},
        )
        return True
    except Exception as e:
        print(f"[avatar upload ERROR] {e}")
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
        return False


# ── Stats do professor ─────────────────────────────────────────────────────────

def get_all_students_stats() -> list:
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


def _get_students_stats_fallback(db: Client) -> list:
    students = load_students()
    result   = []
    for username, data in students.items():
        if data["role"] != "student":
            continue
        msgs  = db.table("messages").select("id", count="exact").eq("username", username).eq("role", "user").execute()
        total = msgs.count or 0
        ai_msgs = db.table("messages").select("content").eq("username", username).eq("role", "assistant").execute().data or []
        keywords = ["Quick check", "we say", "instead of", "should be", "Try saying"]
        fixes = sum(1 for m in ai_msgs if any(kw in m["content"] for kw in keywords))
        last_row = db.table("messages").select("date").eq("username", username).order("id", desc=True).limit(1).execute().data
        last = last_row[0]["date"] if last_row else "---"
        result.append({
            "username": username, "name": data["name"],
            "level": data["level"], "focus": data["focus"],
            "messages": total, "corrections": fixes,
            "last_active": last, "created_at": data["created_at"][:10],
        })
    return result