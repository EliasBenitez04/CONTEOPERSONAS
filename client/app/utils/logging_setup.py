import sys
import threading
from datetime import datetime

from app.paths import CLIENT_DIR


LOG_DIR = CLIENT_DIR / "logs"
LOG_FILE = LOG_DIR / "client.log"
MAX_BYTES = 5 * 1024 * 1024
MAX_FILES = 5
_LOCK = threading.Lock()


def _rotate():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size < MAX_BYTES:
        return

    oldest = LOG_DIR / f"client.log.{MAX_FILES}"
    if oldest.exists():
        oldest.unlink()

    for index in range(MAX_FILES - 1, 0, -1):
        source = LOG_DIR / f"client.log.{index}"
        target = LOG_DIR / f"client.log.{index + 1}"
        if source.exists():
            source.replace(target)

    LOG_FILE.replace(LOG_DIR / "client.log.1")


class TeeStream:
    def __init__(self, original, file_handle):
        self.original = original
        self.file_handle = file_handle

    def write(self, data):
        if not data:
            return 0
        with _LOCK:
            self.original.write(data)
            self.file_handle.write(data)
            self.file_handle.flush()
        return len(data)

    def flush(self):
        with _LOCK:
            self.original.flush()
            self.file_handle.flush()

    def isatty(self):
        return getattr(self.original, "isatty", lambda: False)()


def setup_client_logging():
    _rotate()
    handle = open(
        LOG_FILE,
        "a",
        encoding="utf-8",
        buffering=1
    )

    separator = (
        "\n"
        + "=" * 60
        + "\n"
        + f"INICIO {datetime.now().astimezone().isoformat(timespec='seconds')}"
        + "\n"
        + "=" * 60
        + "\n"
    )
    handle.write(separator)
    handle.flush()

    sys.stdout = TeeStream(sys.stdout, handle)
    sys.stderr = TeeStream(sys.stderr, handle)
    return LOG_FILE
