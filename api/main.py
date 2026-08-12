import os
import time
import bcrypt  
import shutil  
import uuid    
import smtplib  
import logging
from logging.handlers import TimedRotatingFileHandler
import traceback
import asyncio
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import FastAPI, HTTPException, Request, Depends, File, UploadFile, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles  
from sqlalchemy import create_engine, text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Optional, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# 1. SISTEMA DE LOGS E AUDITORIA (RAIZ)
# ==========================================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(ROOT_DIR, "logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "sistema_geral.log")

logger = logging.getLogger("SaavedraChamadosAuditoria")
logger.setLevel(logging.INFO)

file_handler = TimedRotatingFileHandler(LOG_FILE, when="H", interval=12, backupCount=14, encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())

def limpar_logs_antigos():
    try:
        agora = time.time()
        for arquivo in os.listdir(LOG_DIR):
            caminho = os.path.join(LOG_DIR, arquivo)
            if os.path.isfile(caminho) and (agora - os.path.getmtime(caminho) > 7 * 86400):
                os.remove(caminho)
    except Exception: pass

limpar_logs_antigos()

app = FastAPI(title="API Gestão de Chamados Saavedra")

# ==========================================
# 2. CONFIGURAÇÕES, MIDDLEWARES E BANCO DE DADOS
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.environ.get("SAAVEDRA_SECRET_KEY", "chave_secreta_padrao_segura_123!@#")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.middleware("http")
async def audit_and_error_logging_middleware(request: Request, call_next):
    start_time = datetime.now()
    try: user = request.session.get("user", {})
    except Exception: user = {}
    user_str = f"User #{user.get('id')} ({user.get('nome')})" if user.get("id") else "Anônimo"
    client_ip = request.client.host if request.client else "127.0.0.1"

    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        if response.status_code >= 400:
            logger.warning(f"⚠️ [HTTP {response.status_code}] {request.method} {request.url.path} | IP: {client_ip} | {user_str} | Tempo: {process_time:.2f}s")
        return response
    except Exception as exc:
        logger.error(f"❌ [CRITICAL 500] {request.method} {request.url.path} | IP: {client_ip} | {user_str} | Erro: {str(exc)}\n{traceback.format_exc()}")
        raise exc

UPLOAD_DIR = r"C:\Projetos\Apps\GestaoChamados\uploads"
if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

DB_USER = os.environ.get("SAAVEDRA_DB_USER", "chamados")
DB_PASS = os.environ.get("SAAVEDRA_DB_PASS", "WS123br")
DB_HOST = os.environ.get("SAAVEDRA_DB_HOST", "10.0.0.252")
DB_NAME = os.environ.get("SAAVEDRA_DB_NAME", "GestaoChamados")
CONN_STR = f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?driver=SQL+Server"
engine = create_engine(CONN_STR)

# ==========================================
# 3. ROBÔ DE FECHO AUTOMÁTICO (SCHEDULER ITIL)
# ==========================================
def fechar_chamados_inativos():
    try:
        with engine.begin() as conn:
            query_select = text("""
                SELECT T.TAREFA_ID, T.SOLICITANTE_ID 
                FROM tbTAREFAS T
                INNER JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID
                WHERE T.STATUS_ID NOT IN (4, 6)
                  AND (S.STATUS_NOME LIKE '%Aguardando%' OR S.STATUS_NOME LIKE '%Valida%' OR S.STATUS_NOME LIKE '%Pendente%')
                  AND T.DATA_ULTIMA_ATUALIZACAO < DATEADD(day, -3, GETDATE())
            """)
            inativos = conn.execute(query_select).fetchall()
            
            for t in inativos:
                t_id, solic_id = t[0], t[1]
                conn.execute(text("UPDATE tbTAREFAS SET STATUS_ID = 4, DATA_ULTIMA_ATUALIZACAO = GETDATE() WHERE TAREFA_ID = :id"), {"id": t_id})
                conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) VALUES (:t_id, :u_id, 4, '🤖 [SISTEMA] Chamado encerrado automaticamente por inatividade do solicitante (Prazo de 3 dias expirado).', GETDATE(), 0)"), {"t_id": t_id, "u_id": solic_id})
                logger.info(f"🤖 [CRON JOB] Chamado #{t_id} encerrado automaticamente por inatividade.")
    except Exception as e:
        logger.error(f"❌ [CRON JOB ERROR] Falha na varredura de inativos: {e}")

@app.on_event("startup")
async def iniciar_scheduler():
    async def loop_fechamento():
        while True:
            fechar_chamados_inativos()
            await asyncio.sleep(43200) # Roda a cada 12 horas
    asyncio.create_task(loop_fechamento())
    logger.info("⚙️ Scheduler de fecho automático ITIL iniciado em background.")

# ==========================================
# 4. FUNÇÕES DE SUPORTE E MOTOR DE E-MAIL
# ==========================================
SMTP_HOST = os.environ.get("SAAVEDRA_SMTP_HOST")
SMTP_PORT = int(os.environ.get("SAAVEDRA_SMTP_PORT", 587))
SMTP_USER = os.environ.get("SAAVEDRA_SMTP_USER")
SMTP_PASS = os.environ.get("SAAVEDRA_SMTP_PASS")
SMTP_FROM = os.environ.get("SAAVEDRA_SMTP_FROM")

