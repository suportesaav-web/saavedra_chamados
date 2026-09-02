import os
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

SECRET_KEY = os.environ.get("SAAVEDRA_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "chave_secreta_padrao_segura_123!@#"

DB_USER = os.environ.get("SAAVEDRA_DB_USER", "chamados")
DB_PASS = os.environ.get("SAAVEDRA_DB_PASS")
if not DB_PASS:
    raise RuntimeError("Erro: A variável de ambiente SAAVEDRA_DB_PASS não foi configurada no arquivo .env!")

DB_HOST = os.environ.get("SAAVEDRA_DB_HOST", "10.0.0.252")
DB_NAME = os.environ.get("SAAVEDRA_DB_NAME", "GestaoChamados")
CONN_STR = f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?driver=SQL+Server"

SMTP_HOST = os.environ.get("SAAVEDRA_SMTP_HOST")
SMTP_PORT = int(os.environ.get("SAAVEDRA_SMTP_PORT", 587))
SMTP_USER = os.environ.get("SAAVEDRA_SMTP_USER")
SMTP_PASS = os.environ.get("SAAVEDRA_SMTP_PASS")
SMTP_FROM = os.environ.get("SAAVEDRA_SMTP_FROM")

FRONTEND_URL = os.environ.get("SAAVEDRA_FRONTEND_URL", "http://10.0.0.252:8082")
