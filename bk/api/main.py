from bk.api.main import enviar_email_background
from dotenv import load_dotenv
load_dotenv()

import os
import bcrypt  
import shutil  
import uuid    
import smtplib  
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import FastAPI, HTTPException, Request, Depends, File, UploadFile, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles  
from sqlalchemy import create_engine, text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="API Gestão de Chamados Saavedra")

# ==========================================
# 1. CONFIGURAÇÕES E MIDDLEWARES
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500", "http://127.0.0.1:5500", "http://10.0.0.252:5500",
        "http://localhost:8082", "http://127.0.0.1:8082", "http://10.0.0.252:8082",
        "http://localhost", "http://127.0.0.1", "http://10.0.0.252"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.environ.get("SAAVEDRA_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("Defina a variável de ambiente SAAVEDRA_SECRET_KEY antes de iniciar a API.")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

SMTP_HOST = os.environ.get("SAAVEDRA_SMTP_HOST")
SMTP_PORT = int(os.environ.get("SAAVEDRA_SMTP_PORT", 587))
SMTP_USER = os.environ.get("SAAVEDRA_SMTP_USER")
SMTP_PASS = os.environ.get("SAAVEDRA_SMTP_PASS")
SMTP_FROM = os.environ.get("SAAVEDRA_SMTP_FROM")

# ==========================================
# 2. CONEXÃO DO BANCO DE DADOS
# ==========================================
DB_USER = os.environ.get("SAAVEDRA_DB_USER", "chamados")
DB_PASS = os.environ.get("SAAVEDRA_DB_PASS")
DB_HOST = os.environ.get("SAAVEDRA_DB_HOST", "10.0.0.252")
DB_NAME = os.environ.get("SAAVEDRA_DB_NAME", "GestaoChamados")
if not DB_PASS:
    raise RuntimeError("Defina a variável de ambiente SAAVEDRA_DB_PASS.")

CONN_STR = f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?driver=SQL+Server"
engine = create_engine(CONN_STR)

# ==========================================
# 3. FUNÇÕES AUXILIARES
# ==========================================
def hash_senha(senha_plana: str) -> str:
    senha_bytes = senha_plana.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_bytes, salt).decode('utf-8')

def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha_plana.encode('utf-8'), senha_hash.encode('utf-8'))
    except Exception:
        return False

def formatar_data_segura(dt) -> Optional[str]:
    if not dt:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)

##def enviar_email_background(destinatario: str, assunto: str, corpo_html: str):
##    if not all([SMTP_HOST, SMTP_USER, SMTP_FROM]):
#        return
#    try:
#        msg = MIMEMultipart('alternative')
#        msg['Subject'] = assunto
#        msg['From'] = f"Saavedra Suporte <{SMTP_FROM}>"
#        msg['To'] = destinatario
##        msg.attach(MIMEText(corpo_html, 'html'))
 #       
 #       server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
 #       server.ehlo()
 #       if SMTP_PORT == 587:
 #           server.starttls()  
 ##           server.ehlo()
  #      if SMTP_PASS:
  #          server.login(SMTP_USER, SMTP_PASS)
  #      server.sendmail(SMTP_FROM, [destinatario], msg.as_string())
  #      server.quit()
  #  except Exception as e:
  #      print(f"❌ [SMTP ERROR] {e}")

# ==========================================
# TEMPLATES DE E-MAIL CORPORATIVO SAAVEDRA
# ==========================================

def enviar_email_abertura(destinatario: str, nome_usuario: str, tarefa_id: int, titulo: str):
    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid #dc4405; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
        <div style="background: #25282a; padding: 20px; text-align: center;">
            <h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2>
        </div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0; color: #25282a;">Olá, {nome_usuario}!</h3>
            <p style="font-size: 14px; color: #555; line-height: 1.5;">O seu chamado foi registado com sucesso na nossa fila de atendimento técnico e já está a ser processado.</p>
            
            <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #dc4405; border-radius: 4px; margin: 20px 0;">
                <span style="font-size: 12px; color: #888; text-transform: uppercase; font-weight: bold; display: block; margin-bottom: 5px;">Ticket #{tarefa_id}</span>
                <strong style="font-size: 15px; color: #25282a;">{titulo}</strong>
            </div>
            
            <p style="font-size: 14px; color: #555;">Pode acompanhar o andamento da sua solicitação a qualquer momento através do portal interno.</p>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: #dc4405; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px;">Aceder ao Chamado</a>
            </div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eaeaea;">
            Saavedra Tecnologia em Saúde &bull; Setor de TI e Governança
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Chamado Registado - Saavedra", corpo_html)


