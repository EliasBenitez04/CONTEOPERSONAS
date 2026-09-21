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
                normalized.append((
                    int(round(point[0])),
                    int(round(point[1]))
                ))

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
        El margen se usa solamente como histeresis despues de un cruce real.

        Nunca se usa para extender la linea ni para decidir un cruce por
        proximidad. Un evento solo puede nacer de una interseccion geometrica
        entre la trayectoria del punto de los pies y un segmento dibujado.
        """
        self._margin = max(6, int(margin))

        self.crossing_margin = max(
            3.0,
            min(10.0, self._margin * 0.16)
        )
        self.rearm_margin = max(
            self.crossing_margin + 3.0,
            min(22.0, self._margin * 0.34)
        )

        if hasattr(self, "states"):
            self.states.clear()

        return self._margin

    @staticmethod
    def _line_signed_distance(point, p1, p2):
        """Distancia perpendicular firmada a la recta del segmento."""
        px, py = point
        x1, y1 = p1
        x2, y2 = p2

        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)

        if length <= 1e-9:
            return None

        return (
            dx * (py - y1)
            - dy * (px - x1)
        ) / length

    @staticmethod
    def _segment_projection(point, p1, p2):
        """Posicion normalizada del punto sobre el eje del segmento."""
        px, py = point
        x1, y1 = p1
        x2, y2 = p2

        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq <= 1e-9:
            return None

        return (
            (px - x1) * dx
            + (py - y1) * dy
        ) / float(length_sq)

    @classmethod
    def _segment_distance(cls, point, p1, p2):
        """
        Distancia firmada al segmento FINITO.

        La magnitud usa el punto mas cercano del segmento; el signo conserva la
        orientacion del segmento. Esto sirve para etiquetas/histeresis, pero no
        genera eventos de conteo.
        """
        projection = cls._segment_projection(point, p1, p2)
        signed = cls._line_signed_distance(point, p1, p2)

        if projection is None or signed is None:
            return None

        projection = max(0.0, min(1.0, projection))
        x1, y1 = p1
        x2, y2 = p2
        nearest_x = x1 + projection * (x2 - x1)
        nearest_y = y1 + projection * (y2 - y1)

        euclidean = math.hypot(
            point[0] - nearest_x,
            point[1] - nearest_y
        )

        return euclidean if signed >= 0 else -euclidean

    def signed_distance(self, point):
        """Distancia firmada al segmento real mas cercano."""
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
        return self._sign(self.signed_distance(point))

    @staticmethod
    def _sign(value, epsilon=1e-6):
        if value > epsilon:
            return 1
        if value < -epsilon:
            return -1
        return 0

    def _find_actual_crossing(self, previous_point, current_point):
        """
        Busca un cruce REAL entre el movimiento del punto de los pies y la
        polilinea dibujada.

        No considera la prolongacion infinita de los segmentos. Si una persona
        pasa alrededor de una punta o simplemente cambia de lado cerca de ella,
        no existe interseccion y por tanto no hay conteo.
        """
        px, py = previous_point
        cx, cy = current_point

        if math.hypot(cx - px, cy - py) < 0.5:
            return None

        epsilon = 1e-7

        for index in range(len(self.points) - 1):
            p1 = self.points[index]
            p2 = self.points[index + 1]

            previous_distance = self._line_signed_distance(
                previous_point,
                p1,
                p2
            )
            current_distance = self._line_signed_distance(
                current_point,
                p1,
                p2
            )

            if previous_distance is None or current_distance is None:
                continue

            previous_side = self._sign(previous_distance)
            current_side = self._sign(current_distance)

            # Si ambos puntos estan exactamente sobre el segmento, el pie se
            # esta desplazando por la linea, no cruzandola.
            if previous_side == 0 and current_side == 0:
                continue

            denominator = previous_distance - current_distance
            if abs(denominator) <= epsilon:
                continue

            # Fraccion del movimiento en la que alcanza la recta del segmento.
            movement_t = previous_distance / denominator
            if movement_t < -epsilon or movement_t > 1.0 + epsilon:
                continue

            intersection = (
                px + movement_t * (cx - px),
                py + movement_t * (cy - py)
            )

            # CLAVE: la interseccion tiene que caer dentro del segmento
            # dibujado. No se acepta la prolongacion imaginaria de la linea.
            line_t = self._segment_projection(
                intersection,
                p1,
                p2
            )
            if line_t is None:
                continue

            if line_t < -epsilon or line_t > 1.0 + epsilon:
                continue

            # Cruce directo entre dos lados.
            if (
                previous_side != 0
                and current_side != 0
                and previous_side != current_side
            ):
                return {
                    "segment_index": index,
                    "origin_side": previous_side,
                    "destination_side": current_side,
                    "destination_distance": abs(current_distance)
                }

            # El frame termino justo encima de la linea. Guardamos el contacto
            # y esperamos a ver hacia que lado sale el mismo punto.
            if previous_side != 0 and current_side == 0:
                return {
                    "segment_index": index,
                    "origin_side": previous_side,
                    "destination_side": None,
                    "destination_distance": 0.0
                }

        return None

    def _distance_from_segment_line(self, point, segment_index):
        if segment_index < 0 or segment_index >= len(self.points) - 1:
            return None

        return self._line_signed_distance(
            point,
            self.points[segment_index],
            self.points[segment_index + 1]
        )

    def _new_state(self, point):
        distance = abs(self.signed_distance(point))
        return {
            "last_point": point,
            "armed": distance >= self.rearm_margin,
            "pending_crossing": None
        }

    def update(self, track_id, point):
        """
        Cuenta EXCLUSIVAMENTE por el punto inferior de la persona.

        Requisitos para IN/OUT:
        1. Debe existir un punto anterior del MISMO ID.
        2. El segmento recorrido por ese punto debe cortar fisicamente la linea.
        3. La interseccion debe estar dentro de la linea dibujada.
        4. El punto debe confirmar que termino al otro lado.

        Cuerpo, cabeza, bounding box, reflejos cercanos y cambios de lado fuera
        de los extremos no pueden generar un evento por si solos.
        """
        current_point = (
            float(point[0]),
            float(point[1])
        )

        if track_id not in self.states:
            self.states[track_id] = self._new_state(current_point)
            return None

        state = self.states[track_id]
        previous_point = state["last_point"]
        state["last_point"] = current_point

        pending = state.get("pending_crossing")

        # Despues de contar se exige separarse nuevamente de la linea antes de
        # habilitar otro evento para el mismo ID.
        if not state["armed"]:
            if abs(self.signed_distance(current_point)) >= self.rearm_margin:
                state["armed"] = True
            else:
                return None

        # Si el frame anterior termino justo sobre la linea, solo se confirma
        # cuando ese mismo punto sale claramente por el lado contrario.
        if pending is not None:
            distance = self._distance_from_segment_line(
                current_point,
                pending["segment_index"]
            )

            if distance is not None:
                side = self._sign(distance)
                origin_side = pending["origin_side"]

                if (
                    side != 0
                    and side != origin_side
                    and abs(distance) >= self.crossing_margin
                ):
                    state["pending_crossing"] = None
                    state["armed"] = False
                    return self._register_crossing(side)

                if (
                    side == origin_side
                    and abs(distance) >= self.crossing_margin
                ):
                    # Toco la linea pero regreso al mismo lado.
                    state["pending_crossing"] = None

            # Mientras sigue pegado a la linea no inventamos ningun evento.
            if state.get("pending_crossing") is not None:
                return None

        crossing = self._find_actual_crossing(
            previous_point,
            current_point
        )

        if crossing is None:
            return None

        origin_side = crossing["origin_side"]
        destination_side = crossing["destination_side"]

        if destination_side is None:
            state["pending_crossing"] = {
                "segment_index": crossing["segment_index"],
                "origin_side": origin_side
            }
            return None

        # El movimiento ya atraveso la linea finita. Si el punto quedo apenas
        # encima, esperamos confirmacion para evitar jitter de 1-2 pixeles.
        if crossing["destination_distance"] < self.crossing_margin:
            state["pending_crossing"] = {
                "segment_index": crossing["segment_index"],
                "origin_side": origin_side
            }
            return None

        state["pending_crossing"] = None
        state["armed"] = False
        return self._register_crossing(destination_side)

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
