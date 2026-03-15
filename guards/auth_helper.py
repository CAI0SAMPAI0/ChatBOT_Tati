import streamlit as st
import base64
import hmac
import hashlib
import json
import streamlit.components.v1 as components 

class AuthHelper:
    COOKIE_NAME = 'tati_voice_auth'

    def __init__(self):
        self.secret = st.secrets['COOKIE_SECRET'].encode()

    def _sign(self, token: str) -> str:
        signature = hmac.new(
            self.secret,
            token.encode(),
            hashlib.sha256
        ).digest()

        payload = {
            "token": base64.urlsafe_b64encode(token.encode()).decode(),
            "sig": base64.urlsafe_b64encode(signature).decode()
        }

        return base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode()
    
    def _verify(self, signed_value: str) -> str | None:
        try:
            data = json.loads(
                base64.urlsafe_b64decode(signed_value).decode()
            )

            token = base64.urlsafe_b64decode(data["token"]).decode()
            expected_sig = hmac.new(
                self.secret,
                token.encode(),
                hashlib.sha256
            ).digest()

            received_sig = base64.urlsafe_b64decode(data["sig"])

            if hmac.compare_digest(expected_sig, received_sig):
                return token
        except:
            return None
        
    def login(self, token: str):
        signed = self._sign(token)
        components.html(
            f"""
            <script>
                document.cookie = "{self.COOKIE_NAME}={signed}; path=/; SameSite=Strict";
            </script>
            """,
            height=0
        )
    def get_token(self) -> str | None:
        cookies = st.context.cookies
        raw = cookies.get(self.COOKIE_NAME)
        if not raw:
            return None
        return self._verify(raw)
    
    def is_authenticated(self) -> bool:
        return self.get_token() is not None
    
    def logout(self):
        components.html(
            f"""
            <script>
                document.cookie = "{self.COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            </script>
            """,
            height=0
        )