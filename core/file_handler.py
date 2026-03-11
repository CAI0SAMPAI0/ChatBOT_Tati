"""
core/file_handler.py — Geração de PDF/DOCX e leitura de arquivos enviados.
"""

import base64
import json
import os
import re
from pathlib import Path

import streamlit as st

from core.database import append_message, cached_load_conversation

PROF_NAME = os.getenv("PROFESSOR_NAME", "Teacher Tati")


# ══════════════════════════════════════════════════════════════════════════════
# INTERCEPTAÇÃO DE GERAÇÃO DE ARQUIVO (resposta da IA)
# ══════════════════════════════════════════════════════════════════════════════

def intercept_file_generation(reply_text: str, username: str, conv_id: str) -> str:
    """
    Detecta bloco <<<GENERATE_FILE>>> na resposta da IA e gera o arquivo real.
    """
    try:
        match = re.search(
            r'<<<GENERATE_FILE>>>\s*(\{.*?\})\s*<<<END_FILE>>>',
            reply_text, re.DOTALL,
        )
        if not match:
            append_message(username, conv_id, "assistant", reply_text)
            return reply_text

        meta     = json.loads(match.group(1))
        fmt      = meta.get("format", "pdf").lower()
        title    = meta.get("title", "Activity")
        content  = meta.get("content", "")
        filename = meta.get("filename", f"activity.{fmt}")
        if not filename.endswith(f".{fmt}"):
            filename = f"{filename}.{fmt}"

        out_dir  = Path("data/generated")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        if fmt == "pdf":
            generate_pdf(title, content, out_path)
        else:
            generate_docx(title, content, out_path)

        with open(out_path, "rb") as f:
            file_bytes = f.read()

        st.session_state["_pending_download"] = {
            "b64":      base64.b64encode(file_bytes).decode(),
            "filename": filename,
            "mime":     "application/pdf" if fmt == "pdf" else
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        display_msg = (
            f"Arquivo gerado: {filename}\n\n_{title}_\n\n"
            "Clique em Baixar arquivo abaixo para salvar."
        )
        append_message(username, conv_id, "assistant", display_msg, is_file=True)
        cached_load_conversation.clear()
        return display_msg

    except Exception as e:
        err = f"Desculpe, não consegui gerar o arquivo: {e}"
        append_message(username, conv_id, "assistant", err)
        cached_load_conversation.clear()
        return err


# ══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_pdf(title: str, content: str, out_path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units    import cm
    from reportlab.lib          import colors
    from reportlab.platypus     import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums    import TA_CENTER

    doc    = SimpleDocTemplate(str(out_path), pagesize=A4,
                               leftMargin=2.5*cm, rightMargin=2.5*cm,
                               topMargin=2.5*cm, bottomMargin=2.5*cm)
    styles = getSampleStyleSheet()
    story  = []

    t_style = ParagraphStyle("t", parent=styles["Title"],  fontSize=18, spaceAfter=6,
                              textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER)
    s_style = ParagraphStyle("s", parent=styles["Normal"], fontSize=9,  spaceAfter=14,
                              textColor=colors.HexColor("#888888"),  alignment=TA_CENTER)
    b_style = ParagraphStyle("b", parent=styles["Normal"], fontSize=11, leading=18, spaceAfter=8)

    story.append(Paragraph(title, t_style))
    story.append(Paragraph(f"Teacher {PROF_NAME}", s_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#f0a500")))
    story.append(Spacer(1, 0.4*cm))

    for line in content.split("\\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), b_style))
        else:
            story.append(Spacer(1, 0.2*cm))

    doc.build(story)


# ══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE DOCX
# ══════════════════════════════════════════════════════════════════════════════

def generate_docx(title: str, content: str, out_path: Path) -> None:
    from docx           import Document
    from docx.shared    import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    for sec in doc.sections:
        sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Cm(2.5)

    h = doc.add_heading(title, 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)

    sub = doc.add_paragraph(f"Teacher {PROF_NAME}")
    sub.alignment            = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size    = Pt(9)
    sub.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    doc.add_paragraph()

    for line in content.split("\\n"):
        if line.strip():
            p = doc.add_paragraph(line.strip())
            p.style.font.size = Pt(11)
        else:
            doc.add_paragraph()

    doc.save(str(out_path))


# ══════════════════════════════════════════════════════════════════════════════
# LEITURA DE ARQUIVOS ENVIADOS PELO USUÁRIO
# ══════════════════════════════════════════════════════════════════════════════

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".flac"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_EXTS  = {".txt"}


def extract_file(raw: bytes, filename: str) -> dict:
    """
    Detecta tipo e extrai conteúdo de um arquivo enviado pelo usuário.
    Retorna dict com: kind, label, text/b64/media_type.
    """
    suffix = Path(filename).suffix.lower()

    if suffix in AUDIO_EXTS:
        return {"kind": "audio", "label": "Áudio"}

    if suffix in IMAGE_EXTS:
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        return {
            "kind": "image", "label": "Imagem",
            "b64": base64.b64encode(raw).decode(),
            "media_type": mime_map.get(suffix, "image/jpeg"),
        }

    if suffix == ".pdf":
        return {"kind": "text", "label": "PDF", "text": _extract_pdf(raw)}

    if suffix in {".docx", ".doc"}:
        return {"kind": "text", "label": "Documento Word", "text": _extract_docx(raw)}

    if suffix in TEXT_EXTS:
        try:
            return {"kind": "text", "label": "Texto", "text": raw.decode("utf-8", errors="replace")}
        except Exception as e:
            return {"kind": "text", "label": "Texto", "text": f"❌ Erro ao ler arquivo: {e}"}

    return {"kind": "unknown", "label": suffix or "Arquivo desconhecido"}


def _extract_pdf(raw: bytes) -> str:
    try:
        import pdfplumber, io
        parts = []
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return "\n\n".join(parts).strip() or "⚠️ Nenhum texto encontrado no PDF."
    except ImportError:
        return "❌ pdfplumber não instalado."
    except Exception as e:
        return f"❌ Erro ao extrair PDF: {e}"


def _extract_docx(raw: bytes) -> str:
    try:
        import docx, io
        doc = docx.Document(io.BytesIO(raw))
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paras).strip() or "⚠️ Nenhum texto encontrado no documento."
    except ImportError:
        return "❌ python-docx não instalado."
    except Exception as e:
        return f"❌ Erro ao extrair DOCX: {e}"
