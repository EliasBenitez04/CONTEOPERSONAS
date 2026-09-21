import math


class Tracker:
    """
    Tracker liviano para el contador de puerta.

    Mantiene IDs desde la primera deteccion y usa una prediccion de movimiento
    inspirada en SORT/Kalman, sin agregar scipy/filterpy al ejecutable. La
    asociacion combina centro predicho, IoU del bbox predicho, cambio de tamano
    y antiguedad del track para conservar mejor el ID cuando dos personas se
    acercan o YOLO pierde algunos frames.
    """

    def __init__(
        self,
        max_missing=12,
        max_distance=150
    ):
        self.max_missing = int(max_missing)
        self.max_distance = float(max_distance)

        self.next_id = 1
        self.tracks = {}

    @staticmethod
    def _center(box):
        x1, y1, x2, y2 = box
        return (
            (x1 + x2) / 2.0,
            (y1 + y2) / 2.0
        )

    @staticmethod
    def _size(box):
        return (
            max(1.0, box[2] - box[0]),
            max(1.0, box[3] - box[1])
        )

    @staticmethod
    def _iou(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        intersection = iw * ih

        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - intersection

        if union <= 0:
            return 0.0

        return intersection / union

    @staticmethod
    def _detection_point(detection, fallback):
        point = detection.get("point")
        if not point:
            return fallback
        return float(point[0]), float(point[1])

    @staticmethod
    def _box_from_center(center, width, height):
        cx, cy = center
        half_w = max(0.5, width / 2.0)
        half_h = max(0.5, height / 2.0)
        return (
            cx - half_w,
            cy - half_h,
            cx + half_w,
            cy + half_h
        )

    def _prediction(self, track):
        steps = min(
            3.0,
            max(1.0, float(track["missing"]))
        )

        tcx, tcy = track["center"]
        predicted_center = (
            tcx + track["vx"] * steps,
            tcy + track["vy"] * steps
        )

        width = max(1.0, track["width"] + track["vw"] * steps)
        height = max(1.0, track["height"] + track["vh"] * steps)

        return (
            predicted_center,
            self._box_from_center(predicted_center, width, height),
            width,
            height
        )

    def _new_track(self, detection):
        track_id = self.next_id
        self.next_id += 1

        box = (
            float(detection["x1"]),
            float(detection["y1"]),
            float(detection["x2"]),
            float(detection["y2"])
        )

        cx, cy = self._center(box)
        width, height = self._size(box)
        point_x, point_y = self._detection_point(
            detection,
            (cx, cy)
        )

        self.tracks[track_id] = {
            "box": box,
            "center": (cx, cy),
            "point": (point_x, point_y),
            "width": width,
            "height": height,
            "vx": 0.0,
            "vy": 0.0,
            "vw": 0.0,
            "vh": 0.0,
            "missing": 0,
            "age": 1,
            "hits": 1
        }

        return track_id

    def _candidate_cost(self, track, detection):
        box = (
            float(detection["x1"]),
            float(detection["y1"]),
            float(detection["x2"]),
            float(detection["y2"])
        )
        dcx, dcy = self._center(box)
        width, height = self._size(box)

        predicted_center, predicted_box, predicted_w, predicted_h = (
            self._prediction(track)
        )
        predicted_x, predicted_y = predicted_center

        distance = math.hypot(
            dcx - predicted_x,
            dcy - predicted_y
        )

        # El punto de conteo (centro inferior / pies) tambien participa en la
        # asociacion. Ayuda a no intercambiar IDs cuando dos personas se
        # superponen de cintura/cabeza pero sus apoyos siguen separados.
        detected_point = self._detection_point(
            detection,
            (dcx, dcy)
        )
        predicted_point = (
            track["point"][0] + track["vx"],
            track["point"][1] + track["vy"]
        )
        foot_distance = math.hypot(
            detected_point[0] - predicted_point[0],
            detected_point[1] - predicted_point[1]
        )

        diagonal = max(
            math.hypot(width, height),
            math.hypot(predicted_w, predicted_h)
        )
        dynamic_distance = max(
            self.max_distance,
            diagonal * 0.58
        )
        dynamic_distance += min(
            80.0,
            max(0, track["missing"] - 1) * 12.0
        )

        iou = self._iou(predicted_box, box)

        size_delta = (
            abs(width - predicted_w) / max(width, predicted_w, 1.0)
            + abs(height - predicted_h) / max(height, predicted_h, 1.0)
        )

        motion_x = dcx - track["center"][0]
        motion_y = dcy - track["center"][1]
        predicted_speed = math.hypot(track["vx"], track["vy"])
        measured_speed = math.hypot(motion_x, motion_y)

        direction_penalty = 0.0
        if predicted_speed > 4.0 and measured_speed > 4.0:
            dot = (
                track["vx"] * motion_x
                + track["vy"] * motion_y
            ) / (predicted_speed * measured_speed)
            if dot < 0:
                direction_penalty = min(55.0, abs(dot) * 55.0)

        if (
            distance > dynamic_distance
            and foot_distance > dynamic_distance * 1.20
            and iou < 0.025
        ):
            return None

        stale_penalty = max(0, track["missing"] - 1) * 7.0

        # Menor costo = mejor asociacion. IoU alto compensa distancia; cambios
        # bruscos de tamano/direccion penalizan intercambios de ID al cruzarse.
        return (
            distance
            + (foot_distance * 0.18)
            - (iou * 155.0)
            + (size_delta * 45.0)
            + direction_penalty
            + stale_penalty
        )

    def update(self, detections):
        """
        Recibe detecciones del frame actual y devuelve las mismas con ID.

        Los IDs nacen inmediatamente. Cuando falta una deteccion el track sigue
        vivo y su estado de movimiento permite recuperarlo al reaparecer.
        """

        for track in self.tracks.values():
            track["missing"] += 1
            track["age"] += 1

        if not detections:
            self._remove_expired()
            return []

        candidates = []

        for track_id, track in self.tracks.items():
            for detection_index, detection in enumerate(detections):
                cost = self._candidate_cost(track, detection)
                if cost is None:
                    continue
                candidates.append((cost, track_id, detection_index))

        # Asociacion uno-a-uno global por costo. Para una puerta normalmente
        # hay pocos tracks, por lo que ordenar los pares es rapido y estable.
        candidates.sort(key=lambda item: item[0])

        used_tracks = set()
        used_detections = set()
        assignments = {}

        for _, track_id, detection_index in candidates:
            if track_id in used_tracks or detection_index in used_detections:
                continue

            used_tracks.add(track_id)
            used_detections.add(detection_index)
            assignments[detection_index] = track_id

        output = []

        for detection_index, detection in enumerate(detections):
            track_id = assignments.get(detection_index)

            if track_id is None:
                track_id = self._new_track(detection)
            else:
                self._update_track(track_id, detection)

            track = self.tracks[track_id]
            point_x, point_y = track["point"]

            item = dict(detection)
            item["id"] = track_id
            item["point"] = (
                int(round(point_x)),
                int(round(point_y))
            )
            output.append(item)

        self._remove_expired()
        return output

    def _update_track(self, track_id, detection):
        track = self.tracks[track_id]

        box = (
            float(detection["x1"]),
            float(detection["y1"]),
            float(detection["x2"]),
            float(detection["y2"])
        )

        new_cx, new_cy = self._center(box)
        new_width, new_height = self._size(box)
        old_cx, old_cy = track["center"]

        measured_vx = new_cx - old_cx
        measured_vy = new_cy - old_cy
        measured_vw = new_width - track["width"]
        measured_vh = new_height - track["height"]

        # Filtro alfa-beta liviano: conserva inercia pero reacciona rapido a
        # cambios reales. Cumple el objetivo de Kalman/SORT sin dependencias.
        velocity_alpha = 0.62
        size_alpha = 0.35

        track["vx"] = (
            track["vx"] * (1.0 - velocity_alpha)
            + measured_vx * velocity_alpha
        )
        track["vy"] = (
            track["vy"] * (1.0 - velocity_alpha)
            + measured_vy * velocity_alpha
        )
        track["vw"] = (
            track["vw"] * (1.0 - size_alpha)
            + measured_vw * size_alpha
        )
        track["vh"] = (
            track["vh"] * (1.0 - size_alpha)
            + measured_vh * size_alpha
        )

        measured_point_x, measured_point_y = self._detection_point(
            detection,
            (new_cx, new_cy)
        )
        old_point_x, old_point_y = track["point"]

        # El eje Y del punto de pie debe reaccionar casi de inmediato para no
        # retrasar el cruce. X conserva algo mas de suavizado contra jitter.
        point_alpha_x = 0.82
        point_alpha_y = 0.94
        track["point"] = (
            old_point_x * (1.0 - point_alpha_x)
            + measured_point_x * point_alpha_x,
            old_point_y * (1.0 - point_alpha_y)
            + measured_point_y * point_alpha_y
        )

        track["box"] = box
        track["center"] = (new_cx, new_cy)
        track["width"] = new_width
        track["height"] = new_height
        track["missing"] = 0
        track["hits"] += 1

    def _remove_expired(self):
        expired = [
            track_id
            for track_id, track in self.tracks.items()
            if track["missing"] > self.max_missing
        ]

        for track_id in expired:
            del self.tracks[track_id]

    def reset(self):
        self.tracks.clear()
        self.next_id = 1
