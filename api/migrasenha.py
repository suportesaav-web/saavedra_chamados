# migrar_senhas_para_hash.py
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text
import bcrypt  # Usando o pacote oficial diretamente

# 1. Carrega as variáveis do arquivo .env
load_dotenv()

# 2. Lê as variáveis do .env
DB_USER = os.environ.get("SAAVEDRA_DB_USER", "chamados")
DB_PASS = os.environ.get("SAAVEDRA_DB_PASS")
DB_HOST = os.environ.get("SAAVEDRA_DB_HOST", "10.0.0.252")
DB_NAME = os.environ.get("SAAVEDRA_DB_NAME", "GestaoChamados")

if not DB_PASS:
    raise RuntimeError("Erro: A variável SAAVEDRA_DB_PASS não foi encontrada no arquivo .env!")

# 3. Estabelece a conexão com o SQL Server
CONN_STR = f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?driver=SQL+Server"
engine = create_engine(CONN_STR)

def gerar_hash_seguro(senha_plana: str) -> str:
    """Gera um hash bcrypt seguro usando a biblioteca nativa"""
    senha_bytes = senha_plana.encode('utf-8')
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(senha_bytes, salt)
    return hash_bytes.decode('utf-8')

print("⏳ Conectando ao banco de dados e iniciando migração segura...")

with engine.begin() as conn:
    usuarios = conn.execute(text("SELECT USUARIO_ID, NOME, SENHA_HASH FROM tbUSUARIO")).fetchall()
    atualizados = 0
    
    for u in usuarios:
        senha_atual = u.SENHA_HASH
        nome_usuario = u.NOME
        
        # Se a senha já for um hash bcrypt válido, pula para não gerar hash duplo
        if senha_atual and len(senha_atual) == 60 and senha_atual.startswith(("$2b$", "$2a$")):
            continue
            
        # Define a senha plana que vamos converter (se estiver nula no banco, vira a padrão)
        senha_plana_para_converter = senha_atual if senha_atual else "saavedra123"
        
        # Se por algum erro a senha salva exceder 72 caracteres, reseta para a padrão para evitar falhas
        if len(senha_plana_para_converter.encode('utf-8')) > 72:
            print(f"⚠️ Usuário '{nome_usuario}' tinha um valor inválido/longo no banco. Resetando para padrão.")
            senha_plana_para_converter = "saavedra123"
            
        # Gera o hash limpo sem erros do passlib
        novo_hash = gerar_hash_seguro(senha_plana_para_converter)
        
        conn.execute(
            text("UPDATE tbUSUARIO SET SENHA_HASH = :h WHERE USUARIO_ID = :id"),
            {"h": novo_hash, "id": u.USUARIO_ID}
        )
        atualizados += 1

print(f"\n✅ Concluído com sucesso! {atualizados} senha(s) convertida(s) para bcrypt puro.")