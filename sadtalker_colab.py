# ═══════════════════════════════════════════════════════════════════════════════
# SADTALKER — COLAB NOTEBOOK
# Cole cada bloco como uma célula separada no Google Colab
# Runtime: GPU (T4 ou melhor) — Ambiente: Python 3
# ═══════════════════════════════════════════════════════════════════════════════

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 1 — Instala dependências
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
!pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
!pip install -q flask flask-cors pyngrok requests
!pip install -q face_alignment==1.3.5
!pip install -q imageio==2.19.3 imageio-ffmpeg==0.4.7
!pip install -q scikit-image librosa==0.9.2
!pip install -q basicsr facexlib realesrgan
!pip install -q pydub
!apt-get install -qq ffmpeg
print("✅ Dependências instaladas!")
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 2 — Clona SadTalker e baixa modelos
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os

# Clona o repositório
if not os.path.exists('/content/SadTalker'):
    !git clone https://github.com/OpenTalker/SadTalker.git /content/SadTalker
    print("✅ SadTalker clonado!")
else:
    print("✅ SadTalker já existe.")

os.chdir('/content/SadTalker')

# Baixa os checkpoints oficiais
!mkdir -p checkpoints weights/other

print("⬇ Baixando modelos SadTalker...")
!wget -q -O checkpoints/SadTalker_V0.0.2_256.safetensors \\
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors"

!wget -q -O checkpoints/SadTalker_V0.0.2_512.safetensors \\
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors"

print("⬇ Baixando modelos de detecção facial...")
!wget -q -O weights/other/BFM_Fitting.zip \\
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/BFM_Fitting.zip"
!unzip -q -o weights/other/BFM_Fitting.zip -d weights/other/

!wget -q -O weights/other/hub.zip \\
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/hub.zip"
!unzip -q -o weights/other/hub.zip -d weights/other/

# Gfpgan para melhorar qualidade do rosto
!wget -q -O gfpgan/weights/GFPGANv1.4.pth \\
    "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth" 2>/dev/null || true

print("✅ Todos os modelos baixados!")
!ls -lh checkpoints/
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 3 — Sobe a foto da Tati
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
# Opção A: Upload direto pelo Colab
from google.colab import files
import shutil, os

print("Faça upload da foto da Tati (tati.jpg ou tati.png):")
uploaded = files.upload()

os.makedirs('/content/SadTalker/inputs', exist_ok=True)
for fname, data in uploaded.items():
    ext = fname.split('.')[-1].lower()
    dest = f'/content/SadTalker/inputs/tati.{ext}'
    with open(dest, 'wb') as f:
        f.write(data)
    TATI_PHOTO = dest
    print(f"✅ Foto salva em: {dest}")

# Opção B: Se a foto já está no Google Drive, monte e copie:
# from google.colab import drive
# drive.mount('/content/drive')
# TATI_PHOTO = '/content/drive/MyDrive/tati.jpg'
# shutil.copy(TATI_PHOTO, '/content/SadTalker/inputs/tati.jpg')
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 4 — Testa geração local (opcional, para verificar se funciona)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os
os.chdir('/content/SadTalker')

# Gera um vídeo de teste com um áudio de exemplo
!python inference.py \\
    --driven_audio examples/driven_audio/bus_chinese.wav \\
    --source_image inputs/tati.jpg \\
    --result_dir /content/test_output \\
    --still \\
    --preprocess full \\
    --enhancer gfpgan

# Mostra o vídeo gerado
from IPython.display import Video
import os
videos = [f for f in os.listdir('/content/test_output') if f.endswith('.mp4')]
if videos:
    print(f"✅ Vídeo gerado: {videos[0]}")
    Video(f'/content/test_output/{videos[0]}', embed=True)
else:
    print("⚠️ Nenhum vídeo encontrado. Verifique os erros acima.")
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 5 — Servidor Flask + ngrok (PRINCIPAL — deixe rodando)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os, sys, base64, tempfile, subprocess, threading, time, traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from pyngrok import ngrok, conf