def enviar_email_atualizacao(destinatario: str, nome_usuario: str, tarefa_id: int, status_nome: str, comentario: str, status_id: int):
    # Define a cor da barra superior com base no status (Verde para Concluído, Laranja para Andamento)
    cor_topo = "#1e8e3e" if status_id == 4 else "#dc4405"
    
    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid {cor_topo}; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
        <div style="background: #25282a; padding: 20px; text-align: center;">
            <h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2>
        </div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0; color: #25282a;">Atualização no Ticket #{tarefa_id}</h3>
            <p style="font-size: 14px; color: #555; line-height: 1.5;">Olá, <strong>{nome_usuario}</strong>. Houve uma nova movimentação técnica na sua solicitação.</p>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; border: 1px solid #eaeaea;">
                <div style="margin-bottom: 12px;">
                    <span style="font-size: 12px; color: #888; display: block; margin-bottom: 3px;">Estado Atual:</span>
                    <span style="background: {cor_topo}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; display: inline-block;">{status_nome}</span>
                </div>
                <div>
                    <span style="font-size: 12px; color: #888; display: block; margin-bottom: 3px;">Nota da Equipa Técnica:</span>
                    <p style="margin: 0; font-size: 14px; color: #333; background: #ffffff; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0; white-space: pre-wrap;">{comentario}</p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: {cor_topo}; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px;">Ver Detalhes do Chamado</a>
            </div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eaeaea;">
            Saavedra Tecnologia em Saúde &bull; Setor de TI e Governança
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Atualização no Chamado - Saavedra", corpo_html)



# ==========================================
# 4. MODELOS PYDANTIC
# ==========================================
class ItemCadastro(BaseModel):
    descricao: str

class LoginRequest(BaseModel):
    email: str
    senha: str

class AlterarSenhaRequest(BaseModel):
    senha_atual: str
    nova_senha: str

class SlaConfigRequest(BaseModel):
    prioridade_id: int
    tipo_id: int
    tempo_horas: int

class TarefaCreate(BaseModel):
    titulo: str
    descricao: str
    prioridade_id: int
    tecnico_id: Optional[int] = None
    status_id: int
    solicitante_id: int
    tipo_id: int

class TarefaUpdate(BaseModel):
    novo_status_id: int
    novo_tipo_id: int
    novo_tecnico_id: Optional[int] = None
    causa_raiz_id: Optional[int] = None
    comentario: str

class UsuarioCreate(BaseModel):
    nome: str
    email: str
    ad_login: str
    setor_id: Optional[int] = None
    perfil: str
    nivel_acesso: int
    senha: Optional[str] = "saavedra123"

class UsuarioUpdate(BaseModel):
    nome: str
    email: str
    ad_login: str
    setor_id: Optional[int] = None
    perfil: str
    nivel_acesso: int

TABELAS_PERMITIDAS = {
    "status": {"tabela": "tbSTATUS", "id": "STATUS_ID", "nome": "STATUS_NOME"},
    "prioridade": {"tabela": "tbPRIORIDADE", "id": "PRIORIDADE_ID", "nome": "PRIORIDADE_NOME"},
    "tipo": {"tabela": "tbTIPO", "id": "TIPO_ID", "nome": "TIPO_NOME"},
    "causa_raiz": {"tabela": "tbCAUSA_RAIZ", "id": "CAUSA_ID", "nome": "CAUSA_NOME"},
    "setor": {"tabela": "tbSETOR", "id": "SETOR_ID", "nome": "SETOR_NOME"}
}

PERFIS_ADMIN = {"Admin", "Gestor", "Tecnico"}

def get_usuario_sessao(request: Request) -> dict:
    user = request.session.get('user')
    if not user: raise HTTPException(status_code=401, detail="Não autenticado")
    return user

