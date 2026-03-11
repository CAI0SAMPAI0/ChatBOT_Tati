"""
core/ai.py — Integração com Claude (Anthropic).
Inclui: system prompt, chamada à API, geração de TTS, detecção de arquivo.
"""

import base64
import json
import os
import re
from pathlib import Path

import anthropic
import streamlit as st

from core.database import append_message, load_conversation, cached_load_conversation
from core.audio import text_to_speech, tts_available

PROF_NAME = os.getenv("PROFESSOR_NAME", "Teacher Tati")
API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
MODEL     = "claude-haiku-4-5"

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a digital avatar of an English teacher called {PROF_NAME} — warm, witty, very intelligent and encouraging. You help adults speak English with more confidence, over 25 years of experience, Advanced English Hunter College NY, and passionate about teaching.
Students: teenagers (Beginner/Pre-Intermediate) and adults focused on Business/News.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BILINGUAL POLICY (VERY IMPORTANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The student's messages may arrive in English, Portuguese, or a mix.
Adapt your language policy according to the student's level:

BEGINNER / PRE-INTERMEDIATE:
  • Student writes/speaks in Portuguese → Fully acceptable. Respond in simple English
    AND provide the Portuguese translation of key words in parentheses.
  • Student mixes PT and EN → Celebrate the English parts, gently supply the missing
    English for the Portuguese parts. Never make them feel bad for using Portuguese.
  • Always end your reply with an easy, encouraging question in English.
  • Provide Portuguese support freely when they seem lost or frustrated.

INTERMEDIATE:
  • Respond primarily in English. Use Portuguese ONLY to clarify a specific word
    or resolve a genuine comprehension block — keep it brief.
  • If the student writes in Portuguese, acknowledge briefly in English and invite
    them to try saying the same thing in English.
  • Encourage them to push further; celebrate every English sentence they produce.

ADVANCED / BUSINESS ENGLISH:
  • Respond exclusively in English.
  • If the student writes in Portuguese, reply in English and say something like:
    "Let's keep it in English — you've got this!"
  • You may add a brief Portuguese gloss ONLY for highly technical or idiomatic
    terms where the meaning is genuinely ambiguous.

TRANSLATION REQUESTS (any level):
  • When the student asks "como se diz X?", "what does Y mean?", or similar,
    always provide the translation + an example sentence in English.
  • For Beginners/Pre-Intermediate: also include the Portuguese example.

TEACHING STYLE:
- Neuro-learning: guide students to discover errors. Never just give the answer.
  Example: "he go" → "What ending do we add for he/she/it?"
- Sandwich: 1) Validate 2) Guide with question 3) Encourage.
- SHORT conversational responses. Bold grammar points when appropriate.
- End responses with ONE engaging question.
- NEVER use emojis in your responses. No exceptions. Plain text only, always.

RULES:
- Simple English. Teens→Fortnite/Netflix/TikTok/Movies and series refs. Adults→LinkedIn/news/geopolitics.
- Portuguese → briefly acknowledge, when asked to speak Portuguese, speak, but switch to English.
- NEVER start a conversation uninvited. Wait for the student to speak first.
- NEVER use emojis. Not a single one. Ever.

ACTIVITY GENERATION:
- When asked to create exercises, worksheets or activities, generate complete, well-structured content.
- Support: fill-in-the-blank, multiple choice, reading comprehension, dialogue writing,
  grammar drills, vocabulary lists, translation, error correction, etc.
- When the student asks for a FILE (PDF, Word/DOCX), respond ONLY with a special JSON block
  on its own line, no other text, in this exact format:
  <<<GENERATE_FILE>>>
  {{"format":"pdf","filename":"activity.pdf","title":"Exercise Title","content":"Full content here with \\n for line breaks"}}
  <<<END_FILE>>>
  Use "pdf" or "docx" as format. Put ALL the exercise content inside "content".
  The system will intercept this and generate the real file for download."""


_EMOJI_RE = re.compile(
    r'[\U00010000-\U0010ffff'
    r'\U0001F300-\U0001F9FF'
    r'\u2600-\u26FF\u2700-\u27BF'
    r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
    r'\u200d\ufe0f]'
)


def _strip_emojis(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


def _build_context(user: dict) -> str:
    return (
        f"\n\nStudent profile — Name: {user['name']} | "
        f"Level: {user['level']} | Focus: {user['focus']} | "
        f"Native language: Brazilian Portuguese.\n"
        f"Apply the bilingual policy for level '{user['level']}' as instructed."
    )


def send_to_claude(
    username: str, user: dict, conv_id: str,
    text: str, image_b64: str = None, image_media_type: str = None,
) -> str:
    """Envia mensagem ao Claude, salva resposta e TTS no banco. Retorna texto."""
    if not API_KEY:
        return "❌ ANTHROPIC_API_KEY não configurada."

    client  = anthropic.Anthropic(api_key=API_KEY)
    context = _build_context(user)

    # Monta histórico
    msgs     = load_conversation(username, conv_id)
    api_msgs = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in msgs
    ]
    if not api_msgs or api_msgs[-1]["role"] != "user" or api_msgs[-1]["content"] != text:
        api_msgs.append({"role": "user", "content": text})

    # Adiciona imagem se houver
    if image_b64 and image_media_type and api_msgs and api_msgs[-1]["role"] == "user":
        api_msgs[-1]["content"] = [
            {"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": image_b64}},
            {"type": "text",  "text": text},
        ]

    is_activity = any(w in text.lower() for w in [
        "pdf", "word", "docx", "atividade", "exercício", "exercicio",
        "worksheet", "activity", "exercise", "generate", "criar arquivo", "crie um", "make a", "gere um",
    ])
    max_tok = 2000 if is_activity else 400

    resp       = client.messages.create(
        model=MODEL, max_tokens=max_tok,
        system=SYSTEM_PROMPT + context, messages=api_msgs,
    )
    reply_text = _strip_emojis(resp.content[0].text)

    if "<<<GENERATE_FILE>>>" in reply_text:
        from core.file_handler import intercept_file_generation
        return intercept_file_generation(reply_text, username, conv_id)

    tts_b64_str = None
    if tts_available():
        audio_bytes = text_to_speech(reply_text)
        if audio_bytes:
            tts_b64_str = base64.b64encode(audio_bytes).decode()
            st.session_state["_tts_audio"] = tts_b64_str

    append_message(username, conv_id, "assistant", reply_text, tts_b64=tts_b64_str)
    cached_load_conversation.clear()
    return reply_text
