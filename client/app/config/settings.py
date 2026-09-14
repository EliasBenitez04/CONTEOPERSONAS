import os

from dotenv import load_dotenv

from app.paths import CLIENT_DIR


ENV_FILE = CLIENT_DIR / ".env"
# El .env local debe ser la fuente de verdad del cliente. override=True evita
# que variables antiguas de Windows/PowerShell oculten CLIENT_ID/CLIENT_TOKEN
# recien configurados.
load_dotenv(ENV_FILE, override=True)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return bool(default)

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "si",
        "sí",
        "on"
    }


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

    # Produccion: sin consola y sin ventana de OpenCV.
    # Para calibracion local se puede usar HEADLESS=false temporalmente.
    HEADLESS = _env_bool("HEADLESS", True)

    # Limita inferencias por segundo. La camara sigue capturando en un thread
    # separado y siempre se procesa el frame mas reciente.
    PROCESS_FPS = max(
        1.0,
        float(os.getenv("PROCESS_FPS", "12"))
    )

    # Mantiene 640 por defecto para no sacrificar precision. Se puede bajar
    # desde .env si un equipo necesita ahorrar mas recursos.
    YOLO_IMGSZ = max(
        320,
        int(os.getenv("YOLO_IMGSZ", "640"))
    )

    MANAGED_CLIENT = bool(CLIENT_ID and CLIENT_TOKEN)


settings = Settings()
