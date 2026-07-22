# Sistema de Gestão de Chamados - Saavedra Tecnologia em Saúde

Sistema interno de suporte técnico desenvolvido com base nas melhores práticas do **ITIL 4**, estruturado para garantir alta disponibilidade, governança, rastreabilidade e métricas analíticas.

---

## 🛠️ Stack Tecnológica
* **Backend:** FastAPI (Python) com suporte a sessões assíncronas e SQLAlchemy.
* **Banco de Dados:** Microsoft SQL Server (Conexão via `pyodbc`).
* **Frontend:** HTML5, CSS3 Nativo (Design System corporativo Saavedra) e JavaScript Vanilla.
* **Servidor Web / Proxy:** Nginx (Direcionamento de portas e arquivos estáticos).

---

## 📂 Estrutura de Diretórios
* `main.py` — API principal (Endpoints, regras de negócio, envio de e-mails via SMTP e motor de SLA/CSAT).
* `auth.js` — Script centralizado de autenticação, controle de sessão baseada em cookies e RBAC (controle de acesso por perfil).
* `index.html` — Dashboard principal, KPIs dinâmicos, alternância de visão (Fila Pessoal vs. Visão da Equipe) e exportação para Excel.
* `detalhe_chamado.html` — Tela de acompanhamento, linha do tempo (Work Notes), gestão de anexos e notas internas com sigilo ITIL.
* `novo_chamado.html` — Formulário de abertura de tickets.
* `admin.html` — Painel de cadastros globais (Status, Prioridades, Tipos, Causas Raiz, Setores, Usuários e Matriz de SLA).
* `relatorios.html` — Painel analítico de governança (Gráficos de setores, técnicos, causas, top solicitantes e CSAT).
* `uploads/` — Pasta de armazenamento físico de anexos (gerenciada por UUID para evitar colisões).

---

## 🚀 Como Iniciar o Ambiente de Desenvolvimento

1. **Ativar o Ambiente Python e Instalar Dependências:**
   ```bash
   pip install fastapi uvicorn sqlalchemy pyodbc python-dotenv bcrypt
