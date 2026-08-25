from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
import logging

from database import engine
from schemas import ItemCadastro, UsuarioCreate, UsuarioUpdate
from .auth import get_usuario_sessao, exigir_admin, hash_senha

router = APIRouter(tags=["Cadastros e Usuários"])
logger = logging.getLogger("SaavedraChamadosAuditoria")

TABELAS_PERMITIDAS = {
    "status": {"tabela": "tbSTATUS", "id": "STATUS_ID", "nome": "STATUS_NOME"},
    "prioridade": {"tabela": "tbPRIORIDADE", "id": "PRIORIDADE_ID", "nome": "PRIORIDADE_NOME"},
    "tipo": {"tabela": "tbTIPO", "id": "TIPO_ID", "nome": "TIPO_NOME"},
    "causa_raiz": {"tabela": "tbCAUSA_RAIZ", "id": "CAUSA_ID", "nome": "CAUSA_NOME"},
    "setor": {"tabela": "tbSETOR", "id": "SETOR_ID", "nome": "SETOR_NOME"}
}

@router.get("/api/cadastros/{tipo_cadastro}")
def get_cadastros(tipo_cadastro: str, usuario: dict = Depends(get_usuario_sessao)):
    if tipo_cadastro not in TABELAS_PERMITIDAS:
        raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT {cfg['id']}, {cfg['nome']} FROM {cfg['tabela']} WHERE (ATIVO = 1 OR ATIVO IS NULL)")).fetchall()
        if tipo_cadastro == "prioridade":
            return [{"id": r[0], "nome": "Sem Prioridade" if r[0] == 1 else r[1]} for r in rows]
        return [{"id": r[0], "nome": r[1]} for r in rows]

@router.post("/api/cadastros/{tipo_cadastro}")
def create_cadastro(tipo_cadastro: str, item: ItemCadastro, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS:
        raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO {cfg['tabela']} ({cfg['nome']}) VALUES (:nome)"), {"nome": item.descricao})
    logger.info(f"📝 [CADASTRO CRIADO] Usuário #{usuario['id']} criou '{item.descricao}' em {cfg['tabela']}.")
    return {"message": "Criado"}

@router.put("/api/cadastros/{tipo_cadastro}/{id_registro}")
def update_cadastro(tipo_cadastro: str, id_registro: int, item: ItemCadastro, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS:
        raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE {cfg['tabela']} SET {cfg['nome']} = :nome WHERE {cfg['id']} = :id"), {"nome": item.descricao, "id": id_registro})
    logger.info(f"✏️ [CADASTRO ATUALIZADO] Usuário #{usuario['id']} alterou registro #{id_registro} de {cfg['tabela']}.")
    return {"message": "Atualizado"}

@router.delete("/api/cadastros/{tipo_cadastro}/{id_registro}")
def delete_cadastro(tipo_cadastro: str, id_registro: int, usuario: dict = Depends(exigir_admin)):
    if tipo_cadastro not in TABELAS_PERMITIDAS:
        raise HTTPException(404)
    cfg = TABELAS_PERMITIDAS[tipo_cadastro]
    with engine.begin() as conn:
        try:
            conn.execute(text(f"UPDATE {cfg['tabela']} SET ATIVO = 0 WHERE {cfg['id']} = :id"), {"id": id_registro})
        except Exception:
            conn.execute(text(f"DELETE FROM {cfg['tabela']} WHERE {cfg['id']} = :id"), {"id": id_registro})
    logger.info(f"🗑️ [CADASTRO INATIVADO] Usuário #{usuario['id']} inativou registro #{id_registro} de {cfg['tabela']}.")
    return {"message": "Inativado"}

@router.get("/api/usuarios")
def get_usuarios(usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        return [{"id": r[0], "nome": r[1], "email": r[2], "ad_login": r[3], "perfil": r[4], "setor": r[5], "setor_id": r[6], "nivel_acesso": r[7]} for r in conn.execute(text("SELECT U.USUARIO_ID, U.NOME, U.EMAIL, U.AD_LOGIN, U.PERFIL, S.SETOR_NOME, U.SETOR_ID, U.NIVEL_ACESSO FROM tbUSUARIO U LEFT JOIN tbSETOR S ON U.SETOR_ID = S.SETOR_ID WHERE (U.ATIVO = 1 OR U.ATIVO IS NULL) ORDER BY U.NOME ASC")).fetchall()]

@router.get("/api/usuarios/tecnicos")
def get_usuarios_tecnicos(usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        return [{"id": r[0], "nome": r[1]} for r in conn.execute(text("SELECT USUARIO_ID, NOME FROM tbUSUARIO WHERE PERFIL IN ('Admin', 'Gestor', 'Tecnico') AND (ATIVO = 1 OR ATIVO IS NULL) ORDER BY NOME ASC")).fetchall()]

@router.post("/api/usuarios")
def create_usuario(u: UsuarioCreate, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tbUSUARIO (NOME, EMAIL, AD_LOGIN, SETOR_ID, PERFIL, NIVEL_ACESSO, SENHA_HASH, ATIVO) VALUES (:n, :e, :a, :s, :p, :na, :senha, 1)"), {"n": u.nome, "e": u.email, "a": u.ad_login, "s": u.setor_id, "p": u.perfil, "na": u.nivel_acesso, "senha": hash_senha(u.senha if u.senha else "saavedra123")})
    logger.info(f"👤 [USUÁRIO CRIADO] Administrador #{usuario['id']} criou o usuário '{u.email}'.")
    return {"message": "Criado"}

@router.put("/api/usuarios/{id_usuario}")
def update_usuario(id_usuario: int, u: UsuarioUpdate, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbUSUARIO SET NOME = :n, EMAIL = :e, AD_LOGIN = :a, SETOR_ID = :s, PERFIL = :p, NIVEL_ACESSO = :na WHERE USUARIO_ID = :id"), {"n": u.nome, "e": u.email, "a": u.ad_login, "s": u.setor_id, "p": u.perfil, "na": u.nivel_acesso, "id": id_usuario})
    logger.info(f"👤 [USUÁRIO ATUALIZADO] Administrador #{usuario['id']} editou usuário ID #{id_usuario}.")
    return {"message": "Atualizado"}

@router.delete("/api/usuarios/{id_usuario}")
def delete_usuario(id_usuario: int, usuario: dict = Depends(exigir_admin)):
    with engine.begin() as conn:
        try:
            conn.execute(text("UPDATE tbUSUARIO SET ATIVO = 0 WHERE USUARIO_ID = :id"), {"id": id_usuario})
        except Exception:
            conn.execute(text("DELETE FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": id_usuario})
    logger.info(f"🚫 [USUÁRIO DESATIVADO] Administrador #{usuario['id']} inativou usuário ID #{id_usuario}.")
    return {"message": "Inativado"}
