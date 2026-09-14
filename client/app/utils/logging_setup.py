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

    @property
    def encoding(self):
        if self.original is not None:
            encoding = getattr(
                self.original,
                "encoding",
                None
            )
            if encoding:
                return encoding

        return self.file_handle.encoding

    def write(self, data):
        if not data:
            return 0

        with _LOCK:
            if self.original is not None:
                try:
                    self.original.write(data)
                except Exception:
                    pass

            self.file_handle.write(data)
            self.file_handle.flush()

        return len(data)

    def flush(self):
        with _LOCK:
            if self.original is not None:
                try:
                    self.original.flush()
                except Exception:
                    pass

            self.file_handle.flush()

    def isatty(self):
        if self.original is None:
            return False

        return getattr(
            self.original,
            "isatty",
            lambda: False
        )()

    def fileno(self):
        if self.original is not None:
            try:
                return self.original.fileno()
            except Exception:
                pass

        return self.file_handle.fileno()


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

    # En un ejecutable PyInstaller --noconsole, sys.stdout/sys.stderr pueden
    # ser None. TeeStream escribe siempre al archivo y usa la consola solo
    # cuando realmente existe.
    sys.stdout = TeeStream(sys.stdout, handle)
    sys.stderr = TeeStream(sys.stderr, handle)
    return LOG_FILE
