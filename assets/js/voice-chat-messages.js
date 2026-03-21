// ── Voice Chat - Messages Handler ────────────────────────────────

class VoiceChatManager {
    constructor() {
        this.conversationId = null;
        this.messages = [];
        this.isPlaying = false;
        this.currentAudioId = null;

        this.init();
    }

    init() {
        this.attachEventListeners();
        this.loadConversationHistory();
    }

    attachEventListeners() {
        // Delegação de eventos para botões de play
        document.addEventListener('click', (e) => {
            if (e.target.closest('.msg-ouvir-btn')) {
                const btn = e.target.closest('.msg-ouvir-btn');
                const messageId = btn.dataset.msgId;
                this.toggleAudioPlayback(messageId, btn);
            }

            if (e.target.id === 'global-play-btn') {
                this.playAllMessages();
            }

            if (e.target.closest('.bubble-play-btn')) {
                const btn = e.target.closest('.bubble-play-btn');
                const bubbleId = btn.dataset.bubbleId;
                this.playBubbleAudio(bubbleId, btn);
            }
        });
    }

    addMessage(text, sender = 'user', audioUrl = null) {
        const message = {
            id: `msg-${Date.now()}`,
            text,
            sender,
            audioUrl,
            timestamp: new Date(),
            played: false
        };

        this.messages.push(message);
        this.renderMessage(message);
        this.saveConversationHistory();
    }

    renderMessage(message) {
        const historyWrap = document.querySelector('.history-wrap');
        if (!historyWrap) return;

        const bubble = document.createElement('div');
        bubble.className = `bubble ${message.sender}`;
        bubble.dataset.bubbleId = message.id;

        const label = document.createElement('div');
        label.className = `bubble-label ${message.sender === 'user' ? 'right' : 'left'}`;
        label.textContent = message.timestamp.toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit'
        });

        bubble.textContent = message.text;

        // Se for mensagem do bot e tiver áudio, adicionar botão de play
        if (message.sender === 'bot' && message.audioUrl) {
            const playBtn = document.createElement('button');
            playBtn.className = 'bubble-play-btn';
            playBtn.dataset.bubbleId = message.id;
            playBtn.textContent = '▶ Ouvir';
            bubble.before(playBtn);
        }

        const container = document.createElement('div');
        container.style.display = 'flex';
        container.style.flexDirection = message.sender === 'user' ? 'row-reverse' : 'row';
        container.style.alignItems = 'flex-end';
        container.style.justifyContent = message.sender === 'user' ? 'flex-end' : 'flex-start';
        container.style.gap = '8px';

        container.appendChild(bubble);
        container.appendChild(label);

        historyWrap.appendChild(container);
        historyWrap.scrollTop = historyWrap.scrollHeight;
    }

    async toggleAudioPlayback(messageId, btn) {
        if (this.currentAudioId === messageId && this.isPlaying) {
            this.stopAudio();
        } else {
            this.playAudio(messageId, btn);
        }
    }

    async playAudio(messageId, btn) {
        const message = this.messages.find(m => m.id === messageId);
        if (!message || !message.audioUrl) return;

        this.isPlaying = true;
        this.currentAudioId = messageId;
        btn.classList.add('speaking');
        btn.textContent = '⏸ Ouvindo...';

        try {
            const audio = new Audio(message.audioUrl);
            audio.onended = () => {
                this.stopAudio();
                btn.classList.remove('speaking');
                btn.textContent = '▶ Ouvir';
            };
            audio.play();
        } catch (error) {
            console.error('Erro ao reproduzir áudio:', error);
            this.stopAudio();
        }
    }

    async playBubbleAudio(bubbleId, btn) {
        const message = this.messages.find(m => m.id === bubbleId);
        if (!message || !message.audioUrl) return;

        this.isPlaying = true;
        this.currentAudioId = bubbleId;
        btn.classList.add('playing');
        btn.textContent = '⏸ Ouvindo...';

        try {
            const audio = new Audio(message.audioUrl);
            audio.onended = () => {
                this.isPlaying = false;
                this.currentAudioId = null;
                btn.classList.remove('playing');
                btn.textContent = '▶ Ouvir';
            };
            audio.play();
        } catch (error) {
            console.error('Erro ao reproduzir áudio:', error);
        }
    }

    stopAudio() {
        this.isPlaying = false;
        this.currentAudioId = null;
    }

    async playAllMessages() {
        // Reproduzir todas as mensagens do bot em sequência
        const botMessages = this.messages.filter(m => m.sender === 'bot' && m.audioUrl);
        for (const msg of botMessages) {
            await new Promise(resolve => {
                const audio = new Audio(msg.audioUrl);
                audio.onended = resolve;
                audio.play();
            });
        }
    }

    loadConversationHistory() {
        const saved = sessionStorage.getItem(`chat-${this.conversationId}`);
        if (saved) {
            this.messages = JSON.parse(saved);
            this.messages.forEach(msg => this.renderMessage(msg));
        }
    }

    saveConversationHistory() {
        if (!this.conversationId) return;
        sessionStorage.setItem(`chat-${this.conversationId}`, JSON.stringify(this.messages));
    }

    clearHistory() {
        this.messages = [];
        const historyWrap = document.querySelector('.history-wrap');
        if (historyWrap) {
            historyWrap.innerHTML = '';
        }
        this.saveConversationHistory();
    }

    // Utilidade: exportar conversa como JSON
    exportConversation() {
        const data = {
            conversationId: this.conversationId,
            createdAt: new Date().toISOString(),
            messages: this.messages
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `conversation-${this.conversationId}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Inicializar gerenciador de chat
let chatManager;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        chatManager = new VoiceChatManager();
    });
} else {
    chatManager = new VoiceChatManager();
}
