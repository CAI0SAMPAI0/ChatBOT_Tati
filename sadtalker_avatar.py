# sadtalker_avatar.py
import os, base64, requests, time

SADTALKER_URL = os.getenv("SADTALKER_URL", "").rstrip("/")
TIMEOUT = 300  # 5 minutos

def sadtalker_available() -> bool:
    if not SADTALKER_URL:
        return False
    try:
        r = requests.get(f"{SADTALKER_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def generate_talking_video(audio_bytes: bytes) -> str | None:
    if not SADTALKER_URL:
        return None
    audio_b64 = base64.b64encode(audio_bytes).decode()
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{SADTALKER_URL}/generate",
                json={"audio_b64": audio_b64},
                timeout=TIMEOUT,
            )
            if resp.status_code == 429:
                print(f"[SadTalker] Servidor ocupado, aguardando 10s... (tentativa {attempt+1}/3)")
                time.sleep(10)
                continue
            resp.raise_for_status()
            return resp.json().get("video_b64")
        except Exception as e:
            print(f"[SadTalker] Erro tentativa {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(5)
    return None

wav2lip_available = sadtalker_available