def exigir_admin(usuario: dict = Depends(get_usuario_sessao)) -> dict:
    if usuario.get("perfil") not in PERFIS_ADMIN: raise HTTPException(status_code=403, detail="Acesso restrito")
    return usuario

# ==========================================
# 5. ROTAS DE CONFIGURAÇÃO E CADASTROS
# ==========================================
@app.post('/api/auth/login')
def login_local(request: Request, login_data: LoginRequest):
    with engine.connect() as conn:
        query = text("SELECT USUARIO_ID, NOME, EMAIL, PERFIL, SENHA_HASH FROM tbUSUARIO WHERE LOWER(EMAIL) = :email AND ATIVO = 1")
        user = conn.execute(query, {"email": login_data.email.strip().lower()}).fetchone()
    if user and verificar_senha(login_data.senha.strip(), user.SENHA_HASH):
        request.session['user'] = {"id": user.USUARIO_ID, "nome": user.NOME, "email": user.EMAIL, "perfil": user.PERFIL}
        return {"status": "sucesso", "perfil": user.PERFIL}
    raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

@app.get('/api/auth/me')
def get_current_user(usuario: dict = Depends(get_usuario_sessao)): return usuario

@app.get('/api/auth/logout')
def logout(request: Request):
    request.session.clear()
    return {"message": "Sessão encerrada"}

