import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_router(claude_keys=None, gemini_keys=None):
    """Recria o módulo com chaves injetadas via env."""
    env = {}
    for i, k in enumerate(claude_keys or []):
        env["ANTHROPIC_API_KEY" if i == 0 else f"ANTHROPIC_API_KEY_{i+1}"] = k
    for i, k in enumerate(gemini_keys or []):
        env["GEMINI_API_KEY" if i == 0 else f"GEMINI_API_KEY_{i+1}"] = k
    with patch.dict(os.environ, env, clear=False):
        import importlib
        import core.ai_router as m
        importlib.reload(m)
        return m


# ── Testes: carregamento de chaves ────────────────────────────────────────────

def test_load_single_claude_key():
    m = _make_router(claude_keys=["sk-ant-abc"])
    assert len(m._claude_pool) == 1


def test_load_multiple_claude_keys():
    m = _make_router(claude_keys=["sk-ant-1", "sk-ant-2", "sk-ant-3"])
    assert len(m._claude_pool) == 3


def test_load_gemini_key():
    m = _make_router(gemini_keys=["AI-gemini-1"])
    assert len(m._gemini_pool) == 1


def test_empty_keys_pool_is_zero():
    with patch.dict(os.environ, {}, clear=True):
        import importlib
        import core.ai_router as m
        importlib.reload(m)
        assert len(m._claude_pool) == 0


# ── Testes: rotação de chaves ─────────────────────────────────────────────────

def test_pool_round_robin():
    m = _make_router(claude_keys=["key-a", "key-b", "key-c"])
    pool = m._claude_pool
    assert pool.current() == "key-a"
    pool.advance()
    assert pool.current() == "key-b"
    pool.advance()
    assert pool.current() == "key-c"
    pool.advance()
    assert pool.current() == "key-a"  # wraps


def test_pool_advance_returns_next():
    m = _make_router(claude_keys=["key-1", "key-2"])
    pool = m._claude_pool
    nxt  = pool.advance()
    assert nxt == "key-2"


# ── Testes: strip de emojis ───────────────────────────────────────────────────

def test_strip_emojis_removes_common():
    from core.ai_router import _strip_emojis
    assert _strip_emojis("Hello 😀 World") == "Hello  World"
    assert _strip_emojis("No emojis here") == "No emojis here"
    assert _strip_emojis("✅ Done") == " Done"


def test_strip_emojis_empty_string():
    from core.ai_router import _strip_emojis
    assert _strip_emojis("") == ""


# ── Testes: diagnose ──────────────────────────────────────────────────────────

def test_diagnose_returns_dict():
    from core.ai_router import diagnose
    d = diagnose()
    assert "provider" in d
    assert "claude_keys" in d
    assert "gemini_keys" in d
    assert isinstance(d["claude_keys"], int)
    assert isinstance(d["gemini_keys"], int)


# ── Testes: chat_completion com mock ─────────────────────────────────────────

def test_chat_completion_claude_mock():
    """Testa que chat_completion chama _call_claude e retorna texto."""
    with patch("core.ai_router._call_claude", return_value="Hello from Claude") as mock_claude:
        from core.ai_router import chat_completion
        result = chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            system="You are a teacher.",
            provider="claude",
        )
    assert result == "Hello from Claude"
    mock_claude.assert_called_once()


def test_chat_completion_gemini_mock():
    """Testa que chat_completion chama _call_gemini quando provider=gemini."""
    with patch("core.ai_router._call_gemini", return_value="Hello from Gemini") as mock_gemini:
        from core.ai_router import chat_completion
        result = chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            system="You are a teacher.",
            provider="gemini",
        )
    assert result == "Hello from Gemini"
    mock_gemini.assert_called_once()


def test_chat_completion_auto_falls_to_gemini():
    """No modo auto, se Claude falhar, deve tentar Gemini."""
    with patch("core.ai_router._call_claude", side_effect=Exception("rate limit")):
        with patch("core.ai_router._call_gemini", return_value="Gemini fallback") as mock_g:
            from core.ai_router import chat_completion
            result = chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                system="Teacher.",
                provider="auto",
            )
    assert result == "Gemini fallback"
    mock_g.assert_called_once()


def test_chat_completion_strips_emojis_by_default():
    with patch("core.ai_router._call_claude", return_value="Great job! ✅"):
        from core.ai_router import chat_completion
        result = chat_completion(
            messages=[{"role": "user", "content": "test"}],
            system=".",
            provider="claude",
            strip_emojis=True,
        )
    assert "✅" not in result


def test_chat_completion_keeps_emojis_when_disabled():
    with patch("core.ai_router._call_claude", return_value="Great job! ✅"):
        from core.ai_router import chat_completion
        result = chat_completion(
            messages=[{"role": "user", "content": "test"}],
            system=".",
            provider="claude",
            strip_emojis=False,
        )
    assert "✅" in result