def hash_senha(senha_plana: str) -> str:
    return bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    try: return bcrypt.checkpw(senha_plana.encode('utf-8'), senha_hash.encode('utf-8'))
    except Exception: return False

def formatar_data_segura(dt) -> Optional[str]:
    if not dt: return None
    if hasattr(dt, "isoformat"): return dt.isoformat()
    return str(dt)

def enviar_email_background(destinatario: str, assunto: str, corpo_html: str):
    if not all([SMTP_HOST, SMTP_USER, SMTP_FROM]): return
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = assunto
        msg['From'] = f"Saavedra Suporte <{SMTP_FROM}>"
        msg['To'] = destinatario
        msg.attach(MIMEText(corpo_html, 'html'))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.ehlo()
        if SMTP_PORT == 587: server.starttls(); server.ehlo()
        if SMTP_PASS: server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [destinatario], msg.as_string())
        server.quit()
    except Exception as e:
        logger.error(f"❌ [SMTP ERROR] {e}")

def enviar_email_abertura(destinatario: str, nome_usuario: str, tarefa_id: int, titulo: str):
    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid #dc4405; border-radius: 8px;">
        <div style="background: #25282a; padding: 20px; text-align: center;"><h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2></div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0;">Olá, {nome_usuario}!</h3>
            <p style="font-size: 14px; color: #555;">O seu chamado foi registado com sucesso na nossa fila de atendimento técnico.</p>
            <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #dc4405; border-radius: 4px; margin: 20px 0;">
                <span style="font-size: 12px; color: #888; font-weight: bold;">Ticket #{tarefa_id}</span><br>
                <strong style="font-size: 15px;">{titulo}</strong>
            </div>
            <div style="text-align: center; margin-top: 30px;">
                <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: #dc4405; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Aceder ao Chamado</a>
            </div>
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Chamado Registado - Saavedra", corpo_html)

def enviar_email_atualizacao(destinatario: str, nome_usuario: str, tarefa_id: int, status_nome: str, comentario: str, status_id: int):
    cor_topo = "#1e8e3e" if status_id == 4 else "#dc4405"
    bloco_csat = ""
    if status_id == 4:
        bloco_csat = f"""
        <div style="background: #f0f4f8; padding: 20px; border-radius: 6px; margin-top: 20px; text-align: center;">
            <p style="margin: 0 0 10px 0; font-size: 14px; font-weight: bold; color: #25282a;">Como avalia este atendimento?</p>
            <div style="display: flex; justify-content: center; gap: 8px;">
                <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}&avaliar=1" style="background: #da291c; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">1 😞</a>
                <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}&avaliar=5" style="background: #1e8e3e; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">5 🤩</a>
            </div>
        </div>
        """
    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid {cor_topo}; border-radius: 8px;">
        <div style="background: #25282a; padding: 20px; text-align: center;"><h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2></div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0;">Atualização no Ticket #{tarefa_id}</h3>
            <p style="font-size: 14px; color: #555;">Olá, <strong>{nome_usuario}</strong>. Houve uma nova movimentação técnica na sua solicitação.</p>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; border: 1px solid #eaeaea;">
                <div style="margin-bottom: 12px;"><span style="font-size: 12px; color: #888;">Estado Atual:</span><br><span style="background: {cor_topo}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{status_nome}</span></div>
                <div><span style="font-size: 12px; color: #888;">Nota da Equipa Técnica:</span><p style="margin: 0; font-size: 14px; background: #ffffff; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0; white-space: pre-wrap;">{comentario}</p></div>
            </div>
            {bloco_csat}
            <div style="text-align: center; margin-top: 30px;"><a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: {cor_topo}; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Ver Detalhes</a></div>
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Atualização no Chamado - Saavedra", corpo_html)

# ==========================================
# 5. MODELOS E CONTROLE DE ACESSO
# ==========================================
class ItemCadastro(BaseModel): descricao: str
class LoginRequest(BaseModel): email: str; senha: str
class AlterarSenhaRequest(BaseModel): senha_atual: str; nova_senha: str
class SlaConfigRequest(BaseModel): prioridade_id: int; tipo_id: int; tempo_horas: int
class TarefaCreate(BaseModel): titulo: str; descricao: str; prioridade_id: int; tecnico_id: Optional[int] = None; status_id: int; solicitante_id: int; tipo_id: int

class TarefaUpdate(BaseModel): 
    novo_status_id: int
    novo_tipo_id: int
    novo_tecnico_id: Optional[int] = None
    causa_raiz_id: Optional[int] = None
    comentario: str
    nota_interna: bool = False

