// ── PAV Buttons - Mic & Clip Control ──────────────────────────────

class PAVButtons {
    constructor() {
        this.micBtn = document.getElementById('pav-mic-btn');
        this.clipBtn = document.getElementById('pav-clip-btn');
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.stream = null;
        
        this.init();
    }

    init() {
        if (!this.micBtn || !this.clipBtn) return;

        this.micBtn.addEventListener('click', () => this.toggleRecording());
        this.clipBtn.addEventListener('click', () => this.handleClipUpload());
        
        // Atalho: Ctrl+M para gravar
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'm') {
                e.preventDefault();
                this.toggleRecording();
            }
        });
    }

    async toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    }

    async startRecording() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(this.stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstart = () => {
                this.isRecording = true;
                this.micBtn.classList.add('recording');
                this.updateUI();
            };

            this.mediaRecorder.onstop = async () => {
                this.isRecording = false;
                this.micBtn.classList.remove('recording');
                this.updateUI();

                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                await this.processAudio(audioBlob);
            };

            this.mediaRecorder.start();
        } catch (error) {
            console.error('Erro ao acessar microfone:', error);
            alert('Permissão de microfone negada');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
        }
    }

    async processAudio(audioBlob) {
        // Salvar em sessionStorage ou enviar para servidor
        const audioUrl = URL.createObjectURL(audioBlob);
        console.log('Audio gravado:', audioUrl);

        // Exemplo: enviar para um endpoint
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        // Descomente para enviar:
        // try {
        //     const response = await fetch('/api/upload-audio', {
        //         method: 'POST',
        //         body: formData
        //     });
        //     const result = await response.json();
        //     console.log('Resposta:', result);
        // } catch (error) {
        //     console.error('Erro ao enviar áudio:', error);
        // }
    }

    handleClipUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'audio/*';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (file) {
                console.log('Arquivo selecionado:', file.name);
                // Processar arquivo de áudio
                const formData = new FormData();
                formData.append('audio', file);
                // Enviar para servidor se necessário
            }
        };
        input.click();
    }

    updateUI() {
        if (this.isRecording) {
            this.micBtn.setAttribute('data-status', 'recording');
        } else {
            this.micBtn.setAttribute('data-status', 'idle');
        }
    }
}

// Inicializar quando o DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new PAVButtons();
    });
} else {
    new PAVButtons();
}
