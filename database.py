"""
database.py — Teacher Tati · Supabase (PostgreSQL) backend v2
Usa funções RPC do Supabase para queries otimizadas (menos round-trips).

Configuração no .env / Streamlit Secrets:
    SUPABASE_URL  = https://xxxx.supabase.co
    SUPABASE_KEY  = eyJhbGci...
"""

import os
import hashlib
import secrets
from datetime import datetime
import json

import streamlit as st
from supabase import create_client, Client

# ── Cliente Supabase ──────────────────────────────────────────────────────────

def get_client() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "❌ SUPABASE_URL e SUPABASE_KEY não encontrados no .env / Secrets."
        )
    return create_client(url, key)


# ── Senha ─────────────────────────────────────────────────────────────────────

def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


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
        db.table("users").upsert(u, on_conflict="username", ignore_duplicates=True).execute()


# ── Usuários ──────────────────────────────────────────────────────────────────

def load_students() -> dict:
    db   = get_client()
    rows = db.table("users").select("*").execute().data or []
    result = {}
    for r in rows:
        result[r["username"]] = {
            "name":       r["name"],
            "password":   r["password"],
            "role":       r["role"],
            "email":      r.get("email", ""),
            "level":      r["level"],
            "focus":      r["focus"],
            "created_at": r["created_at"],
            "profile":    r.get("profile") or {},
        }
    return result


def authenticate(username: str, password: str) -> dict | None:
    students = load_students()
    resolved = username
    u = students.get(username)
    if u is None:
        resolved = username.lower()
        u = students.get(resolved)
    if u and u["password"] == hash_password(password):
        return {**u, "_resolved_username": resolved}
    return None


