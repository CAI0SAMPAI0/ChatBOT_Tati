"""
Módulo de transcrição de áudio usando faster-whisper (100% local, gratuito).
O modelo é baixado automaticamente na primeira execução (~150MB para 'base').
"""

import tempfile
import os
from pathlib import Path

_model = None  # cache do modelo em memória

def get_model(model_size: str = "base"):
    """Carrega o modelo uma única vez e reutiliza."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


def transcribe_bytes(audio_bytes: bytes, suffix: str = ".wav", language: str = "en") -> str:
    """
    Transcreve bytes de áudio e retorna o texto.

    Args:
        audio_bytes: conteúdo do arquivo de áudio
        suffix:      extensão do arquivo (.wav, .mp3, .webm, .ogg…)
        language:    código do idioma ('en' para inglês, 'pt' para português)

    Returns:
        Texto transcrito ou mensagem de erro.
    """
    try:
        model = get_model()

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, _info = model.transcribe(
            tmp_path,
            language=language,
            # ── Precisão ──────────────────────────────────────────────────────
            beam_size=10,               # mais candidatos = mais preciso
            best_of=5,                  # considera 5 amostras
            temperature=0.0,            # determinístico, sem "criatividade"
            # ── Contexto ─────────────────────────────────────────────────────
            condition_on_previous_text=False,  # evita "completar" texto inventado
            without_timestamps=True,
            word_timestamps=False,
            # ── VAD ───────────────────────────────────────────────────────────
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 400,
                "speech_pad_ms": 200,   # mantém margem ao redor da fala
                "threshold": 0.40,      # menos agressivo no corte de silêncio
            },
            # ── Filtros de qualidade ──────────────────────────────────────────
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,    # aceita trechos de baixa confiança
            no_speech_threshold=0.50,
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()

        # Remove artefatos comuns do Whisper quando detecta silêncio/ruído
        for noise in [
            "[BLANK_AUDIO]", "(silence)", "[silence]", "[ Silence ]",
            "[ silence ]", "[MUSIC]", "(music)", "[Music]", "[ Music ]",
            "(Music)", "(Silence)",
        ]:
            text = text.replace(noise, "").strip()

        return text if text else "⚠️ Não consegui entender o áudio. Tente novamente."

    except Exception as e:
        return f"❌ Erro na transcrição: {str(e)}"

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass