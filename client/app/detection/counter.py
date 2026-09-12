import math


class LineCounter:

    def __init__(
        self,
        point1,
        point2,
        in_side=1,
        margin=18
    ):

        self.point1 = point1
        self.point2 = point2
        self.in_side = 1 if in_side >= 0 else -1
        self.margin = max(4, int(margin))

        # Umbral mas pequeno que confirma que el centro de la persona
        # realmente paso al otro lado de la linea. El margen grande se
        # conserva para rearmar el contador y evitar dobles conteos.
        self.crossing_margin = max(
            4.0,
            self.margin * 0.35
        )

        self.entries = 0
        self.exits = 0

        # Estado independiente de cada track de ByteTrack.
        self.states = {}

    # ==========================================
    # DISTANCIA CON SIGNO A LA LINEA
    # ==========================================

    def signed_distance(self, point):

        px, py = point
        x1, y1 = self.point1
        x2, y2 = self.point2

        dx = x2 - x1
        dy = y2 - y1

        length = math.hypot(dx, dy)

        if length == 0:
            return 0.0

        value = (
            dx * (py - y1)
            - dy * (px - x1)
        )

        return value / length

    @staticmethod
    def _sign(value):

        if value > 0:
            return 1

        if value < 0:
            return -1

        return 0

    # ==========================================
    # ACTUALIZAR TRACK
    # ==========================================

    def update(self, track_id, point):

        distance = self.signed_distance(point)
        raw_side = self._sign(distance)

        if raw_side == 0:
            return None

        if track_id not in self.states:
            self.states[track_id] = {
                "origin_side": None,
                "stable_side": None,
                "armed": False
            }

        state = self.states[track_id]

        # No tomamos como origen un punto pegado a la linea porque
        # pequeñas oscilaciones del bounding box pueden cambiar el signo.
        if (
            state["origin_side"] is None
            and abs(distance) >= self.crossing_margin
        ):
            state["origin_side"] = raw_side

        # Primer lado estable del track.
        if state["stable_side"] is None:

            # Caso importante: el ID apareció cerca de la linea y ya
            # alcanzó claramente el lado contrario. Se cuenta el cruce.
            if (
                state["origin_side"] is not None
                and raw_side != state["origin_side"]
                and abs(distance) >= self.crossing_margin
            ):
                event = self._register_crossing(raw_side)
                state["stable_side"] = raw_side
                state["origin_side"] = raw_side
                state["armed"] = False
                return event

            # Si todavía no cruzó, esperamos que se aleje del centro para
            # considerar ese lado como estable y habilitar un cruce.
            if abs(distance) >= self.margin:
                state["stable_side"] = raw_side
                state["origin_side"] = raw_side
                state["armed"] = True

            return None

        # Después de un conteo exigimos que la persona se aleje hasta el
        # margen completo antes de permitir un cruce de regreso. Esto evita
        # IN/OUT repetidos por vibración del tracking sobre la línea.
        if not state["armed"]:

            if (
                raw_side == state["stable_side"]
                and abs(distance) >= self.margin
            ):
                state["armed"] = True

            return None

        # Sigue del mismo lado.
        if raw_side == state["stable_side"]:
            return None

        # Ya cambió de signo, pero esperamos una separación mínima para
        # confirmar que no fue ruido del bounding box.
        if abs(distance) < self.crossing_margin:
            return None

        event = self._register_crossing(raw_side)

        state["stable_side"] = raw_side
        state["origin_side"] = raw_side
        state["armed"] = False

        return event

    # ==========================================
    # REGISTRAR EVENTO
    # ==========================================

    def _register_crossing(self, destination_side):

        if destination_side == self.in_side:
            self.entries += 1
            return "IN"

        self.exits += 1
        return "OUT"

    # ==========================================
    # CONFIGURACION
    # ==========================================

    def set_line(self, point1, point2):

        self.point1 = point1
        self.point2 = point2
        self.states.clear()

    def set_in_side(self, in_side):

        self.in_side = 1 if in_side >= 0 else -1
        self.states.clear()

    def invert_direction(self):

        self.in_side *= -1
        self.states.clear()

    def reset_counts(self):

        self.entries = 0
        self.exits = 0
        self.states.clear()

    def set_counts(self, entries, exits):
        """Compatibilidad para restauraciones manuales; no se usa al iniciar."""

        self.entries = int(entries)
        self.exits = int(exits)
