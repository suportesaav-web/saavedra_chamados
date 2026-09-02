import os
import shutil
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form, BackgroundTasks
from sqlalchemy import text
import logging

from database import engine
from schemas import TarefaCreate, TarefaUpdate, RespostaSolicitanteRequest
from .auth import get_usuario_sessao, exigir_admin, PERFIS_ADMIN
from utils import formatar_data_segura, enviar_email_abertura, enviar_email_atualizacao, enviar_email_atribuicao_tecnico

router = APIRouter(prefix="/api", tags=["Tarefas e Fila"])
logger = logging.getLogger("SaavedraChamadosAuditoria")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
UPLOAD_DIR = os.path.join(ROOT_DIR, "uploads")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def processar_fila_com_filtros(base_query: str, count_query: str, params: dict, status_id: Optional[int], prioridade_id: Optional[int], tipo_id: Optional[int], sla_filtro: Optional[str], data_inicio: Optional[str], data_fim: Optional[str], user_id_filtro: Optional[int] = None, tecnico_id_filtro: Optional[int] = None, sem_tecnico: bool = False, apenas_nao_avaliados: bool = False, pesquisa: Optional[str] = None, criticos_ativos: bool = False):
    where_conds = []
    
    if user_id_filtro is not None: 
        where_conds.append("T.SOLICITANTE_ID = :user_id_filtro")
        params["user_id_filtro"] = user_id_filtro
    if tecnico_id_filtro is not None: 
        where_conds.append("T.TECNICO_ID = :tecnico_id_filtro")
        params["tecnico_id_filtro"] = tecnico_id_filtro
    if sem_tecnico: 
        where_conds.extend(["T.TECNICO_ID IS NULL", "T.STATUS_ID NOT IN (4,6)"])
    if apenas_nao_avaliados:
        where_conds.extend(["T.STATUS_ID = 4", "(T.NOTA_CSAT IS NULL OR T.NOTA_CSAT = 0)"])
    if criticos_ativos:
        where_conds.append("T.STATUS_ID NOT IN (4,6)")
        
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

    if pesquisa:
        conds = ["T.TITULO LIKE :pesq_str"]
        params["pesq_str"] = f"%{pesquisa}%"
        if pesquisa.isdigit():
            conds.append("T.TAREFA_ID = :pesq_id")
            params["pesq_id"] = int(pesquisa)
        where_conds.append("(" + " OR ".join(conds) + ")")

    where_clause = " WHERE " + " AND ".join(where_conds) if where_conds else ""
    
    with engine.connect() as conn:
        total_items = conn.execute(text(f"{count_query} {where_clause}"), params).scalar() or 0
        ordem = " ORDER BY CASE WHEN T.STATUS_ID IN (4,6) THEN 1 ELSE 0 END ASC, T.PRIORIDADE_ID ASC, T.DATA_LIMITE_SLA ASC" if user_id_filtro is None else " ORDER BY T.DATA_HORA DESC"
        rows = conn.execute(text(f"{base_query} {where_clause} {ordem} OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"), params).fetchall()
        
    return {"dados": [{"id": r[0], "titulo": r[1], "status": r[2], "solicitante": r[3], "tecnico": r[4], "data_limite_sla": formatar_data_segura(r[5]), "status_id": r[6], "prioridade_id": r[7]} for r in rows], "paginas": (total_items + params["limit"] - 1) // params["limit"]}

@router.get("/meus-chamados")
def listar_meus_chamados(request: Request, page: int = 1, limit: int = 20, status_id: Optional[int] = None, tipo_id: Optional[int] = None, prioridade_id: Optional[int] = None, sla_filtro: Optional[str] = None, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, sem_tecnico: bool = False, pendente_csat: bool = False, pesquisa: Optional[str] = None, criticos_ativos: bool = False):
    usuario = request.session.get("user")
    if not usuario: raise HTTPException(status_code=401, detail="Não autorizado")
    usuario_id = usuario.get("id") or usuario.get("usuario_id")
    base = "SELECT T.TAREFA_ID, T.TITULO, S.STATUS_NOME, U.NOME, TEC.NOME, T.DATA_LIMITE_SLA, T.STATUS_ID, T.PRIORIDADE_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID"
    return processar_fila_com_filtros(base, "SELECT COUNT(*) FROM tbTAREFAS T", {"offset": (page - 1) * limit, "limit": limit}, status_id=status_id, prioridade_id=prioridade_id, tipo_id=tipo_id, sla_filtro=sla_filtro, data_inicio=data_inicio, data_fim=data_fim, user_id_filtro=usuario_id, tecnico_id_filtro=None, sem_tecnico=sem_tecnico, apenas_nao_avaliados=pendente_csat, pesquisa=pesquisa, criticos_ativos=criticos_ativos)

@router.get("/tarefas")
def get_tarefas(page: int = 1, limit: int = 20, visao_equipe: bool = False, sem_tecnico: bool = False, meus_pessoais: bool = False, status_id: Optional[int] = None, tipo_id: Optional[int] = None, prioridade_id: Optional[int] = None, sla_filtro: Optional[str] = None, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, pesquisa: Optional[str] = None, criticos_ativos: bool = False, usuario: dict = Depends(exigir_admin)):
    base = "SELECT T.TAREFA_ID, T.TITULO, S.STATUS_NOME, U.NOME, TEC.NOME, T.DATA_LIMITE_SLA, T.STATUS_ID, T.PRIORIDADE_ID FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID"
    user_id_filtro = usuario["id"] if meus_pessoais else None
    tecnico_filtro = None if (visao_equipe or sem_tecnico or meus_pessoais) else usuario["id"]
    return processar_fila_com_filtros(base, "SELECT COUNT(*) FROM tbTAREFAS T", {"offset": (page - 1) * limit, "limit": limit}, status_id=status_id, prioridade_id=prioridade_id, tipo_id=tipo_id, sla_filtro=sla_filtro, data_inicio=data_inicio, data_fim=data_fim, user_id_filtro=user_id_filtro, tecnico_id_filtro=tecnico_filtro, sem_tecnico=sem_tecnico, pesquisa=pesquisa, criticos_ativos=criticos_ativos)

@router.get("/tarefas/{tarefa_id}")
def get_tarefa_detalhe(tarefa_id: int, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT T.TAREFA_ID, T.TITULO, T.DESCRICAO, T.DATA_HORA, T.DATA_LIMITE_SLA, S.STATUS_NOME, T.STATUS_ID, U.NOME, T.SOLICITANTE_ID, TEC.NOME, T.TECNICO_ID, TIP.TIPO_NOME, T.TIPO_ID, T.CAUSA_RAIZ_ID, T.NOTA_CSAT FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbUSUARIO TEC ON T.TECNICO_ID = TEC.USUARIO_ID LEFT JOIN tbTIPO TIP ON T.TIPO_ID = TIP.TIPO_ID WHERE T.TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
        if not r: raise HTTPException(status_code=404, detail="Chamado não encontrado.")
        
        if usuario.get("perfil") not in PERFIS_ADMIN and r[8] != usuario["id"]:
            raise HTTPException(status_code=403, detail="Você não tem permissão para visualizar este chamado.")
            
        anexos = conn.execute(text("SELECT ANEXO_ID, NOME_ORIGINAL, NOME_SALVO FROM tbTAREFA_ANEXO WHERE TAREFA_ID = :id AND HISTORICO_ID IS NULL"), {"id": tarefa_id}).fetchall()
    return {"id": r[0], "titulo": r[1], "descricao": r[2], "data_hora": formatar_data_segura(r[3]), "data_limite_sla": formatar_data_segura(r[4]), "status_nome": r[5], "status_id": r[6], "solicitante_nome": r[7], "solicitante_id": r[8], "tecnico_nome": r[9], "tecnico_id": r[10], "tipo_nome": r[11], "tipo_id": r[12], "causa_raiz_id": r[13], "nota_csat": r[14], "anexos": [{"id": a.ANEXO_ID, "nome_original": a.NOME_ORIGINAL, "nome_salvo": a.NOME_SALVO} for a in anexos]}

@router.get("/tarefas/{tarefa_id}/historico")
def get_tarefa_historico(tarefa_id: int, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        t = conn.execute(text("SELECT SOLICITANTE_ID FROM tbTAREFAS WHERE TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
        if not t: raise HTTPException(status_code=404)
        if usuario.get("perfil") not in PERFIS_ADMIN and t.SOLICITANTE_ID != usuario["id"]: raise HTTPException(status_code=403)
        
        query = "SELECT H.HISTORICO_ID, H.DATA_HORA, U.NOME, S.STATUS_NOME, H.COMENTARIO, A.NOME_ORIGINAL, A.NOME_SALVO, H.NOTA_INTERNA FROM tbTAREFA_HISTORICO H LEFT JOIN tbUSUARIO U ON H.USUARIO_ID = U.USUARIO_ID LEFT JOIN tbSTATUS S ON H.STATUS_ID_NA_OCASIAO = S.STATUS_ID LEFT JOIN tbTAREFA_ANEXO A ON H.HISTORICO_ID = A.HISTORICO_ID WHERE H.TAREFA_ID = :id"
        if usuario.get("perfil") not in PERFIS_ADMIN: query += " AND (H.NOTA_INTERNA = 0 OR H.NOTA_INTERNA IS NULL)"
        query += " ORDER BY H.DATA_HORA ASC"
        rows = conn.execute(text(query), {"id": tarefa_id}).fetchall()
        return [{"id": r[0], "data_hora": formatar_data_segura(r[1]), "usuario_nome": r[2], "status_nome": r[3], "comentario": r[4], "anexo_nome": r[5], "anexo_salvo": r[6], "nota_interna": r[7]} for r in rows]

@router.post("/tarefas")
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
    logger.info(f"🎫 [NOVO CHAMADO] Ticket #{novo_id} registrado pelo usuário #{tarefa.solicitante_id}.")
    if solicitante and solicitante.EMAIL: background_tasks.add_task(enviar_email_abertura, solicitante.EMAIL, solicitante.NOME, novo_id, tarefa.titulo)
    if tecnico_id_final:
        with engine.connect() as conn:
            tec = conn.execute(text("SELECT NOME, EMAIL FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": tecnico_id_final}).fetchone()
        if tec and tec.EMAIL:
            solic_nome = solicitante.NOME if solicitante else "N/A"
            background_tasks.add_task(enviar_email_atribuicao_tecnico, tec.EMAIL, tec.NOME, novo_id, tarefa.titulo, solic_nome)
    return {"message": "Criado", "id": novo_id}

@router.put("/tarefas/{tarefa_id}")
def update_tarefa(tarefa_id: int, update: TarefaUpdate, background_tasks: BackgroundTasks, usuario: dict = Depends(exigir_admin)):
    if update.novo_status_id in (4, 6) and not update.causa_raiz_id: 
        raise HTTPException(status_code=400, detail="Causa raiz obrigatória.")
    
    with engine.begin() as conn:
        tec_antigo = conn.execute(text("SELECT TECNICO_ID FROM tbTAREFAS WHERE TAREFA_ID = :id"), {"id": tarefa_id}).scalar()
        
        status_final = update.novo_status_id
        if update.novo_tecnico_id is None and tec_antigo is not None:
            ultimo_status = conn.execute(text("SELECT TOP 1 STATUS_ID_NA_OCASIAO FROM tbTAREFA_HISTORICO WHERE TAREFA_ID = :id AND STATUS_ID_NA_OCASIAO != :status_atual ORDER BY HISTORICO_ID DESC"), {"id": tarefa_id, "status_atual": update.novo_status_id}).scalar()
            if ultimo_status:
                status_final = ultimo_status

        conn.execute(text("UPDATE tbTAREFAS SET STATUS_ID = :status, TIPO_ID = :tipo, TECNICO_ID = :tec, CAUSA_RAIZ_ID = :causa, PRIORIDADE_ID = ISNULL(:prio, PRIORIDADE_ID), DATA_ULTIMA_ATUALIZACAO = GETDATE() WHERE TAREFA_ID = :id"), {"id": tarefa_id, "status": status_final, "tipo": update.novo_tipo_id, "tec": update.novo_tecnico_id, "causa": update.causa_raiz_id, "prio": update.nova_prioridade_id})
        interna_flag = 1 if update.nota_interna else 0
        historico_id = conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) OUTPUT INSERTED.HISTORICO_ID VALUES (:tarefa_id, :usuario_acao, :status, :comentario, GETDATE(), :interna)"), {"tarefa_id": tarefa_id, "usuario_acao": usuario["id"], "status": status_final, "comentario": update.comentario, "interna": interna_flag}).fetchone()[0]
        ticket = conn.execute(text("SELECT T.TITULO, S.STATUS_NOME, U.NOME, U.EMAIL FROM tbTAREFAS T JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID WHERE T.TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
    
    logger.info(f"🔄 [CHAMADO MOVIMENTADO] Ticket #{tarefa_id} alterado pelo técnico #{usuario['id']} para status #{status_final}.")
    if ticket and ticket.EMAIL and not update.nota_interna: 
        background_tasks.add_task(enviar_email_atualizacao, ticket.EMAIL, ticket.NOME, tarefa_id, ticket.STATUS_NOME, update.comentario, update.novo_status_id)
        
    if update.novo_tecnico_id and update.novo_tecnico_id != tec_antigo:
        with engine.connect() as conn:
            tec_novo = conn.execute(text("SELECT NOME, EMAIL FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": update.novo_tecnico_id}).fetchone()
        if tec_novo and tec_novo.EMAIL:
            solic_nome = ticket.NOME if ticket else "N/A"
            titulo_ticket = ticket.TITULO if ticket else f"Chamado #{tarefa_id}"
            background_tasks.add_task(enviar_email_atribuicao_tecnico, tec_novo.EMAIL, tec_novo.NOME, tarefa_id, titulo_ticket, solic_nome)

    return {"message": "Atualizado", "historico_id": historico_id}

@router.post("/tarefas/{tarefa_id}/responder")
def responder_tarefa(tarefa_id: int, resp: RespostaSolicitanteRequest, background_tasks: BackgroundTasks, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        t = conn.execute(text("SELECT SOLICITANTE_ID, STATUS_ID FROM tbTAREFAS WHERE TAREFA_ID = :id"), {"id": tarefa_id}).fetchone()
    if not t: raise HTTPException(404, detail="Chamado não encontrado")
    if usuario.get("perfil") not in PERFIS_ADMIN and t.SOLICITANTE_ID != usuario["id"]: raise HTTPException(403, detail="Acesso negado")
    if not resp.comentario.strip(): raise HTTPException(400, detail="O comentário é obrigatório")

    with engine.begin() as conn:
        conn.execute(text("UPDATE tbTAREFAS SET DATA_ULTIMA_ATUALIZACAO = GETDATE() WHERE TAREFA_ID = :id"), {"id": tarefa_id})
        historico_id = conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) OUTPUT INSERTED.HISTORICO_ID VALUES (:tarefa_id, :usuario_acao, :status, :comentario, GETDATE(), 0)"), {"tarefa_id": tarefa_id, "usuario_acao": usuario["id"], "status": t.STATUS_ID, "comentario": resp.comentario.strip()}).fetchone()[0]
    logger.info(f"💬 [RESPOSTA REGISTRADA] Usuário #{usuario['id']} respondeu no Ticket #{tarefa_id}.")
    return {"message": "Resposta inserida com sucesso", "historico_id": historico_id}

@router.post("/tarefas/{tarefa_id}/anexar")
def anexar_arquivo(tarefa_id: int, historico_id: Optional[int] = Form(None), files: List[UploadFile] = File(...), usuario: dict = Depends(get_usuario_sessao)):
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
    logger.info(f"📎 [ANEXO SALVO] Ficheiro adicionado ao Ticket #{tarefa_id}.")
    return {"status": "sucesso"}

@router.post("/tarefas/{tarefa_id}/avaliar")
def avaliar_chamado(tarefa_id: int, nota: int, request: Request, usuario: dict = Depends(get_usuario_sessao)):
    if not (1 <= nota <= 5): raise HTTPException(status_code=400, detail="A nota deve ser entre 1 e 5.")
    desc_notas = {1: "1/5 - Insatisfeito 😞", 2: "2/5 - Regular 😕", 3: "3/5 - Neutro 😐", 4: "4/5 - Satisfeito 😊", 5: "5/5 - Excelente 🤩"}
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbTAREFAS SET NOTA_CSAT = :nota WHERE TAREFA_ID = :id"), {"nota": nota, "id": tarefa_id})
        conn.execute(text("INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA, NOTA_INTERNA) VALUES (:id, :u_id, 4, :comentario, GETDATE(), 0)"), {"id": tarefa_id, "u_id": usuario["id"], "comentario": f"⭐ Avaliação CSAT registrada pelo usuário: {desc_notas.get(nota, f'{nota}/5')}"})
    logger.info(f"⭐ [CSAT AVALIADO] Ticket #{tarefa_id} recebeu nota {nota} do usuário #{usuario['id']}.")
    return {"status": "sucesso", "mensagem": "Obrigado por avaliar o atendimento!"}
