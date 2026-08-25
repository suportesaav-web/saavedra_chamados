from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import text
from typing import Dict
import bcrypt
import logging

from database import engine
from schemas import LoginRequest, AlterarSenhaRequest

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])
logger = logging.getLogger("SaavedraChamadosAuditoria")

PERFIS_ADMIN = {"Admin", "Gestor", "Tecnico"}

def hash_senha(senha_plana: str) -> str:
    return bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha_plana.encode('utf-8'), senha_hash.encode('utf-8'))
    except Exception:
        return False

def get_usuario_sessao(request: Request) -> Dict:
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return user

def exigir_admin(usuario: Dict = Depends(get_usuario_sessao)) -> Dict:
    if usuario.get("perfil") not in PERFIS_ADMIN:
        raise HTTPException(status_code=403, detail="Acesso restrito")
    return usuario

@router.post("/login")
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

@router.get("/me")
def get_current_user(usuario: dict = Depends(get_usuario_sessao)):
    return usuario

@router.get("/logout")
def logout(request: Request, usuario: dict = Depends(get_usuario_sessao)):
    logger.info(f"🚪 [LOGOUT] Usuário #{usuario.get('id')} encerrou a sessão.")
    request.session.clear()
    return {"message": "Sessão encerrada"}

@router.post("/alterar-senha")
def alterar_senha(request: Request, data: AlterarSenhaRequest, usuario: dict = Depends(get_usuario_sessao)):
    with engine.connect() as conn:
        user = conn.execute(text("SELECT SENHA_HASH FROM tbUSUARIO WHERE USUARIO_ID = :id"), {"id": usuario["id"]}).fetchone()
    if not user or not verificar_senha(data.senha_atual.strip(), user.SENHA_HASH):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    with engine.begin() as conn:
        conn.execute(text("UPDATE tbUSUARIO SET SENHA_HASH = :h WHERE USUARIO_ID = :id"), {"h": hash_senha(data.nova_senha.strip()), "id": usuario["id"]})
    logger.info(f"🔑 [SENHA ALTERADA] Usuário #{usuario['id']} alterou a sua senha com sucesso.")
    return {"status": "sucesso"}
