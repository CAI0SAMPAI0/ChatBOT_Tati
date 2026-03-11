import io
import re
from gtts import gTTS


def tts_available() -> bool:
    return True


def text_to_speech(text: str) -> bytes | None:
    try:
        text = re.sub(r'\*+', '', text).strip()[:600]
        if not text:
            return None

        print(f"🎙️  TTS: gerando áudio com gTTS...")
        mp3_fp = io.BytesIO()
        tts = gTTS(text=text, lang='en', tld='com', slow=False)
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        audio_bytes = mp3_fp.read()
        print(f"✅ TTS: áudio gerado ({len(audio_bytes)} bytes)")
        return audio_bytes

    except Exception as e:
        print(f"❌ TTS: exceção — {e}")
        return None
