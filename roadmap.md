# 🗺️ Roadmap — Avatar Professora de Inglês

---

### 1. 📊 Progresso e Gamificação

**O que é:**
Sistema de pontos, streak de dias consecutivos, conquistas e nível de fluência estimado pelo Claude.

- XP por mensagens enviadas, correções aceitas, conversas completas
- Badges: "First Conversation", "7-day Streak", "Grammar Master"
- Gráfico de evolução no dashboard do aluno
- Claude avalia nível a cada 10 mensagens e sugere progresso
- Desafios diários diversos para cada nível, cada tópico a ser aprendido

**Stack:** JSON local (já existe) + recharts no Streamlit
**Complexidade:** Média
**Estimativa:** 1 sessão

---


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