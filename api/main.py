import os
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import traceback
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles  
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config import SECRET_KEY
from database import engine

# ==========================================
# 1. SISTEMA DE LOGS E AUDITORIA AVANÇADO
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

# ==========================================
# 2. SCHEDULER ITIL & LIFESPAN (MODERNIZADO)
# ==========================================
def obter_ou_criar_causa_inatividade(conn) -> int:
    try:
        r = conn.execute(text("SELECT CAUSA_ID FROM tbCAUSA_RAIZ WHERE CAUSA_NOME LIKE '%Inatividade%' OR CAUSA_NOME LIKE '%Automátic%'")).fetchone()
        if r: return r[0]
        r_new = conn.execute(text("INSERT INTO tbCAUSA_RAIZ (CAUSA_NOME, ATIVO) OUTPUT INSERTED.CAUSA_ID VALUES ('Encerramento Automático (Inatividade ITIL)', 1)")).fetchone()
        return r_new[0]
    except Exception as e:
        logger.error(f"❌ Erro ao obter causa raiz de inatividade: {e}")
        return 1

def fechar_chamados_inativos():
    try:
        with engine.begin() as conn:
            causa_id = obter_ou_criar_causa_inatividade(conn)
            query_select = text("""
                SELECT T.TAREFA_ID, T.SOLICITANTE_ID 
                FROM tbTAREFAS T
                INNER JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID
                WHERE T.STATUS_ID NOT IN (4, 6)
                  AND (S.STATUS_NOME LIKE '%Aguardando%' OR S.STATUS_NOME LIKE '%Valida%' OR S.STATUS_NOME LIKE '%Pendente%')
                  AND ISNULL(T.DATA_ULTIMA_ATUALIZACAO, T.DATA_HORA) < DATEADD(day, -7, GETDATE())
            """)
            inativos = conn.execute(query_select).fetchall()
            
            for t in inativos:
                t_id, solic_id = t[0], t[1]
                conn.execute(text("UPDATE tbTAREFAS SET STATUS_ID = 4, CAUSA_RAIZ_ID = :causa_id, DATA_ULTIMA_ATUALIZACAO = GETDATE() WHERE TAREFA_ID = :id"), {"id": t_id, "causa_id": causa_id})
                conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) VALUES (:t_id, :u_id, 4, '🤖 [SISTEMA] Chamado encerrado automaticamente por inatividade do solicitante (Prazo de 7 dias expirado).', GETDATE(), 0)"), {"t_id": t_id, "u_id": solic_id})
                logger.info(f"🤖 [CRON JOB] Chamado #{t_id} encerrado automaticamente por inatividade.")
    except Exception as e:
        logger.error(f"❌ [CRON JOB ERROR] Falha na varredura de inativos: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def loop_fechamento():
        while True:
            try:
                fechar_chamados_inativos()
            except Exception as e:
                logger.error(f"❌ [CRON JOB ERROR] {e}")
            await asyncio.sleep(43200)
            
    task = asyncio.create_task(loop_fechamento())
    logger.info("⚙️ Scheduler de fecho automático ITIL iniciado em background (Lifespan).")
    try:
        yield
    finally:
        task.cancel()
        logger.info("🛑 Scheduler de fecho automático ITIL finalizado.")

# ==========================================
# 3. INSTÂNCIA E MIDDLEWARES
# ==========================================
app = FastAPI(title="API Gestão de Chamados Saavedra", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

UPLOAD_DIR = os.path.join(ROOT_DIR, "uploads")
if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ==========================================
# 4. REGISTRO DOS ROUTERS
# ==========================================
from routers import auth, cadastros, admin, tarefas, relatorios

app.include_router(auth.router)
app.include_router(cadastros.router)
app.include_router(admin.router)
app.include_router(tarefas.router)
app.include_router(relatorios.router)