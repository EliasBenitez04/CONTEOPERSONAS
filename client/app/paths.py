import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    CLIENT_DIR = Path(sys.executable).resolve().parent
else:
    CLIENT_DIR = Path(__file__).resolve().parents[1]


def resource_path(name: str):
    """Ruta de recurso empaquetado o archivo local de desarrollo."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        bundled = Path(bundle_dir) / name
        if bundled.exists():
            return bundled
    return CLIENT_DIR / name
