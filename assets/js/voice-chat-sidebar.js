// ── Voice Chat - Sidebar Manager ────────────────────────────────

class SidebarManager {
    constructor() {
        this.sidebar = document.querySelector('section[data-testid="stSidebar"]');
        this.mainContent = document.querySelector('section[data-testid="stMain"]');
        this.toggleBtn = null;
        this.isClosed = false;

        this.init();
    }

    init() {
        this.createToggleButton();
        this.attachEventListeners();
        this.loadState();
    }

    createToggleButton() {
        const btn = document.createElement('button');
        btn.id = 'pav-sb-btn';
        btn.innerHTML = '‹';
        btn.title = 'Alternar sidebar';
        btn.type = 'button';

        document.body.appendChild(btn);
        this.toggleBtn = btn;
    }

    attachEventListeners() {
        if (this.toggleBtn) {
            this.toggleBtn.addEventListener('click', () => this.toggleSidebar());
        }

        // Fechar sidebar ao clicar em um link de navegação
        if (this.sidebar) {
            this.sidebar.addEventListener('click', (e) => {
                if (e.target.closest('button[kind="primary"]')) {
                    // Apenas em mobile
                    if (window.innerWidth < 768) {
                        this.closeSidebar();
                    }
                }
            });
        }

        // Responsivo: reabrir ao redimensionar para desktop
        window.addEventListener('resize', () => {
            if (window.innerWidth >= 768 && this.isClosed) {
                this.openSidebar();
            }
        });

        // Atalho: Alt+S para toggle
        document.addEventListener('keydown', (e) => {
            if ((e.altKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.toggleSidebar();
            }
        });
    }

    toggleSidebar() {
        if (this.isClosed) {
            this.openSidebar();
        } else {
            this.closeSidebar();
        }
    }

    openSidebar() {
        this.isClosed = false;
        if (this.sidebar) {
            this.sidebar.classList.remove('pav-sb-closed');
        }
        if (this.mainContent) {
            this.mainContent.style.marginLeft = 'var(--sb-w)';
        }
        document.body.classList.remove('pav-sb-closed');
        if (this.toggleBtn) {
            this.toggleBtn.classList.remove('pav-closed');
            this.toggleBtn.textContent = '‹';
        }
        this.saveState();
    }

    closeSidebar() {
        this.isClosed = true;
        if (this.sidebar) {
            this.sidebar.classList.add('pav-sb-closed');
        }
        if (this.mainContent) {
            this.mainContent.style.marginLeft = '0';
        }
        document.body.classList.add('pav-sb-closed');
        if (this.toggleBtn) {
            this.toggleBtn.classList.add('pav-closed');
            this.toggleBtn.textContent = '›';
        }
        this.saveState();
    }

    saveState() {
        localStorage.setItem('pav-sidebar-closed', this.isClosed ? '1' : '0');
    }

    loadState() {
        const saved = localStorage.getItem('pav-sidebar-closed');
        if (saved === '1') {
            this.closeSidebar();
        } else {
            this.openSidebar();
        }
    }
}

// Inicializar sidebar manager
let sidebarManager;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Aguardar Streamlit renderizar
        setTimeout(() => {
            sidebarManager = new SidebarManager();
        }, 500);
    });
} else {
    setTimeout(() => {
        sidebarManager = new SidebarManager();
    }, 500);
}
