from sqlalchemy import create_engine
from config import CONN_STR
engine = create_engine(
    CONN_STR,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=1800
)
