# 🗺️ Roadmap — Avatar Professora de Inglês

## ✅ Já implementado
- Login com persistência (localStorage)
- Múltiplas conversas com histórico na sidebar
- Chat com Claude (Método Sanduíche + Neuroaprendizagem)
- Avatar com foto e anel dourado animado
- Upload de áudio com transcrição (faster-whisper)
- Upload de PDF → extração real de texto (pdfplumber)
- Upload de DOCX/DOC → extração real de texto (python-docx)
- Upload de imagens → Claude Vision descreve e ensina
- TTS com botão ▶ Ouvir na bolha (ElevenLabs)
- Painel do professor (dashboard com métricas)

---

## 🔜 Próximas funcionalidades

---

### 1. 🎙️ Modo Conversa (estilo ChatGPT Advanced Voice)

**O que é:**
Um botão fixo na tela que ativa um modo de conversa contínua por voz — o aluno fala, a IA detecta o silêncio, transcreve, responde em texto e vocaliza automaticamente. Enquanto a IA fala, se o aluno começar a falar, a IA para (barge-in).

**Como funciona tecnicamente:**

```
[Aluno fala] → Web Speech API (reconhecimento contínuo no browser)
            → Detecta silêncio (>1.5s sem fala)
            → Envia para Claude via WebSocket/fetch
            → Claude responde em texto
            → ElevenLabs gera MP3
            → Toca no browser
            → Se aluno falar durante reprodução → para o áudio (barge-in)
            → Loop
```

**Stack:**
- Frontend: `Web Speech API` (SpeechRecognition) para captura contínua
- Backend: `FastAPI` com WebSocket ou endpoint SSE para streaming
- TTS: ElevenLabs (já integrado)
- Integração: `components.html` grande com JS que gerencia todo o ciclo

**Complexidade:** Alta — requer refatorar o backend para streaming
**Estimativa:** 1-2 sessões de desenvolvimento

---

### 2. 🧑‍💻 Avatar Animado com Boca Sincronizada

**O que é:**
O avatar da professora tem o rosto animado em tempo real enquanto fala — boca abrindo e fechando sincronizada com o áudio TTS, similar a apps como HeyGen ou D-ID.

**Duas abordagens possíveis:**

#### Opção A — Avatar 2D com CSS/Canvas (mais simples, roda no browser)
- Foto da professora como base
- Sobreposição de sprites de boca (fechada, meio aberta, aberta) trocando em sincronia com amplitude do áudio
- Análise de amplitude via `Web Audio API` (`AnalyserNode`)
- Sem dependência externa, roda 100% no browser

```javascript
// Exemplo do ciclo:
analyser.getByteFrequencyData(dataArray);
const volume = dataArray.reduce((a,b) => a+b) / dataArray.length;
mouth.style.height = Math.min(volume / 3, 20) + 'px'; // simula boca
```

#### Opção B — Avatar 3D com lip-sync real (mais sofisticado)
- Biblioteca: **Three.js** + modelo GLB (ex: Ready Player Me avatar)
- Geração de visemas (formas de boca) a partir do áudio TTS
- Lib: `rhubarb-lip-sync` ou API da **D-ID** / **HeyGen**
- Requer modelo 3D com blend shapes de boca

**Recomendação:** Começar com Opção A (rápido, visual já convincente) e evoluir para B depois.

**Complexidade:** Média (Opção A) / Alta (Opção B)
**Estimativa:** 1 sessão (Opção A) / 3+ sessões (Opção B)

---

### 3. 📊 Progresso e Gamificação

**O que é:**
Sistema de pontos, streak de dias consecutivos, conquistas e nível de fluência estimado pelo Claude.

- XP por mensagens enviadas, correções aceitas, conversas completas
- Badges: "First Conversation", "7-day Streak", "Grammar Master"
- Gráfico de evolução no dashboard do aluno
- Claude avalia nível a cada 10 mensagens e sugere progresso

**Stack:** JSON local (já existe) + recharts no Streamlit
**Complexidade:** Média
**Estimativa:** 1 sessão

---

### 4. 🌐 Deploy online (Streamlit Community Cloud)

**O que é:**
Colocar o app no ar para acessar de qualquer lugar, sem precisar rodar localmente.

**Passos:**
1. Criar repositório no GitHub (público ou privado)
2. Adicionar `secrets.toml` no Streamlit Cloud com as API keys
3. Conectar repo → deploy automático
4. URL pública tipo: `https://professora-tatiana.streamlit.app`

**Limitação importante:** O Streamlit Community Cloud tem disco efêmero — os dados de conversas somem a cada deploy. Para persistência real, precisa de banco externo:
- **Opção gratuita:** Supabase (PostgreSQL) ou Firebase Firestore
- **Opção paga:** Railway, Render, ou VPS

**Complexidade:** Baixa (sem banco) / Média (com banco externo)
**Estimativa:** 1 sessão

---

## 📦 Dependências a instalar para próximas features

```bash
# Modo Conversa (backend streaming)
pip install fastapi uvicorn websockets

# Avatar animado Opção B (D-ID API)
pip install requests  # já instalado

# Gamificação + gráficos
pip install altair  # já incluso no Streamlit

# Deploy com banco externo
pip install supabase
```

---

## 🎯 Ordem sugerida de implementação

1. **Deploy** → app no ar para testar com alunos reais
2. **Modo Conversa** → diferencial principal do produto
3. **Avatar animado** (Opção A) → impacto visual imediato
4. **Gamificação** → retenção e engajamento dos alunos
5. **Avatar 3D** (Opção B) → evolução premium

---

## 💡 Notas técnicas — Modo Conversa detalhado

O grande desafio do Modo Conversa é a **latência**:

```
Fala do aluno:     ~2-5s de gravação
Transcrição:       ~0.5s (Whisper local)
Claude resposta:   ~1-2s (haiku)
TTS geração:       ~1-2s (ElevenLabs)
─────────────────────────────────────
Total percebido:   ~3-5s (aceitável)
```

Para reduzir a latência:
- **Streaming do Claude:** recebe tokens em tempo real e já inicia TTS com as primeiras frases
- **TTS por chunks:** gera áudio frase a frase em vez de esperar a resposta completa
- **Cache de áudio:** frases comuns pré-geradas (ex: "Good job!", "Let me think...")

Esta arquitetura de streaming + TTS por chunks reduz a latência percebida para ~1.5s — equivalente ao ChatGPT Advanced Voice.