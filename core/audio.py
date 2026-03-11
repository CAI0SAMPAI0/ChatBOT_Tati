"""
core/audio.py — Transcrição (Faster-Whisper) + TTS (gTTS).
Consolidado a partir de transcriber.py e tts.py.
"""

import io
import os
import re
import tempfile

# ══════════════════════════════════════════════════════════════════════════════
# TEXT-TO-SPEECH (gTTS)
# ══════════════════════════════════════════════════════════════════════════════

def tts_available() -> bool:
    return True


def text_to_speech(text: str) -> bytes | None:
    """Gera áudio MP3 a partir de texto usando gTTS."""
    try:
        from gtts import gTTS
        text = re.sub(r'\*+', '', text).strip()[:600]
        if not text:
            return None
        mp3_fp = io.BytesIO()
        gTTS(text=text, lang='en', tld='com', slow=False).write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return mp3_fp.read()
    except Exception as e:
        print(f"❌ TTS: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# TRANSCRIÇÃO (Faster-Whisper)
# ══════════════════════════════════════════════════════════════════════════════

_model = None  # cache do modelo


def get_model(model_size: str = "small"):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


_CONTEXT_PROMPT = (
    "Teacher Tatiana, English class, Brazilian student, vocabulary, grammar, "
    "pronunciation, past simple, present perfect, modal verbs, conditional, "
    "subjunctive, Beginner, Pre-Intermediate, Intermediate, Business English, "
    "Fortnite, Netflix, TikTok, LinkedIn, worksheet, exercise, activity, PDF, "
    "como se diz, o que significa, não entendi, pode repetir, "
    "hello, how are you, I don't understand, can you help me, "
    "good morning, good afternoon, what does it mean, "
    "teacher, student, lesson, homework, practice, fluent, accent."
)

_CORRECTIONS: list[tuple[str, str]] = [
    (r"\bsh[ei]t[\s-]?on\b",    "Tatiana"),
    (r"\bta[ck]i[aeo]n[ae]\b",  "Tatiana"),
    (r"\btatyana\b",             "Tatiana"),
    (r"\btatianna\b",            "Tatiana"),
    (r"\btachiana\b",            "Tatiana"),
    (r"\btati\s*anna\b",         "Tatiana"),
    (r"\bwork\s*sheet\b",        "worksheet"),
    (r"\bpast\s*simple\b",       "past simple"),
    (r"\bpresent\s*perfect\b",   "present perfect"),
    (r"\bmodal\s*verbs?\b",      "modal verbs"),
    (r"\bgramm?[ae]r\b",         "grammar"),
    (r"\bvocabul[ae]ry\b",       "vocabulary"),
    (r"\bpronunci[ae]tion\b",    "pronunciation"),
    (r"\bconditional\b",         "conditional"),
    (r"\bsubjunctive\b",         "subjunctive"),
    (r"\[BLANK_AUDIO\]",         ""),
    (r"\(silence\)",             ""),
    (r"\[silence\]",             ""),
    (r"\[ ?[Ss]ilence ?\]",      ""),
    (r"\[MUSIC\]",               ""),
    (r"\(music\)",               ""),
    (r"Subtitles by.*$",         ""),
    (r"Transcribed by.*$",       ""),
]


def _apply_corrections(text: str) -> str:
    for pattern, replacement in _CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE).strip()
    return re.sub(r" {2,}", " ", text).strip()


_WHISPER_PARAMS = dict(
    initial_prompt=_CONTEXT_PROMPT,
    beam_size=10,
    best_of=5,
    temperature=0.0,
    condition_on_previous_text=False,
    without_timestamps=True,
    word_timestamps=False,
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,
    no_speech_threshold=0.40,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 200, "threshold": 0.40},
)


def _detect_and_transcribe(model, tmp_path: str, hint_lang: str) -> tuple[str, str]:
    ALLOWED = {"pt", "en"}
    try:
        segs, info = model.transcribe(tmp_path, language=None, **_WHISPER_PARAMS)
        detected   = getattr(info, "language", None) or hint_lang
        text_auto  = " ".join(seg.text.strip() for seg in segs).strip()
    except Exception:
        detected  = hint_lang
        text_auto = ""

    final_lang = detected if detected in ALLOWED else hint_lang

    try:
        segs, _ = model.transcribe(tmp_path, language=final_lang, **_WHISPER_PARAMS)
        text_forced = " ".join(seg.text.strip() for seg in segs).strip()
    except Exception:
        text_forced = text_auto

    text = text_forced if len(text_forced) >= len(text_auto) else text_auto
    return text, final_lang


def transcribe_bytes(audio_bytes: bytes, suffix: str = ".wav", language: str = None) -> str:
    """
    Transcreve bytes de áudio e retorna o texto.
    language=None → detecção automática (bilíngue pt/en).
    """
    tmp_path = None
    try:
        model = get_model()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        use_auto = language in ("auto", None, "")
        hint     = "en" if use_auto else language

        if use_auto:
            text, _ = _detect_and_transcribe(model, tmp_path, hint)
        else:
            segs, _ = model.transcribe(tmp_path, language=language, **_WHISPER_PARAMS)
            text    = " ".join(seg.text.strip() for seg in segs).strip()

        text = _apply_corrections(text)
        return text or "⚠️ Não consegui entender o áudio. Tente novamente."

    except Exception as e:
        return f"❌ Erro na transcrição: {e}"

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
