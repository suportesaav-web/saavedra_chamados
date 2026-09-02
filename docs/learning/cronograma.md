# 📅 Cronograma Detalhado: Roteiro Semanal (30 Dias)

Este documento descreve o passo a passo de estudos para cada semana e dia do plano de 30 dias.

---

## 🛠️ Semana 1: Fundamentos de Python e Versionamento

**Foco:** Sintaxe essencial, estruturas de controle/dados, funções, preparação do ambiente no VS Code e fluxo de versionamento Git.

### 📋 Checklist Semanal
- [ ] Configurar ambiente de desenvolvimento (VS Code, Python 3.x, Git).
- [ ] Dominar comandos básicos do Git terminal (`init`, `add`, `commit`, `push`, `status`).
- [ ] Criar o repositório no GitHub para o plano de estudos.
- [ ] Escrever scripts em Python cobrindo lógica básica e manipulação de arquivos.

### 📆 Distribuição Diária
- **Dia 1:** Configuração do ambiente (VS Code, extensões Python/Git), instalação do Python e Git. Primeiros passos com `print()`, variáveis e tipos de dados (`str`, `int`, `float`, `bool`).
- **Dia 2:** Estruturas condicionais (`if`, `elif`, `else`) e operadores lógicos/comparativos.
- **Dia 3:** Coleções de dados: listas, tuplas e dicionários. Operações de manipulação e iteração.
- **Dia 4:** Laços de repetição (`for` e `while`) e tratamento de exceções básico (`try/except`).
- **Dia 5:** Modularização: criação de funções (`def`), parâmetros, retornos e escopo de variáveis.
- **Dia 6:** Git Hands-On: Inicializar repositório local, criar `.gitignore`, vincular ao GitHub remoto, efetuar os primeiros commits e pushes.
- **Dia 7:** Mini-projeto da semana: Script CLI simples em Python (ex: gerenciador de tarefas em memória ou calculador de métricas) subido para o GitHub.

---

## 🌐 Semana 2: Integração de Dados e Conceitos de Rede

**Foco:** Conexão de scripts Python a bancos de dados relacionais (SQL), fundamentos do protocolo HTTP, formato JSON e consumo/teste de APIs.

### 📋 Checklist Semanal
- [ ] Entender a estrutura de bancos de dados relacionais e comandos SQL (CRUD).
- [ ] Conectar o Python a um banco SQL (SQLite/PostgreSQL/SQL Server) via biblioteca (`sqlite3`, `pyodbc` ou `psycopg2`).
- [ ] Compreender a arquitetura cliente-servidor e protocolo HTTP.
- [ ] Realizar requisições de teste usando Postman, cURL e a biblioteca `requests` do Python.

### 📆 Distribuição Diária
- **Dia 8:** Conceitos de banco de dados SQL. Sintaxe SQL básica: `CREATE TABLE`, `INSERT`, `SELECT`, `UPDATE`, `DELETE`.
- **Dia 9:** Modelagem simples de tabelas e uso do filtro `WHERE`, ordenação (`ORDER BY`) e relacionamentos básicos.
- **Dia 10:** Integração Python + Banco de Dados: criando conexões, cursores e executando consultas CRUD via script.
- **Dia 11:** Protocolo HTTP na prática: Métodos (`GET`, `POST`, `PUT`, `DELETE`), Status Codes (`200`, `201`, `400`, `404`, `500`) e Headers.
- **Dia 12:** Estrutura e manipulação do formato JSON em Python (`json.dumps`, `json.loads`) e respostas de APIs.
- **Dia 13:** Teste prático de chamadas HTTP com cURL e Postman em APIs públicas (ex: ViaCEP, JSONPlaceholder, GitHub API).
- **Dia 14:** Lab Prático: Script Python usando a biblioteca `requests` para consumir uma API externa e salvar o resultado formatado no banco SQL.

---

## ⚡ Semana 3: Primeiro Framework Web (FastAPI ou Flask)

**Foco:** Criação de APIs RESTful profissionais, validação de schemas de entrada, roteamento, geração automática de documentação e integração com banco de dados.

### 📋 Checklist Semanal
- [ ] Instalar e configurar o framework escolhido (Recomendado: **FastAPI** com `uvicorn`).
- [ ] Criar endpoints REST cobrindo as operações CRUD.
- [ ] Implementar validação de dados com Pydantic (ou Marshmallow/Flask-RESTful).
- [ ] Conectar a API aos dados do banco estudado na Semana 2.
- [ ] Explorar a documentação interativa automática (Swagger UI / ReDoc).

### 📆 Distribuição Diária
- **Dia 15:** Apresentação do FastAPI/Flask. Instalação de dependências e criação do primeiro endpoint `"Hello World"`. Execução do servidor web (`uvicorn main:app --reload`).
- **Dia 16:** Roteamento e parâmetros: Path Parameters, Query Parameters e Request Body.
- **Dia 17:** Validação de schemas e contratos de entrada/saída utilizando Pydantic (`BaseModel`).
- **Dia 18:** Conexão da API ao banco de dados SQL (via consultas diretas ou SQLAlchemy ORM).
- **Dia 19:** Construção de endpoints CRUD completos (ex: cadastro de equipamentos, usuários ou tickets de suporte).
- **Dia 20:** Tratamento de erros HTTP customizados (`HTTPException`), validação de status codes e respostas estruturadas em JSON.
- **Dia 21:** Teste dos endpoints via Swagger UI interativo (`/docs`) e validação completa do fluxo API + Banco de Dados.

---

## 🤖 Semana 4: Consolidação, Automação e DevOps

**Foco:** Desenvolvimento de um script de automação para um problema real de infraestrutura/operação, refatoração de código, modularização e persistência no GitHub.

### 📋 Checklist Semanal
- [ ] Identificar um cenário real de automação (ex: backup automatizado, monitoramento de saúde de servidores/APIs, rotina de coleta de logs).
- [ ] Escrever um script Python completo com tratamento robusto de erros e logs.
- [ ] Aplicar refatoração: código limpo, variáveis de ambiente (`.env`), separação de responsabilidades.
- [ ] Garantir versionamento no GitHub com documentação atualizada no `README.md`.

### 📆 Distribuição Diária
- **Dia 22:** Definição do escopo do Projeto Final de Automação (ex: Script de Monitoramento de Uptime com alerta ou Backup Automatizado de Banco de Dados para nuvem/disco).
- **Dia 23:** Estruturação da lógica principal de automação utilizando módulos nativos Python (`os`, `sys`, `shutil`, `subprocess`, `logging`).
- **Dia 24:** Implementação do sistema de logs (`logging`) para registrar execuções, sucessos e falhas em arquivos local/servidor.
- **Dia 25:** Tratamento avançado de exceções, tentativas de reexecução (*retry logic*) e segurança (uso de `python-dotenv` para esconder credenciais).
- **Dia 26:** Integração opcional com notificações (envio de alerta por e-mail SMTP, Webhook do Discord/Slack ou Telegram).
- **Dia 27:** Refatoração do código: aplicação de boas práticas (PEP 8), remoção de duplicações e separação em módulos (`utils`, `config`, `main`).
- **Dia 28:** Testes de ponta a ponta da automação simulando cenários de falha e sucesso.
- **Dia 29:** Documentação completa do projeto no repositório do GitHub (como instalar, configurar `.env` e rodar a automação).
- **Dia 30:** Revisão geral dos aprendizados dos 30 dias, organização do portfólio no GitHub e definição dos próximos passos (ex: Docker, CI/CD, Terraform).
