# sadtalker_avatar.py
# Drop-in replacement para wav2lip_avatar.py
# Coloque este arquivo na raiz do projeto (mesmo lugar que wav2lip_avatar.py)

import os
import base64
import requests

SADTALKER_URL = os.getenv("SADTALKER_URL", "").rstrip("/")
TIMEOUT = 120  # segundos (SadTalker é mais lento que Wav2Lip)


def sadtalker_available() -> bool:
    """Retorna True se o servidor SadTalker no Colab está acessível."""
    if not SADTALKER_URL:
        return False
    try:
        r = requests.get(f"{SADTALKER_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def generate_talking_video(audio_bytes: bytes) -> str | None:
    """
    Envia áudio (bytes WAV/MP3) para o servidor SadTalker no Colab.
    Retorna o vídeo animado como string base64, ou None em caso de erro.
    """
    if not SADTALKER_URL:
        return None
    try:
        audio_b64 = base64.b64encode(audio_bytes).decode()
        resp = requests.post(
            f"{SADTALKER_URL}/generate",
            json={"audio_b64": audio_b64},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("video_b64")
    except Exception as e:
        print(f"[SadTalker] Erro ao gerar vídeo: {e}")
        return None


# Aliases para compatibilidade com app.py (que importa wav2lip_avatar)
wav2lip_available = sadtalker_available
