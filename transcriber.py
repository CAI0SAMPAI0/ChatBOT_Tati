"""
Módulo de transcrição de áudio usando faster-whisper (100% local, gratuito).
Versão 2.0 — suporte bilíngue pt-BR / en com detecção automática de idioma,
prompt contextual e dicionário de correções fonéticas.
"""

import tempfile
import os
import re
from pathlib import Path

_model = None  # cache do modelo em memória


def get_model(model_size: str = "small"):
    """
    Carrega o modelo uma única vez e reutiliza.
    'small' (~500 MB) é o mínimo recomendado para bilíngue com qualidade.
    Use 'medium' para produção se tiver RAM disponível.
    """
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


# ── Prompt contextual — "ensina" o Whisper sobre o vocabulário do app ────────
# Inclui nomes próprios, termos pedagógicos e palavras PT/EN que coexistem.
# Quanto mais rico este prompt, menos erros fonéticos acontecem.
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

# ── Dicionário de correções pós-transcrição ──────────────────────────────────
# Chave: padrão regex (case-insensitive) | Valor: substituição correta
_CORRECTIONS: list[tuple[str, str]] = [
    # Nome da professora — variações fonéticas comuns
    (r"\bshit\s*on\b",       "Tatiana"),
    (r"\bsh[ei]t[\s-]?on\b", "Tatiana"),
    (r"\bta[ck]i[aeo]n[ae]\b","Tatiana"),
    (r"\btatyana\b",          "Tatiana"),
    (r"\btatianna\b",         "Tatiana"),
    (r"\btachiana\b",         "Tatiana"),
    (r"\btati\s*anna\b",      "Tatiana"),

    # Termos pedagógicos frequentemente mal transcritos
    (r"\bwork\s*sheet\b",     "worksheet"),
    (r"\bpast\s*simple\b",    "past simple"),
    (r"\bpresent\s*perfect\b","present perfect"),
    (r"\bmodal\s*verbs?\b",   "modal verbs"),
    (r"\bgramm?[ae]r\b",      "grammar"),
    (r"\bvocabul[ae]ry\b",    "vocabulary"),
    (r"\bpronunci[ae]tion\b",  "pronunciation"),
    (r"\bconditional\b",       "conditional"),
    (r"\bsubjunctive\b",       "subjunctive"),

    # Ruídos comuns do Whisper em silêncio/ruído
    (r"\[BLANK_AUDIO\]",      ""),
    (r"\(silence\)",          ""),
    (r"\[silence\]",          ""),
    (r"\[ ?[Ss]ilence ?\]",   ""),
    (r"\[MUSIC\]",            ""),
    (r"\(music\)",            ""),
    (r"\[ ?[Mm]usic ?\]",     ""),
    (r"\(Music\)",            ""),
    (r"\(Silence\)",          ""),
    (r"Subtitles by.*$",      ""),   # artefato comum
    (r"Transcribed by.*$",    ""),
]


def _apply_corrections(text: str) -> str:
    """Aplica o dicionário de correções fonéticas ao texto transcrito."""
    for pattern, replacement in _CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE).strip()
    # Remove espaços múltiplos
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _detect_and_transcribe(model, tmp_path: str, hint_lang: str) -> tuple[str, str]:
    """
    Estratégia de detecção bilíngue em dois estágios:

    1. Detecta o idioma automaticamente (sem forçar).
    2. Se o idioma detectado for pt ou en, usa esse idioma para a transcrição final.
    3. Se for outro idioma (possível confusão do modelo), usa hint_lang.

    Retorna (texto_transcrito, idioma_detectado).
    """
    ALLOWED = {"pt", "en"}

    # Parâmetros comuns de qualidade
    common_params = dict(
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
        vad_parameters={
            "min_silence_duration_ms": 400,
            "speech_pad_ms": 200,
            "threshold": 0.40,
        },
    )

    # Estágio 1: detecção automática (language=None)
    try:
        segs, info = model.transcribe(tmp_path, language=None, **common_params)
        detected = getattr(info, "language", None) or hint_lang
        text_auto = " ".join(seg.text.strip() for seg in segs).strip()
    except Exception:
        detected = hint_lang
        text_auto = ""

    # Usa o idioma detectado se for pt ou en; caso contrário cai no hint
    final_lang = detected if detected in ALLOWED else hint_lang

    # Estágio 2: transcrição forçada no idioma final (melhora precisão)
    try:
        segs, _ = model.transcribe(tmp_path, language=final_lang, **common_params)
        text_forced = " ".join(seg.text.strip() for seg in segs).strip()
    except Exception:
        text_forced = text_auto

    # Escolhe o resultado mais longo (geralmente mais completo)
    text = text_forced if len(text_forced) >= len(text_auto) else text_auto

    return text, final_lang


def transcribe_bytes(
    audio_bytes: bytes,
    suffix: str = ".wav",
    language: str = "auto",   # "auto" | "en" | "pt" | etc.
) -> str:
    """
    Transcreve bytes de áudio e retorna o texto.

    Args:
        audio_bytes: conteúdo do arquivo de áudio
        suffix:      extensão do arquivo (.wav, .mp3, .webm, .ogg…)
        language:    "auto" (recomendado para bilíngue) | "en" | "pt" | outro código

    Returns:
        Texto transcrito (com correções aplicadas) ou mensagem de erro.

    Comportamento bilíngue:
        - "auto": detecta automaticamente se o aluno falou em pt ou en.
          Funciona bem para a maioria dos casos no app Teacher Tati.
        - "en" / "pt": força o idioma (use quando tiver certeza).
    """
    tmp_path = None
    try:
        model = get_model()

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Normaliza o hint de idioma
        hint = "en" if language == "auto" else language

        if language == "auto":
            text, detected_lang = _detect_and_transcribe(model, tmp_path, hint)
        else:
            # Transcrição direta no idioma especificado
            segs, _ = model.transcribe(
                tmp_path,
                language=language,
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
                vad_parameters={
                    "min_silence_duration_ms": 400,
                    "speech_pad_ms": 200,
                    "threshold": 0.40,
                },
            )
            text = " ".join(seg.text.strip() for seg in segs).strip()
            detected_lang = language

        # Aplica correções fonéticas
        text = _apply_corrections(text)

        if not text:
            return "⚠️ Não consegui entender o áudio. Tente novamente."

        return text

    except Exception as e:
        return f"❌ Erro na transcrição: {str(e)}"

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass