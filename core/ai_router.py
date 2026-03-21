"""
core/ai_router.py — Roteador de IA com rotação de chaves.

Suporta múltiplas chaves de Claude e Gemini.
Formato no .env:

    ANTHROPIC_API_KEY=sk-ant-...
    ANTHROPIC_API_KEY_2=sk-ant-...
    ANTHROPIC_API_KEY_3=sk-ant-...

    GEMINI_API_KEY=AI...
    GEMINI_API_KEY_2=AI...
    GEMINI_API_KEY_3=AI...

    AI_PROVIDER=claude          # "claude" | "gemini" | "auto"
    AI_MODEL_CLAUDE=claude-haiku-4-5
    AI_MODEL_GEMINI=gemini-2.0-flash

Rotação: round-robin por chave. Se uma chave falhar com 429 (rate limit),
tenta automaticamente a próxima. Se todas falharem, levanta a última exceção.
"""

import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

_EMOJI_RE = re.compile(
    r"[\U00010000-\U0010ffff"
    r"\U0001F300-\U0001F9FF"
    r"\u2600-\u26FF\u2700-\u27BF"
    r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
    r"\u200d\ufe0f]"
)


def _strip_emojis(text: str) -> str:
    return _EMOJI_RE.sub("", text)


# ── Carregamento de chaves ────────────────────────────────────────────────────

def _load_keys(prefix: str) -> list[str]:
    """
    Carrega todas as chaves com o prefixo dado.
    Ex: ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_2, ANTHROPIC_API_KEY_3 ...
    Retorna lista de chaves válidas (não vazias).
    """
    keys: list[str] = []
    # Chave principal (sem sufixo numérico)
    main = os.getenv(prefix, "").strip()
    if main:
        keys.append(main)
    # Chaves numeradas: _2, _3, _4 ...
    for i in range(2, 10):
        k = os.getenv(f"{prefix}_{i}", "").strip()
        if k:
            keys.append(k)
        else:
            break  # para no primeiro gap
    return keys


# ── Estado de rotação (em memória por processo) ───────────────────────────────

class _KeyPool:
    """Round-robin sobre uma lista de chaves API."""

    def __init__(self, keys: list[str]):
        self._keys = keys
        self._idx  = 0

    def __len__(self) -> int:
        return len(self._keys)

    def current(self) -> str | None:
        if not self._keys:
            return None
        return self._keys[self._idx % len(self._keys)]

    def advance(self) -> str | None:
        """Avança para a próxima chave e retorna ela."""
        if not self._keys:
            return None
        self._idx = (self._idx + 1) % len(self._keys)
        return self.current()

    def all(self) -> list[str]:
        return list(self._keys)


_claude_pool = _KeyPool(_load_keys("ANTHROPIC_API_KEY"))
_gemini_pool = _KeyPool(_load_keys("GEMINI_API_KEY"))


def reload_keys() -> None:
    """Recarrega chaves do ambiente (útil em testes ou após hot-reload)."""
    global _claude_pool, _gemini_pool
    _claude_pool = _KeyPool(_load_keys("ANTHROPIC_API_KEY"))
    _gemini_pool = _KeyPool(_load_keys("GEMINI_API_KEY"))


# ── Provider padrão ───────────────────────────────────────────────────────────

def _default_provider() -> str:
    return os.getenv("AI_PROVIDER", "claude").lower()


def _claude_model() -> str:
    return os.getenv("AI_MODEL_CLAUDE", DEFAULT_CLAUDE_MODEL)


def _gemini_model() -> str:
    return os.getenv("AI_MODEL_GEMINI", DEFAULT_GEMINI_MODEL)


# ── Chamada ao Claude com rotação de chaves ───────────────────────────────────

