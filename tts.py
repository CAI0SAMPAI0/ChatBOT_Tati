"""
Text-to-Speech via ElevenLabs API.
"""
import os
import re
import requests

ELEVEN_MODEL = "eleven_multilingual_v2"

def _key() -> str:
    return os.getenv("ELEVENLABS_API_KEY", "")

def _voice() -> str:
    return os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

def tts_available() -> bool:
    return bool(_key())

def text_to_speech(text: str) -> bytes | None:
    key = _key()
    if not key:
        return None

    # Remove markdown e limita tamanho
    text = re.sub(r'\*+', '', text).strip()[:600]
    if not text:
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{_voice()}"
    headers = {
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.content
        print(f"[TTS] Erro {resp.status_code}: {resp.text[:300]}")
        return None
    except Exception as e:
        print(f"[TTS] Exceção: {e}")
        return None