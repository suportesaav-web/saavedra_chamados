// auth.js - Gerenciador central de Autenticação e Configurações

// 1. Configuração Global da API
const API_BASE_URL = 'http://10.0.0.252:8082/api';

// Variável global para armazenar quem está logado
window.usuarioLogado = null;

// 2. Função de Verificação de Login
async function verificarLogin() {
    try {
        // O "credentials: 'include'" é OBRIGATÓRIO para enviar o cookie de sessão para o FastAPI [cite: 24]
        const res = await fetch(`${API_BASE_URL}/auth/me`, { 
            method: 'GET',
            credentials: 'include' 
        });

        if (!res.ok) {
            // Se a API retornar 401 (Não autorizado), joga para o login
            window.location.href = 'login.html';
        } else {
            // Salva os dados do usuário na memória para usarmos nas telas
            window.usuarioLogado = await res.json();
            console.log("Usuário autenticado:", window.usuarioLogado);

            // Executa a limpeza do menu administrativo de forma segura
            const limparMenuAdministrativo = () => {
                const perfisAdmin = ['Admin', 'Gestor', 'Tecnico']; // conjunto de perfis permitidos [cite: 28, 64]
                if (window.usuarioLogado && !perfisAdmin.includes(window.usuarioLogado.perfil)) {
                    // Remove do HTML qualquer componente marcado com o atributo "data-admin-only" 
                    document.querySelectorAll('[data-admin-only]').forEach(el => el.remove());
                }
            };

            // Se o DOM já estiver pronto, limpa imediatamente; caso contrário, aguarda o evento
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', limparMenuAdministrativo);
            } else {
                limparMenuAdministrativo();
            }
        }
    } catch (error) {
        console.error("Erro de conexão ao verificar login:", error);
        window.location.href = 'login.html';
    }
}

// 3. Função de Logout Global
async function fazerLogout() {
    try {
        await fetch(`${API_BASE_URL}/auth/logout`, { credentials: 'include' });
        window.location.href = 'login.html';
    } catch(e) {
        console.error("Erro ao tentar sair:", e);
    }
}

// 4. Gatilho Automático
// Executa a verificação imediatamente ao carregar o script, EXCETO se já estiver na tela de login
if (!window.location.pathname.endsWith('login.html')) {
    verificarLogin();
}