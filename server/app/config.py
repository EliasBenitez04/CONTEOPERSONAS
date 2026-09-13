import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


SERVER_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = SERVER_DIR / ".env"
load_dotenv(ENV_FILE)


def _bool_env(name: str, default: str = "0"):
    return os.getenv(name, default).strip().lower() in (
        "1", "true", "yes", "on"
    )


class Settings:
    APP_NAME = os.getenv(
        "APP_NAME",
        "SISTEMA CAMARA - API CENTRAL"
    )
    API_PREFIX = os.getenv("API_PREFIX", "/api").rstrip("/")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    ENABLE_DOCS = _bool_env("ENABLE_DOCS", "1")
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", "0")
    TRUSTED_HOSTS = [
        item.strip()
        for item in os.getenv("TRUSTED_HOSTS", "*").split(",")
        if item.strip()
    ] or ["*"]

    PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DATABASE = os.getenv("PG_DATABASE", "contepersonas")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

    _DATABASE_URL_OVERRIDE = os.getenv("DATABASE_URL", "").strip()
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

    # Token global solo para compatibilidad V2 / operaciones tecnicas antiguas.
    API_TOKEN = os.getenv("API_TOKEN", "").strip()

    SESSION_SECRET = os.getenv(
        "SESSION_SECRET",
        "cambiar-esta-clave-sistema-camara-2026"
    ).strip()
    SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
    ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "Administrador").strip()


settings = Settings()