class RespostaSolicitanteRequest(BaseModel): comentario: str
class UsuarioCreate(BaseModel): nome: str; email: str; ad_login: str; setor_id: Optional[int] = None; perfil: str; nivel_acesso: int; senha: Optional[str] = "saavedra123"
class UsuarioUpdate(BaseModel): nome: str; email: str; ad_login: str; setor_id: Optional[int] = None; perfil: str; nivel_acesso: int

TABELAS_PERMITIDAS = {"status": {"tabela": "tbSTATUS", "id": "STATUS_ID", "nome": "STATUS_NOME"}, "prioridade": {"tabela": "tbPRIORIDADE", "id": "PRIORIDADE_ID", "nome": "PRIORIDADE_NOME"}, "tipo": {"tabela": "tbTIPO", "id": "TIPO_ID", "nome": "TIPO_NOME"}, "causa_raiz": {"tabela": "tbCAUSA_RAIZ", "id": "CAUSA_ID", "nome": "CAUSA_NOME"}, "setor": {"tabela": "tbSETOR", "id": "SETOR_ID", "nome": "SETOR_NOME"}}
PERFIS_ADMIN = {"Admin", "Gestor", "Tecnico"}

def get_usuario_sessao(request: Request) -> dict:
    user = request.session.get('user')
    if not user: raise HTTPException(status_code=401, detail="Não autenticado")
    return user

def exigir_admin(usuario: dict = Depends(get_usuario_sessao)) -> dict:
    if usuario.get("perfil") not in PERFIS_ADMIN: raise HTTPException(status_code=403, detail="Acesso restrito")
    return usuario

# ==========================================
# 6. ROTAS GERAIS E CADASTROS
# ==========================================
@app.post('/api/auth/login')
def login_local(request: Request, login_data: LoginRequest):
    email_limpo = login_data.email.strip().lower()
    with engine.connect() as conn:
        user = conn.execute(text("SELECT USUARIO_ID, NOME, EMAIL, PERFIL, SENHA_HASH FROM tbUSUARIO WHERE LOWER(EMAIL) = :email AND (ATIVO = 1 OR ATIVO IS NULL)"), {"email": email_limpo}).fetchone()
    if user and verificar_senha(login_data.senha.strip(), user.SENHA_HASH):
        request.session['user'] = {"id": user.USUARIO_ID, "nome": user.NOME, "email": user.EMAIL, "perfil": user.PERFIL}
        logger.info(f"🔑 [LOGIN SUCESSO] Usuário '{email_limpo}' autenticado com êxito (ID #{user.USUARIO_ID}).")
        return {"status": "sucesso", "perfil": user.PERFIL}
    logger.warning(f"🔒 [LOGIN FALHA] Tentativa de login inválida para o e-mail '{email_limpo}'.")
    raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

@app.get('/api/auth/me')
def get_current_user(usuario: dict = Depends(get_usuario_sessao)): return usuario

@app.get('/api/auth/logout')
def logout(request: Request): request.session.clear(); return {"message": "Sessão encerrada"}

