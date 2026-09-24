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
    APP_VERSION = "4.0.0"

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

    HEADLESS = _env_bool("HEADLESS", False)
    TRAY_MODE = _env_bool("TRAY_MODE", True)

    # Vista abierta: conserva suficiente fluidez para calibrar y diagnosticar.
    PROCESS_FPS = _env_float("PROCESS_FPS", 12.0, minimum=1.0)

    # Perfil de produccion oculto. Menos de 5 FPS puede saltarse por completo
    # el paso de un pie sobre la linea. Se permite hasta 8 FPS, pero el motion
    # gate evita inferencias YOLO continuas cuando la zona esta quieta.
    BACKGROUND_PROCESS_FPS = min(
        8.0,
        max(
            5.0,
            _env_float("BACKGROUND_PROCESS_FPS", 6.0, minimum=1.0)
        )
    )

    YOLO_IMGSZ = _env_int("YOLO_IMGSZ", 640, minimum=320)
    BACKGROUND_YOLO_IMGSZ = min(
        480,
        max(
            384,
            _env_int("BACKGROUND_YOLO_IMGSZ", 416, minimum=320)
        )
    )

    # Se respeta el .env para poder ajustar cada PC. Un hilo sigue siendo el
    # valor seguro por defecto; equipos de escritorio pueden usar 2 sin tocar
    # el codigo.
    YOLO_CPU_THREADS = min(
        4,
        _env_int("YOLO_CPU_THREADS", 1, minimum=1)
    )

    MANAGED_CLIENT = bool(CLIENT_ID and CLIENT_TOKEN)


settings = Settings()
