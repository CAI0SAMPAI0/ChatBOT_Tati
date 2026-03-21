"""
tests/test_auth_helper.py — Testes do AuthHelper (HMAC sign/verify).
"""

import pytest
from unittest.mock import patch, MagicMock


def _make_auth():
    """Cria AuthHelper com segredo fixo, sem depender de st.secrets."""
    with patch("streamlit.components.v1.html"):
        with patch("guards.auth_helper._get_secret", return_value=b"segredo_fixo_32bytes_para_teste_"):
            from guards.auth_helper import AuthHelper
            auth = AuthHelper.__new__(AuthHelper)
            auth.secret = b"segredo_fixo_32bytes_para_teste_"
            return auth


def test_sign_verify_roundtrip():
    auth   = _make_auth()
    token  = "token_valido_qualquer"
    signed = auth._sign(token)
    assert auth._verify(signed) == token


def test_verify_rejeita_adulterado():
    auth    = _make_auth()
    signed  = auth._sign("token_original")
    adulterado = signed[:-4] + "XXXX"
    assert auth._verify(adulterado) is None


def test_verify_rejeita_invalido():
    auth = _make_auth()
    assert auth._verify("nao_e_base64_valido!!!") is None
    assert auth._verify("") is None


def test_tokens_diferentes_produzem_assinaturas_diferentes():
    auth = _make_auth()
    s1 = auth._sign("token_a")
    s2 = auth._sign("token_b")
    assert s1 != s2


def test_mesmo_token_mesma_assinatura():
    auth = _make_auth()
    s1 = auth._sign("token_fixo")
    s2 = auth._sign("token_fixo")
    assert s1 == s2  # HMAC é determinístico
