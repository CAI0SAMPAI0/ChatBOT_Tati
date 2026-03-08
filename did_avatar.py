"""
did_avatar.py — Integração com D-ID API para avatar realista com lip-sync
Documentação: https://docs.d-id.com/reference/createtalk

Como usar:
1. Crie conta em studio.d-id.com
2. Pegue sua API key em Settings → API
3. Adicione no .env:  DID_API_KEY=sua_chave_aqui
4. Faça upload da foto em studio.d-id.com e pegue a source_url (ou use URL pública da imagem)

Plano gratuito D-ID: ~20 créditos (≈ 5 minutos de vídeo)
Plano pago: a partir de $5.99/mês
"""

import os
import time
import base64
import requests
from pathlib import Path

DID_API_KEY = os.getenv("DID_API_KEY", "")
DID_BASE    = "https://api.d-id.com"

# ── URLs das fotos dos avatares (coloque URLs públicas ou base64) ──────────────
# Opção 1: URL pública (hospedada no GitHub, Supabase Storage, etc.)
# Opção 2: Caminho local — o módulo converte para base64 automaticamente

AVATAR_PROFESSOR_URL = os.getenv("DID_AVATAR_PROFESSOR", "")  # foto da Tati
AVATAR_STUDENT_URL   = os.getenv("DID_AVATAR_STUDENT",   "")  # foto do aluno


def _get_headers() -> dict:
    """Headers de autenticação para a API D-ID."""
    if not DID_API_KEY:
        raise RuntimeError("❌ DID_API_KEY não configurada no .env / Secrets")
    key_b64 = base64.b64encode(DID_API_KEY.encode()).decode()
    return {
        "Authorization": f"Basic {key_b64}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _image_to_data_uri(path: str) -> str:
    """Converte imagem local para data URI (usado se não tiver URL pública)."""
    p = Path(path)
    ext  = p.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    data = base64.b64encode(p.read_bytes()).decode()
    return f"data:image/{mime};base64,{data}"


def get_avatar_source(is_professor: bool = True) -> str:
    """
    Retorna a source_url do avatar correto.
    Prioridade: variável de ambiente → arquivo local → fallback D-ID stock.
    """
    if is_professor:
        url = AVATAR_PROFESSOR_URL
        local_fallbacks = [
            "assets/professor.jpg",
            "data/avatars/professor.jpg",
            "data/avatars/professor.png",
        ]
    else:
        url = AVATAR_STUDENT_URL
        local_fallbacks = [
            "data/avatars/aluno.jpg",
            "data/avatars/aluno.png",
        ]

    if url:
        return url

    # Tenta arquivo local
    for path in local_fallbacks:
        if Path(path).exists():
            return _image_to_data_uri(path)

    # Fallback: avatar stock do D-ID (funciona sem foto própria)
    return "https://d-id-public-bucket.s3.amazonaws.com/alice.jpg"


def create_talk(
    text: str,
    is_professor: bool = True,
    voice_id: str = "en-US-JennyNeural",   # voz Azure Neural
    language: str = "en-US",
) -> dict | None:
    """
    Cria um vídeo de "talk" (avatar falando o texto) via D-ID API.

    Args:
        text:         Texto que o avatar vai falar
        is_professor: True = avatar da professora, False = avatar do aluno
        voice_id:     Voz Azure Neural (veja lista abaixo)
        language:     Código do idioma

    Returns:
        dict com 'id' do talk criado, ou None em caso de erro.

    Vozes recomendadas (Azure Neural — grátis no plano D-ID):
        Inglês feminino:  en-US-JennyNeural, en-US-AriaNeural, en-GB-SoniaNeural
        Inglês masculino: en-US-GuyNeural, en-US-DavisNeural
        Português:        pt-BR-FranciscaNeural (fem), pt-BR-AntonioNeural (masc)
    """
    if not DID_API_KEY:
        return None

    source_url = get_avatar_source(is_professor)
    # Limita texto (D-ID tem limite de ~500 chars por talk)
    text_clean = text[:500].strip()

    payload = {
        "source_url": source_url,
        "script": {
            "type":     "text",
            "input":    text_clean,
            "provider": {
                "type":   "microsoft",
                "voice_id": voice_id,
            },
        },
        "config": {
            "fluent":    True,     # movimentos mais suaves
            "pad_audio": 0.0,      # sem silêncio extra no início
            "stitch":    True,     # cola o avatar com o fundo original
        },
    }

    try:
        resp = requests.post(
            f"{DID_BASE}/talks",
            headers=_get_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()   # contém: { "id": "tlk_xxx", "status": "created", ... }
    except requests.HTTPError as e:
        print(f"❌ D-ID create_talk error: {e.response.status_code} — {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ D-ID create_talk exception: {e}")
        return None


def wait_for_talk(talk_id: str, timeout: int = 60) -> str | None:
    """
    Aguarda o vídeo ficar pronto e retorna a URL do MP4.

    Args:
        talk_id: ID retornado pelo create_talk
        timeout: segundos máximos de espera

    Returns:
        URL do vídeo MP4, ou None se falhar/timeout.
    """
    if not DID_API_KEY or not talk_id:
        return None

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{DID_BASE}/talks/{talk_id}",
                headers=_get_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data   = resp.json()
            status = data.get("status", "")

            if status == "done":
                return data.get("result_url")   # URL pública do vídeo MP4
            elif status in ("error", "rejected"):
                print(f"❌ D-ID talk falhou: {data.get('error', {})}")
                return None

            # Ainda processando — aguarda 2s antes de tentar novamente
            time.sleep(2)

        except Exception as e:
            print(f"❌ D-ID poll error: {e}")
            time.sleep(2)

    print(f"⏱ D-ID timeout após {timeout}s")
    return None


def get_talk_video_b64(talk_id: str) -> str | None:
    """
    Baixa o vídeo do talk e retorna como base64.
    Útil para embutir no HTML sem depender de URL externa.
    """
    video_url = wait_for_talk(talk_id)
    if not video_url:
        return None

    try:
        resp = requests.get(video_url, timeout=30)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode()
    except Exception as e:
        print(f"❌ D-ID download video error: {e}")
        return None


def generate_avatar_video(
    text: str,
    is_professor: bool = True,
    voice_id: str = "en-US-JennyNeural",
) -> str | None:
    """
    Pipeline completo: cria talk → aguarda → retorna URL do vídeo.

    Retorna URL pública do MP4 ou None se falhar.
    Tempo médio: 5-15 segundos dependendo do texto.
    """
    talk = create_talk(text, is_professor=is_professor, voice_id=voice_id)
    if not talk:
        return None

    talk_id = talk.get("id")
    if not talk_id:
        return None

    print(f"🎬 D-ID talk criado: {talk_id} — aguardando renderização...")
    return wait_for_talk(talk_id)


def did_available() -> bool:
    """Verifica se a API D-ID está configurada."""
    return bool(DID_API_KEY)
