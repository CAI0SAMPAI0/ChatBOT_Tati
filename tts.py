"""
Text-to-Speech via ElevenLabs API.
Rotação automática de chaves — usa sempre a com menor uso (abaixo de 80% preferencial).

.env esperado:
    ELEVEN_KEY_1=sk_...
    ELEVEN_KEY_2=sk_...
    ELEVEN_KEY_3=sk_...

    # Opcional — sobrescreve a voz padrão:
    ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
"""

import os
import re
import requests

ELEVEN_MODEL = "eleven_turbo_v2_5"

# ── Vozes femininas gratuitas disponíveis em qualquer conta ElevenLabs ────────
# Rachel : 21m00Tcm4TlvDq8ikWAM  (feminina, suave) ← padrão
# Domi   : AZnzlk1XvdvUeBnXmlld  (feminina, confiante)
# Bella  : EXAVITQu4vr4xnSDxMaL  (feminina, jovem)
# Elli   : MF3mGyEYCl7XYWbV9V6O  (feminina, emocional)
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — feminina, suave
USAGE_THRESHOLD  = 0.80


# ── Leitura das chaves ────────────────────────────────────────────────────────

def _load_keys() -> list[str]:
    keys = []
    i = 1
    while True:
        k = os.getenv(f"ELEVEN_KEY_{i}", "").strip()
        if not k:
            break
        keys.append(k)
        i += 1
    if not keys:
        legacy = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if legacy:
            keys.append(legacy)
    return keys


def _voice() -> str:
    """Retorna o voice ID — prioriza .env, fallback para Rachel (feminina)."""
    v = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if v:
        return v
    return DEFAULT_VOICE_ID


# ── Consulta de uso ───────────────────────────────────────────────────────────

def _get_usage_ratio(api_key: str) -> float:
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": api_key},
            timeout=8,
        )
        if resp.status_code == 200:
            data  = resp.json()
            used  = data.get("character_count", 0)
            limit = data.get("character_limit", 1)
            ratio = used / limit if limit > 0 else 1.0
            print(f"    chave ...{api_key[-6:]}: {used}/{limit} chars ({ratio*100:.1f}%)")
            return ratio
        print(f"    chave ...{api_key[-6:]}: erro {resp.status_code}")
        return 1.0
    except Exception as e:
        print(f"    chave ...{api_key[-6:]}: exceção — {e}")
        return 1.0


def _pick_best_key(keys: list[str]) -> str | None:
    if not keys:
        return None
    print("🔑 TTS: verificando uso das chaves ElevenLabs...")
    usage = [(k, _get_usage_ratio(k)) for k in keys]
    below = [(k, r) for k, r in usage if r < USAGE_THRESHOLD]
    if below:
        best = min(below, key=lambda x: x[1])
        print(f"✅ TTS: usando chave ...{best[0][-6:]} ({best[1]*100:.1f}%)")
        return best[0]
    best = min(usage, key=lambda x: x[1])
    print(f"⚠️  TTS: todas acima de {USAGE_THRESHOLD*100:.0f}%. Menor uso: ...{best[0][-6:]} ({best[1]*100:.1f}%)")
    return best[0]


# ── Cache ─────────────────────────────────────────────────────────────────────

_cached_key: str | None = None
_call_count: int        = 0
_RECHECK_EVERY          = 20


def _get_key() -> str | None:
    global _cached_key, _call_count
    keys = _load_keys()
    if not keys:
        return None
    _call_count += 1
    if _cached_key is None or _call_count % _RECHECK_EVERY == 0:
        _cached_key = _pick_best_key(keys)
    return _cached_key


def _invalidate_cache() -> None:
    global _cached_key, _call_count
    _cached_key = None
    _call_count = 0


# ── Interface pública ─────────────────────────────────────────────────────────

def tts_available() -> bool:
    return bool(_load_keys())


def text_to_speech(text: str) -> bytes | None:
    def text_to_speech(text: str) -> bytes | None:
    import os
    print("DEBUG ENV:", os.environ.get("ELEVENLABS_VOICE_ID", "NAO ENCONTRADO"))
    print("DEBUG _voice():", _voice())
    key = _get_key()
    if not key:
        print("🚨 TTS: nenhuma chave ElevenLabs encontrada no .env")
        return None

    voice_id = _voice()
    print(f"🎙️  TTS: usando voice_id={voice_id}, key=")

    text = re.sub(r'\*+', '', text).strip()[:600]
    if not text:
        return None

    def _call(api_key: str) -> requests.Response:
        return requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key":   api_key,
                "Content-Type": "application/json",
                "Accept":       "audio/mpeg",
            },
            json={
                "text":     text,
                "model_id": ELEVEN_MODEL,
                "voice_settings": {
                    "stability":        0.5,
                    "similarity_boost": 0.75,
                    "style":            0.0,
                    "use_speaker_boost": True,
                },
            },
            timeout=20,
        )

    try:
        resp = _call(key)

        if resp.status_code == 200:
            print(f"✅ TTS: áudio gerado (chave ...{key[-6:]}, voz {voice_id})")
            return resp.content

        elif resp.status_code == 429:
            print(f"⚠️  TTS: cota esgotada em ...{key[-6:]}. Tentando próxima...")
            _invalidate_cache()
            new_key = _get_key()
            if new_key and new_key != key:
                resp2 = _call(new_key)
                if resp2.status_code == 200:
                    print(f"✅ TTS: áudio gerado na segunda tentativa (...{new_key[-6:]})")
                    return resp2.content
                print(f"❌ TTS: segunda tentativa falhou ({resp2.status_code})")
            else:
                print("❌ TTS: sem chaves alternativas")
            return None

        else:
            print(f"❌ TTS: erro {resp.status_code} — {resp.text[:300]}")
            return None

    except Exception as e:
        print(f"❌ TTS: exceção — {e}")
        return None