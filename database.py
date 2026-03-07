import json
import hashlib
from datetime import datetime
from pathlib import Path

DATA_DIR      = Path("data")
STUDENTS_FILE = DATA_DIR / "students.json"
CONVS_DIR     = DATA_DIR / "conversations"

def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    CONVS_DIR.mkdir(exist_ok=True)
    if not STUDENTS_FILE.exists():
        save_students({"professor": {
            "name": "Professor", "password": hash_password("prof123"),
            "role": "professor", "level": "Advanced",
            "focus": "General Conversation",
            "email": "", "created_at": datetime.now().isoformat(),
            "profile": {}
        }})

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def load_students():
    if not STUDENTS_FILE.exists(): return {}
    return json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))

def save_students(s):
    STUDENTS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

def register_student(username, name, password, email="",
                     level="False Beginner", focus="General Conversation"):
    students = load_students()
    if username in students: return False, "Username ja existe."
    students[username] = {
        "name": name, "password": hash_password(password),
        "role": "student", "email": email,
        "level": level, "focus": focus,
        "created_at": datetime.now().isoformat(),
        "profile": {
            "theme": "dark", "accent_color": "#f0a500", "language": "pt-BR",
            "nickname": "", "occupation": "",
            "ai_style": "Warm & Encouraging", "ai_tone": "Teacher",
            "custom_instructions": "",
            "voice_lang": "en", "speech_lang": "en-US",
        }
    }
    save_students(students)
    return True, "Conta criada!"

def authenticate(username, password):
    """Login case-insensitive: Professor, professor e PROFESSOR funcionam igual."""
    students = load_students()
    resolved = username
    u = students.get(username)
    if u is None:
        resolved = username.lower()
        u = students.get(resolved)
    if u and u["password"] == hash_password(password):
        return {**u, "_resolved_username": resolved}
    return None

def update_profile(username: str, patch: dict) -> bool:
    students = load_students()
    if username not in students: return False
    u = students[username]
    if "profile" not in u: u["profile"] = {}
    for f in ("name", "email", "level", "focus"):
        if f in patch: u[f] = patch.pop(f)
    u["profile"].update(patch)
    save_students(students)
    return True

def update_password(username: str, new_pw: str) -> bool:
    students = load_students()
    if username not in students: return False
    students[username]["password"] = hash_password(new_pw)
    save_students(students)
    return True

def _user_dir(u):
    d = CONVS_DIR / u; d.mkdir(parents=True, exist_ok=True); return d

def _conv_file(u, cid): return _user_dir(u) / f"{cid}.json"

def new_conversation(username):
    cid = datetime.now().strftime("%Y%m%d_%H%M%S")
    _conv_file(username, cid).write_text("[]", encoding="utf-8")
    return cid

def delete_conversation(username, conv_id):
    f = _conv_file(username, conv_id)
    if f.exists():
        f.unlink()

def list_conversations(username):
    result = []
    for f in sorted(_user_dir(username).glob("*.json"), reverse=True):
        msgs = json.loads(f.read_text(encoding="utf-8"))
        um = [m for m in msgs if m["role"] == "user"]
        if not um: continue
        title = um[0]["content"][:45] + ("..." if len(um[0]["content"]) > 45 else "")
        try:    date = datetime.strptime(f.stem, "%Y%m%d_%H%M%S").strftime("%d/%m %H:%M")
        except: date = f.stem[:13]
        result.append({"id": f.stem, "title": title, "date": date, "count": len(um)})
    return result

def load_conversation(username, conv_id):
    f = _conv_file(username, conv_id)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

def save_conversation(username, conv_id, messages):
    _conv_file(username, conv_id).write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")

def append_message(username, conv_id, role, content, audio=False, tts_b64=None, is_file=False):
    msgs = load_conversation(username, conv_id)
    entry = {"role": role, "content": content, "audio": audio,
             "time": datetime.now().strftime("%H:%M"),
             "date": datetime.now().strftime("%Y-%m-%d"),
             "timestamp": datetime.now().isoformat()}
    if tts_b64: entry["tts_b64"] = tts_b64
    if is_file:  entry["is_file"] = True
    msgs.append(entry)
    save_conversation(username, conv_id, msgs)

def load_history(username):
    old = DATA_DIR / "history" / f"{username}.json"
    return json.loads(old.read_text(encoding="utf-8")) if old.exists() else []

def get_all_students_stats():
    students = load_students()
    result = []
    for username, data in students.items():
        if data["role"] != "student": continue
        convs = list_conversations(username)
        total = sum(c["count"] for c in convs)
        fixes = sum(1 for c in convs
                    for m in load_conversation(username, c["id"])
                    if m["role"] == "assistant" and any(
                        k.lower() in m["content"].lower() for k in
                        ["Quick check", "we say", "instead of", "should be", "Try saying"]))
        result.append({
            "username": username, "name": data["name"], "level": data["level"],
            "focus": data["focus"], "messages": total, "corrections": fixes,
            "last_active": convs[0]["date"] if convs else "---",
            "created_at": data["created_at"][:10]
        })
    return result