"""
tests/test_database.py — Testes de hash e verificação de senha.
"""

import pytest
from core.database import hash_password, check_password, _migrate_password_to_bcrypt
import hashlib


# ── Hash ──────────────────────────────────────────────────────────────────────

def test_hash_retorna_bcrypt():
    h = hash_password("minhasenha")
    assert h.startswith("$2b$")

def test_hash_rounds_12():
    h = hash_password("minhasenha")
    assert h.startswith("$2b$12$")

def test_hash_diferente_a_cada_chamada():
    h1 = hash_password("mesmasenha")
    h2 = hash_password("mesmasenha")
    assert h1 != h2


# ── Verificação ───────────────────────────────────────────────────────────────

def test_check_bcrypt_correto():
    h = hash_password("senha_certa")
    assert check_password("senha_certa", h) is True

def test_check_bcrypt_errado():
    h = hash_password("senha_certa")
    assert check_password("senha_errada", h) is False

def test_check_sha256_legado_correto():
    plain  = "senha_antiga"
    stored = hashlib.sha256(plain.encode()).hexdigest()
    assert check_password(plain, stored) is True

def test_check_sha256_legado_errado():
    stored = hashlib.sha256("senha_certa".encode()).hexdigest()
    assert check_password("senha_errada", stored) is False

def test_check_string_vazia():
    h = hash_password("qualquer")
    assert check_password("", h) is False
    assert check_password("qualquer", "") is False

def test_check_hash_invalido():
    assert check_password("senha", "isso_nao_e_hash") is False


# ── Detecção de migração ──────────────────────────────────────────────────────

def test_sha256_precisa_migracao():
    stored = hashlib.sha256("qualquer".encode()).hexdigest()
    assert not stored.startswith("$2")

def test_bcrypt_nao_precisa_migracao():
    stored = hash_password("qualquer")
    assert stored.startswith("$2")