# ── Configuração ──────────────────────────────────────────────────────
SADTALKER_DIR = '/content/SadTalker'
TATI_PHOTO    = '/content/SadTalker/inputs/tati.jpg'   # ajuste se necessário
OUTPUT_DIR    = '/content/sadtalker_output'
NGROK_TOKEN   = ''   # ← Cole seu token de https://dashboard.ngrok.com/get-started/your-authtoken
                     #   (gratuito, só precisa criar conta)

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.chdir(SADTALKER_DIR)
sys.path.insert(0, SADTALKER_DIR)

app = Flask(__name__)
CORS(app)

def run_sadtalker(audio_path: str, output_dir: str) -> str:
    \"\"\"Executa o SadTalker e retorna o caminho do vídeo gerado.\"\"\"
    cmd = [
        'python', f'{SADTALKER_DIR}/inference.py',
        '--driven_audio',  audio_path,
        '--source_image',  TATI_PHOTO,
        '--result_dir',    output_dir,
        '--still',                    # cabeça mais estável (menos wobble)
        '--preprocess',    'full',    # usa rosto inteiro (melhor qualidade)
        '--enhancer',      'gfpgan',  # melhora qualidade do rosto
        '--size',          '256',     # 256 ou 512 (512 = mais lento)
        '--expression_scale', '1.0',  # intensidade das expressões (0.5–2.0)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SADTALKER_DIR)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])

    # Encontra o vídeo gerado
    mp4s = sorted(
        [f for f in os.listdir(output_dir) if f.endswith('.mp4')],
        key=lambda f: os.path.getmtime(os.path.join(output_dir, f)),
        reverse=True
    )
    if not mp4s:
        raise RuntimeError('Nenhum vídeo encontrado após execução do SadTalker.')
    return os.path.join(output_dir, mp4s[0])


@app.route('/health', methods=['GET'])
def health():
    import torch
    gpu_mb = round(torch.cuda.memory_allocated() / 1024**2) if torch.cuda.is_available() else 0
    return jsonify({'status': 'ok', 'gpu_mb': gpu_mb})


@app.route('/generate', methods=['POST'])
def generate():
    try:
        data      = request.get_json(force=True)
        audio_b64 = data.get('audio_b64', '')
        if not audio_b64:
            return jsonify({'error': 'audio_b64 ausente'}), 400

        # Salva o áudio em arquivo temporário
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(audio_bytes)
            audio_path = tmp.name

        # Pasta de saída única por request
        req_dir = tempfile.mkdtemp(dir=OUTPUT_DIR)

        print(f'[SadTalker] Gerando vídeo... áudio={len(audio_bytes)/1024:.1f}KB')
        video_path = run_sadtalker(audio_path, req_dir)

        with open(video_path, 'rb') as f:
            video_b64 = base64.b64encode(f.read()).decode()

        # Limpeza
        os.unlink(audio_path)
        os.unlink(video_path)

        print(f'[SadTalker] ✅ Vídeo gerado ({len(video_b64)//1024}KB base64)')
        return jsonify({'video_b64': video_b64})

    except Exception as e:
        tb = traceback.format_exc()
        print(f'[SadTalker] ERRO:\\n{tb}')
        return jsonify({'error': str(e), 'traceback': tb[-1000:]}), 500


def start_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ── Inicia ngrok ──────────────────────────────────────────────────────
if NGROK_TOKEN:
    conf.get_default().auth_token = NGROK_TOKEN
    ngrok.kill()
    tunnel = ngrok.connect(5000)
    public_url = tunnel.public_url
else:
    # Sem token: usa pyngrok sem auth (limite 1 conexão simultânea)
    ngrok.kill()
    tunnel = ngrok.connect(5000)
    public_url = tunnel.public_url

print('=' * 60)
print(f'SERVIDOR ATIVO: {public_url}')
print(f'Copie para o .env do Streamlit:')
print(f'SADTALKER_URL={public_url}')
print('=' * 60)

# Inicia Flask em thread separada
t = threading.Thread(target=start_server, daemon=True)
t.start()
time.sleep(2)
print('Servidor rodando. Deixe esta célula ativa!')

# Monitor de GPU em loop
import torch
while True:
    gpu_mb = round(torch.cuda.memory_allocated()/1024**2) if torch.cuda.is_available() else 0
    print(f'\\rServidor ativo | GPU: {gpu_mb}MB usados', end='', flush=True)
    time.sleep(10)
"""
