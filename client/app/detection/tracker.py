import math
from functools import lru_cache


class Tracker:
    """
    Tracker liviano para el contador de puerta.

    Mantiene IDs desde la primera deteccion y usa prediccion de movimiento,
    IoU, cambio de tamano y el ancla corporal para recuperar el mismo ID
    despues de oclusiones breves.

    La prediccion sirve SOLO para asociar IDs. Los puntos que llegan al
    contador se obtienen exclusivamente de detecciones reales recientes.
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

        area_a = (
            max(0.0, ax2 - ax1)
            * max(0.0, ay2 - ay1)
        )
        area_b = (
            max(0.0, bx2 - bx1)
            * max(0.0, by2 - by1)
        )
        union = (
            area_a
            + area_b
            - intersection
        )

        if union <= 0:
            return 0.0

        return intersection / union

    @staticmethod
    def _detection_point(
        detection,
        fallback
    ):
        point = detection.get("point")

        if not point:
            return fallback

        return (
            float(point[0]),
            float(point[1])
        )

    @staticmethod
    def _detection_movement_point(
        detection,
        fallback
    ):
        point = detection.get("foot_point")

        if not point:
            point = detection.get("point")

        if not point:
            return fallback

        return (
            float(point[0]),
            float(point[1])
        )

    @staticmethod
    def _median_point(points):
        if not points:
            return 0.0, 0.0

        xs = sorted(
            point[0]
            for point in points
        )
        ys = sorted(
            point[1]
            for point in points
        )

        middle = len(points) // 2

        if len(points) % 2:
            return (
                xs[middle],
                ys[middle]
            )

        return (
            (
                xs[middle - 1]
                + xs[middle]
            ) / 2.0,
            (
                ys[middle - 1]
                + ys[middle]
            ) / 2.0
        )

    @staticmethod
    def _box_from_center(
        center,
        width,
        height
    ):
        cx, cy = center

        half_w = max(
            0.5,
            width / 2.0
        )
        half_h = max(
            0.5,
            height / 2.0
        )

        return (
            cx - half_w,
            cy - half_h,
            cx + half_w,
            cy + half_h
        )

    def _prediction(self, track):
        steps = min(
            3.0,
            max(
                1.0,
                float(track["missing"])
            )
        )

        tcx, tcy = track["center"]

        predicted_center = (
            tcx + track["vx"] * steps,
            tcy + track["vy"] * steps
        )

        width = max(
            1.0,
            track["width"]
            + track["vw"] * steps
        )
        height = max(
            1.0,
            track["height"]
            + track["vh"] * steps
        )

        return (
            predicted_center,
            self._box_from_center(
                predicted_center,
                width,
                height
            ),
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

        point_x, point_y = (
            self._detection_point(
                detection,
                (cx, cy)
            )
        )

        movement_x, movement_y = (
            self._detection_movement_point(
                detection,
                (cx, cy)
            )
        )

        self.tracks[track_id] = {
            "box": box,
            "center": (cx, cy),
            "origin_center": (cx, cy),
            "max_displacement": 0.0,

            "point": (
                point_x,
                point_y
            ),
            "point_history": [
                (point_x, point_y)
            ],

            "movement_point": (
                movement_x,
                movement_y
            ),
            "movement_history": [
                (movement_x, movement_y)
            ],

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

    def _candidate_cost(
        self,
        track,
        detection
    ):
        box = (
            float(detection["x1"]),
            float(detection["y1"]),
            float(detection["x2"]),
            float(detection["y2"])
        )

        dcx, dcy = self._center(box)
        width, height = self._size(box)

        (
            predicted_center,
            predicted_box,
            predicted_w,
            predicted_h
        ) = self._prediction(track)

        predicted_x, predicted_y = (
            predicted_center
        )

        distance = math.hypot(
            dcx - predicted_x,
            dcy - predicted_y
        )

        # El torso participa en asociacion porque suele seguir visible aunque
        # los pies se ocluyan parcialmente.
        detected_point = (
            self._detection_point(
                detection,
                (dcx, dcy)
            )
        )

        predicted_point = (
            track["point"][0]
            + track["vx"],
            track["point"][1]
            + track["vy"]
        )

        anchor_distance = math.hypot(
            detected_point[0]
            - predicted_point[0],
            detected_point[1]
            - predicted_point[1]
        )

        detected_movement = (
            self._detection_movement_point(
                detection,
                (dcx, dcy)
            )
        )
        predicted_movement = (
            track["movement_point"][0]
            + track["vx"],
            track["movement_point"][1]
            + track["vy"]
        )
        movement_anchor_distance = math.hypot(
            detected_movement[0]
            - predicted_movement[0],
            detected_movement[1]
            - predicted_movement[1]
        )

        diagonal = max(
            math.hypot(
                width,
                height
            ),
            math.hypot(
                predicted_w,
                predicted_h
            )
        )

        dynamic_distance = max(
            self.max_distance,
            diagonal * 0.58
        )

        dynamic_distance += min(
            80.0,
            max(
                0,
                track["missing"] - 1
            ) * 12.0
        )

        iou = self._iou(
            predicted_box,
            box
        )

        size_delta = (
            abs(
                width - predicted_w
            )
            / max(
                width,
                predicted_w,
                1.0
            )
            + abs(
                height - predicted_h
            )
            / max(
                height,
                predicted_h,
                1.0
            )
        )

        motion_x = (
            dcx
            - track["center"][0]
        )
        motion_y = (
            dcy
            - track["center"][1]
        )

        predicted_speed = math.hypot(
            track["vx"],
            track["vy"]
        )
        measured_speed = math.hypot(
            motion_x,
            motion_y
        )

        direction_penalty = 0.0

        if (
            predicted_speed > 3.0
            and measured_speed > 3.0
        ):
            dot = (
                track["vx"] * motion_x
                + track["vy"] * motion_y
            ) / (
                predicted_speed
                * measured_speed
            )
            dot = max(-1.0, min(1.0, dot))

            # En cruces simultaneos el IoU puede favorecer al bbox equivocado.
            # La direccion historica pesa fuerte para no intercambiar IDs.
            if dot < 0.55:
                direction_penalty = (
                    0.55 - dot
                ) * 95.0

            if (
                track["hits"] >= 3
                and track["missing"] <= 1
                and dot < -0.60
            ):
                direction_penalty += 45.0

        if (
            distance > dynamic_distance
            and (
                anchor_distance
                > dynamic_distance * 1.20
            )
            and (
                movement_anchor_distance
                > dynamic_distance * 1.35
            )
            and iou < 0.025
        ):
            return None

        stale_penalty = (
            max(
                0,
                track["missing"] - 1
            ) * 7.0
        )

        return (
            distance
            + anchor_distance * 0.18
            + movement_anchor_distance * 0.10
            - iou * 155.0
            + size_delta * 45.0
            + direction_penalty
            + stale_penalty
        )

    @staticmethod
    def _velocity_cosine(track_a, track_b):
        speed_a = math.hypot(
            track_a["vx"],
            track_a["vy"]
        )
        speed_b = math.hypot(
            track_b["vx"],
            track_b["vy"]
        )

        if speed_a < 2.0 or speed_b < 2.0:
            return 1.0

        return (
            track_a["vx"] * track_b["vx"]
            + track_a["vy"] * track_b["vy"]
        ) / (speed_a * speed_b)

    def _assign_detections(self, detections):
        """
        Asignacion global de costo minimo.

        El greedy anterior podia tomar primero una pareja localmente barata y
        dejar la segunda persona con un ID incorrecto. Con max_det pequeno,
        DP por mascara es rapido y evita ese problema.
        """
        if not self.tracks or not detections:
            return {}, set()

        track_ids = list(self.tracks.keys())
        detection_count = len(detections)

        costs = []
        for track_id in track_ids:
            track = self.tracks[track_id]
            row = []
            for detection in detections:
                row.append(
                    self._candidate_cost(
                        track,
                        detection
                    )
                )
            costs.append(row)

        # Si YOLO fusiona temporalmente dos personas que venian en sentidos
        # opuestos en una sola deteccion, no contaminamos ninguno de los IDs.
        recent_tracks = [
            index
            for index, track_id in enumerate(track_ids)
            if (
                self.tracks[track_id]["hits"] >= 3
                and self.tracks[track_id]["missing"] <= 1
            )
        ]

        suppressed_detections = set()

        if detection_count < len(recent_tracks):
            for detection_index in range(detection_count):
                candidates = [
                    (
                        costs[track_index][detection_index],
                        track_index
                    )
                    for track_index in recent_tracks
                    if costs[track_index][detection_index] is not None
                ]
                candidates.sort(
                    key=lambda item: item[0]
                )

                if len(candidates) < 2:
                    continue

                first_cost, first_index = candidates[0]
                second_cost, second_index = candidates[1]

                if abs(first_cost - second_cost) > 18.0:
                    continue

                cosine = self._velocity_cosine(
                    self.tracks[track_ids[first_index]],
                    self.tracks[track_ids[second_index]]
                )

                if cosine < -0.35:
                    costs[first_index][detection_index] = None
                    costs[second_index][detection_index] = None
                    suppressed_detections.add(
                        detection_index
                    )

        new_track_penalty = 120.0

        @lru_cache(maxsize=None)
        def solve(track_index, used_mask):
            if track_index >= len(track_ids):
                unmatched = (
                    detection_count
                    - used_mask.bit_count()
                )
                return (
                    unmatched * new_track_penalty,
                    ()
                )

            best_cost, best_pairs = solve(
                track_index + 1,
                used_mask
            )

            for detection_index in range(detection_count):
                if used_mask & (1 << detection_index):
                    continue

                candidate_cost = costs[
                    track_index
                ][detection_index]

                if candidate_cost is None:
                    continue

                next_cost, next_pairs = solve(
                    track_index + 1,
                    used_mask | (1 << detection_index)
                )
                total_cost = (
                    candidate_cost
                    + next_cost
                )

                if total_cost < best_cost:
                    best_cost = total_cost
                    best_pairs = (
                        (
                            track_ids[track_index],
                            detection_index
                        ),
                    ) + next_pairs

            return best_cost, best_pairs

        _, pairs = solve(0, 0)

        return (
            {
                detection_index: track_id
                for track_id, detection_index in pairs
            },
            suppressed_detections
        )

    def update(self, detections):
        """
        Devuelve detecciones reales con ID.

        Una oclusion breve mantiene vivo el track, pero nunca se devuelve una
        posicion predicha como si fuera una observacion real de conteo.
        """

        for track in self.tracks.values():
            track["missing"] += 1
            track["age"] += 1

        if not detections:
            self._remove_expired()
            return []

        (
            assignments,
            suppressed_detections
        ) = self._assign_detections(
            detections
        )

        output = []

        for (
            detection_index,
            detection
        ) in enumerate(detections):
            if detection_index in suppressed_detections:
                continue

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

            track = self.tracks[track_id]

            raw_point = (
                self._detection_point(
                    detection,
                    track["point"]
                )
            )

            count_point = (
                self._median_point(
                    track["point_history"]
                )
            )

            movement_point = (
                self._median_point(
                    track[
                        "movement_history"
                    ]
                )
            )

            smooth_point_x = (
                track["point"][0]
            )
            smooth_point_y = (
                track["point"][1]
            )

            item = dict(detection)

            item["id"] = track_id

            item["raw_point"] = (
                int(round(raw_point[0])),
                int(round(raw_point[1]))
            )

            # Torso: decide el cruce geometrico.
            item["point"] = (
                int(round(count_point[0])),
                int(round(count_point[1]))
            )

            # Apoyo inferior: valida locomocion real. Nunca decide la linea.
            item["movement_point"] = (
                int(round(movement_point[0])),
                int(round(movement_point[1]))
            )

            item["tracking_point"] = (
                int(round(smooth_point_x)),
                int(round(smooth_point_y))
            )

            item["hits"] = int(
                track["hits"]
            )

            item["max_displacement"] = float(
                track["max_displacement"]
            )
            item["velocity"] = (
                float(track["vx"]),
                float(track["vy"])
            )
            item["missing"] = int(
                track["missing"]
            )

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
            float(detection["x1"]),
            float(detection["y1"]),
            float(detection["x2"]),
            float(detection["y2"])
        )

        new_cx, new_cy = self._center(
            box
        )
        new_width, new_height = (
            self._size(box)
        )

        old_cx, old_cy = (
            track["center"]
        )

        measured_vx = (
            new_cx - old_cx
        )
        measured_vy = (
            new_cy - old_cy
        )
        measured_vw = (
            new_width
            - track["width"]
        )
        measured_vh = (
            new_height
            - track["height"]
        )

        velocity_alpha = 0.62
        size_alpha = 0.35

        track["vx"] = (
            track["vx"]
            * (1.0 - velocity_alpha)
            + measured_vx
            * velocity_alpha
        )

        track["vy"] = (
            track["vy"]
            * (1.0 - velocity_alpha)
            + measured_vy
            * velocity_alpha
        )

        track["vw"] = (
            track["vw"]
            * (1.0 - size_alpha)
            + measured_vw
            * size_alpha
        )

        track["vh"] = (
            track["vh"]
            * (1.0 - size_alpha)
            + measured_vh
            * size_alpha
        )

        (
            measured_point_x,
            measured_point_y
        ) = self._detection_point(
            detection,
            (new_cx, new_cy)
        )

        (
            measured_movement_x,
            measured_movement_y
        ) = self._detection_movement_point(
            detection,
            (new_cx, new_cy)
        )

        old_point_x, old_point_y = (
            track["point"]
        )

        point_alpha_x = 0.82
        point_alpha_y = 0.82

        track["point"] = (
            old_point_x
            * (1.0 - point_alpha_x)
            + measured_point_x
            * point_alpha_x,
            old_point_y
            * (1.0 - point_alpha_y)
            + measured_point_y
            * point_alpha_y
        )

        track["movement_point"] = (
            measured_movement_x,
            measured_movement_y
        )

        track["point_history"].append((
            measured_point_x,
            measured_point_y
        ))

        if len(
            track["point_history"]
        ) > 3:
            del track[
                "point_history"
            ][:-3]

        track[
            "movement_history"
        ].append((
            measured_movement_x,
            measured_movement_y
        ))

        if len(
            track["movement_history"]
        ) > 3:
            del track[
                "movement_history"
            ][:-3]

        origin_x, origin_y = (
            track["origin_center"]
        )

        track["max_displacement"] = max(
            track["max_displacement"],
            math.hypot(
                new_cx - origin_x,
                new_cy - origin_y
            )
        )

        track["box"] = box
        track["center"] = (
            new_cx,
            new_cy
        )
        track["width"] = new_width
        track["height"] = new_height
        track["missing"] = 0
        track["hits"] += 1

    def _remove_expired(self):
        expired = [
            track_id
            for (
                track_id,
                track
            ) in self.tracks.items()
            if (
                track["missing"]
                > self.max_missing
            )
        ]

        for track_id in expired:
            del self.tracks[track_id]

    def reset(self):
        self.tracks.clear()
        self.next_id = 1
