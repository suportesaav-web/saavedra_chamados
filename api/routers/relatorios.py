from fastapi import APIRouter, Depends
from sqlalchemy import text
from typing import Optional
import logging

from database import engine
from .auth import get_usuario_sessao, PERFIS_ADMIN

router = APIRouter(tags=["Relatórios e KPIs"])
logger = logging.getLogger("SaavedraChamadosAuditoria")

@router.get("/api/relatorios/gerais")
def get_relatorios_gerais(data_inicio: Optional[str] = None, data_fim: Optional[str] = None, tecnico_nome: Optional[str] = None, status_nome: Optional[str] = None, setor_nome: Optional[str] = None, usuario: dict = Depends(get_usuario_sessao)):
    is_comum = usuario.get("perfil") not in PERFIS_ADMIN
    user_id = usuario.get("id")

    filtros = ""
    params = {}
    if data_inicio:
        filtros += " AND CAST(T.DATA_HORA AS DATE) >= :d_ini"
        params["d_ini"] = data_inicio
    if data_fim:
        filtros += " AND CAST(T.DATA_HORA AS DATE) <= :d_fim"
        params["d_fim"] = data_fim
    if tecnico_nome:
        filtros += " AND UT.NOME = :t_nome"
        params["t_nome"] = tecnico_nome
    if status_nome:
        filtros += " AND S.STATUS_NOME = :s_nome"
        params["s_nome"] = status_nome
    if setor_nome:
        filtros += " AND SETOR.SETOR_NOME = :set_nome"
        params["set_nome"] = setor_nome

    with engine.connect() as conn:
        if is_comum:
            params["uid"] = user_id
            return {
                "perfil_visao": "comum",
                "tipos": [{"label": r[0], "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(TP.TIPO_NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbTIPO TP ON T.TIPO_ID = TP.TIPO_ID LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID WHERE T.SOLICITANTE_ID = :uid {filtros} GROUP BY TP.TIPO_NOME"), params).fetchall()],
                "status": [{"label": r[0], "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(S.STATUS_NOME, 'Outros'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID WHERE T.SOLICITANTE_ID = :uid {filtros} GROUP BY S.STATUS_NOME"), params).fetchall()],
                "csats": [{"label": f"Nota {r[0]} ⭐️" if r[0] else "Pendente", "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(NOTA_CSAT, 0), COUNT(TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID WHERE T.SOLICITANTE_ID = :uid {filtros} GROUP BY NOTA_CSAT ORDER BY NOTA_CSAT ASC"), params).fetchall()]
            }
        
        where_admin = f"WHERE 1=1 {filtros}" if filtros else ""
        return {
            "perfil_visao": "admin",
            "setores": [{"label": r[0], "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(SETOR.SETOR_NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR SETOR ON U.SETOR_ID = SETOR.SETOR_ID LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID {where_admin} GROUP BY SETOR.SETOR_NOME"), params).fetchall()],
            "tipos": [{"label": r[0], "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(TP.TIPO_NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbTIPO TP ON T.TIPO_ID = TP.TIPO_ID LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR SETOR ON U.SETOR_ID = SETOR.SETOR_ID {where_admin} GROUP BY TP.TIPO_NOME"), params).fetchall()],
            "causas": [{"label": r[0], "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(C.CAUSA_NOME, 'Em Andamento'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbCAUSA_RAIZ C ON T.CAUSA_RAIZ_ID = C.CAUSA_ID LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR SETOR ON U.SETOR_ID = SETOR.SETOR_ID {where_admin} GROUP BY C.CAUSA_NOME"), params).fetchall()],
            "tecnicos": [{"label": r[0], "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(UT.NOME, 'Fila de Triagem'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR SETOR ON U.SETOR_ID = SETOR.SETOR_ID {where_admin} GROUP BY UT.NOME"), params).fetchall()],
            "usuarios_ranking": [{"label": r[0], "value": r[1]} for r in conn.execute(text(f"SELECT TOP 10 ISNULL(U.NOME, 'Não Informado'), COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR SETOR ON U.SETOR_ID = SETOR.SETOR_ID LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID {where_admin} GROUP BY U.NOME ORDER BY COUNT(T.TAREFA_ID) DESC"), params).fetchall()],
            "csats": [{"label": f"Nota {r[0]} ⭐️" if r[0] else "Não Avaliado", "value": r[1]} for r in conn.execute(text(f"SELECT ISNULL(NOTA_CSAT, 0), COUNT(TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR SETOR ON U.SETOR_ID = SETOR.SETOR_ID {where_admin} GROUP BY NOTA_CSAT ORDER BY NOTA_CSAT ASC"), params).fetchall()]
        }

