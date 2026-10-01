import math
import time


class LineCounter:
    """
    Contador V4.2.0: cruce por torso + validacion de locomocion.

    El torso decide si hubo cruce geometrico de la polilinea, pero un evento
    solo se confirma si el punto inferior (apoyo/pies) tambien demuestra
    desplazamiento real en la misma direccion perpendicular a la linea.

    Esto evita que agacharse, levantarse o deformar el bbox sobre la linea
    genere IN/OUT sin que la persona haya caminado realmente.
    """

    def __init__(
        self,
        point1=None,
        point2=None,
        points=None,
        in_side=1,
        margin=18
    ):
        self.points = self._normalize_points(
            points,
            point1,
            point2
        )
        self.point1 = self.points[0]
        self.point2 = self.points[-1]
        self.in_side = 1 if int(in_side) >= 0 else -1

        self.entries = 0
        self.exits = 0
        self.states = {}

        self.stable_frames = 3
        self.destination_frames = 3
        self.rearm_frames = 3
        self.max_step = 260.0
        self.crossing_timeout_seconds = 4.0

        self.set_margin(margin)

    @staticmethod
    def _normalize_points(
        points,
        point1=None,
        point2=None
    ):
        normalized = []

        if points:
            for point in points:
                if point is not None and len(point) >= 2:
                    normalized.append((
                        int(round(point[0])),
                        int(round(point[1]))
                    ))

        if len(normalized) < 2:
            p1 = (
                point1
                if point1 is not None
                else (640, 100)
            )
            p2 = (
                point2
                if point2 is not None
                else (640, 650)
            )
            normalized = [
                (int(p1[0]), int(p1[1])),
                (int(p2[0]), int(p2[1]))
            ]

        compact = [normalized[0]]
        for point in normalized[1:]:
            if point != compact[-1]:
                compact.append(point)

        if len(compact) < 2:
            compact.append((
                compact[0][0],
                compact[0][1] + 1
            ))

        return compact

    @property
    def margin(self):
        return self._margin

    @margin.setter
    def margin(self, value):
        self.set_margin(value)

    def set_margin(self, margin):
        self._margin = max(6, int(margin))

        # Franja central donde no se toman decisiones por jitter.
        self.crossing_margin = max(
            6.0,
            min(
                24.0,
                self._margin * 0.60
            )
        )

        # El torso debe terminar fuera de esta distancia para confirmar lado.
        self.confirm_margin = max(
            self.crossing_margin + 5.0,
            min(
                42.0,
                self._margin * 1.00
            )
        )

        # Distancia POST-CRUCE. Tocar/cruzar la linea no alcanza:
        # el torso debe alejarse claramente hacia el destino antes de contar.
        self.completion_margin = max(
            self.confirm_margin + 12.0,
            min(
                64.0,
                self._margin * 2.0
            )
        )

        # Movimiento minimo REAL del punto inferior DESPUES del cruce.
        # Con margin=18 exige ~32 px de locomocion perpendicular.
        self.movement_confirm_distance = max(
            28.0,
            min(
                56.0,
                self._margin * 1.80
            )
        )

        # Despues de contar, debe alejarse aun mas antes de rearmar el ID.
        self.rearm_margin = max(
            self.completion_margin + 10.0,
            min(
                78.0,
                self._margin * 2.40
            )
        )

        if hasattr(self, "states"):
            self.states.clear()

        return self._margin

    @staticmethod
    def _line_signed_distance(
        point,
        p1,
        p2
    ):
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
    def _segment_projection(
        point,
        p1,
        p2
    ):
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
    def _segment_distance(
        cls,
        point,
        p1,
        p2
    ):
        projection = cls._segment_projection(
            point,
            p1,
            p2
        )
        signed = cls._line_signed_distance(
            point,
            p1,
            p2
        )

        if projection is None or signed is None:
            return None

        projection = max(
            0.0,
            min(1.0, projection)
        )

        nearest_x = (
            p1[0]
            + projection * (p2[0] - p1[0])
        )
        nearest_y = (
            p1[1]
            + projection * (p2[1] - p1[1])
        )

        euclidean = math.hypot(
            point[0] - nearest_x,
            point[1] - nearest_y
        )

        return (
            euclidean
            if signed >= 0
            else -euclidean
        )

    def signed_distance(self, point):
        best = None

        for index in range(len(self.points) - 1):
            value = self._segment_distance(
                point,
                self.points[index],
                self.points[index + 1]
            )

            if (
                value is not None
                and (
                    best is None
                    or abs(value) < abs(best)
                )
            ):
                best = value

        return (
            0.0
            if best is None
            else float(best)
        )

    @staticmethod
    def _sign(
        value,
        epsilon=1e-6
    ):
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

    def _find_actual_crossing(
        self,
        previous_point,
        current_point
    ):
        px, py = previous_point
        cx, cy = current_point

        movement = math.hypot(
            cx - px,
            cy - py
        )

        if (
            movement < 0.5
            or movement > self.max_step
        ):
            return None

        epsilon = 1e-7

        for index in range(len(self.points) - 1):
            p1 = self.points[index]
            p2 = self.points[index + 1]

            previous_distance = (
                self._line_signed_distance(
                    previous_point,
                    p1,
                    p2
                )
            )
            current_distance = (
                self._line_signed_distance(
                    current_point,
                    p1,
                    p2
                )
            )

            if (
                previous_distance is None
                or current_distance is None
            ):
                continue

            previous_side = self._sign(
                previous_distance
            )
            current_side = self._sign(
                current_distance
            )

            if (
                previous_side == 0
                and current_side == 0
            ):
                continue

            denominator = (
                previous_distance
                - current_distance
            )

            if abs(denominator) <= epsilon:
                continue

            movement_t = (
                previous_distance
                / denominator
            )

            if (
                movement_t < -epsilon
                or movement_t > 1.0 + epsilon
            ):
                continue

            intersection = (
                px + movement_t * (cx - px),
                py + movement_t * (cy - py)
            )

            line_t = self._segment_projection(
                intersection,
                p1,
                p2
            )

            if (
                line_t is None
                or line_t < -epsilon
                or line_t > 1.0 + epsilon
            ):
                continue

            if (
                previous_side != 0
                and current_side != 0
                and previous_side != current_side
            ):
                return index

            if (
                previous_side != 0
                and current_side == 0
            ):
                return index

        return None

    def _movement_progress(
        self,
        start_point,
        current_point,
        segment_index,
        destination_side
    ):
        """
        Desplazamiento del punto inferior proyectado sobre la normal del
        segmento que realmente cruzo el torso.

        Un valor positivo significa movimiento hacia el lado destino.
        """
        if (
            start_point is None
            or current_point is None
            or segment_index is None
        ):
            return 0.0

        p1 = self.points[segment_index]
        p2 = self.points[segment_index + 1]

        start_distance = (
            self._line_signed_distance(
                start_point,
                p1,
                p2
            )
        )
        current_distance = (
            self._line_signed_distance(
                current_point,
                p1,
                p2
            )
        )

        if (
            start_distance is None
            or current_distance is None
        ):
            return 0.0

        return (
            current_distance
            - start_distance
        ) * destination_side

    def _new_state(
        self,
        point,
        movement_point
    ):
        return {
            "last_point": point,
            "last_movement_point": movement_point,
            "stable_side": None,
            "stable_count": 0,
            "origin_side": None,
            "crossed": False,
            "crossed_at": None,
            "segment_index": None,
            "destination_side": None,
            "destination_count": 0,
            "movement_start_point": None,
            "locked": False,
            "rearm_side": None,
            "rearm_count": 0,
        }

    @staticmethod
    def _cancel_crossing(state):
        state["crossed"] = False
        state["crossed_at"] = None
        state["segment_index"] = None
        state["destination_side"] = None
        state["destination_count"] = 0
        state["movement_start_point"] = None

    def update(
        self,
        track_id,
        point,
        movement_point=None
    ):
        current = (
            float(point[0]),
            float(point[1])
        )

        # Compatibilidad con llamadas antiguas/tests: si no llega punto
        # inferior, usa el mismo punto. En produccion V4.1.1 siempre llega.
        if movement_point is None:
            movement_current = current
        else:
            movement_current = (
                float(movement_point[0]),
                float(movement_point[1])
            )

        if track_id not in self.states:
            state = self._new_state(
                current,
                movement_current
            )

            distance = self.signed_distance(
                current
            )
            side = (
                0
                if abs(distance) < self.crossing_margin
                else self._sign(distance)
            )

            if (
                side != 0
                and abs(distance) >= self.confirm_margin
            ):
                state["stable_side"] = side
                state["stable_count"] = 1

            self.states[track_id] = state
            return None

        state = self.states[track_id]

        previous = state["last_point"]
        previous_movement = (
            state["last_movement_point"]
        )

        state["last_point"] = current
        state["last_movement_point"] = (
            movement_current
        )

        distance = self.signed_distance(
            current
        )
        side = (
            0
            if abs(distance) < self.crossing_margin
            else self._sign(distance)
        )

        now = time.monotonic()

        if (
            state["crossed"]
            and state["crossed_at"] is not None
            and (
                now - state["crossed_at"]
                > self.crossing_timeout_seconds
            )
        ):
            self._cancel_crossing(state)
            state["origin_side"] = None
            state["stable_side"] = None
            state["stable_count"] = 0

        # Despues de un conteo, jitter o agacharse cerca de la linea no puede
        # volver a disparar hasta que el torso se aleje claramente.
        if state["locked"]:
            if (
                side == state["rearm_side"]
                and abs(distance) >= self.rearm_margin
            ):
                state["rearm_count"] += 1

                if (
                    state["rearm_count"]
                    >= self.rearm_frames
                ):
                    state["locked"] = False
                    state["stable_side"] = side
                    state["stable_count"] = (
                        self.stable_frames
                    )
                    state["origin_side"] = side
                    self._cancel_crossing(state)
            else:
                state["rearm_count"] = 0

            return None

        # Antes del cruce: demostrar un origen estable fuera del corredor.
        if not state["crossed"]:
            if (
                side != 0
                and abs(distance) >= self.confirm_margin
            ):
                if side == state["stable_side"]:
                    state["stable_count"] += 1
                else:
                    state["stable_side"] = side
                    state["stable_count"] = 1

                if (
                    state["stable_count"]
                    >= self.stable_frames
                ):
                    state["origin_side"] = side

            elif (
                side != 0
                and side != state["stable_side"]
            ):
                state["stable_count"] = 0

            segment_index = (
                self._find_actual_crossing(
                    previous,
                    current
                )
            )

            if (
                segment_index is not None
                and state["origin_side"] is not None
            ):
                previous_raw = (
                    self._line_signed_distance(
                        previous,
                        self.points[segment_index],
                        self.points[
                            segment_index + 1
                        ]
                    )
                )

                if (
                    previous_raw is not None
                    and self._sign(previous_raw)
                    == state["origin_side"]
                ):
                    state["crossed"] = True
                    state["crossed_at"] = now
                    state["segment_index"] = (
                        segment_index
                    )
                    state["destination_side"] = (
                        -state["origin_side"]
                    )
                    state["destination_count"] = 0

                    # Se toma el apoyo inmediatamente ANTES del cruce del
                    # torso. Agacharse deja este punto casi igual; caminar no.
                    state["movement_start_point"] = (
                        previous_movement
                    )

            if not state["crossed"]:
                return None

        segment_index = state["segment_index"]

        segment_distance = (
            self._line_signed_distance(
                current,
                self.points[segment_index],
                self.points[segment_index + 1]
            )
        )

        if segment_distance is None:
            return None

        segment_side = (
            0
            if abs(segment_distance)
            < self.crossing_margin
            else self._sign(segment_distance)
        )

        destination = (
            state["destination_side"]
        )

        movement_progress = (
            self._movement_progress(
                state["movement_start_point"],
                movement_current,
                segment_index,
                destination
            )
        )

        # Solo suma frames de destino cuando:
        # 1) el torso ya recorrio una distancia POST-CRUCE suficiente;
        # 2) el punto inferior tambien demostro locomocion real;
        # 3) esto se mantiene varios frames consecutivos.
        #
        # Importante: cruzar/tocar la linea NO genera el evento.
        if (
            segment_side == destination
            and abs(segment_distance)
            >= self.completion_margin
            and movement_progress
            >= self.movement_confirm_distance
        ):
            state["destination_count"] += 1

        elif (
            segment_side == state["origin_side"]
            and abs(segment_distance)
            >= self.confirm_margin
        ):
            # Volvio al origen: no hubo cruce completo.
            self._cancel_crossing(state)
            state["stable_side"] = (
                state["origin_side"]
            )
            state["stable_count"] = (
                self.stable_frames
            )
            return None

        else:
            # Sigue dentro del corredor, o el torso cruzo pero los pies no
            # demostraron locomocion real. Mantener pendiente sin contar.
            return None

        if (
            state["destination_count"]
            < self.destination_frames
        ):
            return None

        state["locked"] = True
        state["rearm_side"] = destination
        state["rearm_count"] = 0

        self._cancel_crossing(state)

        return self._register_crossing(
            destination
        )

    def _register_crossing(
        self,
        destination_side
    ):
        if destination_side == self.in_side:
            self.entries += 1
            return "IN"

        self.exits += 1
        return "OUT"

    def set_line(
        self,
        point1=None,
        point2=None,
        points=None
    ):
        self.points = self._normalize_points(
            points,
            point1,
            point2
        )
        self.point1 = self.points[0]
        self.point2 = self.points[-1]
        self.states.clear()

    def set_in_side(
        self,
        in_side,
        swap_counts=False
    ):
        new_side = (
            1
            if int(in_side) >= 0
            else -1
        )
        changed = new_side != self.in_side

        if changed and swap_counts:
            self.entries, self.exits = (
                self.exits,
                self.entries
            )

        self.in_side = new_side
        self.states.clear()

        return changed

    def invert_direction(
        self,
        swap_counts=False
    ):
        return self.set_in_side(
            -self.in_side,
            swap_counts=swap_counts
        )

    def reset_counts(self):
        self.entries = 0
        self.exits = 0
        self.states.clear()
