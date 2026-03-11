import io
import re
from gtts import gTTS


def tts_available() -> bool:
    return True


# ── Palavras/padrões que indicam português ───────────────────────────────────
# Se o texto contiver pelo menos N dessas marcas, assume-se pt-BR.
_PT_PATTERNS = re.compile(
    r"\b("
    r"não|sim|como|isso|que|mas|para|com|uma?|o[s]?|a[s]?|em|de|do|da|no|na"
    r"|você|eu|ele|ela|nos|eles|elas|meu|minha|seu|sua"
    r"|também|porque|quando|onde|quem|qual|quanto|aqui|lá|já"
    r"|olá|oi|bom\s+dia|boa\s+tarde|boa\s+noite|obrigad[oa]|por\s+favor"
    r"|tudo\s+bem|até\s+logo|tchau|entendi|pode\s+repetir|não\s+entendi"
    r"|o\s+que\s+significa|como\s+se\s+diz|ajuda|certo|errado"
    r")\b",
    re.IGNORECASE,
)

_PT_THRESHOLD = 2  # mínimo de matches para considerar pt-BR


def _detect_language(text: str) -> tuple[str, str]:
    """
    Detecta se o texto é majoritariamente pt-BR ou en.

    Retorna (lang, tld) compatíveis com gTTS:
      - Português: ('pt', 'com.br')
      - Inglês:    ('en', 'com')
    """
    matches = _PT_PATTERNS.findall(text)
    if len(matches) >= _PT_THRESHOLD:
        return "pt", "com.br"
    return "en", "com"


def text_to_speech(text: str, language: str = "auto") -> bytes | None:
    """
    Converte texto em áudio MP3.

    Args:
        text:     Texto a ser sintetizado.
        language: "auto" (padrão) → detecta pt-BR ou en automaticamente.
                  "pt"            → força português brasileiro.
                  "en"            → força inglês.

    Returns:
        Bytes do MP3 ou None em caso de erro.
    """
    try:
        # Remove markdown bold/italic e trunca
        text = re.sub(r'\*+', '', text).strip()[:600]
        if not text:
            return None

        # Determina idioma/sotaque
        if language == "auto" or language in (None, ""):
            lang, tld = _detect_language(text)
        elif language.startswith("pt"):
            lang, tld = "pt", "com.br"
        else:
            lang, tld = "en", "com"

        print(f"🎙️  TTS: idioma detectado = {lang} ({tld}) — gerando áudio com gTTS...")

        mp3_fp = io.BytesIO()
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        audio_bytes = mp3_fp.read()

        print(f"✅ TTS: áudio gerado ({len(audio_bytes)} bytes)")
        return audio_bytes

    except Exception as e:
        print(f"❌ TTS: exceção — {e}")
        return None