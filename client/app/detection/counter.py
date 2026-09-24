import math


class LineCounter:
    """
    Contador V4: maquina de estados por ID.

    Un evento requiere:
    - origen estable fuera de la zona neutral;
    - interseccion geometrica REAL del punto de pies con la polilinea;
    - destino estable durante varios frames;
    - rearmado solo despues de permanecer claramente en el lado destino.

    Estar parado, oscilar o caminar sobre la linea no genera eventos.
    """

    def __init__(self, point1=None, point2=None, points=None, in_side=1, margin=18):
        self.points = self._normalize_points(points, point1, point2)
        self.point1 = self.points[0]
        self.point2 = self.points[-1]
        self.in_side = 1 if int(in_side) >= 0 else -1
        self.entries = 0
        self.exits = 0
        self.states = {}
        self.stable_frames = 2
        self.destination_frames = 2
        self.rearm_frames = 3
        self.max_step = 260.0
        self.set_margin(margin)

    @staticmethod
    def _normalize_points(points, point1=None, point2=None):
        normalized = []
        if points:
            for point in points:
                if point is not None and len(point) >= 2:
                    normalized.append((int(round(point[0])), int(round(point[1]))))
        if len(normalized) < 2:
            p1 = point1 if point1 is not None else (640, 100)
            p2 = point2 if point2 is not None else (640, 650)
            normalized = [(int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))]
        compact = [normalized[0]]
        for point in normalized[1:]:
            if point != compact[-1]:
                compact.append(point)
        if len(compact) < 2:
            compact.append((compact[0][0], compact[0][1] + 1))
        return compact

    @property
    def margin(self):
        return self._margin

    @margin.setter
    def margin(self, value):
        self.set_margin(value)

    def set_margin(self, margin):
        self._margin = max(6, int(margin))
        # V4 usa el margen como zona neutral/histeresis, no para extender linea.
        self.crossing_margin = max(4.0, min(14.0, self._margin * 0.35))
        self.rearm_margin = max(self.crossing_margin + 6.0, min(34.0, self._margin * 0.80))
        if hasattr(self, "states"):
            self.states.clear()
        return self._margin

    @staticmethod
    def _line_signed_distance(point, p1, p2):
        px, py = point
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return None
        return (dx * (py - y1) - dy * (px - x1)) / length

    @staticmethod
    def _segment_projection(point, p1, p2):
        px, py = point
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-9:
            return None
        return ((px - x1) * dx + (py - y1) * dy) / float(length_sq)

    @classmethod
    def _segment_distance(cls, point, p1, p2):
        projection = cls._segment_projection(point, p1, p2)
        signed = cls._line_signed_distance(point, p1, p2)
        if projection is None or signed is None:
            return None
        projection = max(0.0, min(1.0, projection))
        nearest_x = p1[0] + projection * (p2[0] - p1[0])
        nearest_y = p1[1] + projection * (p2[1] - p1[1])
        euclidean = math.hypot(point[0] - nearest_x, point[1] - nearest_y)
        return euclidean if signed >= 0 else -euclidean

    def signed_distance(self, point):
        best = None
        for index in range(len(self.points) - 1):
            value = self._segment_distance(point, self.points[index], self.points[index + 1])
            if value is not None and (best is None or abs(value) < abs(best)):
                best = value
        return 0.0 if best is None else float(best)

    @staticmethod
    def _sign(value, epsilon=1e-6):
        if value > epsilon:
            return 1
        if value < -epsilon:
            return -1
        return 0

    def side_of_point(self, point):
        distance = self.signed_distance(point)
        if abs(distance) < self.crossing_margin:
            return 0
        return self._sign(distance)

    def _find_actual_crossing(self, previous_point, current_point):
        px, py = previous_point
        cx, cy = current_point
        movement = math.hypot(cx - px, cy - py)
        if movement < 0.5 or movement > self.max_step:
            return None

        epsilon = 1e-7
        for index in range(len(self.points) - 1):
            p1, p2 = self.points[index], self.points[index + 1]
            previous_distance = self._line_signed_distance(previous_point, p1, p2)
            current_distance = self._line_signed_distance(current_point, p1, p2)
            if previous_distance is None or current_distance is None:
                continue
            previous_side = self._sign(previous_distance)
            current_side = self._sign(current_distance)
            if previous_side == 0 and current_side == 0:
                continue
            denominator = previous_distance - current_distance
            if abs(denominator) <= epsilon:
                continue
            movement_t = previous_distance / denominator
            if movement_t < -epsilon or movement_t > 1.0 + epsilon:
                continue
            intersection = (px + movement_t * (cx - px), py + movement_t * (cy - py))
            line_t = self._segment_projection(intersection, p1, p2)
            if line_t is None or line_t < -epsilon or line_t > 1.0 + epsilon:
                continue
            if previous_side != 0 and current_side != 0 and previous_side != current_side:
                return index
            if previous_side != 0 and current_side == 0:
                return index
        return None

    def _new_state(self, point):
        return {
            "last_point": point,
            "stable_side": None,
            "stable_count": 0,
            "origin_side": None,
            "crossed": False,
            "segment_index": None,
            "destination_side": None,
            "destination_count": 0,
            "locked": False,
            "rearm_side": None,
            "rearm_count": 0,
        }

    def update(self, track_id, point):
        current = (float(point[0]), float(point[1]))
        if track_id not in self.states:
            self.states[track_id] = self._new_state(current)
            return None

        state = self.states[track_id]
        previous = state["last_point"]
        state["last_point"] = current
        distance = self.signed_distance(current)
        side = 0 if abs(distance) < self.crossing_margin else self._sign(distance)

        # Tras un conteo, el ID solo se rearma tras permanecer claramente
        # alejado en el lado al que llego. Jitter sobre la linea queda bloqueado.
        if state["locked"]:
            if side == state["rearm_side"] and abs(distance) >= self.rearm_margin:
                state["rearm_count"] += 1
                if state["rearm_count"] >= self.rearm_frames:
                    state["locked"] = False
                    state["stable_side"] = side
                    state["stable_count"] = self.stable_frames
                    state["origin_side"] = side
                    state["crossed"] = False
                    state["destination_side"] = None
                    state["destination_count"] = 0
            else:
                state["rearm_count"] = 0
            return None

        # Antes de admitir un cruce, el ID debe demostrar un origen estable.
        if not state["crossed"]:
            if side != 0:
                if side == state["stable_side"]:
                    state["stable_count"] += 1
                else:
                    state["stable_side"] = side
                    state["stable_count"] = 1
                if state["stable_count"] >= self.stable_frames:
                    state["origin_side"] = side

            segment_index = self._find_actual_crossing(previous, current)
            if segment_index is not None and state["origin_side"] is not None:
                # Solo aceptamos interseccion si venia del lado estable conocido.
                previous_raw = self._line_signed_distance(
                    previous, self.points[segment_index], self.points[segment_index + 1]
                )
                if previous_raw is not None and self._sign(previous_raw) == state["origin_side"]:
                    state["crossed"] = True
                    state["segment_index"] = segment_index
                    state["destination_side"] = -state["origin_side"]
                    state["destination_count"] = 0

            if not state["crossed"]:
                return None

        # Ya hubo interseccion real. Exigimos varios frames claros en destino.
        segment_index = state["segment_index"]
        segment_distance = self._line_signed_distance(
            current, self.points[segment_index], self.points[segment_index + 1]
        )
        if segment_distance is None:
            return None

        segment_side = 0 if abs(segment_distance) < self.crossing_margin else self._sign(segment_distance)
        destination = state["destination_side"]

        if segment_side == destination:
            state["destination_count"] += 1
        elif segment_side == state["origin_side"] and abs(segment_distance) >= self.crossing_margin:
            # Toco/cruzo por jitter pero regreso al origen: cancelar.
            state["crossed"] = False
            state["segment_index"] = None
            state["destination_side"] = None
            state["destination_count"] = 0
            state["stable_side"] = state["origin_side"]
            state["stable_count"] = self.stable_frames
            return None
        else:
            # Sobre la zona neutral: mantener pendiente sin sumar.
            return None

        if state["destination_count"] < self.destination_frames:
            return None

        state["locked"] = True
        state["rearm_side"] = destination
        state["rearm_count"] = 0
        state["crossed"] = False
        state["segment_index"] = None
        state["destination_count"] = 0
        return self._register_crossing(destination)

    def _register_crossing(self, destination_side):
        if destination_side == self.in_side:
            self.entries += 1
            return "IN"
        self.exits += 1
        return "OUT"

    def set_line(self, point1=None, point2=None, points=None):
        self.points = self._normalize_points(points, point1, point2)
        self.point1, self.point2 = self.points[0], self.points[-1]
        self.states.clear()

    def set_in_side(self, in_side, swap_counts=False):
        new_side = 1 if int(in_side) >= 0 else -1
        changed = new_side != self.in_side
        if changed and swap_counts:
            self.entries, self.exits = self.exits, self.entries
        self.in_side = new_side
        self.states.clear()
        return changed

    def invert_direction(self, swap_counts=False):
        return self.set_in_side(-self.in_side, swap_counts=swap_counts)

    def reset_counts(self):
        self.entries = 0
        self.exits = 0
        self.states.clear()
