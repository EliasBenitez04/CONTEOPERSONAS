import json
from pathlib import Path


CONFIG_FILE = Path(__file__).resolve().parents[2] / "data" / "camera_config.json"


DEFAULT_CONFIG = {
    "line": {
        "x1": 640,
        "y1": 100,
        "x2": 640,
        "y2": 650
    },
    "in_side": 1
}


def load_camera_config():

    if not CONFIG_FILE.exists():
        save_camera_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_camera_config(config):

    CONFIG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        CONFIG_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            config,
            file,
            indent=4
        )