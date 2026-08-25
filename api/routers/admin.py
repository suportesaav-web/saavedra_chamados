from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import text
import logging

from database import engine
from schemas import SlaConfigRequest
from .auth import exigir_admin
from utils import enviar_email_lembrete_csat

router = APIRouter(prefix="/api/admin", tags=["Administração"])
logger = logging.getLogger("SaavedraChamadosAuditoria")

@router.get("/sla-matrix")
def get_sla_matrix(usuario: dict = Depends(exigir_admin)):
    with engine.connect() as conn:
        return [{"id": r[0], "prioridade": r[1], "tipo": r[2], "tempo_horas": r[3], "prioridade_id": r[4], "tipo_id": r[5]} 
                for r in conn.execute(text("SELECT M.SLA_ID, P.PRIORIDADE_NOME, TP.TIPO_NOME, M.TEMPO_HORAS, M.PRIORIDADE_ID, M.TIPO_ID FROM tbSLA_CONFIG M INNER JOIN tbPRIORIDADE P ON M.PRIORIDADE_ID = P.PRIORIDADE_ID INNER JOIN tbTIPO TP ON M.TIPO_ID = TP.TIPO_ID ORDER BY TP.TIPO_NOME, P.PRIORIDADE_ID ASC"))]

@router.put("/sla-matrix/{sla_id}")
def update_sla_matrix(sla_id: int, data: SlaConfigRequest, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbSLA_CONFIG SET TEMPO_HORAS = :horas WHERE SLA_ID = :id"), {"horas": data.tempo_horas, "id": sla_id})
    return {"status": "sucesso"}

@router.get("/csat-pendentes-count")
def get_csat_pendentes_count(usuario: dict = Depends(exigir_admin)):
    with engine.connect() as conn:
        qtd = conn.execute(text("""
            SELECT COUNT(T.TAREFA_ID) 
            FROM tbTAREFAS T
            JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID
            WHERE T.STATUS_ID = 4 
              AND (T.NOTA_CSAT IS NULL OR T.NOTA_CSAT = 0)
              AND U.EMAIL IS NOT NULL AND U.EMAIL LIKE '%@%'
        """)).scalar() or 0
    return {"total_pendentes": qtd}

@router.post("/reenviar-csat-pendentes")
def reenviar_csat_pendentes(background_tasks: BackgroundTasks, usuario: dict = Depends(exigir_admin)):
    with engine.connect() as conn:
        pendentes = conn.execute(text("""
            SELECT T.TAREFA_ID, T.TITULO, U.NOME, U.EMAIL 
            FROM tbTAREFAS T
            JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID
            WHERE T.STATUS_ID = 4 
              AND (T.NOTA_CSAT IS NULL OR T.NOTA_CSAT = 0)
              AND U.EMAIL IS NOT NULL AND U.EMAIL LIKE '%@%'
        """)).fetchall()
    
    enviados = 0
    for row in pendentes:
        t_id, titulo, u_nome, u_email = row[0], row[1], row[2], row[3]
        background_tasks.add_task(enviar_email_lembrete_csat, u_email, u_nome, t_id, titulo)
        enviados += 1
        
    logger.info(f"📧 [DISPARO CSAT] Administrador #{usuario['id']} solicitou o reenvio de {enviados} e-mails de avaliação CSAT pendentes.")
    return {"status": "sucesso", "total_disparados": enviados}
