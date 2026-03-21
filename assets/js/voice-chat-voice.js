// ── Voice Chat - Voice Mode Manager ────────────────────────────

class VoiceModeManager {
    constructor() {
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.analyser = null;
        this.animationId = null;
        this.recordedAudio = null;
        this.recognitionScript = null;

        this.init();
    }

    init() {
        this.initAudioContext();
        this.attachVoiceControls();
        this.initSpeechRecognition();
    }

    initAudioContext() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        this.audioContext = new AudioContext();
    }

    initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn('Speech Recognition não suportado');
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'pt-BR';

        this.recognition.onstart = () => {
            console.log('Reconhecimento iniciado');
        };

        this.recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;

                if (event.results[i].isFinal) {
                    finalTranscript += transcript + ' ';
                } else {
                    interimTranscript += transcript;
                }
            }

            if (finalTranscript) {
                this.handleTranscription(finalTranscript);
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Erro no reconhecimento:', event.error);
        };

        this.recognition.onend = () => {
            console.log('Reconhecimento finalizado');
        };
    }

    attachVoiceControls() {
        // Botão mic
        const micBtn = document.querySelector('.mic-btn');
        if (micBtn) {
            micBtn.addEventListener('click', () => this.toggleMicRecording());
        }

        // Controles de áudio
        const rangeInputs = document.querySelectorAll('input[type="range"].ctrl-range');
        rangeInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const label = e.target.dataset.label;
                const value = e.target.value;
                const display = e.target.nextElementSibling;
                if (display) display.textContent = value;
            });
        });
    }

    async toggleMicRecording() {
        if (this.isRecording) {
            this.stopMicRecording();
        } else {
            this.startMicRecording();
        }
    }

    async startMicRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const micBtn = document.querySelector('.mic-btn');

            this.mediaRecorder = new MediaRecorder(stream);
            this.isRecording = true;

            if (micBtn) {
                micBtn.classList.add('recording');
            }

            const chunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                chunks.push(event.data);
            };

            this.mediaRecorder.onstop = async () => {
                this.isRecording = false;
                if (micBtn) {
                    micBtn.classList.remove('recording');
                }

                const audioBlob = new Blob(chunks, { type: 'audio/webm' });
                this.recordedAudio = audioBlob;

                // Tentar reconhecimento de fala
                if (this.recognition) {
                    const audioUrl = URL.createObjectURL(audioBlob);
                    // Iniciar reconhecimento (nota: isso depende da implementação)
                    // this.recognition.start();
                }
            };

            this.mediaRecorder.start();

            // Parar automaticamente após 30 segundos
            setTimeout(() => {
                if (this.isRecording) {
                    this.stopMicRecording();
                }
            }, 30000);
        } catch (error) {
            console.error('Erro ao acessar microfone:', error);
            alert('Permissão de microfone negada');
        }
    }

    stopMicRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            const tracks = this.mediaRecorder.stream.getTracks();
            tracks.forEach(track => track.stop());
        }
    }

    handleTranscription(text) {
        console.log('Transcrição:', text);
        // Aqui você enviaria o texto para o chat
        // Exemplo: chatManager.addMessage(text, 'user');
    }

    // Utilidade: visualizar áudio em tempo real (canvas)
    visualizeAudio(stream) {
        if (!this.audioContext) return;

        const source = this.audioContext.createMediaStreamSource(stream);
        this.analyser = this.audioContext.createAnalyser();
        source.connect(this.analyser);

        const canvas = document.querySelector('.audio-visualizer');
        if (!canvas) return;

        const canvasCtx = canvas.getContext('2d');
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const draw = () => {
            this.animationId = requestAnimationFrame(draw);

            this.analyser.getByteFrequencyData(dataArray);

            canvasCtx.fillStyle = 'rgb(15, 24, 36)';
            canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

            canvasCtx.lineWidth = 2;
            canvasCtx.strokeStyle = 'rgb(240, 165, 0)';
            canvasCtx.beginPath();

            const sliceWidth = canvas.width / bufferLength;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const v = dataArray[i] / 128.0;
                const y = (v * canvas.height) / 2;

                if (i === 0) {
                    canvasCtx.moveTo(x, y);
                } else {
                    canvasCtx.lineTo(x, y);
                }

                x += sliceWidth;
            }

            canvasCtx.lineTo(canvas.width, canvas.height / 2);
            canvasCtx.stroke();
        };

        draw();
    }

    stopVisualization() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }

    // Utilidade: reproduzir áudio com análise
    async playAudioWithAnalysis(audioBlob) {
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);

        const source = this.audioContext.createMediaElementAudioSource(audio);
        this.analyser = this.audioContext.createAnalyser();
        source.connect(this.analyser);
        this.analyser.connect(this.audioContext.destination);

        audio.play();
        this.visualizeAudio(audio);

        audio.onended = () => {
            this.stopVisualization();
            URL.revokeObjectURL(audioUrl);
        };
    }
}

// Inicializar voice mode
let voiceMode;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        voiceMode = new VoiceModeManager();
    });
} else {
    voiceMode = new VoiceModeManager();
}
