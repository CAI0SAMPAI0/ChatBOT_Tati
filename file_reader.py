"""
Módulo para extração de conteúdo de diferentes tipos de arquivo.
Suporta: PDF, DOCX/DOC, TXT, imagens e áudio.
"""

import base64
from pathlib import Path


AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".flac"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_EXTS  = {".txt"}


def extract_file(raw: bytes, filename: str) -> dict:
    """
    Detecta o tipo do arquivo e extrai seu conteúdo.

    Retorna um dict com:
      - kind: "audio" | "text" | "image" | "unknown"
      - label: descrição amigável do tipo
      - text: conteúdo extraído (para text/pdf/docx)
      - b64: imagem em base64 (para image)
      - media_type: mime type (para image)
    """
    suffix = Path(filename).suffix.lower()

    # ── Áudio ────────────────────────────────────────────────────────────────
    if suffix in AUDIO_EXTS:
        return {"kind": "audio", "label": "Áudio"}

    # ── Imagem ───────────────────────────────────────────────────────────────
    if suffix in IMAGE_EXTS:
        mime_map = {".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg", ".webp": "image/webp"}
        return {
            "kind": "image",
            "label": "Imagem",
            "b64": base64.b64encode(raw).decode(),
            "media_type": mime_map.get(suffix, "image/jpeg"),
        }

    # ── PDF ──────────────────────────────────────────────────────────────────
    if suffix == ".pdf":
        return {"kind": "text", "label": "PDF", "text": _extract_pdf(raw)}

    # ── DOCX / DOC ───────────────────────────────────────────────────────────
    if suffix in {".docx", ".doc"}:
        return {"kind": "text", "label": "Documento Word", "text": _extract_docx(raw)}

    # ── TXT ──────────────────────────────────────────────────────────────────
    if suffix in TEXT_EXTS:
        try:
            return {"kind": "text", "label": "Texto", "text": raw.decode("utf-8", errors="replace")}
        except Exception as e:
            return {"kind": "text", "label": "Texto", "text": f"❌ Erro ao ler arquivo: {e}"}

    # ── Desconhecido ─────────────────────────────────────────────────────────
    return {"kind": "unknown", "label": suffix or "Arquivo desconhecido"}


# ── Helpers internos ──────────────────────────────────────────────────────────

def _extract_pdf(raw: bytes) -> str:
    try:
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n\n".join(text_parts).strip() or "⚠️ Nenhum texto encontrado no PDF."
    except ImportError:
        return "❌ pdfplumber não instalado. Execute: pip install pdfplumber"
    except Exception as e:
        return f"❌ Erro ao extrair PDF: {e}"


def _extract_docx(raw: bytes) -> str:
    try:
        import docx
        import io
        doc = docx.Document(io.BytesIO(raw))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs).strip() or "⚠️ Nenhum texto encontrado no documento."
    except ImportError:
        return "❌ python-docx não instalado. Execute: pip install python-docx"
    except Exception as e:
        return f"❌ Erro ao extrair DOCX: {e}"