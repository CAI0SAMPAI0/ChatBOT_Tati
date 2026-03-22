# 🎓 Teacher Tati — AI English Coach

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38+-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Claude AI](https://img.shields.io/badge/Claude-Haiku-orange?logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Plataforma conversacional de ensino de inglês com IA, recursos de voz, avatar animado e dashboard de gerenciamento de alunos.**

[Demo](#) · [Documentação](#-guia-de-instalação) · [Reportar Bug](https://github.com/CAI0SAMPAI0/ChatBOT_Tati/issues)

</div>

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Problema que Resolve](#-problema-que-resolve)
- [Principais Funcionalidades](#-principais-funcionalidades)
- [Stack Tecnológica](#-stack-tecnológica)
- [Guia de Instalação](#-guia-de-instalação)
- [Uso](#-uso)
- [Roadmap](#-roadmap)

---

## 🎯 Sobre o Projeto

**Teacher Tati** é uma plataforma full-stack de tutoria de inglês alimentada por inteligência artificial. Oferece experiência de aprendizado personalizada através de conversação por texto ou voz, com avatar digital interativo que simula uma professora de inglês real.

### ✨ Diferenciais

- 🧠 **IA Pedagógica**: Claude Haiku com metodologia estruturada de 25+ anos
- 🎙️ **Modo Voz Imersivo**: Interface full-screen com avatar animado sincronizado
- 📊 **Dashboard Professor**: Analytics em tempo real de progresso dos alunos
- 🌐 **Sistema Bilíngue**: Adaptação automática PT/EN baseada no nível
- 📝 **Geração de Conteúdo**: Exercícios e atividades em PDF/DOCX

---

## 🔧 Problema que Resolve

### Desafios do Ensino Tradicional de Idiomas

1. **Alto Custo**: Aulas custam R$ 80-200/hora
2. **Falta de Prática**: Poucas oportunidades fora das aulas semanais
3. **Feedback Limitado**: Correções apenas durante sessões agendadas
4. **Barreira de Timidez**: Vergonha de praticar com outras pessoas
5. **Falta de Personalização**: Métodos genéricos não adaptáveis

### Solução Automatizada

✅ **Disponibilidade 24/7** - Pratique a qualquer hora  
✅ **Custo Zero** - Escala sem custos variáveis  
✅ **Feedback Imediato** - Correções em tempo real  
✅ **Ambiente Seguro** - Sem julgamento ou pressão  
✅ **Adaptação Inteligente** - Ajuste automático ao nível  
✅ **Rastreamento Completo** - Monitoramento sem esforço manual  

### Casos de Uso

- **Escolas de Idiomas**: Complemento com prática ilimitada
- **Professores Independentes**: Gerenciamento de múltiplos alunos
- **Empresas**: Treinamento corporativo com analytics
- **Autodidatas**: Plataforma completa para aprendizado autônomo

---

## 🚀 Principais Funcionalidades

### 🤖 Motor de IA Pedagógica

- **Claude Haiku** com prompt pedagógico estruturado
- **Política Bilíngue**: Transição PT-EN por proficiência
- **Neuro-aprendizagem**: Guia à autocorreção
- **Geração de Material**: Worksheets em PDF/DOCX

### 🎙️ Modo Voz Completo

- Interface full-screen com avatar animado
- **Faster-Whisper** para transcrição local (sem custos)
- VAD bilíngue com detecção automática
- **gTTS** text-to-speech com controles de velocidade
- Animação sincronizada com volume de áudio

### 💬 Interface de Chat

- Bolhas estilo ChatGPT com áudio por mensagem
- Anexos: PDF, DOCX, TXT, imagens e áudio
- Player TTS inline com controles completos
- Histórico persistente de conversas

### 👤 Sistema de Usuários

- Autenticação SHA-256 segura
- Sessões persistentes (localStorage + cookie)
- Auto-login em retornos
- Perfil com avatar, nível, foco e preferências

### 📊 Dashboard do Professor

- Stats em tempo real: alunos, mensagens, correções
- Breakdown individual por aluno
- Alternância fluida entre modos

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Função |
|--------|-----------|---------|
| **Frontend** | Streamlit 1.38+ | Interface interativa |
| **IA** | Claude Haiku | Motor conversacional |
| **STT** | Faster-Whisper | Transcrição local |
| **TTS** | gTTS | Síntese de voz |
| **Database** | Supabase PostgreSQL | Persistência |
| **Storage** | Supabase Storage | Avatares |
| **PDF** | ReportLab | Geração documentos |
| **DOCX** | python-docx | Geração Word |

---

## 🚀 Guia de Instalação

### Pré-requisitos

- Python 3.11+
- Conta Supabase (free tier OK)
- API Key Anthropic Claude

### 1. Clone e Configure

```bash
git clone https://github.com/CAI0SAMPAI0/ChatBOT_Tati.git
cd ChatBOT_Tati
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Variáveis de Ambiente

Crie `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
PROFESSOR_NAME=Teacher Tati
```

### 3. Setup Supabase

Execute no SQL Editor:

```sql
CREATE TABLE users (
  username TEXT PRIMARY KEY,
  name TEXT, password TEXT,
  role TEXT DEFAULT 'student',
  level TEXT DEFAULT 'Beginner',
  created_at TEXT,
  profile JSONB DEFAULT '{}'
);

CREATE TABLE sessions (
  token TEXT PRIMARY KEY,
  username TEXT REFERENCES users(username) ON DELETE CASCADE,
  created_at TEXT, last_seen TEXT
);

CREATE TABLE conversations (
  id TEXT, username TEXT,
  created_at TEXT,
  PRIMARY KEY (id, username)
);

CREATE TABLE messages (
  id BIGSERIAL PRIMARY KEY,
  conv_id TEXT, username TEXT,
  role TEXT, content TEXT,
  audio BOOLEAN DEFAULT FALSE,
  timestamp TEXT
);
```

Crie bucket "avatars" em Storage (público).

### 4. Execute

```bash
streamlit run app.py
```

Acesse: **http://localhost:8501**

---

## 📖 Uso

### Credenciais Padrão

| Papel | Username | Senha |
|-------|----------|-------|
| Professor | `professor` | `prof123` |
| Dev | `programador` | `cai0_based` |

⚠️ Altere após primeiro login!

### Para Alunos

1. Registre-se com username único
2. Configure nível e preferências
3. Chat por texto ou voz
4. Acesse histórico na sidebar

### Para Professores

1. Login com credenciais de professor
2. Visualize dashboard de analytics
3. Monitore progresso individual
4. Teste experiência em modo aluno

---

## 🗺️ Roadmap

- [ ] Sistema de gamificação (XP, badges, streaks)
- [ ] Desafios diários por nível
- [ ] TTS streaming (menor latência)
- [ ] Avatar realista (D-ID/Wav2Lip)
- [ ] Relatórios PDF de progresso
- [ ] Integração com calendário
- [ ] App mobile nativo

---

## 📄 Licença

MIT © 2025 Teacher Tati Project

---

## 👨‍💻 Autor

**Caio Sampaio** - [@CAI0SAMPAI0](https://github.com/CAI0SAMPAI0)

---

<div align="center">

**⭐ Se foi útil, dê uma estrela!**

Made with ❤️ in Brazil

</div>
