"""
core/auth.py — Autenticação segura com rate limiting por username.
"""

import time
from collections import defaultdict

import streamlit as st

# Controle de tentativas em memória (por processo)
# Em produção com múltiplas instâncias, usar Redis ou tabela no banco.
_attempts: dict[str, list[float]] = defaultdict(list)

MAX_ATTEMPTS = 5
WINDOW_SECS  = 300  # 5 minutos


def is_rate_limited(username: str) -> bool:
    """Verifica se o username está bloqueado por excesso de tentativas."""
    now  = time.time()
    hist = _attempts[username]
    # Remove tentativas fora da janela
    hist[:] = [t for t in hist if now - t < WINDOW_SECS]
    return len(hist) >= MAX_ATTEMPTS


def register_attempt(username: str):
    """Registra uma tentativa de login falha."""
    _attempts[username].append(time.time())


def clear_attempts(username: str):
    """Limpa tentativas após login bem-sucedido."""
    _attempts.pop(username, None)


def remaining_attempts(username: str) -> int:
    """Quantas tentativas restam antes do bloqueio."""
    now  = time.time()
    hist = _attempts.get(username, [])
    hist = [t for t in hist if now - t < WINDOW_SECS]
    return max(0, MAX_ATTEMPTS - len(hist))


def seconds_until_unlock(username: str) -> int:
    """Segundos até o desbloqueio (0 se não bloqueado)."""
    if not is_rate_limited(username):
        return 0
    now  = time.time()
    hist = _attempts.get(username, [])
    hist = [t for t in hist if now - t < WINDOW_SECS]
    if not hist:
        return 0
    oldest = min(hist)
    return max(0, int(WINDOW_SECS - (now - oldest)))