def register_student(username, name, password, email="",
                     level="Beginner", focus="General Conversation"):
    db = get_client()
    existing = db.table("users").select("username").eq("username", username).execute().data
    if existing:
        return False, "Username já existe."

    now = datetime.now().isoformat()
    profile = {
        "theme": "dark", "accent_color": "#f0a500", "language": "pt-BR",
        "nickname": "", "occupation": "",
        "ai_style": "Warm & Encouraging", "ai_tone": "Teacher",
        "custom_instructions": "", "voice_lang": "en", "speech_lang": "en-US",
    }
    db.table("users").insert({
        "username":   username,
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
    db = get_client()
    row = db.table("users").select("*").eq("username", username).execute().data
    if not row:
        return False
    row = row[0]

    top_fields = {}
    for f in ("name", "email", "level", "focus"):
        if f in patch:
            top_fields[f] = patch.pop(f)

    profile = row.get("profile") or {}
    profile.update(patch)

    update_data = {"profile": profile}
    update_data.update(top_fields)

    db.table("users").update(update_data).eq("username", username).execute()
    return True


def update_password(username: str, new_pw: str) -> bool:
    db = get_client()
    db.table("users").update({"password": hash_password(new_pw)}).eq("username", username).execute()
    return True


# ── Sessões persistentes ──────────────────────────────────────────────────────

def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    now   = datetime.now().isoformat()
    db    = get_client()
    db.table("sessions").insert({
        "token":      token,
        "username":   username,
        "created_at": now,
        "last_seen":  now,
    }).execute()
    return token


def validate_session(token: str) -> dict | None:
    """Usa RPC para validar e atualizar last_seen em uma única query."""
    if not token:
        return None
    db = get_client()

    try:
        result = db.rpc("validate_session", {"p_token": token}).execute()
        username = result.data
        if not username:
            return None
    except Exception:
        row = db.table("sessions").select("username").eq("token", token).execute().data
        if not row:
            return None
        username = row[0]["username"]
        db.table("sessions").update({"last_seen": datetime.now().isoformat()}).eq("token", token).execute()

    return load_students().get(username)


def delete_session(token: str):
    db = get_client()
    db.table("sessions").delete().eq("token", token).execute()


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


def delete_conversation(username: str, conv_id: str):
    """Usa RPC para deletar conversa e mensagens atomicamente."""
    db = get_client()
    try:
        db.rpc("delete_conversation", {
            "p_username": username,
            "p_conv_id":  conv_id,
        }).execute()
    except Exception:
        db.table("messages").delete().eq("username", username).eq("conv_id", conv_id).execute()
        db.table("conversations").delete().eq("username", username).eq("id", conv_id).execute()


def list_conversations(username: str) -> list:
    """Usa RPC — era N+1 queries, agora é 1 query só."""
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


def _list_conversations_fallback(username: str, db: Client) -> list:
    """Fallback para list_conversations sem RPC."""
    convs = (
        db.table("conversations")
        .select("id, created_at")
        .eq("username", username)
        .order("created_at", desc=True)
        .execute()
        .data or []
    )
    result = []
    for c in convs:
        msgs = (
            db.table("messages")
            .select("content")
            .eq("username", username)
            .eq("conv_id", c["id"])
            .eq("role", "user")
            .order("id")
            .limit(1)
            .execute()
            .data or []
        )
        if not msgs:
            continue
        count = (
            db.table("messages")
            .select("id", count="exact")
            .eq("username", username)
            .eq("conv_id", c["id"])
            .eq("role", "user")
            .execute()
            .count or 0
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
    """Usa RPC para carregar conversa."""
    db = get_client()
    try:
        rows = db.rpc("load_conversation", {
            "p_username": username,
            "p_conv_id":  conv_id,
        }).execute().data or []
        for r in rows:
            if "msg_time" in r:
                r["time"]      = r.pop("msg_time")
                r["date"]      = r.pop("msg_date")
                r["timestamp"] = r.pop("msg_timestamp")
    except Exception:
        rows = (
            db.table("messages")
            .select("*")
            .eq("username", username)
            .eq("conv_id", conv_id)
            .order("id")
            .execute()
            .data or []
        )
    return rows


@st.cache_data(show_spinner=False, ttl=60)
def cached_load_conversation(username: str, conv_id: str) -> list:
    """Versão cacheada de load_conversation para evitar queries repetidas."""
    return load_conversation(username, conv_id)


def append_message(username, conv_id, role, content,
                   audio=False, tts_b64=None, is_file=False):
    """Usa RPC para inserir mensagem atomicamente."""
    now = datetime.now()
    db  = get_client()

    try:
        db.rpc("append_message", {
            "p_username":       username,
            "p_conv_id":        conv_id,
            "p_role":           role,
            "p_content":        content,
            "p_audio":          bool(audio),
            "p_is_file":        bool(is_file),
            "p_tts_b64":        tts_b64 or "",
            "p_msg_time":       now.strftime("%H:%M"),
            "p_msg_date":       now.strftime("%Y-%m-%d"),
            "p_msg_timestamp":  now.isoformat(),
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


# ── Avatar do usuário (Supabase Storage) ─────────────────────────────────────

AVATAR_BUCKET = "avatars"

def save_user_avatar_db(username: str, raw: bytes, mime: str) -> bool:
    db   = get_client()
    path = f"{username}/avatar"
    try:
        try:
            db.storage.from_(AVATAR_BUCKET).remove([path])
        except Exception as e:
            print(f"[avatar remove old] {e}")

        result = db.storage.from_(AVATAR_BUCKET).upload(
            path, raw,
            file_options={"content-type": mime, "upsert": "true"},
        )
        print(f"[avatar upload ok] {result}")
        return True
    except Exception as e:
        print(f"[avatar upload ERROR] {e}")
        return False

def get_user_avatar_db(username: str) -> tuple[bytes, str] | None:
    """Retorna (bytes, mime) da foto do usuário ou None."""
    db   = get_client()
    path = f"{username}/avatar"
    try:
        raw = db.storage.from_(AVATAR_BUCKET).download(path)
        mime = "image/jpeg"
        if raw[:4] == b"\x89PNG":
            mime = "image/png"
        elif raw[:4] == b"RIFF":
            mime = "image/webp"
        return raw, mime
    except Exception:
        return None


def remove_user_avatar_db(username: str) -> bool:
    """Remove foto de perfil do Supabase Storage."""
    db   = get_client()
    path = f"{username}/avatar"
    try:
        db.storage.from_(AVATAR_BUCKET).remove([path])
        return True
    except Exception:
        return False


# ── Stats do professor ────────────────────────────────────────────────────────

def get_all_students_stats() -> list:
    """Usa RPC — era loop Python com N queries, agora é 1 query."""
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
    """Fallback para get_all_students_stats sem RPC."""
    students = load_students()
    result   = []
    for username, data in students.items():
        if data["role"] != "student":
            continue
        msgs = (
            db.table("messages")
            .select("id", count="exact")
            .eq("username", username)
            .eq("role", "user")
            .execute()
        )
        total = msgs.count or 0

        ai_msgs = (
            db.table("messages")
            .select("content")
            .eq("username", username)
            .eq("role", "assistant")
            .execute()
            .data or []
        )
        correction_keywords = ["Quick check", "we say", "instead of", "should be", "Try saying"]
        fixes = sum(1 for m in ai_msgs if any(kw in m["content"] for kw in correction_keywords))

        last_row = (
            db.table("messages")
            .select("date")
            .eq("username", username)
            .order("id", desc=True)
            .limit(1)
            .execute()
            .data
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