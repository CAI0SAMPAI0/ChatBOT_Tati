"""
guards/auth_helper.py — Autenticação via cookie HMAC-SHA256.

Diferença deste projeto vs o anterior:
  - Usa st.context.cookies (Streamlit >= 1.31) para leitura do cookie HTTP.
  - NÃO precisa de CookieController (sem componente React externo).
  - Gravação ainda é via JavaScript (única forma no Streamlit).

Segurança:
  - HMAC-SHA256 assina o token (protege contra falsificação).
  - SameSite=Strict + Secure (quando HTTPS) no cookie.
  - Falha explícita se COOKIE_SECRET não estiver configurado.
"""

import base64
import hashlib
import hmac
import json
import logging
import os

import streamlit as st
import streamlit.components.v1 as components

logger = logging.getLogger(__name__)

_THIRTY_DAYS_SECS = 60 * 60 * 24 * 30


def _get_secret() -> bytes:
    """Carrega o segredo do cookie. Falha explicitamente se não configurado."""
    # 1. Segredo dedicado (preferido)
    for key in ("COOKIE_SECRET",):
        try:
            val = st.secrets[key]
            if val:
                return val.encode()
        except Exception:
            pass
        val = os.getenv(key, "").strip()
        if val:
            return val.encode()

    # 2. Fallback: reutiliza chave do Supabase (aceitável)
    for key in ("SUPABASE_KEY",):
        try:
            val = st.secrets[key]
            if val:
                return val.encode()
        except Exception:
            pass
        val = os.getenv(key, "").strip()
        if val:
            return val.encode()

    # 3. Sem segredo → falha explícita, nunca silenciosa
    raise RuntimeError(
        "Nenhum segredo de cookie configurado. "
        "Defina COOKIE_SECRET (ou SUPABASE_KEY) no .env ou em st.secrets."
    )


class AuthHelper:
    COOKIE_NAME = "tati_voice_auth"

    def __init__(self) -> None:
        self.secret = _get_secret()

    # ── Assinatura HMAC ────────────────────────────────────────────────────────

    def _sign(self, token: str) -> str:
        sig = hmac.new(self.secret, token.encode(), hashlib.sha256).digest()
        payload = {
            "token": base64.urlsafe_b64encode(token.encode()).decode(),
            "sig":   base64.urlsafe_b64encode(sig).decode(),
        }
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    def _verify(self, signed: str) -> str | None:
        try:
            data     = json.loads(base64.urlsafe_b64decode(signed).decode())
            token    = base64.urlsafe_b64decode(data["token"]).decode()
            expected = hmac.new(self.secret, token.encode(), hashlib.sha256).digest()
            received = base64.urlsafe_b64decode(data["sig"])
            if hmac.compare_digest(expected, received):
                return token
        except Exception:
            pass
        return None

    # ── API pública ────────────────────────────────────────────────────────────

    def save(self, token: str) -> None:
        """Salva token assinado no cookie via JavaScript."""
        signed = self._sign(token)
        # SameSite=Strict bloqueia envio cross-site
        # Secure só é adicionado em HTTPS (detectado no JS)
        components.html(
            f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function(){{
    var signed = {json.dumps(signed)};
    var name   = {json.dumps(self.COOKIE_NAME)};
    var exp    = new Date(Date.now() + {_THIRTY_DAYS_SECS * 1000}).toUTCString();
    var secure = location.protocol === 'https:' ? ';Secure' : '';
    var cookie = name + '=' + encodeURIComponent(signed)
               + ';expires=' + exp
               + ';path=/'
               + ';SameSite=Strict'
               + secure;
    try {{ window.parent.document.cookie = cookie; }} catch(e) {{}}
    try {{ document.cookie = cookie; }} catch(e) {{}}
}})();
</script></body></html>""",
            height=1,
        )

    def get_token(self) -> str | None:
        """
        Lê o cookie via st.context.cookies (Streamlit >= 1.31).
        Retorna o token verificado ou None.
        """
        try:
            cookies = st.context.cookies
            raw = cookies.get(self.COOKIE_NAME)
        except AttributeError:
            # Streamlit < 1.31 ou fora de contexto HTTP
            logger.debug("st.context.cookies não disponível neste ambiente.")
            return None

        if not raw:
            return None
        return self._verify(raw)

    def is_authenticated(self) -> bool:
        return self.get_token() is not None

    def clear(self) -> None:
        """Remove o cookie via JavaScript."""
        components.html(
            f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function(){{
    var name = {json.dumps(self.COOKIE_NAME)};
    var expired = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;SameSite=Strict';
    try {{ window.parent.document.cookie = expired; }} catch(e) {{}}
    try {{ document.cookie = expired; }} catch(e) {{}}
}})();
</script></body></html>""",
            height=1,
        )

    # Aliases
    def login(self, token: str) -> None:
        self.save(token)

    def logout(self) -> None:
        self.clear()


# ── Singleton ─────────────────────────────────────────────────────────────────

def get_auth() -> AuthHelper:
    """Uma instância por sessão — evita conflitos de múltiplas instâncias."""
    if "_auth_instance" not in st.session_state:
        st.session_state["_auth_instance"] = AuthHelper()
    return st.session_state["_auth_instance"]