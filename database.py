import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
import json

DATA_DIR = Path("data")
DB_PATH  = DATA_DIR / "app.db"


def get_conn():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    # ── Usuários ──────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username    TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'student',
            email       TEXT DEFAULT '',
            level       TEXT DEFAULT 'False Beginner',
            focus       TEXT DEFAULT 'General Conversation',
            created_at  TEXT NOT NULL,
            profile     TEXT DEFAULT '{}'
        )
    """)

    # ── Conversas ─────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          TEXT NOT NULL,
            username    TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            PRIMARY KEY (id, username)
        )
    """)

    # ── Mensagens ─────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id     TEXT NOT NULL,
            username    TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            audio       INTEGER DEFAULT 0,
            is_file     INTEGER DEFAULT 0,
            tts_b64     TEXT DEFAULT '',
            time        TEXT NOT NULL,
            date        TEXT NOT NULL,
            timestamp   TEXT NOT NULL
        )
    """)

    # ── Sessões persistentes ──────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            username    TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        )
    """)

    conn.commit()

    # Cria usuários padrão se não existirem
    _ensure_default_users(conn)
    conn.close()


def _ensure_default_users(conn):
    c = conn.cursor()
    now = datetime.now().isoformat()

    defaults = [
        {
            "username": "professor",
            "name": "Professor",
            "password": hash_password("prof123"),
            "role": "professor",
            "level": "Advanced",
            "focus": "General Conversation",
        },
        {
            "username": "programador",
            "name": "Programador",
            "password": hash_password("cai0_based"),
            "role": "programador",
            "level": "Advanced",
            "focus": "General Conversation",
        },
    ]
    for u in defaults:
        c.execute("INSERT OR IGNORE INTO users (username,name,password,role,level,focus,created_at,profile) VALUES (?,?,?,?,?,?,?,?)",
                  (u["username"], u["name"], u["password"], u["role"],
                   u["level"], u["focus"], now, "{}"))
    conn.commit()


# ── Senha ─────────────────────────────────────────────────────────────────────

def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


# ── Sessões persistentes ──────────────────────────────────────────────────────

def create_session(username: str) -> str:
    """Cria um token de sessão e salva no banco."""
    import secrets
    token = secrets.token_urlsafe(32)
    now   = datetime.now().isoformat()
    conn  = get_conn()
    conn.execute("INSERT INTO sessions (token,username,created_at,last_seen) VALUES (?,?,?,?)",
                 (token, username, now, now))
    conn.commit()
    conn.close()
    return token