@app.post('/api/auth/alterar-senha')
def alterar_senha(request: Request, data: AlterarSenhaRequest, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        user = conn.execute(text("SELECT SENHA_HASH FROM tbUSUARIO WHERE USUARIO_ID = :id AND ATIVO = 1"), {"id": usuario["id"]}).fetchone()
    if not user or not verificar_senha(data.senha_atual.strip(), user.SENHA_HASH): raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbUSUARIO SET SENHA_HASH = :h WHERE USUARIO_ID = :id"), {"h": hash_senha(data.nova_senha.strip()), "id": usuario["id"]})
    return {"status": "sucesso"}

@app.get("/api/cadastros/{tipo_cadastro}")
def get_cadastros(tipo_cadastro: str, usuario: dict = Depends(get_usuario_sessao)):
    if tipo_cadastro not in TABELAS_PERMITIDAS: raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.connect() as conn:
        return [{"id": r[0], "nome": r[1]} for r in conn.execute(text(f"SELECT {cfg['id']}, {cfg['nome']} FROM {cfg['tabela']} WHERE ATIVO = 1"))]

@app.post("/api/cadastros/{tipo_cadastro}")
def create_cadastro(tipo_cadastro: str, item: ItemCadastro, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS: raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO {cfg['tabela']} ({cfg['nome']}) VALUES (:nome)"), {"nome": item.descricao})
    return {"message": "Criado"}

@app.delete("/api/cadastros/{tipo_cadastro}/{id_registro}")
def delete_cadastro(tipo_cadastro: str, id_registro: int, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS: raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE {cfg['tabela']} SET ATIVO = 0 WHERE {cfg['id']} = :id"), {"id": id_registro})
    return {"message": "Inativado"}

@app.get("/api/usuarios")
def get_usuarios(usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        query = text("""SELECT U.USUARIO_ID, U.NOME, U.EMAIL, U.AD_LOGIN, U.PERFIL, S.SETOR_NOME, U.SETOR_ID, U.NIVEL_ACESSO
                         FROM tbUSUARIO U LEFT JOIN tbSETOR S ON U.SETOR_ID = S.SETOR_ID WHERE U.ATIVO = 1""")
        return [{"id": r[0], "nome": r[1], "email": r[2], "ad_login": r[3], "perfil": r[4], "setor": r[5], "setor_id": r[6], "nivel_acesso": r[7]} for r in conn.execute(query)]

@app.post("/api/usuarios")
def create_usuario(u: UsuarioCreate, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO tbUSUARIO (NOME, EMAIL, AD_LOGIN, SETOR_ID, PERFIL, NIVEL_ACESSO, SENHA_HASH, ATIVO)
                              VALUES (:n, :e, :a, :s, :p, :na, :senha, 1)"""),
                     {"n": u.nome, "e": u.email, "a": u.ad_login, "s": u.setor_id, "p": u.perfil,
                      "na": u.nivel_acesso, "senha": hash_senha(u.senha if u.senha else "saavedra123")})
    return {"message": "Criado"}

@app.put("/api/usuarios/{id}")
def update_usuario(id: int, u: UsuarioUpdate, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        conn.execute(text("""UPDATE tbUSUARIO SET NOME=:n, EMAIL=:e, AD_LOGIN=:a, SETOR_ID=:s, PERFIL=:p, NIVEL_ACESSO=:na
                              WHERE USUARIO_ID=:id AND ATIVO = 1"""),
                     {"id": id, "n": u.nome, "e": u.email, "a": u.ad_login, "s": u.setor_id, "p": u.perfil, "na": u.nivel_acesso})
    return {"message": "Atualizado"}

@app.delete("/api/usuarios/{id}")
def delete_usuario(id: int, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbUSUARIO SET ATIVO = 0 WHERE USUARIO_ID = :id"), {"id": id})
    return {"message": "Desativado"}

@app.get("/api/admin/sla-matrix")
def get_sla_matrix(usuario: dict = Depends(exigir_admin)):
    with engine.connect() as conn:
        query = text("""
            SELECT M.SLA_ID, P.PRIORIDADE_NOME, TP.TIPO_NOME, M.TEMPO_HORAS, M.PRIORIDADE_ID, M.TIPO_ID
            FROM tbSLA_CONFIG M
            INNER JOIN tbPRIORIDADE P ON M.PRIORIDADE_ID = P.PRIORIDADE_ID
            INNER JOIN tbTIPO TP ON M.TIPO_ID = TP.TIPO_ID
            WHERE M.ATIVO = 1
            ORDER BY TP.TIPO_NOME, P.PRIORIDADE_ID ASC
        """)
        return [{"id": r[0], "prioridade": r[1], "tipo": r[2], "tempo_horas": r[3], "prioridade_id": r[4], "tipo_id": r[5]} for r in conn.execute(query)]

@app.put("/api/admin/sla-matrix/{sla_id}")
def update_sla_matrix(sla_id: int, data: SlaConfigRequest, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbSLA_CONFIG SET TEMPO_HORAS = :horas WHERE SLA_ID = :id"), {"horas": data.tempo_horas, "id": sla_id})
    return {"status": "sucesso"}

# ==========================================
# 6. KPIS E DASHBOARDS ANALYTICS
# ==========================================
@app.get("/api/kpis")
def get_kpis(usuario: dict = Depends(get_usuario_sessao)):
    where_clause = ""
    params = {}
    if usuario.get("perfil") not in PERFIS_ADMIN:
        where_clause = "WHERE T.SOLICITANTE_ID = :user_id"
        params = {"user_id": usuario["id"]}
    with engine.connect() as conn:
        res_esp = conn.execute(text(f"SELECT SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) < GETDATE() THEN 1 ELSE 0 END), SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) >= GETDATE() AND DATEDIFF(MINUTE, GETDATE(), TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME)) <= 120 THEN 1 ELSE 0 END), SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND T.PRIORIDADE_ID = 1 THEN 1 ELSE 0 END) FROM tbTAREFAS T {where_clause}"), params).fetchone()
        res_status = conn.execute(text(f"SELECT S.STATUS_ID, S.STATUS_NOME, COUNT(T.TAREFA_ID) FROM tbSTATUS S LEFT JOIN tbTAREFAS T ON S.STATUS_ID = T.STATUS_ID {"AND T.SOLICITANTE_ID = :user_id" if usuario.get("perfil") not in PERFIS_ADMIN else ""} WHERE S.ATIVO = 1 GROUP BY S.STATUS_ID, S.STATUS_NOME ORDER BY S.STATUS_ID ASC"), params).fetchall()
    return {"sla_estourado": res_esp[0] or 0, "sla_atencao": res_esp[1] or 0, "criticos": res_esp[2] or 0, "status_dinamicos": [{"id": r[0], "nome": r[1], "qtd": r[2]} for r in res_status]}

@app.get("/api/relatorios/gerais")
def get_relatorios_gerais(usuario: dict = Depends(exigir_admin)):
    with engine.connect() as conn:
        setores = conn.execute(text("SELECT ISNULL(S.SETOR_NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR S ON U.SETOR_ID = S.SETOR_ID GROUP BY S.SETOR_NOME")).fetchall()
        tipos = conn.execute(text("SELECT ISNULL(TP.TIPO_NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbTIPO TP ON T.TIPO_ID = TP.TIPO_ID GROUP BY TP.TIPO_NOME")).fetchall()
        causas = conn.execute(text("SELECT ISNULL(C.CAUSA_NOME, 'Em Andamento'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbCAUSA_RAIZ C ON T.CAUSA_RAIZ_ID = C.CAUSA_ID GROUP BY C.CAUSA_NOME")).fetchall()
        tecnicos = conn.execute(text("SELECT ISNULL(U.NOME, 'Fila de Triagem'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO U ON T.TECNICO_ID = U.USUARIO_ID GROUP BY U.NOME")).fetchall()
    return {"setores": [{"label": r[0], "value": r[1]} for r in setores], "tipos": [{"label": r[0], "value": r[1]} for r in tipos], "causas": [{"label": r[0], "value": r[1]} for r in causas], "tecnicos": [{"label": r[0], "value": r[1]} for r in tecnicos]}

# ==========================================
# 7. MOTOR DE PROCESSAMENTO DE FILA CONJUNTO (COM TIPO_ID INJETADO)
# ==========================================
def processar_fila_com_filtros(base_query: str, count_query: str, params: dict, status_id: Optional[int], prioridade_id: Optional[int], tipo_id: Optional[int], sla_filtro: Optional[str], data_inicio: Optional[str], data_fim: Optional[str], user_id_filtro: Optional[int] = None):
    where_conds = []
    if user_id_filtro is not None:
        where_conds.append("T.SOLICITANTE_ID = :user_id_filtro")
        params["user_id_filtro"] = user_id_filtro
        
    if status_id:
        where_conds.append("T.STATUS_ID = :status_id")
        params["status_id"] = status_id
    if prioridade_id:
        where_conds.append("T.PRIORIDADE_ID = :prioridade_id")
        params["prioridade_id"] = prioridade_id
    # 🌟 INJEÇÃO DO NOVO FILTRO DE TRIAGEM POR TIPO DE CHAMADO (HARDWARE VS SOFTWARE)
    if tipo_id:
        where_conds.append("T.TIPO_ID = :tipo_id")
        params["tipo_id"] = tipo_id
        
    if data_inicio:
        where_conds.append("TRY_CAST(T.DATA_HORA AS DATE) >= :data_inicio")
        params["data_inicio"] = data_inicio
    if data_fim:
        where_conds.append("TRY_CAST(T.DATA_HORA AS DATE) <= :data_fim")
        params["data_fim"] = data_fim
        
    if sla_filtro == "estourado":
        where_conds.append("T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) < GETDATE()")
    elif sla_filtro == "atencao":
        where_conds.append("T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) >= GETDATE() AND DATEDIFF(MINUTE, GETDATE(), TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME)) <= 120")

    where_clause = " WHERE " + " AND ".join(where_conds) if where_conds else ""
    with engine.connect() as conn:
        total_items = conn.execute(text(f"{count_query} {where_clause}"), params).scalar() or 0
        ordem = " ORDER BY CASE WHEN T.STATUS_ID IN (4,6) THEN 1 ELSE 0 END ASC, T.PRIORIDADE_ID ASC, T.DATA_LIMITE_SLA ASC" if user_id_filtro is None else " ORDER BY T.DATA_HORA DESC"
        final_query = text(f"{base_query} {where_clause} {ordem} OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY")
        rows = conn.execute(final_query, params).fetchall()
        
    return {"dados": [{"id": r[0], "titulo": r[1], "status": r[2], "solicitante": r[3], "tecnico": r[4], "data_limite_sla": formatar_data_segura(r[5]), "status_id": r[6], "prioridade_id": r[7]} for r in rows], "paginas": (total_items + params["limit"] - 1) // params["limit"]}

@app.get("/api/meus-chamados")
def get_meus_chamados(page: int = 1, limit: int = 20, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, status_id: Optional[int] = None, prioridade_id: Optional[int] = None, tipo_id: Optional[int] = None, sla_filtro: Optional[str] = None, usuario: dict = Depends(get_usuario_sessao)):
    base = "SELECT T.TAREFA_ID, T.TITULO, S.STATUS_NOME, U.NOME, TEC.NOME, T.DATA_LIMITE_SLA, T.STATUS_ID, T.PRIORIDADE_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID"
    return processar_fila_com_filtros(base, "SELECT COUNT(*) FROM tbTAREFAS T", {"offset": (page - 1) * limit, "limit": limit}, status_id, prioridade_id, tipo_id, sla_filtro, data_inicio, data_fim, user_id_filtro=usuario['id'])

@app.get("/api/tarefas")
def get_tarefas(page: int = 1, limit: int = 20, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, status_id: Optional[int] = None, prioridade_id: Optional[int] = None, tipo_id: Optional[int] = None, sla_filtro: Optional[str] = None, usuario: dict = Depends(exigir_admin)):
    base = "SELECT T.TAREFA_ID, T.TITULO, S.STATUS_NOME, U.NOME, TEC.NOME, T.DATA_LIMITE_SLA, T.STATUS_ID, T.PRIORIDADE_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID"
    return processar_fila_com_filtros(base, "SELECT COUNT(*) FROM tbTAREFAS T", {"offset": (page - 1) * limit, "limit": limit}, status_id, prioridade_id, tipo_id, sla_filtro, data_inicio, data_fim, user_id_filtro=None)

# ==========================================
# 8. DETALHES, HISTÓRICO E OPERAÇÃO CORE
# ==========================================
@app.get("/api/tarefas/{tarefa_id}")
def get_tarefa_detalhe(tarefa_id: int, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT T.TAREFA_ID, T.TITULO, T.DESCRICAO, T.DATA_HORA, T.DATA_LIMITE_SLA, S.STATUS_NOME, T.STATUS_ID, U.NOME, T.SOLICITANTE_ID, TEC.NOME, T.TECNICO_ID, TIP.TIPO_NOME, T.TIPO_ID, T.CAUSA_RAIZ_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID LEFT JOIN tbTIPO TIP ON T.TIPO_ID = TIP.TIPO_ID WHERE T.TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
        if not r: raise HTTPException(404)
        if usuario.get("perfil") not in PERFIS_ADMIN and r[8] != usuario["id"]: raise HTTPException(403)
        anexos = conn.execute(text("SELECT ANEXO_ID, NOME_ORIGINAL, NOME_SALVO FROM tbTAREFA_ANEXO WHERE TAREFA_ID = :id AND HISTORICO_ID IS NULL"), {"id": tarefa_id}).fetchall()
    return {"id": r[0], "titulo": r[1], "descricao": r[2], "data_hora": formatar_data_segura(r[3]), "data_limite_sla": formatar_data_segura(r[4]), "status_nome": r[5], "status_id": r[6], "solicitante_nome": r[7], "solicitante_id": r[8], "tecnico_nome": r[9], "tecnico_id": r[10], "tipo_nome": r[11], "tipo_id": r[12], "causa_raiz_id": r[13], "anexos": [{"id": a.ANEXO_ID, "nome_original": a.NOME_ORIGINAL, "nome_salvo": a.NOME_SALVO} for a in anexos]}

@app.get("/api/tarefas/{tarefa_id}/historico")
def get_tarefa_historico(tarefa_id: int, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        query = text("SELECT H.HISTORICO_ID, H.DATA_HORA, U.NOME, S.STATUS_NOME, H.COMENTARIO, A.NOME_ORIGINAL, A.NOME_SALVO FROM tbTAREFA_HISTORICO H LEFT JOIN tbUSUARIO U ON H.USUARIO_ID = U.USUARIO_ID LEFT JOIN tbSTATUS S ON H.STATUS_ID_NA_OCASIAO = S.STATUS_ID LEFT JOIN tbTAREFA_ANEXO A ON H.HISTORICO_ID = A.HISTORICO_ID WHERE H.TAREFA_ID = :id ORDER BY H.DATA_HORA ASC")
        return [{"id": r[0], "data_hora": formatar_data_segura(r[1]), "usuario_nome": r[2], "status_nome": r[3], "comentario": r[4], "anexo_nome": r[5], "anexo_salvo": r[6]} for r in conn.execute(query, {"id": tarefa_id})]

@app.post("/api/tarefas")
def create_tarefa(tarefa: TarefaCreate, background_tasks: BackgroundTasks, usuario: dict = Depends(get_usuario_sessao)):
    if usuario.get("perfil") not in PERFIS_ADMIN and tarefa.solicitante_id != usuario["id"]: raise HTTPException(status_code=403)
    with engine.connect() as conn:
        sla_row = conn.execute(text("SELECT TEMPO_HORAS FROM tbSLA_CONFIG WHERE PRIORIDADE_ID = :p AND TIPO_ID = :t AND ATIVO = 1"), {"p": tarefa.prioridade_id, "t": tarefa.tipo_id}).fetchone()
    tempo_sla_horas = sla_row[0] if sla_row else 24
    with engine.begin() as conn:
        res = conn.execute(text("INSERT INTO tbTAREFAS (TITULO, DESCRICAO, PRIORIDADE_ID, STATUS_ID, SOLICITANTE_ID, TIPO_ID, TECNICO_ID, DATA_HORA, DATA_LIMITE_SLA) OUTPUT INSERTED.TAREFA_ID VALUES (:t, :d, :p, 1, :sol, :tip, :tec, GETDATE(), DATEADD(hour, :horas, GETDATE()))"), {"t": tarefa.titulo, "d": tarefa.descricao, "p": tarefa.prioridade_id, "sol": tarefa.solicitante_id, "tip": tarefa.tipo_id, "tec": tarefa.tecnico_id, "horas": tempo_sla_horas})
        novo_id = res.fetchone()[0]
        conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA) VALUES (:t_id, :u_id, 1, 'Chamado aberto via painel.', GETDATE())"), {"t_id": novo_id, "u_id": tarefa.solicitante_id})
        solicitante = conn.execute(text("SELECT NOME, EMAIL FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": tarefa.solicitante_id}).fetchone()
    if solicitante and solicitante.EMAIL:
        background_tasks.add_task(enviar_email_background, solicitante.EMAIL, f"Novo Chamado Saavedra #{novo_id}", f"<h3>Chamado #{novo_id} registrado!</h3>")
    return {"message": "Criado", "id": novo_id}

@app.put("/api/tarefas/{tarefa_id}")
def update_tarefa(tarefa_id: int, update: TarefaUpdate, background_tasks: BackgroundTasks, usuario: dict = Depends(exigir_admin)):
    if update.novo_status_id in (4, 6) and not update.causa_raiz_id: raise HTTPException(status_code=400, detail="Causa raiz obrigatória.")
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbTAREFAS SET STATUS_ID = :status, TIPO_ID = :tipo, TECNICO_ID = :tec, CAUSA_RAIZ_ID = :causa, DATA_ULTIMA_ATUALIZACAO = GETDATE() WHERE TAREFA_ID = :id"), {"id": tarefa_id, "status": update.novo_status_id, "tipo": update.novo_tipo_id, "tec": update.novo_tecnico_id, "causa": update.causa_raiz_id})
        res_hist = conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA) OUTPUT INSERTED.HISTORICO_ID VALUES (:tarefa_id, :usuario_acao, :status, :comentario, GETDATE())"), {"tarefa_id": tarefa_id, "usuario_acao": usuario["id"], "status": update.novo_status_id, "comentario": update.comentario})
        historico_id = res_hist.fetchone()[0]
    return {"message": "Atualizado", "historico_id": historico_id}

@app.post("/api/tarefas/{tarefa_id}/anexar")
async def anexar_arquivo(tarefa_id: int, historico_id: Optional[int] = Form(None), file: UploadFile = File(...), usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        t = conn.execute(text("SELECT SOLICITANTE_ID FROM tbTAREFAS WHERE TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
    if not t or (usuario.get("perfil") not in PERFIS_ADMIN and t.SOLICITANTE_ID != usuario["id"]): raise HTTPException(403)
    nome_salvo = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
    with open(os.path.join(UPLOAD_DIR, nome_salvo), "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tbTAREFA_ANEXO (TAREFA_ID, HISTORICO_ID, NOME_ORIGINAL, NOME_SALVO, DATA_HORA) VALUES (:t_id, :h_id, :nome_orig, :nome_salvo, GETDATE())"), {"t_id": tarefa_id, "h_id": historico_id, "nome_orig": file.filename, "nome_salvo": nome_salvo})
    return {"status": "sucesso"}