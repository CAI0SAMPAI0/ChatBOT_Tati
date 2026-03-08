"""
wav2lip_avatar.py
Integração do Wav2Lip (rodando no Colab) com o Streamlit.

Configuração .env necessária:
    WAV2LIP_URL=https://xxxx.ngrok-free.app   # URL gerada no Colab
"""

import os
import base64
import tempfile
import requests
from typing import Optional


# ── Configuração ──────────────────────────────────────────────────────────────
WAV2LIP_URL     = os.getenv("WAV2LIP_URL", "").rstrip("/")
REQUEST_TIMEOUT = int(os.getenv("WAV2LIP_TIMEOUT", "90"))   # segundos


# ── Funções públicas ──────────────────────────────────────────────────────────

def wav2lip_available() -> bool:
    """Verifica se o servidor Wav2Lip está online."""
    if not WAV2LIP_URL:
        return False
    try:
        r = requests.get(f"{WAV2LIP_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def generate_talking_video(audio_bytes: bytes) -> Optional[str]:
    """
    Envia áudio WAV para o servidor Wav2Lip e recebe vídeo MP4.

    Parâmetros:
        audio_bytes: bytes do arquivo WAV (saída do TTS)

    Retorna:
        String base64 do MP4, ou None em caso de erro.
    """
    if not WAV2LIP_URL:
        print("[wav2lip] WAV2LIP_URL não configurado no .env")
        return None

    audio_b64 = base64.b64encode(audio_bytes).decode()

    try:
        resp = requests.post(
            f"{WAV2LIP_URL}/generate",
            json={"audio_b64": audio_b64},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if "video_b64" in data:
            return data["video_b64"]
        else:
            print(f"[wav2lip] Resposta inesperada: {data}")
            return None

    except requests.Timeout:
        print("[wav2lip] Timeout — servidor demorou demais. Tente aumentar WAV2LIP_TIMEOUT.")
        return None
    except requests.RequestException as e:
        print(f"[wav2lip] Erro de conexão: {e}")
        return None
    except Exception as e:
        print(f"[wav2lip] Erro inesperado: {e}")
        return None


def audio_file_to_bytes(path: str) -> Optional[bytes]:
    """Lê um arquivo de áudio e retorna bytes."""
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception as e:
        print(f"[wav2lip] Erro ao ler áudio: {e}")
        return None


def tts_text_to_audio_bytes(text: str, voice_id: str = "en-US-AriaNeural",
                             rate: str = "+0%", pitch: str = "+0Hz") -> Optional[bytes]:
    """
    Gera áudio WAV a partir de texto usando edge-tts (já usado no app).
    Retorna bytes do WAV, ou None em caso de erro.

    Requer: pip install edge-tts
    """
    try:
        import asyncio
        import edge_tts
        import io

        async def _synth():
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()

        return asyncio.run(_synth())

    except ImportError:
        print("[wav2lip] edge-tts não instalado. Rode: pip install edge-tts")
        return None
    except Exception as e:
        print(f"[wav2lip] Erro no TTS: {e}")
        return None
