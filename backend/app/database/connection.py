import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def database_url() -> str:
    user = os.getenv("POSTGRES_USER", "salescast")
    password = os.getenv("POSTGRES_PASSWORD", "salescast")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "salescast")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_engine(retries: int = 15, delay: float = 2.0) -> Engine:
    """Create an engine and wait until PostgreSQL accepts connections."""
    engine = create_engine(database_url(), pool_pre_ping=True)
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception:
            if attempt == retries:
                raise
            time.sleep(delay)
    return engine
