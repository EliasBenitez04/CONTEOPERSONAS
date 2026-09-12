import math


class LineCounter:

    def __init__(
        self,
        point1,
        point2,
        in_side=1,
        margin=35
    ):

        self.point1 = point1
        self.point2 = point2

        self.in_side = in_side

        self.margin = margin

        self.entries = 0
        self.exits = 0

        # Estado individual por ID
        self.states = {}

    def _signed_distance(
        self,
        point
    ):

        px, py = point

        x1, y1 = self.point1
        x2, y2 = self.point2

        dx = x2 - x1
        dy = y2 - y1

        length = math.sqrt(
            dx * dx + dy * dy
        )

        if length == 0:
            return 0

        # Distancia perpendicular con signo
        value = (
            dx * (py - y1)
            -
            dy * (px - x1)
        )

        return value / length

    def _stable_side(
        self,
        point
    ):

        distance = self._signed_distance(
            point
        )

        # Zona muerta alrededor de la línea
        if abs(distance) < self.margin:
            return 0

        if distance > 0:
            return 1

        return -1

    def update(
        self,
        track_id,
        point
    ):

        side = self._stable_side(
            point
        )

        # ==============================
        # CREAR ESTADO DEL ID
        # ==============================

        if track_id not in self.states:

            self.states[track_id] = {
                "origin_side": None,
                "last_side": None
            }

        state = self.states[
            track_id
        ]

        # ==========================================
        # ESTÁ CERCA DE LA LÍNEA
        # No hacemos absolutamente nada
        # ==========================================

        if side == 0:
            return None

        # ==========================================
        # PRIMER LADO ESTABLE OBSERVADO
        # ==========================================

        if state["origin_side"] is None:

            state["origin_side"] = side
            state["last_side"] = side

            return None

        # ==========================================
        # SIGUE DEL MISMO LADO
        # ==========================================

        if side == state["last_side"]:

            return None

        # ==========================================
        # LLEGÓ ESTABLE AL OTRO LADO
        # CRUCE CONFIRMADO
        # ==========================================

        old_side = state["last_side"]

        state["last_side"] = side
        state["origin_side"] = side

        # Entró hacia el lado configurado como IN
        if side == self.in_side:

            self.entries += 1

            return "IN"

        # Se movió hacia el lado OUT
        self.exits += 1

        return "OUT"

    def set_line(
        self,
        point1,
        point2
    ):

        self.point1 = point1
        self.point2 = point2

        self.states.clear()

    def set_in_side(
        self,
        in_side
    ):

        self.in_side = in_side

        self.states.clear()

    def invert_direction(self):

        self.in_side *= -1

        self.states.clear()

    def reset_counts(self):

        self.entries = 0
        self.exits = 0

        self.states.clear()