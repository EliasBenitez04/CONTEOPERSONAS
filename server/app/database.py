from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


DATABASE_URL = settings.DATABASE_URL

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    database_file = DATABASE_URL.replace(
        "sqlite:///",
        "",
        1
    )

    if database_file:
        Path(database_file).parent.mkdir(
            parents=True,
            exist_ok=True
        )

    connect_args = {
        "check_same_thread": False
    }


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args
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
