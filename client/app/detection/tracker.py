import math


class Tracker:
    """
    Tracker liviano para el contador de puerta.

    A diferencia de ByteTrack, asigna un ID desde la PRIMERA deteccion
    de YOLO. Esto es importante cuando una persona aparece muy cerca de
    la linea y no hay tiempo suficiente para que un tracker externo
    confirme un ID antes del cruce.
    """

    def __init__(
        self,
        max_missing=15,
        max_distance=170
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

    def _new_track(self, detection):
        track_id = self.next_id
        self.next_id += 1

        box = (
            detection["x1"],
            detection["y1"],
            detection["x2"],
            detection["y2"]
        )

        cx, cy = self._center(box)

        self.tracks[track_id] = {
            "box": box,
            "center": (cx, cy),
            "vx": 0.0,
            "vy": 0.0,
            "missing": 0
        }

        return track_id

    def update(self, detections):
        """
        Recibe las detecciones del frame actual y devuelve las mismas
        detecciones con un ID local estable.

        El ID se crea inmediatamente; no espera varios frames para
        confirmarlo.
        """

        for track in self.tracks.values():
            track["missing"] += 1

        if not detections:
            self._remove_expired()
            return []

        candidates = []

        for track_id, track in self.tracks.items():
            tcx, tcy = track["center"]

            predicted_x = tcx + track["vx"]
            predicted_y = tcy + track["vy"]

            for detection_index, detection in enumerate(detections):
                box = (
                    detection["x1"],
                    detection["y1"],
                    detection["x2"],
                    detection["y2"]
                )

                dcx, dcy = self._center(box)

                distance = math.hypot(
                    dcx - predicted_x,
                    dcy - predicted_y
                )

                width = max(1.0, box[2] - box[0])
                height = max(1.0, box[3] - box[1])

                track_box = track["box"]
                track_width = max(
                    1.0,
                    track_box[2] - track_box[0]
                )
                track_height = max(
                    1.0,
                    track_box[3] - track_box[1]
                )

                dynamic_distance = max(
                    self.max_distance,
                    0.55 * max(
                        math.hypot(width, height),
                        math.hypot(
                            track_width,
                            track_height
                        )
                    )
                )

                dynamic_distance += min(
                    100.0,
                    track["missing"] * 12.0
                )

                iou = self._iou(
                    track_box,
                    box
                )

                if (
                    distance <= dynamic_distance
                    or iou >= 0.05
                ):
                    cost = distance - (iou * 120.0)

                    candidates.append(
                        (
                            cost,
                            track_id,
                            detection_index
                        )
                    )

        candidates.sort(
            key=lambda item: item[0]
        )

        used_tracks = set()
        used_detections = set()
        assignments = {}

        for _, track_id, detection_index in candidates:
            if track_id in used_tracks:
                continue

            if detection_index in used_detections:
                continue

            used_tracks.add(track_id)
            used_detections.add(detection_index)

            assignments[detection_index] = track_id

        output = []

        for detection_index, detection in enumerate(detections):
            track_id = assignments.get(
                detection_index
            )

            if track_id is None:
                track_id = self._new_track(
                    detection
                )
            else:
                self._update_track(
                    track_id,
                    detection
                )

            item = dict(detection)
            item["id"] = track_id
            output.append(item)

        self._remove_expired()

        return output

    def _update_track(
        self,
        track_id,
        detection
    ):
        track = self.tracks[track_id]

        box = (
            detection["x1"],
            detection["y1"],
            detection["x2"],
            detection["y2"]
        )

        new_cx, new_cy = self._center(box)
        old_cx, old_cy = track["center"]

        measured_vx = new_cx - old_cx
        measured_vy = new_cy - old_cy

        track["vx"] = (
            track["vx"] * 0.45
            + measured_vx * 0.55
        )

        track["vy"] = (
            track["vy"] * 0.45
            + measured_vy * 0.55
        )

        track["box"] = box
        track["center"] = (
            new_cx,
            new_cy
        )
        track["missing"] = 0

    def _remove_expired(self):
        expired = [
            track_id
            for track_id, track
            in self.tracks.items()
            if track["missing"] > self.max_missing
        ]

        for track_id in expired:
            del self.tracks[track_id]

    def reset(self):
        self.tracks.clear()
        self.next_id = 1
