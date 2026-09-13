import json

from app.paths import CLIENT_DIR


# Se conserva la ruta historica del proyecto para no perder la linea
# ya calibrada al migrar a V3 ni al actualizar el ejecutable.
CONFIG_FILE = CLIENT_DIR / "config" / "camera_config.json"


DEFAULT_CONFIG = {
    "line": {
        "x1": 640,
        "y1": 100,
        "x2": 640,
        "y2": 650
    },
    "in_side": 1,
    "margin": 18,
    "confidence": 0.22,
    "config_version": 0
}


def load_camera_config():
    if not CONFIG_FILE.exists():
        save_camera_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        config = json.load(file)

    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    merged["line"] = {
        **DEFAULT_CONFIG["line"],
        **config.get("line", {})
    }
    return merged


def save_camera_config(config):
    CONFIG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)
