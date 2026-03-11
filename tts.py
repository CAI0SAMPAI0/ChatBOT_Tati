"""
Text-to-Speech via gTTS (Google Text-to-Speech).
Gratuito, sem chave de API, sem limite prático.
Versão 3.0 — detecta o idioma DOMINANTE do texto inteiro e usa um único
              idioma para gerar o áudio, evitando alternâncias estranhas.

Lógica:
  - A IA responde predominantemente em EN (mesmo para alunos iniciantes).
  - Palavras/glosas em PT aparecem embutidas na resposta em inglês.
  - Quebrar por sentença causava o TTS ler PT no meio do EN → solução:
    detectar o idioma majoritário de TODO o texto e usar esse para o áudio.
  - Só usa pt-BR quando o texto é MAJORITARIAMENTE português (ex: o aluno
    configurou resposta em PT ou a IA respondeu num bloco todo em PT).
"""

import io
import re


def tts_available() -> bool:
    return True


# ── Marcadores de português ───────────────────────────────────────────────────
# Palavras funcionais PT-BR: artigos, pronomes, preposições, conjunções, verbos
# Evitamos palavras curtas ambíguas (a, o, as...) que existem em EN também.
# Focamos em palavras EXCLUSIVAMENTE ou fortemente portuguesas.
_PT_EXCLUSIVE = re.compile(
    r"\b("
    r"você|vocês|não|também|mas|então|pois|porque|porém|todavia|contudo"
    r"|isso|isto|aquilo|aquele|aquela|aqueles|aquelas|esse|essa|esses|essas"
    r"|nós|eles|elas|nosso|nossa|nossos|nossas|meu|minha|meus|minhas"
    r"|seu|sua|seus|suas|dele|dela|deles|delas"
    r"|está|estão|estou|estava|eram|somos|serei|seria|fosse|teria"
    r"|pode|podem|deve|devem|vai|vão|vim|disse|fez|tem|têm|há"
    r"|muito|muita|muitos|muitas|ainda|sempre|nunca|talvez|mesmo|já"
    r"|sim|ótimo|correto|errado|parabéns|certo|difícil|fácil"
    r"|como|quando|onde|qual|quais|quem|quanto|quantos"
    r"|para|com|sem|sobre|entre|após|desde|até|durante"
    r"|da|do|das|dos|num|numa|nos|nas|ao|aos|à|às"
    r"|que|se"   # ambíguas mas muito comuns em PT
    r")\b",
    re.IGNORECASE | re.UNICODE,
)

# Palavras funcionais EN — para calibrar a proporção
_EN_EXCLUSIVE = re.compile(
    r"\b("
    r"the|is|are|was|were|have|has|had|will|would|could|should|shall"
    r"|this|that|these|those|it|its|he|she|they|we|you|your|our|their"
    r"|and|but|or|so|because|although|however|therefore|thus|while"
    r"|what|which|who|where|when|how|why"
    r"|do|does|did|be|been|being|get|got|make|made"
    r"|can|may|might|must|need|let|put|say|said|know|think|want"
    r"|not|no|yes|just|also|very|really|too|more|most|some|any|all"
    r")\b",
    re.IGNORECASE,
)

# Threshold: proporção mínima de marcadores PT para considerar o texto PT
# (relativa à soma PT + EN para evitar falsos positivos)
_PT_RATIO_THRESHOLD = 0.55   # 55% dos marcadores precisam ser PT


def _dominant_language(text: str) -> str:
    """
    Retorna 'pt' se o texto for predominantemente português, 'en' caso contrário.

    Conta marcadores exclusivos de cada idioma e compara proporções.
    """
    pt_count = len(_PT_EXCLUSIVE.findall(text))
    en_count = len(_EN_EXCLUSIVE.findall(text))
    total = pt_count + en_count

    if total == 0:
        return "en"  # sem marcadores → assume EN (padrão do app)

    pt_ratio = pt_count / total
    return "pt" if pt_ratio >= _PT_RATIO_THRESHOLD else "en"


def text_to_speech(text: str) -> bytes | None:
    """
    Converte texto em áudio MP3 com detecção automática de idioma dominante.

    Usa UM único idioma para todo o texto, evitando trocas estranhas de voz
    no meio do áudio. Textos mistos (EN com glosas em PT) são lidos em EN.
    """
    from gtts import gTTS

    try:
        # Limpeza básica
        text = re.sub(r"\*+", "", text).strip()
        text = re.sub(r"\s{2,}", " ", text)
        text = text[:800]

        if not text:
            return None

        lang = _dominant_language(text)

        if lang == "pt":
            gtts_params = {"lang": "pt", "tld": "com.br", "slow": False}
        else:
            gtts_params = {"lang": "en", "tld": "com", "slow": False}

        print(f"TTS: idioma detectado = [{lang.upper()}] | "
              f"gerando audio para: {text[:60]!r}...")

        mp3_fp = io.BytesIO()
        gTTS(text=text, **gtts_params).write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        audio_bytes = mp3_fp.read()

        print(f"TTS: audio gerado ({len(audio_bytes)} bytes)")
        return audio_bytes

    except Exception as e:
        print(f"TTS: excecao — {e}")
        return None