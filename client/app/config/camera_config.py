import copy
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
        "y2": 650,
        "points": [
            [640, 100],
            [640, 650]
        ]
    },
    "in_side": 1,
    "margin": 18,
    "confidence": 0.22,
    "config_version": 0
}


def normalize_line(line):
    source = dict(line or {})
    points = []

    raw_points = source.get("points") or []
    for point in raw_points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            points.append([
                max(0, int(round(float(point[0])))),
                max(0, int(round(float(point[1]))))
            ])
        except (TypeError, ValueError):
            continue

    if len(points) < 2:
        points = [
            [
                max(0, int(source.get("x1", DEFAULT_CONFIG["line"]["x1"]))),
                max(0, int(source.get("y1", DEFAULT_CONFIG["line"]["y1"])))
            ],
            [
                max(0, int(source.get("x2", DEFAULT_CONFIG["line"]["x2"]))),
                max(0, int(source.get("y2", DEFAULT_CONFIG["line"]["y2"])))
            ]
        ]

    compact = [points[0]]
    for point in points[1:]:
        if point != compact[-1]:
            compact.append(point)

    if len(compact) < 2:
        compact.append([compact[0][0], compact[0][1] + 1])

    return {
        "x1": compact[0][0],
        "y1": compact[0][1],
        "x2": compact[-1][0],
        "y2": compact[-1][1],
        "points": compact
    }


def normalize_camera_config(config):
    source = dict(config or {})
    merged = copy.deepcopy(DEFAULT_CONFIG)
    merged.update(source)
    merged["line"] = normalize_line(source.get("line", merged["line"]))
    merged["in_side"] = 1 if int(merged.get("in_side", 1)) >= 0 else -1
    merged["margin"] = max(1, int(merged.get("margin", 18)))
    merged["confidence"] = min(
        0.99,
        max(0.01, float(merged.get("confidence", 0.22)))
    )
    merged["config_version"] = int(merged.get("config_version", 0))
    return merged


def get_line_points(config):
    normalized = normalize_line((config or {}).get("line", {}))
    return [tuple(point) for point in normalized["points"]]


def load_camera_config():
    if not CONFIG_FILE.exists():
        config = normalize_camera_config(DEFAULT_CONFIG)
        save_camera_config(config)
        return config

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        config = json.load(file)

    return normalize_camera_config(config)


def save_camera_config(config):
    normalized = normalize_camera_config(config)

    CONFIG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=4)

    # El llamador suele conservar el mismo diccionario en memoria. Lo
    # actualizamos para que el primer guardado ya use exactamente los puntos
    # persistidos sin necesitar cerrar/reabrir el editor.
    if isinstance(config, dict):
        config.clear()
        config.update(copy.deepcopy(normalized))

    return normalized
