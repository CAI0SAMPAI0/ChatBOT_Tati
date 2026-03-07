import json
import hashlib
from datetime import datetime
from pathlib import Path

DATA_DIR      = Path("data")
STUDENTS_FILE = DATA_DIR / "students.json"
CONVS_DIR     = DATA_DIR / "conversations"   # data/conversations/<username>/<conv_id>.json

def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    CONVS_DIR.mkdir(exist_ok=True)
    if not STUDENTS_FILE.exists():
        save_students({"professor": {
            "name": "Professor", "password": hash_password("prof123"),
            "role": "professor", "level": "Advanced",
            "focus": "General Conversation", "created_at": datetime.now().isoformat(),
        }})

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def load_students():
    if not STUDENTS_FILE.exists(): return {}
    return json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))

def save_students(s):
    STUDENTS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

def register_student(username, name, password, level, focus):
    students = load_students()
    if username in students: return False, "Username já existe."
    students[username] = {"name":name,"password":hash_password(password),"role":"student",
                          "level":level,"focus":focus,"created_at":datetime.now().isoformat()}
    save_students(students)
    return True, "Conta criada com sucesso!"

def authenticate(username, password):
    students = load_students()
    u = students.get(username)
    if u and u["password"] == hash_password(password): return u
    return None

# ── Conversas ────────────────────────────────────────────────────────────────
def _user_dir(username):
    d = CONVS_DIR / username
    d.mkdir(parents=True, exist_ok=True)
    return d

def _conv_file(username, conv_id):
    return _user_dir(username) / f"{conv_id}.json"

def new_conversation(username):
    """Cria nova conversa e retorna seu ID."""
    conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    _conv_file(username, conv_id).write_text("[]", encoding="utf-8")
    return conv_id

def list_conversations(username):
    """Retorna lista de conversas com pelo menos 1 mensagem, mais recentes primeiro."""
    d = _user_dir(username)
    result = []
    for f in sorted(d.glob("*.json"), reverse=True):
        msgs = json.loads(f.read_text(encoding="utf-8"))
        user_msgs = [m for m in msgs if m["role"] == "user"]
        if not user_msgs:
            continue  # ignora conversas vazias
        title = user_msgs[0]["content"][:45] + "…" if len(user_msgs[0]["content"]) > 45 else user_msgs[0]["content"]
        # formata data: "20240315_143200" → "15/03 14:32"
        try:
            dt = datetime.strptime(f.stem, "%Y%m%d_%H%M%S")
            date = dt.strftime("%d/%m %H:%M")
        except Exception:
            date = f.stem[:13]
        result.append({"id": f.stem, "title": title, "date": date, "count": len(user_msgs)})
    return result

def load_conversation(username, conv_id):
    f = _conv_file(username, conv_id)
    if not f.exists(): return []
    return json.loads(f.read_text(encoding="utf-8"))

def save_conversation(username, conv_id, messages):
    _conv_file(username, conv_id).write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")

def append_message(username, conv_id, role, content, audio=False):
    msgs = load_conversation(username, conv_id)
    msgs.append({"role":role,"content":content,"audio":audio,
                 "time":datetime.now().strftime("%H:%M"),
                 "date":datetime.now().strftime("%Y-%m-%d"),
                 "timestamp":datetime.now().isoformat()})
    save_conversation(username, conv_id, msgs)

# ── Compatibilidade retroativa com código antigo ──────────────────────────────
def load_history(username):
    """Lê o arquivo legado username.json se existir."""
    old = DATA_DIR / "history" / f"{username}.json"
    if old.exists(): return json.loads(old.read_text(encoding="utf-8"))
    return []

def get_all_students_stats():
    students = load_students()
    result = []
    for username, data in students.items():
        if data["role"] != "student": continue
        convs = list_conversations(username)
        total_msgs = sum(c["count"] for c in convs)
        # contar correções em todas as conversas
        corrections = 0
        for c in convs:
            for m in load_conversation(username, c["id"]):
                if m["role"]=="assistant" and any(
                    k.lower() in m["content"].lower() for k in
                    ["Quick check","we say","instead of","should be","Try saying"]):
                    corrections += 1
        last = convs[0]["date"] if convs else "—"
        result.append({"username":username,"name":data["name"],"level":data["level"],
                       "focus":data["focus"],"messages":total_msgs,"corrections":corrections,
                       "last_active":last,"created_at":data["created_at"][:10]})
    return result