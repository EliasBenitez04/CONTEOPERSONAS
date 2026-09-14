import os

from dotenv import load_dotenv

from app.paths import CLIENT_DIR


ENV_FILE = CLIENT_DIR / ".env"
# El .env local debe ser la fuente de verdad del cliente. override=True evita
# que variables antiguas de Windows/PowerShell oculten CLIENT_ID/CLIENT_TOKEN
# recién configurados.
load_dotenv(ENV_FILE, override=True)


class Settings:
    APP_VERSION = os.getenv("APP_VERSION", "3.0.0")

    CAMERA_NAME = os.getenv("CAMERA_NAME", "CAMARA_01")
    CAMERA_RTSP_URL = os.getenv("CAMERA_RTSP_URL", "")
    RECONNECT_SECONDS = int(os.getenv("RECONNECT_SECONDS", "3"))
    BRANCH_ID = int(os.getenv("BRANCH_ID", "1"))

    API_URL = os.getenv(
        "API_URL",
        "http://127.0.0.1:8000/api"
    ).rstrip("/")

    CLIENT_ID = os.getenv("CLIENT_ID", "").strip()
    CLIENT_TOKEN = os.getenv("CLIENT_TOKEN", "").strip()
    API_TOKEN = os.getenv("API_TOKEN", "").strip()

    API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "5"))
    SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "5"))
    SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "100"))
    HEARTBEAT_INTERVAL_SECONDS = int(
        os.getenv("HEARTBEAT_INTERVAL_SECONDS", "20")
    )
    REMOTE_CONFIG_INTERVAL_SECONDS = int(
        os.getenv("REMOTE_CONFIG_INTERVAL_SECONDS", "30")
    )

    MANAGED_CLIENT = bool(CLIENT_ID and CLIENT_TOKEN)


settings = Settings()
