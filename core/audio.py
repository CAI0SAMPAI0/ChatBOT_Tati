"""
core/audio.py — TTS (gTTS) e transcrição (Groq Whisper).
"""

import concurrent.futures
import io
import logging
import os
import re
import tempfile

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# TEXT-TO-SPEECH (gTTS) — assíncrono para não bloquear a UI
# ══════════════════════════════════════════════════════════════════════════════

def tts_available() -> bool:
    return True


def _sanitize_tts(text: str) -> str:
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:600]


def _gtts_sync(text: str) -> bytes | None:
    try:
        from gtts import gTTS
        clean = _sanitize_tts(text)
        if not clean:
            return None
        mp3_fp = io.BytesIO()
        gTTS(text=clean, lang="en", tld="com", slow=False).write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return mp3_fp.read()
    except Exception as e:
        logger.error("gTTS falhou", exc_info=True)
        return None


def text_to_speech(text: str, timeout: int = 15) -> bytes | None:
    """
    Gera áudio MP3 via gTTS em thread separada.
    Não bloqueia a thread principal (Streamlit).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_gtts_sync, text)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("TTS timeout após %ds", timeout)
            return None
        except Exception as e:
            logger.error("TTS erro inesperado: %s", e, exc_info=True)
            return None


# ══════════════════════════════════════════════════════════════════════════════
# TRANSCRIÇÃO (Groq Whisper API)
# ══════════════════════════════════════════════════════════════════════════════

_CORRECTIONS: list[tuple[str, str]] = [
    (r"\bsh[ei]t[\s-]?on\b",   "Tatiana"),
    (r"\bta[ck]i[aeo]n[ae]\b", "Tatiana"),
    (r"\btatyana\b",            "Tatiana"),
    (r"\btatianna\b",           "Tatiana"),
    (r"\btachiana\b",           "Tatiana"),
    (r"\btati\s*anna\b",        "Tatiana"),
    (r"\bwork\s*sheet\b",       "worksheet"),
    (r"\bpast\s*simple\b",      "past simple"),
    (r"\bpresent\s*perfect\b",  "present perfect"),
    (r"\bmodal\s*verbs?\b",     "modal verbs"),
    (r"\bgramm?[ae]r\b",        "grammar"),
    (r"\bvocabul[ae]ry\b",      "vocabulary"),
    (r"\bpronunci[ae]tion\b",   "pronunciation"),
    (r"\[BLANK_AUDIO\]",        ""),
    (r"\(silence\)",            ""),
    (r"\[silence\]",            ""),
    (r"\[ ?[Ss]ilence ?\]",     ""),
    (r"\[MUSIC\]",              ""),
    (r"\(music\)",              ""),
    (r"Subtitles by.*$",        ""),
    (r"Transcribed by.*$",      ""),
]

_GROQ_PROMPT = (
    "Teacher Tatiana, English class, Brazilian student, "
    "vocabulary, grammar, pronunciation, past simple, present perfect, "
    "modal verbs, conditional, subjunctive, worksheet, exercise, activity, "
    "como se diz, o que significa, não entendi, pode repetir."
)


def _apply_corrections(text: str) -> str:
    for pattern, replacement in _CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE).strip()
    return re.sub(r" {2,}", " ", text).strip()


def transcribe_bytes(
    audio_bytes: bytes,
    suffix: str = ".wav",
    language: str | None = None,
) -> str:
    tmp_path: str | None = None
    try:
        from groq import Groq

        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            return "❌ GROQ_API_KEY não configurada."

        client = Groq(api_key=api_key)

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            kwargs: dict = {
                "file":            (f"audio{suffix}", f, "audio/webm"),
                "model":           "whisper-large-v3-turbo",
                "prompt":          _GROQ_PROMPT,
                "response_format": "text",
            }
            if language and language not in ("auto", ""):
                kwargs["language"] = language

            transcription = client.audio.transcriptions.create(**kwargs)

        text = transcription if isinstance(transcription, str) else transcription.text
        return _apply_corrections(text.strip()) or "⚠️ Não consegui entender o áudio. Tente novamente."

    except Exception as e:
        logger.error("Transcrição falhou", exc_info=True)
        return f"❌ Erro na transcrição: {e}"

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass