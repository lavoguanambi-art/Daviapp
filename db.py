# Caminho do arquivo: /Users/gustavomontalvao/Downloads/APP_DAVI_streamlit_v8_1_charts-2/db.py
# --- DB bootstrap seguro (funciona local e no Streamlit Cloud) ---
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

try:
    # usa o módulo db.py se existir
    from db import engine, SessionLocal, Base  # type: ignore
except Exception:
    # fallback integrado
    DB_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
    engine = create_engine(
        DB_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    Base = declarative_base()