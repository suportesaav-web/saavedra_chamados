from sqlalchemy import create_engine
from config import CONN_STR

engine = create_engine(CONN_STR, pool_pre_ping=True, pool_recycle=3600)
