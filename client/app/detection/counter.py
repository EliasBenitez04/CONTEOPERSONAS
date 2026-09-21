import math


class LineCounter:

    def __init__(
        self,
        point1=None,
        point2=None,
        points=None,
        in_side=1,
        margin=18
    ):
        self.points = self._normalize_points(points, point1, point2)
        self.point1 = self.points[0]
        self.point2 = self.points[-1]
        self.in_side = 1 if int(in_side) >= 0 else -1
        self.entries = 0
        self.exits = 0
        self.states = {}
        self.set_margin(margin)

    @staticmethod
    def _normalize_points(points, point1=None, point2=None):
        normalized = []

        if points:
            for point in points:
                if point is None or len(point) < 2:
                    continue
                normalized.append((int(point[0]), int(point[1])))

        if len(normalized) < 2:
            p1 = point1 if point1 is not None else (640, 100)
            p2 = point2 if point2 is not None else (640, 650)
            normalized = [
                (int(p1[0]), int(p1[1])),
                (int(p2[0]), int(p2[1]))
            ]

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
        """
        Configura una histeresis simetrica para IN y OUT.

        El margen visual puede ser grande, pero los umbrales internos quedan
        acotados para que ninguna direccion necesite recorrer una distancia
        exagerada antes de confirmar el cruce.
        """
        self._margin = max(6, int(margin))

        self.crossing_margin = max(
            3.0,
            min(12.0, self._margin * 0.18)
        )

        self.rearm_margin = max(
            self.crossing_margin + 3.0,
            min(24.0, self._margin * 0.36)
        )

        if hasattr(self, "states"):
            self.states.clear()

        return self._margin

    @staticmethod
    def _segment_distance(point, p1, p2):
        px, py = point
        x1, y1 = p1
        x2, y2 = p2

        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq <= 0:
            return None

        projection = (
            (px - x1) * dx
            + (py - y1) * dy
        ) / float(length_sq)
        projection = max(0.0, min(1.0, projection))

        nearest_x = x1 + projection * dx
        nearest_y = y1 + projection * dy
        euclidean = math.hypot(
            px - nearest_x,
            py - nearest_y
        )

        length = math.sqrt(length_sq)
        signed = (
            dx * (py - y1)
            - dy * (px - x1)
        ) / length

        # Fuera de la extension del segmento el signo sigue viniendo de la
        # orientacion local, pero la distancia usa el punto proyectado real.
        signed_distance = euclidean if signed >= 0 else -euclidean
        return signed_distance

    def signed_distance(self, point):
        """Distancia firmada al segmento mas cercano de la polilinea."""
        best = None

        for index in range(len(self.points) - 1):
            value = self._segment_distance(
                point,
                self.points[index],
                self.points[index + 1]
            )
            if value is None:
                continue

            if best is None or abs(value) < abs(best):
                best = value

        return 0.0 if best is None else float(best)

    def side_of_point(self, point):
        """Devuelve el lado real que usa el contador para ese punto."""
        return self._sign(self.signed_distance(point))

    @staticmethod
    def _sign(value):
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    def update(self, track_id, point):
        """
        Actualiza el estado usando el punto inferior de la persona.

        El cambio de lado se recuerda aunque el primer frame despues del
        cruce todavia este dentro de la banda de tolerancia. El evento se
        confirma cuando el mismo track alcanza crossing_margin en el lado
        destino. Esto evita perder cruces por FPS bajos o pasos rapidos.
        """
        distance = self.signed_distance(point)
        side = self._sign(distance)

        if side == 0:
            return None

        if track_id not in self.states:
            stable_side = (
                side
                if abs(distance) >= self.rearm_margin
                else None
            )
            self.states[track_id] = {
                "origin_side": side,
                "stable_side": stable_side,
                "armed": stable_side is not None,
                "pending_side": None,
                "last_distance": distance
            }
            return None

        state = self.states[track_id]
        state["last_distance"] = distance

        # Track nacido muy cerca de la linea: recordamos el primer lado y
        # permitimos contar cuando confirma claramente el lado opuesto.
        if state["stable_side"] is None:
            if side != state["origin_side"]:
                state["pending_side"] = side

            if (
                state.get("pending_side") == side
                and abs(distance) >= self.crossing_margin
            ):
                event = self._register_crossing(side)
                state["stable_side"] = side
                state["origin_side"] = side
                state["armed"] = False
                state["pending_side"] = None
                return event

            if abs(distance) >= self.rearm_margin:
                state["stable_side"] = side
                state["origin_side"] = side
                state["armed"] = True
                state["pending_side"] = None

            return None

        # Permanecer o volver al lado estable cancela un cruce incompleto.
        if side == state["stable_side"]:
            state["pending_side"] = None
            if abs(distance) >= self.rearm_margin:
                state["armed"] = True
            return None

        # Todavia no se alejo suficientemente del ultimo cruce.
        if not state["armed"]:
            return None

        # Ya cambio de lado. Aunque este primer punto quede dentro del margen,
        # conservamos el destino y esperamos la confirmacion.
        state["pending_side"] = side

        if abs(distance) < self.crossing_margin:
            return None

        event = self._register_crossing(side)
        state["stable_side"] = side
        state["origin_side"] = side
        state["armed"] = False
        state["pending_side"] = None
        return event

    def _register_crossing(self, destination_side):
        if destination_side == self.in_side:
            self.entries += 1
            return "IN"

        self.exits += 1
        return "OUT"

    def set_line(self, point1=None, point2=None, points=None):
        self.points = self._normalize_points(points, point1, point2)
        self.point1 = self.points[0]
        self.point2 = self.points[-1]
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
        return self.set_in_side(
            -self.in_side,
            swap_counts=swap_counts
        )

    def reset_counts(self):
        self.entries = 0
        self.exits = 0
        self.states.clear()