@router.get("/api/kpis")
def get_kpis(visao_equipe: bool = False, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, tecnico_nome: Optional[str] = None, status_nome: Optional[str] = None, setor_nome: Optional[str] = None, usuario: dict = Depends(get_usuario_sessao)):
    is_admin = usuario.get("perfil") in PERFIS_ADMIN
    perfil = usuario.get("perfil")

    filtros = ""
    params = {}
    if data_inicio:
        filtros += " AND CAST(T.DATA_HORA AS DATE) >= :d_ini"
        params["d_ini"] = data_inicio
    if data_fim:
        filtros += " AND CAST(T.DATA_HORA AS DATE) <= :d_fim"
        params["d_fim"] = data_fim
    if tecnico_nome:
        filtros += " AND UT.NOME = :t_nome"
        params["t_nome"] = tecnico_nome
    if status_nome:
        filtros += " AND S.STATUS_NOME = :s_nome"
        params["s_nome"] = status_nome
    if setor_nome:
        filtros += " AND SETOR.SETOR_NOME = :set_nome"
        params["set_nome"] = setor_nome
    
    joins = "LEFT JOIN tbUSUARIO UT ON T.TECNICO_ID = UT.USUARIO_ID LEFT JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID LEFT JOIN tbSETOR SETOR ON U.SETOR_ID = SETOR.SETOR_ID "

    if perfil == "Comum":
        user_id = usuario["id"]
        params["uid"] = user_id
        with engine.connect() as conn:
            nao_avaliados = conn.execute(text(f"SELECT COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID {joins} WHERE T.SOLICITANTE_ID = :uid AND T.STATUS_ID = 4 AND (T.NOTA_CSAT IS NULL OR T.NOTA_CSAT = 0) {filtros}"), params).scalar() or 0
            
            res_status = conn.execute(text(f"""
                SELECT S.STATUS_ID, S.STATUS_NOME, COUNT(T2.TAREFA_ID) 
                FROM tbSTATUS S 
                LEFT JOIN (
                    SELECT T.TAREFA_ID, T.STATUS_ID FROM tbTAREFAS T
                    LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID
                    {joins}
                    WHERE T.SOLICITANTE_ID = :uid {filtros}
                ) T2 ON S.STATUS_ID = T2.STATUS_ID
                WHERE (S.ATIVO = 1 OR S.ATIVO IS NULL)
                GROUP BY S.STATUS_ID, S.STATUS_NOME
                ORDER BY S.STATUS_ID ASC
            """), params).fetchall()
            
        return {
            "perfil": "Comum",
            "concluidos_sem_avaliacao": nao_avaliados,
            "status_dinamicos": [{"id": r[0], "nome": r[1], "qtd": r[2]} for r in res_status]
        }

    where_clause = f"WHERE 1=1 {filtros}"
    if not visao_equipe:
        where_clause = f"WHERE T.TECNICO_ID = :user_id {filtros}"
        params["user_id"] = usuario["id"]

    with engine.connect() as conn:
        res_esp = conn.execute(text(f"SELECT SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) < GETDATE() THEN 1 ELSE 0 END), SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME) >= GETDATE() AND DATEDIFF(MINUTE, GETDATE(), TRY_CAST(T.DATA_LIMITE_SLA AS DATETIME)) <= 120 THEN 1 ELSE 0 END), SUM(CASE WHEN T.STATUS_ID NOT IN (4,6) AND T.PRIORIDADE_ID = 1 THEN 1 ELSE 0 END) FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID {joins} {where_clause}"), params).fetchone() 
        
        res_status = conn.execute(text(f"""
            SELECT S.STATUS_ID, S.STATUS_NOME, COUNT(T2.TAREFA_ID) 
            FROM tbSTATUS S 
            LEFT JOIN (
                SELECT T.TAREFA_ID, T.STATUS_ID FROM tbTAREFAS T
                LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID
                {joins}
                {where_clause}
            ) T2 ON S.STATUS_ID = T2.STATUS_ID
            WHERE (S.ATIVO = 1 OR S.ATIVO IS NULL)
            GROUP BY S.STATUS_ID, S.STATUS_NOME
            ORDER BY S.STATUS_ID ASC
        """), params).fetchall()
        
        triagem = conn.execute(text(f"SELECT COUNT(T.TAREFA_ID) FROM tbTAREFAS T LEFT JOIN tbSTATUS S ON T.STATUS_ID = S.STATUS_ID {joins} WHERE T.STATUS_ID NOT IN (4,6) AND T.TECNICO_ID IS NULL {filtros}"), params).scalar() or 0 if visao_equipe else 0

    return {
        "perfil": "Tecnico",
        "sla_estourado": res_esp[0] or 0, 
        "sla_atencao": res_esp[1] or 0, 
        "criticos": res_esp[2] or 0, 
        "aguardando_triagem": triagem, 
        "status_dinamicos": [{"id": r[0], "nome": r[1], "qtd": r[2]} for r in res_status]
    }
