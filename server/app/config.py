import os
from pathlib import Path

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

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///./data/server.db"
    )

    API_TOKEN = os.getenv(
        "API_TOKEN",
        ""
    ).strip()


settings = Settings()
