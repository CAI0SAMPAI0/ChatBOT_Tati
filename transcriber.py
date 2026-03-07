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
        # device="cpu" funciona em qualquer máquina
        # compute_type="int8" é mais leve e rápido na CPU
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


def transcribe_bytes(audio_bytes: bytes, suffix: str = ".wav", language: str = "en") -> str:
    """
    Transcreve bytes de áudio e retorna o texto.
    
    Args:
        audio_bytes: conteúdo do arquivo de áudio
        suffix: extensão do arquivo (.wav, .mp3, .webm, .ogg…)
        language: código do idioma ('en' para inglês, 'pt' para português)
    
    Returns:
        Texto transcrito ou mensagem de erro.
    """
    try:
        model = get_model()

        # Salva em arquivo temporário (faster-whisper precisa de path)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, info = model.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            vad_filter=True,           # remove silêncio
            vad_parameters={"min_silence_duration_ms": 500},
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text if text else "⚠️ Não consegui entender o áudio. Tente novamente."

    except Exception as e:
        return f"❌ Erro na transcrição: {str(e)}"

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass