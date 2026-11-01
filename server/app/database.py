import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_use_lifo=True,
    pool_size=max(1, int(os.getenv("DB_POOL_SIZE", "10"))),
    max_overflow=max(0, int(os.getenv("DB_MAX_OVERFLOW", "10"))),
    pool_timeout=max(1, int(os.getenv("DB_POOL_TIMEOUT", "15"))),
    pool_recycle=1800
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_database():
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()