def validate_session(token: str) -> dict | None:
    """Valida um token e retorna os dados do usuário, ou None se inválido."""
    if not token:
        return None
    conn = get_conn()
    row  = conn.execute(
        "SELECT username FROM sessions WHERE token=?", (token,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    username = row["username"]
    # Atualiza last_seen
    conn.execute("UPDATE sessions SET last_seen=? WHERE token=?",
                 (datetime.now().isoformat(), token))
    conn.commit()
    conn.close()
    return load_students().get(username)


def delete_session(token: str):
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()


# ── Usuários ──────────────────────────────────────────────────────────────────

def load_students() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    result = {}
    for r in rows:
        result[r["username"]] = {
            "name":       r["name"],
            "password":   r["password"],
            "role":       r["role"],
            "email":      r["email"],
            "level":      r["level"],
            "focus":      r["focus"],
            "created_at": r["created_at"],
            "profile":    json.loads(r["profile"] or "{}"),
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
    conn = get_conn()
    existing = conn.execute("SELECT username FROM users WHERE username=?",
                            (username,)).fetchone()
    if existing:
        conn.close()
        return False, "Username já existe."
    now = datetime.now().isoformat()
    profile = json.dumps({
        "theme": "dark", "accent_color": "#f0a500", "language": "pt-BR",
        "nickname": "", "occupation": "",
        "ai_style": "Warm & Encouraging", "ai_tone": "Teacher",
        "custom_instructions": "", "voice_lang": "en", "speech_lang": "en-US",
    })
    conn.execute(
        "INSERT INTO users (username,name,password,role,email,level,focus,created_at,profile) VALUES (?,?,?,?,?,?,?,?,?)",
        (username, name, hash_password(password), "student", email, level, focus, now, profile)
    )
    conn.commit()
    conn.close()
    return True, "Conta criada!"


def update_profile(username: str, patch: dict) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        conn.close()
        return False
    # Campos de nível superior
    top_fields = {}
    for f in ("name", "email", "level", "focus"):
        if f in patch:
            top_fields[f] = patch.pop(f)
    # Atualiza campos de nível superior
    for field, val in top_fields.items():
        conn.execute(f"UPDATE users SET {field}=? WHERE username=?", (val, username))
    # Atualiza profile JSON
    profile = json.loads(row["profile"] or "{}")
    profile.update(patch)
    conn.execute("UPDATE users SET profile=? WHERE username=?",
                 (json.dumps(profile), username))
    conn.commit()
    conn.close()
    return True


def update_password(username: str, new_pw: str) -> bool:
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE username=?",
                 (hash_password(new_pw), username))
    conn.commit()
    conn.close()
    return True


# ── Conversas ─────────────────────────────────────────────────────────────────

def new_conversation(username: str) -> str:
    cid = datetime.now().strftime("%Y%m%d_%H%M%S")
    now = datetime.now().isoformat()
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO conversations (id,username,created_at) VALUES (?,?,?)",
                 (cid, username, now))
    conn.commit()
    conn.close()
    return cid


def delete_conversation(username: str, conv_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE username=? AND conv_id=?", (username, conv_id))
    conn.execute("DELETE FROM conversations WHERE username=? AND id=?", (username, conv_id))
    conn.commit()
    conn.close()


def list_conversations(username: str) -> list:
    conn  = get_conn()
    convs = conn.execute(
        "SELECT id, created_at FROM conversations WHERE username=? ORDER BY created_at DESC",
        (username,)
    ).fetchall()
    result = []
    for c in convs:
        msgs = conn.execute(
            "SELECT role, content, date FROM messages WHERE username=? AND conv_id=? AND role='user' ORDER BY id",
            (username, c["id"])
        ).fetchall()
        if not msgs:
            continue
        first  = msgs[0]["content"]
        title  = first[:45] + ("..." if len(first) > 45 else "")
        count  = len(msgs)
        try:
            date = datetime.strptime(c["id"], "%Y%m%d_%H%M%S").strftime("%d/%m %H:%M")
        except:
            date = c["id"][:13]
        result.append({"id": c["id"], "title": title, "date": date, "count": count})
    conn.close()
    return result


def load_conversation(username: str, conv_id: str) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE username=? AND conv_id=? ORDER BY id",
        (username, conv_id)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def append_message(username, conv_id, role, content,
                   audio=False, tts_b64=None, is_file=False):
    now = datetime.now()
    conn = get_conn()
    # Garante que a conversa existe
    conn.execute("INSERT OR IGNORE INTO conversations (id,username,created_at) VALUES (?,?,?)",
                 (conv_id, username, now.isoformat()))
    conn.execute(
        """INSERT INTO messages
           (conv_id,username,role,content,audio,is_file,tts_b64,time,date,timestamp)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (conv_id, username, role, content,
         1 if audio else 0,
         1 if is_file else 0,
         tts_b64 or "",
         now.strftime("%H:%M"),
         now.strftime("%Y-%m-%d"),
         now.isoformat())
    )
    conn.commit()
    conn.close()


# ── Stats do professor ────────────────────────────────────────────────────────

def get_all_students_stats() -> list:
    students = load_students()
    conn     = get_conn()
    result   = []
    for username, data in students.items():
        if data["role"] not in ("student",):
            continue
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE username=? AND role='user'",
            (username,)
        ).fetchone()
        total = row["cnt"] if row else 0

        fix_row = conn.execute(
            """SELECT COUNT(*) as cnt FROM messages
               WHERE username=? AND role='assistant'
               AND (content LIKE '%Quick check%' OR content LIKE '%we say%'
                    OR content LIKE '%instead of%' OR content LIKE '%should be%'
                    OR content LIKE '%Try saying%')""",
            (username,)
        ).fetchone()
        fixes = fix_row["cnt"] if fix_row else 0

        last_row = conn.execute(
            "SELECT date FROM messages WHERE username=? ORDER BY id DESC LIMIT 1",
            (username,)
        ).fetchone()
        last = last_row["date"] if last_row else "---"

        result.append({
            "username":   username,
            "name":       data["name"],
            "level":      data["level"],
            "focus":      data["focus"],
            "messages":   total,
            "corrections": fixes,
            "last_active": last,
            "created_at": data["created_at"][:10],
        })
    conn.close()
    return result