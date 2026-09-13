import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


SERVER_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = SERVER_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings:
    APP_NAME = os.getenv(
        "APP_NAME",
        "SISTEMA CAMARA - API CENTRAL"
    )

    API_PREFIX = os.getenv(
        "API_PREFIX",
        "/api"
    ).rstrip("/")

    PG_HOST = os.getenv(
        "PG_HOST",
        "127.0.0.1"
    )

    PG_PORT = int(
        os.getenv("PG_PORT", "5432")
    )

    PG_DATABASE = os.getenv(
        "PG_DATABASE",
        "contepersonas"
    )

    PG_USER = os.getenv(
        "PG_USER",
        "postgres"
    )

    PG_PASSWORD = os.getenv(
        "PG_PASSWORD",
        "postgres"
    )

    _DATABASE_URL_OVERRIDE = os.getenv(
        "DATABASE_URL",
        ""
    ).strip()

    _DEFAULT_POSTGRES_URL = (
        "postgresql+psycopg2://"
        f"{quote_plus(PG_USER)}:"
        f"{quote_plus(PG_PASSWORD)}@"
        f"{PG_HOST}:{PG_PORT}/"
        f"{quote_plus(PG_DATABASE)}"
    )

    DATABASE_URL = (
        _DATABASE_URL_OVERRIDE
        if _DATABASE_URL_OVERRIDE.startswith(
            ("postgresql://", "postgresql+psycopg2://")
        )
        else _DEFAULT_POSTGRES_URL
    )

    API_TOKEN = os.getenv(
        "API_TOKEN",
        ""
    ).strip()


settings = Settings()
