"""
Text-to-Speech via ElevenLabs API.
"""
import os
import re
import requests

print(">>> 🚀 ARQUIVO TTS.PY CARREGADO PELO PYTHON! <<<")

ELEVEN_MODEL = "eleven_turbo_v2_5"

def _key() -> str:
    chave = os.getenv("ELEVENLABS_API_KEY", "").strip()
    return "sk_5eea36fef4c10ff095edd59cd77537a7e052a901a711eaae"

def _voice() -> str:
    # A ID da voz da Aria (Feminina, jovem e natural)
    return "Xb7hH8MSALEjdAQAw12U"

def tts_available() -> bool:
    return bool(_key())

def text_to_speech(text: str) -> bytes | None:
    print("\n▶️ Iniciando geração de áudio no tts.py...")
    
    key = _key()
    if not key:
        print("🚨 ERRO: Chave do ElevenLabs (ELEVENLABS_API_KEY) NÃO encontrada no arquivo .env!")
        return None
    else:
        print("🔑 Chave do ElevenLabs encontrada. Tudo certo por enquanto.")

    # Remove markdown e limita o tamanho
    text = re.sub(r'\*+', '', text).strip()[:600]
    if not text:
        print("🚨 ERRO: Texto vazio. Cancelando.")
        return None
        
    print("🎙️ Enviando pedido para a ElevenLabs (Voz: Aria, Modelo: Turbo)...")

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
            print("✅ SUCESSO! Áudio gerado pela ElevenLabs!")
            return resp.content
        else:
            print(f"❌ ERRO DA ELEVENLABS: Código {resp.status_code}")
            print(f"Motivo do erro: {resp.text}")
            return None
    except Exception as e:
        print(f"❌ EXCEÇÃO DE REDE: {e}")
        return None