@app.post('/api/auth/alterar-senha')
def alterar_senha(request: Request, data: AlterarSenhaRequest, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn: user = conn.execute(text("SELECT SENHA_HASH FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": usuario["id"]}).fetchone()
    if not user or not verificar_senha(data.senha_atual.strip(), user.SENHA_HASH): raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    with engine.begin() as conn: conn.execute(text("UPDATE tbUSUARIO SET SENHA_HASH = :h WHERE USUARIO_ID = :id"), {"h": hash_senha(data.nova_senha.strip()), "id": usuario["id"]})
    logger.info(f"🔑 [SENHA ALTERADA] Usuário #{usuario['id']} alterou a sua senha com sucesso.")
    return {"status": "sucesso"}

@app.get("/api/cadastros/{tipo_cadastro}")
def get_cadastros(tipo_cadastro: str, usuario: dict = Depends(get_usuario_sessao)):
    if tipo_cadastro not in TABELAS_PERMITIDAS: raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.connect() as conn: 
        return [{"id": r[0], "nome": r[1]} for r in conn.execute(text(f"SELECT {cfg['id']}, {cfg['nome']} FROM {cfg['tabela']} WHERE (ATIVO = 1 OR ATIVO IS NULL)"))]

@app.post("/api/cadastros/{tipo_cadastro}")
def create_cadastro(tipo_cadastro: str, item: ItemCadastro, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS: raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn: conn.execute(text(f"INSERT INTO {cfg['tabela']} ({cfg['nome']}) VALUES (:nome)"), {"nome": item.descricao})
    return {"message": "Criado"}

@app.put("/api/cadastros/{tipo_cadastro}/{id_registro}")
def update_cadastro(tipo_cadastro: str, id_registro: int, item: ItemCadastro, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS: raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn: 
        conn.execute(text(f"UPDATE {cfg['tabela']} SET {cfg['nome']} = :nome WHERE {cfg['id']} = :id"), {"nome": item.descricao, "id": id_registro})
    return {"message": "Atualizado"}

@app.delete("/api/cadastros/{tipo_cadastro}/{id_registro}")
def delete_cadastro(tipo_cadastro: str, id_registro: int, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS: raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn: 
        try:
            conn.execute(text(f"UPDATE {cfg['tabela']} SET ATIVO = 0 WHERE {cfg['id']} = :id"), {"id": id_registro})
        except Exception:
            conn.execute(text(f"DELETE FROM {cfg['tabela']} WHERE {cfg['id']} = :id"), {"id": id_registro})
    return {"message": "Inativado"}

# 🌟 MELHORIA 3: Usuários em ORDEM ALFABÉTICA
@app.get("/api/usuarios")
def get_usuarios(usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        return [{"id": r[0], "nome": r[1], "email": r[2], "ad_login": r[3], "perfil": r[4], "setor": r[5], "setor_id": r[6], "nivel_acesso": r[7]} for r in conn.execute(text("SELECT U.USUARIO_ID, U.NOME, U.EMAIL, U.AD_LOGIN, U.PERFIL, S.SETOR_NOME, U.SETOR_ID, U.NIVEL_ACESSO FROM tbUSUARIO U LEFT JOIN tbSETOR S ON U.SETOR_ID = S.SETOR_ID WHERE (U.ATIVO = 1 OR U.ATIVO IS NULL) ORDER BY U.NOME ASC")).fetchall()]

# 🌟 MELHORIA 4: Apenas Usuários da Área Técnica
@app.get("/api/usuarios/tecnicos")
def get_usuarios_tecnicos(usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        return [{"id": r[0], "nome": r[1]} for r in conn.execute(text("SELECT USUARIO_ID, NOME FROM tbUSUARIO WHERE PERFIL IN ('Admin', 'Gestor', 'Tecnico') AND (ATIVO = 1 OR ATIVO IS NULL) ORDER BY NOME ASC")).fetchall()]

# 🌟 MELHORIA 1: Modificar e Excluir Usuário no Backend
@app.post("/api/usuarios")
def create_usuario(u: UsuarioCreate, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn: 
        conn.execute(text("INSERT INTO tbUSUARIO (NOME, EMAIL, AD_LOGIN, SETOR_ID, PERFIL, NIVEL_ACESSO, SENHA_HASH, ATIVO) VALUES (:n, :e, :a, :s, :p, :na, :senha, 1)"), {"n": u.nome, "e": u.email, "a": u.ad_login, "s": u.setor_id, "p": u.perfil, "na": u.nivel_acesso, "senha": hash_senha(u.senha if u.senha else "saavedra123")})
    return {"message": "Criado"}

@app.put("/api/usuarios/{id_usuario}")
def update_usuario(id_usuario: int, u: UsuarioUpdate, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn: 
        conn.execute(text("UPDATE tbUSUARIO SET NOME = :n, EMAIL = :e, AD_LOGIN = :a, SETOR_ID = :s, PERFIL = :p, NIVEL_ACESSO = :na WHERE USUARIO_ID = :id"), {"n": u.nome, "e": u.email, "a": u.ad_login, "s": u.setor_id, "p": u.perfil, "na": u.nivel_acesso, "id": id_usuario})
    return {"message": "Atualizado"}

@app.delete("/api/usuarios/{id_usuario}")
def delete_usuario(id_usuario: int, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn: 
        try:
            conn.execute(text("UPDATE tbUSUARIO SET ATIVO = 0 WHERE USUARIO_ID = :id"), {"id": id_usuario})
        except Exception:
            conn.execute(text("DELETE FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": id_usuario})
    return {"message": "Inativado"}

@app.get("/api/admin/sla-matrix")
def get_sla_matrix(usuario: dict = Depends(exigir_admin)):
    with engine.connect() as conn: return [{"id": r[0], "prioridade": r[1], "tipo": r[2], "tempo_horas": r[3], "prioridade_id": r[4], "tipo_id": r[5]} for r in conn.execute(text("SELECT M.SLA_ID, P.PRIORIDADE_NOME, TP.TIPO_NOME, M.TEMPO_HORAS, M.PRIORIDADE_ID, M.TIPO_ID FROM tbSLA_CONFIG M INNER JOIN tbPRIORIDADE P ON M.PRIORIDADE_ID = P.PRIORIDADE_ID INNER JOIN tbTIPO TP ON M.TIPO_ID = TP.TIPO_ID ORDER BY TP.TIPO_NOME, P.PRIORIDADE_ID ASC"))]

@app.put("/api/admin/sla-matrix/{sla_id}")
def update_sla_matrix(sla_id: int, data: SlaConfigRequest, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn: conn.execute(text("UPDATE tbSLA_CONFIG SET TEMPO_HORAS = :horas WHERE SLA_ID = :id"), {"horas": data.tempo_horas, "id": sla_id})
    return {"status": "sucesso"}

@app.get("/api/relatorios/gerais")
def get_relatorios_gerais(usuario: dict = Depends(exigir_admin)):
    with engine.connect() as conn:
        return {
            "setores": [{"label": r[0], "value": r[1]} for r in conn.execute(text("SELECT ISNULL(S.SETOR_NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR S ON U.SETOR_ID = S.SETOR_ID GROUP BY S.SETOR_NOME")).fetchall()],
            "tipos": [{"label": r[0], "value": r[1]} for r in conn.execute(text("SELECT ISNULL(TP.TIPO_NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbTIPO TP ON T.TIPO_ID = TP.TIPO_ID GROUP BY TP.TIPO_NOME")).fetchall()],
            "causas": [{"label": r[0], "value": r[1]} for r in conn.execute(text("SELECT ISNULL(C.CAUSA_NOME, 'Em Andamento'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbCAUSA_RAIZ C ON T.CAUSA_RAIZ_ID = C.CAUSA_ID GROUP BY C.CAUSA_NOME")).fetchall()],
            "tecnicos": [{"label": r[0], "value": r[1]} for r in conn.execute(text("SELECT ISNULL(U.NOME, 'Fila de Triagem'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO U ON T.TECNICO_ID = U.USUARIO_ID GROUP BY U.NOME")).fetchall()],
            "usuarios_ranking": [{"label": r[0], "value": r[1]} for r in conn.execute(text("SELECT TOP 10 ISNULL(U.NOME, 'Desconhecido'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID GROUP BY U.NOME ORDER BY COUNT(T.TAREFA_ID) DESC")).fetchall()],
            "csats": [{"label": f"Nota {r[0]} ⭐️" if r[0] else "Não Avaliado", "value": r[1]} for r in conn.execute(text("SELECT ISNULL(NOTA_CSAT, 0), COUNT(TAREFA_ID) FROM tbTAREFAS GROUP BY NOTA_CSAT ORDER BY NOTA_CSAT ASC")).fetchall()]
        }

# ==========================================
# 7. MOTOR DE PROCESSAMENTO DE FILA E TAREFAS
# ==========================================
@app.get("/api/kpis")
def get_kpis(visao_equipe: bool = False, usuario: dict = Depends(get_usuario_sessao)):
    where_clause, join_cond, params = "", "", {}
    is_admin = usuario.get("perfil") in PERFIS_ADMIN
    perfil = usuario.get("perfil")
    
    if perfil == "Comum":
        where_clause, join_cond, params = "WHERE T.SOLICITANTE_ID = :user_id", "AND T.SOLICITANTE_ID = :user_id", {"user_id": usuario["id"]}
    elif not is_admin or not visao_equipe:
        where_clause, join_cond, params = "WHERE T.TECNICO_ID = :user_id", "AND T.TECNICO_ID = :user_id", {"user_id": usuario["id"]}

    with engine.connect() as conn:
        res_esp = [0, 0, 0] if perfil == "Comum" else conn.execute(text(f"SELECT SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) < GETDATE() THEN 1 ELSE 0 END), SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) >= GETDATE() AND DATEDIFF(MINUTE, GETDATE(), TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME)) <= 120 THEN 1 ELSE 0 END), SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND T.PRIORIDADE_ID = 1 THEN 1 ELSE 0 END) FROM tbTAREFAS T {where_clause}"), params).fetchone() 
        res_status = conn.execute(text(f"SELECT S.STATUS_ID, S.STATUS_NOME, COUNT(T.TAREFA_ID) FROM tbSTATUS S LEFT JOIN tbTAREFAS T ON S.STATUS_ID = T.STATUS_ID {join_cond} WHERE (S.ATIVO = 1 OR S.ATIVO IS NULL) GROUP BY S.STATUS_ID, S.STATUS_NOME ORDER BY S.STATUS_ID ASC"), params).fetchall()
        triagem = conn.execute(text("SELECT COUNT(TAREFA_ID) FROM tbTAREFAS WHERE STATUS_ID NOT IN (4,6) AND TECNICO_ID IS NULL")).scalar() or 0 if (is_admin and visao_equipe) else 0

    return {"sla_estourado": res_esp[0] or 0, "sla_atencao": res_esp[1] or 0, "criticos": res_esp[2] or 0, "aguardando_triagem": triagem, "status_dinamicos": [{"id": r[0], "nome": r[1], "qtd": r[2]} for r in res_status]}

def processar_fila_com_filtros(base_query: str, count_query: str, params: dict, status_id: Optional[int], prioridade_id: Optional[int], tipo_id: Optional[int], sla_filtro: Optional[str], data_inicio: Optional[str], data_fim: Optional[str], user_id_filtro: Optional[int] = None, tecnico_id_filtro: Optional[int] = None, sem_tecnico: bool = False):
    where_conds = []
    
    if user_id_filtro is not None: 
        where_conds.append("T.SOLICITANTE_ID = :user_id_filtro")
        params["user_id_filtro"] = user_id_filtro
    if tecnico_id_filtro is not None: 
        where_conds.append("T.TECNICO_ID = :tecnico_id_filtro")
        params["tecnico_id_filtro"] = tecnico_id_filtro
    if sem_tecnico: 
        where_conds.extend(["T.TECNICO_ID IS NULL", "T.STATUS_ID NOT IN (4,6)"])
        
    if status_id: 
        where_conds.append("T.STATUS_ID = :status_id")
        params["status_id"] = status_id
    if prioridade_id: 
        where_conds.append("T.PRIORIDADE_ID = :prioridade_id")
        params["prioridade_id"] = prioridade_id
    if tipo_id: 
        where_conds.append("T.TIPO_ID = :tipo_id")
        params["tipo_id"] = tipo_id

    if data_inicio:
        where_conds.append("CAST(T.DATA_HORA AS DATE) >= :data_inicio")
        params["data_inicio"] = data_inicio
    if data_fim:
        where_conds.append("CAST(T.DATA_HORA AS DATE) <= :data_fim")
        params["data_fim"] = data_fim

    if sla_filtro == 'estourado':
        where_conds.extend(["T.STATUS_ID NOT IN (4,6)", "T.DATA_LIMITE_SLA < GETDATE()"])
    elif sla_filtro == 'atencao':
        where_conds.extend(["T.STATUS_ID NOT IN (4,6)", "T.DATA_LIMITE_SLA >= GETDATE()", "DATEDIFF(hour, GETDATE(), T.DATA_LIMITE_SLA) <= 2"])

    where_clause = " WHERE " + " AND ".join(where_conds) if where_conds else ""
    
    with engine.connect() as conn:
        total_items = conn.execute(text(f"{count_query} {where_clause}"), params).scalar() or 0
        ordem = " ORDER BY CASE WHEN T.STATUS_ID IN (4,6) THEN 1 ELSE 0 END ASC, T.PRIORIDADE_ID ASC, T.DATA_LIMITE_SLA ASC" if user_id_filtro is None else " ORDER BY T.DATA_HORA DESC"
        rows = conn.execute(text(f"{base_query} {where_clause} {ordem} OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"), params).fetchall()
        
    return {"dados": [{"id": r[0], "titulo": r[1], "status": r[2], "solicitante": r[3], "tecnico": r[4], "data_limite_sla": formatar_data_segura(r[5]), "status_id": r[6], "prioridade_id": r[7]} for r in rows], "paginas": (total_items + params["limit"] - 1) // params["limit"]}

@app.get("/api/meus-chamados")
async def listar_meus_chamados(request: Request, page: int = 1, limit: int = 20, status_id: Optional[int] = None, tipo_id: Optional[int] = None, prioridade_id: Optional[int] = None, sla_filtro: Optional[str] = None, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, sem_tecnico: bool = False):
    usuario = request.session.get("user")
    if not usuario: raise HTTPException(status_code=401, detail="Não autorizado")
    usuario_id = usuario.get("id") or usuario.get("usuario_id")
    base = "SELECT T.TAREFA_ID, T.TITULO, S.STATUS_NOME, U.NOME, TEC.NOME, T.DATA_LIMITE_SLA, T.STATUS_ID, T.PRIORIDADE_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID"
    return processar_fila_com_filtros(base, "SELECT COUNT(*) FROM tbTAREFAS T", {"offset": (page - 1) * limit, "limit": limit}, status_id=status_id, prioridade_id=prioridade_id, tipo_id=tipo_id, sla_filtro=sla_filtro, data_inicio=data_inicio, data_fim=data_fim, user_id_filtro=usuario_id, tecnico_id_filtro=None, sem_tecnico=sem_tecnico)

@app.get("/api/tarefas")
def get_tarefas(page: int = 1, limit: int = 20, visao_equipe: bool = False, sem_tecnico: bool = False, meus_pessoais: bool = False, status_id: Optional[int] = None, tipo_id: Optional[int] = None, prioridade_id: Optional[int] = None, sla_filtro: Optional[str] = None, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, usuario: dict = Depends(exigir_admin)):
    base = "SELECT T.TAREFA_ID, T.TITULO, S.STATUS_NOME, U.NOME, TEC.NOME, T.DATA_LIMITE_SLA, T.STATUS_ID, T.PRIORIDADE_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID"
    user_id_filtro = usuario["id"] if meus_pessoais else None
    tecnico_filtro = None if (visao_equipe or sem_tecnico or meus_pessoais) else usuario["id"]
    return processar_fila_com_filtros(base, "SELECT COUNT(*) FROM tbTAREFAS T", {"offset": (page - 1) * limit, "limit": limit}, status_id=status_id, prioridade_id=prioridade_id, tipo_id=tipo_id, sla_filtro=sla_filtro, data_inicio=data_inicio, data_fim=data_fim, user_id_filtro=user_id_filtro, tecnico_id_filtro=tecnico_filtro, sem_tecnico=sem_tecnico)

# ==========================================
# 8. DETALHES, CRIAÇÃO E AVALIAÇÃO DO CHAMADO
# ==========================================
@app.get("/api/tarefas/{tarefa_id}")
def get_tarefa_detalhe(tarefa_id: int, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT T.TAREFA_ID, T.TITULO, T.DESCRICAO, T.DATA_HORA, T.DATA_LIMITE_SLA, S.STATUS_NOME, T.STATUS_ID, U.NOME, T.SOLICITANTE_ID, TEC.NOME, T.TECNICO_ID, TIP.TIPO_NOME, T.TIPO_ID, T.CAUSA_RAIZ_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID LEFT JOIN tbTIPO TIP ON T.TIPO_ID = TIP.TIPO_ID WHERE T.TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
        if not r: raise HTTPException(status_code=404, detail="Chamado não encontrado.")
        anexos = conn.execute(text("SELECT ANEXO_ID, NOME_ORIGINAL, NOME_SALVO FROM tbTAREFA_ANEXO WHERE TAREFA_ID = :id AND HISTORICO_ID IS NULL"), {"id": tarefa_id}).fetchall()
    return {"id": r[0], "titulo": r[1], "descricao": r[2], "data_hora": formatar_data_segura(r[3]), "data_limite_sla": formatar_data_segura(r[4]), "status_nome": r[5], "status_id": r[6], "solicitante_nome": r[7], "solicitante_id": r[8], "tecnico_nome": r[9], "tecnico_id": r[10], "tipo_nome": r[11], "tipo_id": r[12], "causa_raiz_id": r[13], "anexos": [{"id": a.ANEXO_ID, "nome_original": a.NOME_ORIGINAL, "nome_salvo": a.NOME_SALVO} for a in anexos]}

@app.get("/api/tarefas/{tarefa_id}/historico")
def get_tarefa_historico(tarefa_id: int, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        query = "SELECT H.HISTORICO_ID, H.DATA_HORA, U.NOME, S.STATUS_NOME, H.COMENTARIO, A.NOME_ORIGINAL, A.NOME_SALVO, H.NOTA_INTERNA FROM tbTAREFA_HISTORICO H LEFT JOIN tbUSUARIO U ON H.USUARIO_ID = U.USUARIO_ID LEFT JOIN tbSTATUS S ON H.STATUS_ID_NA_OCASIAO = S.STATUS_ID LEFT JOIN tbTAREFA_ANEXO A ON H.HISTORICO_ID = A.HISTORICO_ID WHERE H.TAREFA_ID = :id"
        if usuario.get("perfil") not in PERFIS_ADMIN: query += " AND (H.NOTA_INTERNA = 0 OR H.NOTA_INTERNA IS NULL)"
        query += " ORDER BY H.DATA_HORA ASC"
        rows = conn.execute(text(query), {"id": tarefa_id}).fetchall()
        return [{"id": r[0], "data_hora": formatar_data_segura(r[1]), "usuario_nome": r[2], "status_nome": r[3], "comentario": r[4], "anexo_nome": r[5], "anexo_salvo": r[6], "nota_interna": r[7]} for r in rows]

@app.post("/api/tarefas")
def create_tarefa(tarefa: TarefaCreate, background_tasks: BackgroundTasks, usuario: dict = Depends(get_usuario_sessao)):
    is_comum = usuario.get("perfil") not in PERFIS_ADMIN
    if is_comum and tarefa.solicitante_id != usuario["id"]: raise HTTPException(status_code=403)
    tecnico_id_final = None if is_comum else tarefa.tecnico_id

    with engine.connect() as conn:
        sla_row = conn.execute(text("SELECT TEMPO_HORAS FROM tbSLA_CONFIG WHERE PRIORIDADE_ID = :p AND TIPO_ID = :t"), {"p": tarefa.prioridade_id, "t": tarefa.tipo_id}).fetchone()
    tempo_sla_horas = sla_row[0] if sla_row else 24
    with engine.begin() as conn:
        novo_id = conn.execute(text("INSERT INTO tbTAREFAS (TITULO, DESCRICAO, PRIORIDADE_ID, STATUS_ID, SOLICITANTE_ID, TIPO_ID, TECNICO_ID, DATA_HORA, DATA_LIMITE_SLA) OUTPUT INSERTED.TAREFA_ID VALUES (:t, :d, :p, 1, :sol, :tip, :tec, GETDATE(), DATEADD(hour, :horas, GETDATE()))"), {"t": tarefa.titulo, "d": tarefa.descricao, "p": tarefa.prioridade_id, "sol": tarefa.solicitante_id, "tip": tarefa.tipo_id, "tec": tecnico_id_final, "horas": tempo_sla_horas}).fetchone()[0]
        conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) VALUES (:t_id, :u_id, 1, 'Chamado aberto via painel.', GETDATE(), 0)"), {"t_id": novo_id, "u_id": tarefa.solicitante_id})
        solicitante = conn.execute(text("SELECT NOME, EMAIL FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": tarefa.solicitante_id}).fetchone()
    if solicitante and solicitante.EMAIL: background_tasks.add_task(enviar_email_abertura, solicitante.EMAIL, solicitante.NOME, novo_id, tarefa.titulo)
    return {"message": "Criado", "id": novo_id}

@app.put("/api/tarefas/{tarefa_id}")
async def update_tarefa(tarefa_id: int, update: TarefaUpdate, background_tasks: BackgroundTasks, usuario: dict = Depends(exigir_admin)):
    if update.novo_status_id in (4, 6) and not update.causa_raiz_id: 
        raise HTTPException(status_code=400, detail="Causa raiz obrigatória.")
    
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbTAREFAS SET STATUS_ID = :status, TIPO_ID = :tipo, TECNICO_ID = :tec, CAUSA_RAIZ_ID = :causa, DATA_ULTIMA_ATUALIZACAO = GETDATE() WHERE TAREFA_ID = :id"), {"id": tarefa_id, "status": update.novo_status_id, "tipo": update.novo_tipo_id, "tec": update.novo_tecnico_id, "causa": update.causa_raiz_id})
        interna_flag = 1 if update.nota_interna else 0
        historico_id = conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) OUTPUT INSERTED.HISTORICO_ID VALUES (:tarefa_id, :usuario_acao, :status, :comentario, GETDATE(), :interna)"), {"tarefa_id": tarefa_id, "usuario_acao": usuario["id"], "status": update.novo_status_id, "comentario": update.comentario, "interna": interna_flag}).fetchone()[0]
        ticket = conn.execute(text("SELECT T.TITULO, S.STATUS_NOME, U.NOME, U.EMAIL FROM tbTAREFAS T JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID WHERE T.TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
    
    if ticket and ticket.EMAIL and not update.nota_interna: 
        background_tasks.add_task(enviar_email_atualizacao, ticket.EMAIL, ticket.NOME, tarefa_id, ticket.STATUS_NOME, update.comentario, update.novo_status_id)
        
    return {"message": "Atualizado", "historico_id": historico_id}

@app.post("/api/tarefas/{tarefa_id}/responder")
def responder_tarefa(tarefa_id: int, resp: RespostaSolicitanteRequest, background_tasks: BackgroundTasks, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        t = conn.execute(text("SELECT SOLICITANTE_ID, STATUS_ID FROM tbTAREFAS WHERE TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
    if not t: raise HTTPException(404, detail="Chamado não encontrado")
    if usuario.get("perfil") not in PERFIS_ADMIN and t.SOLICITANTE_ID != usuario["id"]: raise HTTPException(403, detail="Acesso negado")
    if not resp.comentario.strip(): raise HTTPException(400, detail="O comentário é obrigatório")

    with engine.begin() as conn:
        conn.execute(text("UPDATE tbTAREFAS SET DATA_ULTIMA_ATUALIZACAO = GETDATE() WHERE TAREFA_ID = :id"), {"id": tarefa_id})
        historico_id = conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) OUTPUT INSERTED.HISTORICO_ID VALUES (:tarefa_id, :usuario_acao, :status, :comentario, GETDATE(), 0)"), {"tarefa_id": tarefa_id, "usuario_acao": usuario["id"], "status": t.STATUS_ID, "comentario": resp.comentario.strip()}).fetchone()[0]
    return {"message": "Resposta inserida com sucesso", "historico_id": historico_id}

@app.post("/api/tarefas/{tarefa_id}/anexar")
async def anexar_arquivo(tarefa_id: int, historico_id: Optional[int] = Form(None), files: List[UploadFile] = File(...), usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn: 
        t = conn.execute(text("SELECT SOLICITANTE_ID FROM tbTAREFAS WHERE TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
    if not t or (usuario.get("perfil") not in PERFIS_ADMIN and t.SOLICITANTE_ID != usuario["id"]): 
        raise HTTPException(403)
        
    with engine.begin() as conn:
        for file in files:
            if file.filename: 
                nome_salvo = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
                with open(os.path.join(UPLOAD_DIR, nome_salvo), "wb") as buffer: 
                    shutil.copyfileobj(file.file, buffer)
                conn.execute(text("INSERT INTO tbTAREFA_ANEXO (TAREFA_ID, HISTORICO_ID, NOME_ORIGINAL, NOME_SALVO, DATA_HORA) VALUES (:t_id, :h_id, :nome_orig, :nome_salvo, GETDATE())"), {"t_id": tarefa_id, "h_id": historico_id, "nome_orig": file.filename, "nome_salvo": nome_salvo})
    return {"status": "sucesso"}

@app.post("/api/tarefas/{tarefa_id}/avaliar")
def avaliar_chamado(tarefa_id: int, nota: int, request: Request):
    if not (1 <= nota <= 5): raise HTTPException(status_code=400, detail="A nota deve ser entre 1 e 5.")
    desc_notas = {1: "1/5 - Insatisfeito 😞", 2: "2/5 - Regular 😕", 3: "3/5 - Neutro 😐", 4: "4/5 - Satisfeito 😊", 5: "5/5 - Excelente 🤩"}
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbTAREFAS SET NOTA_CSAT = :nota WHERE TAREFA_ID = :id"), {"nota": nota, "id": tarefa_id})
        conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) SELECT :id, SOLICITANTE_ID, STATUS_ID, :comentario, GETDATE(), 0 FROM tbTAREFAS WHERE TAREFA_ID = :id"), {"id": tarefa_id, "comentario": f"Nota de Atendimento atribuída pelo utilizador: {desc_notas.get(nota, f'{nota}/5')}"})
    return {"status": "sucesso", "mensagem": "Obrigado por avaliar o atendimento!"}