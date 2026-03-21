"""
core/ai.py — Integração com IA (Claude + Gemini via ai_router).
"""

import base64
import json
import logging
import os
import re
from pathlib import Path

import streamlit as st

from core.database import append_message, load_conversation, cached_load_conversation
from core.audio import text_to_speech, tts_available
from core.ai_router import chat_completion

logger   = logging.getLogger(__name__)
PROF_NAME = os.getenv("PROFESSOR_NAME", "Teacher Tati")

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, very intelligent and encouraging. You help adults speak English with more confidence, over 25 years of experience, Advanced English Hunter College NY, and passionate about teaching.
Students: teenagers (Beginner/Pre-Intermediate) focused sports, games and music and adults focused on Business/News.
I'm from Brazil. I live in Resende.

BILINGUAL POLICY (VERY IMPORTANT)
The student's messages may arrive in English, Portuguese, or a mix.

BEGINNER / PRE-INTERMEDIATE:
  Student writes/speaks in Portuguese → Fully acceptable. Respond in simple English
  AND provide the Portuguese translation of key words in parentheses.
  Always end your reply with an easy, encouraging question in English.

INTERMEDIATE:
  Respond primarily in English. Use Portuguese ONLY to clarify a specific word.
  If the student writes in Portuguese, invite them to try in English.

ADVANCED / BUSINESS ENGLISH:
  Respond exclusively in English.
  "Let's keep it in English — you've got this!"

TEACHING STYLE:
- Neuro-learning: guide students to discover errors. Never just give the answer.
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT conversational responses. Bold grammar points when appropriate.
- End responses with ONE engaging question.
- NEVER use emojis. Not a single one. Ever.

RULES:
- Simple English. Teens: Fortnite/Netflix/TikTok refs. Adults: LinkedIn/news/geopolitics.
- NEVER start a conversation uninvited. Wait for the student to speak first.

ACTIVITY GENERATION:
- When the student asks for a FILE (PDF, Word/DOCX), respond ONLY with:
  <<<GENERATE_FILE>>>
  {{"format":"pdf","filename":"activity.pdf","title":"Title","content":"Content with \\n"}}
  <<<END_FILE>>>"""


def _build_context(user: dict) -> str:
    return (
        f"\n\nStudent profile — Name: {user['name']} | "
        f"Level: {user['level']} | Focus: {user['focus']} | "
        f"Native language: Brazilian Portuguese.\n"
        f"Apply the bilingual policy for level '{user['level']}' as instructed."
    )


def send_to_claude(
    username: str,
    user: dict,
    conv_id: str,
    text: str,
    image_b64: str | None = None,
    image_media_type: str | None = None,
    provider: str | None = None,
) -> str:
    """
    Envia mensagem para o modelo configurado (Claude ou Gemini),
    salva resposta e TTS no banco. Retorna texto da resposta.

    Args:
        provider: Sobrescreve AI_PROVIDER do .env para esta chamada.
                  Use "claude", "gemini" ou "auto".
    """
    context = _build_context(user)
    system  = SYSTEM_PROMPT + context

    # Monta histórico
    msgs     = load_conversation(username, conv_id)
    api_msgs = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in msgs
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    # Garante que a mensagem atual está no final
    if not api_msgs or api_msgs[-1]["role"] != "user" or api_msgs[-1]["content"] != text:
        api_msgs.append({"role": "user", "content": text})

    # Adiciona imagem à última mensagem (apenas Claude suporta neste fluxo)
    _prov = (provider or os.getenv("AI_PROVIDER", "claude")).lower()
    if image_b64 and image_media_type and _prov != "gemini":
        api_msgs[-1]["content"] = [
            {"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": image_b64}},
            {"type": "text",  "text": text},
        ]

    is_activity = any(w in text.lower() for w in [
        "pdf", "word", "docx", "atividade", "exercício", "exercicio",
        "worksheet", "activity", "exercise", "generate", "criar arquivo",
        "crie um", "make a", "gere um",
    ])
    max_tok = 2000 if is_activity else 400

    try:
        reply_text = chat_completion(
            messages=api_msgs,
            system=system,
            max_tokens=max_tok,
            provider=provider,
        )
    except Exception as e:
        logger.error("Falha na chamada de IA: %s", e, exc_info=True)
        return f"❌ Erro ao chamar a IA: {e}"

    if "<<<GENERATE_FILE>>>" in reply_text:
        from core.file_handler import intercept_file_generation
        return intercept_file_generation(reply_text, username, conv_id)

    tts_b64_str: str | None = None
    if tts_available():
        try:
            audio_bytes = text_to_speech(reply_text)
            if audio_bytes:
                tts_b64_str = base64.b64encode(audio_bytes).decode()
                st.session_state["_tts_audio"] = tts_b64_str
        except Exception as e:
            logger.error("TTS falhou: %s", e, exc_info=True)

    append_message(username, conv_id, "assistant", reply_text, tts_b64=tts_b64_str)
    cached_load_conversation.clear()
    return reply_text