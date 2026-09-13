import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings:

    CAMERA_NAME = os.getenv(
        "CAMERA_NAME",
        "CAMARA_01"
    )

    CAMERA_RTSP_URL = os.getenv(
        "CAMERA_RTSP_URL",
        ""
    )

    RECONNECT_SECONDS = int(
        os.getenv("RECONNECT_SECONDS", "3")
    )

    BRANCH_ID = int(
        os.getenv("BRANCH_ID", "1")
    )

    API_URL = os.getenv(
        "API_URL",
        "http://127.0.0.1:8000/api"
    )

    API_TOKEN = os.getenv(
        "API_TOKEN",
        ""
    )

    API_TIMEOUT_SECONDS = int(
        os.getenv(
            "API_TIMEOUT_SECONDS",
            "5"
        )
    )

    SYNC_INTERVAL_SECONDS = int(
        os.getenv(
            "SYNC_INTERVAL_SECONDS",
            "5"
        )
    )

    SYNC_BATCH_SIZE = int(
        os.getenv(
            "SYNC_BATCH_SIZE",
            "100"
        )
    )


settings = Settings()