def _call_claude(
    messages: list[dict],
    system: str,
    max_tokens: int = 400,
) -> str:
    import anthropic

    if not _claude_pool:
        raise RuntimeError("Nenhuma ANTHROPIC_API_KEY configurada.")

    last_exc: Exception | None = None
    # Tenta cada chave uma vez, em ordem round-robin
    for _ in range(len(_claude_pool)):
        key = _claude_pool.current()
        try:
            client = anthropic.Anthropic(api_key=key)
            resp   = client.messages.create(
                model=_claude_model(),
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return resp.content[0].text

        except Exception as e:
            err_str = str(e).lower()
            is_rate  = "429" in err_str or "rate_limit" in err_str or "overloaded" in err_str
            is_auth  = "401" in err_str or "authentication" in err_str or "invalid" in err_str

            if is_auth:
                logger.warning("Claude: chave inválida (idx=%d), pulando.", _claude_pool._idx)
                _claude_pool.advance()
                last_exc = e
                continue

            if is_rate:
                logger.warning("Claude: rate limit (idx=%d), tentando próxima chave.", _claude_pool._idx)
                _claude_pool.advance()
                last_exc = e
                continue

            # Outro erro (rede, etc.) — não rotaciona, relança
            raise

    raise last_exc or RuntimeError("Todas as chaves Claude falharam.")


# ── Chamada ao Gemini com rotação de chaves ───────────────────────────────────

def _call_gemini(
    messages: list[dict],
    system: str,
    max_tokens: int = 400,
) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai não instalado. "
            "Execute: pip install google-generativeai"
        )

    if not _gemini_pool:
        raise RuntimeError("Nenhuma GEMINI_API_KEY configurada.")

    # Converte formato Anthropic → Gemini
    # Anthropic: [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}]
    # Gemini:    [{"role":"user","parts":[{"text":"..."}]}, {"role":"model","parts":[...]}]
    def _to_gemini_role(r: str) -> str:
        return "model" if r == "assistant" else "user"

    gemini_history = [
        {
            "role":  _to_gemini_role(m["role"]),
            "parts": [{"text": m["content"]}],
        }
        for m in messages[:-1]  # histórico sem a última mensagem
    ]
    last_msg = messages[-1]["content"] if messages else ""

    last_exc: Exception | None = None
    for _ in range(len(_gemini_pool)):
        key = _gemini_pool.current()
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=_gemini_model(),
                system_instruction=system,
            )
            chat  = model.start_chat(history=gemini_history)
            resp  = chat.send_message(
                last_msg,
                generation_config={"max_output_tokens": max_tokens},
            )
            return resp.text

        except Exception as e:
            err_str = str(e).lower()
            is_rate = "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str
            is_auth = "401" in err_str or "403" in err_str or "api_key" in err_str

            if is_auth or is_rate:
                logger.warning("Gemini: falha (idx=%d): %s", _gemini_pool._idx, e)
                _gemini_pool.advance()
                last_exc = e
                continue

            raise

    raise last_exc or RuntimeError("Todas as chaves Gemini falharam.")


# ── Ponto de entrada público ──────────────────────────────────────────────────

def chat_completion(
    messages: list[dict],
    system: str,
    max_tokens: int = 400,
    provider: str | None = None,
    strip_emojis: bool = True,
) -> str:
    """
    Envia mensagens para o provider configurado e retorna o texto da resposta.

    Args:
        messages:     Lista de dicts {"role": "user"|"assistant", "content": str}
        system:       System prompt
        max_tokens:   Limite de tokens na resposta
        provider:     "claude" | "gemini" | None (usa AI_PROVIDER do .env)
        strip_emojis: Remove emojis da resposta (padrão: True)

    Returns:
        Texto da resposta do modelo.

    Raises:
        RuntimeError: Se nenhuma chave estiver configurada ou todas falharem.
    """
    prov = (provider or _default_provider()).lower()

    if prov == "auto":
        # "auto": tenta Claude primeiro, cai para Gemini se falhar
        try:
            text = _call_claude(messages, system, max_tokens)
        except Exception as e:
            logger.warning("Claude falhou no modo auto, tentando Gemini: %s", e)
            text = _call_gemini(messages, system, max_tokens)
    elif prov == "gemini":
        text = _call_gemini(messages, system, max_tokens)
    else:
        text = _call_claude(messages, system, max_tokens)

    return _strip_emojis(text) if strip_emojis else text


# ── Diagnóstico ───────────────────────────────────────────────────────────────

def diagnose() -> dict:
    """Retorna informações sobre chaves configuradas (sem expor os valores)."""
    return {
        "provider":      _default_provider(),
        "claude_model":  _claude_model(),
        "gemini_model":  _gemini_model(),
        "claude_keys":   len(_claude_pool),
        "gemini_keys":   len(_gemini_pool),
        "claude_active": _claude_pool._idx if _claude_pool else None,
        "gemini_active": _gemini_pool._idx if _gemini_pool else None,
    }
