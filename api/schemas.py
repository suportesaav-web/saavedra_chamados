from pydantic import BaseModel
from typing import Optional

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
    nota_interna: bool = False

class RespostaSolicitanteRequest(BaseModel): 
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
