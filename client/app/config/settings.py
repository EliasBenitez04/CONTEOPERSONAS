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


def _env_int(name: str, default: int, minimum=None) -> int:
    value = os.getenv(name)

    try:
        parsed = int(value.strip()) if value and value.strip() else int(default)
    except (TypeError, ValueError):
        parsed = int(default)

    if minimum is not None:
        parsed = max(int(minimum), parsed)

    return parsed


def _env_float(name: str, default: float, minimum=None) -> float:
    value = os.getenv(name)

    try:
        parsed = float(value.strip()) if value and value.strip() else float(default)
    except (TypeError, ValueError):
        parsed = float(default)

    if minimum is not None:
        parsed = max(float(minimum), parsed)

    return parsed


class Settings:
    APP_VERSION = os.getenv("APP_VERSION", "3.0.0")

    CAMERA_NAME = os.getenv("CAMERA_NAME", "CAMARA_01")
    CAMERA_RTSP_URL = os.getenv("CAMERA_RTSP_URL", "")
    RECONNECT_SECONDS = _env_int("RECONNECT_SECONDS", 3, minimum=1)
    BRANCH_ID = _env_int("BRANCH_ID", 1, minimum=1)

    API_URL = os.getenv(
        "API_URL",
        "http://127.0.0.1:8000/api"
    ).rstrip("/")

    CLIENT_ID = os.getenv("CLIENT_ID", "").strip()
    CLIENT_TOKEN = os.getenv("CLIENT_TOKEN", "").strip()
    API_TOKEN = os.getenv("API_TOKEN", "").strip()

    API_TIMEOUT_SECONDS = _env_int("API_TIMEOUT_SECONDS", 5, minimum=1)
    SYNC_INTERVAL_SECONDS = _env_int("SYNC_INTERVAL_SECONDS", 5, minimum=1)
    SYNC_BATCH_SIZE = _env_int("SYNC_BATCH_SIZE", 100, minimum=1)
    HEARTBEAT_INTERVAL_SECONDS = _env_int(
        "HEARTBEAT_INTERVAL_SECONDS",
        20,
        minimum=1
    )
    REMOTE_CONFIG_INTERVAL_SECONDS = _env_int(
        "REMOTE_CONFIG_INTERVAL_SECONDS",
        30,
        minimum=1
    )

    # Modo visual por defecto: muestra la camara y permite minimizarla
    # al area de iconos ocultos. HEADLESS=true sigue disponible si alguna
    # sucursal necesita funcionar sin interfaz grafica.
    HEADLESS = _env_bool("HEADLESS", False)
    TRAY_MODE = _env_bool("TRAY_MODE", True)

    # Limita inferencias por segundo. La camara sigue capturando en un thread
    # separado y siempre se procesa el frame mas reciente.
    PROCESS_FPS = _env_float("PROCESS_FPS", 12.0, minimum=1.0)

    # Mantiene 640 por defecto para no sacrificar precision. Se puede bajar
    # desde .env si un equipo necesita ahorrar mas recursos.
    YOLO_IMGSZ = _env_int("YOLO_IMGSZ", 640, minimum=320)

    MANAGED_CLIENT = bool(CLIENT_ID and CLIENT_TOKEN)


settings = Settings()
