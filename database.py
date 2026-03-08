"""
database.py — Teacher Tati · Supabase (PostgreSQL) backend
Substitui o SQLite local por Supabase para persistência real no deploy.

Configuração no .env / Streamlit Secrets:
    SUPABASE_URL  = https://xxxx.supabase.co
    SUPABASE_KEY  = eyJhbGci...  (anon key ou service_role key)
"""

import os
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
import json

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


# ── Init DB — garante usuários padrão ────────────────────────────────────────
# No Supabase as tabelas são criadas pelo SQL abaixo (cole no SQL Editor):
#
# -- USERS
# create table if not exists users (
#   username    text primary key,
#   name        text not null,
#   password    text not null,
#   role        text not null default 'student',
#   email       text default '',
#   level       text default 'False Beginner',
#   focus       text default 'General Conversation',
#   created_at  text not null,
#   profile     jsonb default '{}'::jsonb
# );
#
# -- CONVERSATIONS
# create table if not exists conversations (
#   id          text not null,
#   username    text not null,
#   created_at  text not null,
#   primary key (id, username)
# );
#
# -- MESSAGES
# create table if not exists messages (
#   id          bigserial primary key,
#   conv_id     text not null,
#   username    text not null,
#   role        text not null,
#   content     text not null,
#   audio       boolean default false,
#   is_file     boolean default false,
#   tts_b64     text default '',
#   time        text not null,
#   date        text not null,
#   timestamp   text not null
# );
#
# -- SESSIONS
# create table if not exists sessions (
#   token       text primary key,
#   username    text not null,
#   created_at  text not null,
#   last_seen   text not null
# );
#
# -- Índices para performance
# create index if not exists idx_messages_username_conv on messages(username, conv_id);
# create index if not exists idx_conversations_username on conversations(username);
# create index if not exists idx_sessions_token on sessions(token);

def init_db():
    """Garante que os usuários padrão existem. Tabelas são criadas via SQL Editor."""
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
        # upsert ignora se já existir
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
                     level="False Beginner", focus="General Conversation"):
    db = get_client()
    # Verifica se já existe
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

    # Campos de nível superior
    top_fields = {}
    for f in ("name", "email", "level", "focus"):
        if f in patch:
            top_fields[f] = patch.pop(f)

    # Atualiza perfil JSON
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
    if not token:
        return None
    db  = get_client()
    row = db.table("sessions").select("username").eq("token", token).execute().data
    if not row:
        return None
    username = row[0]["username"]
    # Atualiza last_seen
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
    # upsert evita duplicata se chamado duas vezes no mesmo segundo
    db.table("conversations").upsert(
        {"id": cid, "username": username, "created_at": now},
        on_conflict="id,username",
        ignore_duplicates=True,
    ).execute()
    return cid


def delete_conversation(username: str, conv_id: str):
    db = get_client()
    db.table("messages").delete().eq("username", username).eq("conv_id", conv_id).execute()
    db.table("conversations").delete().eq("username", username).eq("id", conv_id).execute()


def list_conversations(username: str) -> list:
    db    = get_client()
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
            .select("role, content, date")
            .eq("username", username)
            .eq("conv_id", c["id"])
            .eq("role", "user")
            .order("id")
            .execute()
            .data or []
        )
        if not msgs:
            continue
        first = msgs[0]["content"]
        title = first[:45] + ("..." if len(first) > 45 else "")
        count = len(msgs)
        try:
            date = datetime.strptime(c["id"], "%Y%m%d_%H%M%S").strftime("%d/%m %H:%M")
        except Exception:
            date = c["id"][:13]
        result.append({"id": c["id"], "title": title, "date": date, "count": count})
    return result


def load_conversation(username: str, conv_id: str) -> list:
    db   = get_client()
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


def append_message(username, conv_id, role, content,
                   audio=False, tts_b64=None, is_file=False):
    now = datetime.now()
    db  = get_client()

    # Garante que a conversa existe
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


# ── Stats do professor ────────────────────────────────────────────────────────

def get_all_students_stats() -> list:
    db       = get_client()
    students = load_students()
    result   = []

    for username, data in students.items():
        if data["role"] not in ("student",):
            continue

        # Total de mensagens do aluno
        msgs = (
            db.table("messages")
            .select("id", count="exact")
            .eq("username", username)
            .eq("role", "user")
            .execute()
        )
        total = msgs.count or 0

        # Correções (heurística — mensagens da IA com frases de correção)
        # O Supabase não tem LIKE nativo no SDK sem RPC, então filtramos no Python
        ai_msgs = (
            db.table("messages")
            .select("content")
            .eq("username", username)
            .eq("role", "assistant")
            .execute()
            .data or []
        )
        correction_keywords = [
            "Quick check", "we say", "instead of", "should be", "Try saying"
        ]
        fixes = sum(
            1 for m in ai_msgs
            if any(kw in m["content"] for kw in correction_keywords)
        )

        # Último acesso
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