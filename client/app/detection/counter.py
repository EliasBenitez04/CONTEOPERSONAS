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

        self.in_side = in_side

        # Distancia que debe superar para
        # considerar que llegó a un lado estable
        self.margin = margin

        self.entries = 0
        self.exits = 0

        # Estado independiente de cada ID
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

        length = math.hypot(
            dx,
            dy
        )

        if length == 0:
            return 0.0

        value = (
            dx * (py - y1)
            -
            dy * (px - x1)
        )

        return value / length

    # ==========================================
    # SIGNO
    # ==========================================

    @staticmethod
    def _sign(value):

        if value > 0:
            return 1

        if value < 0:
            return -1

        return 0

    # ==========================================
    # UPDATE
    # ==========================================

    def update(
        self,
        track_id,
        point
    ):

        distance = self.signed_distance(
            point
        )

        raw_side = self._sign(
            distance
        )

        if track_id not in self.states:

            self.states[track_id] = {
                # Primer lado del que parece venir
                "origin_side": None,

                # Último lado confirmado
                "stable_side": None
            }

        state = self.states[
            track_id
        ]

        # ==========================================
        # PRIMERA APARICION
        #
        # Incluso si aparece cerca de la línea,
        # guardamos el signo.
        # ==========================================

        if state["origin_side"] is None:

            if raw_side != 0:

                state[
                    "origin_side"
                ] = raw_side

        # ==========================================
        # TODAVIA ESTA EN LA ZONA CENTRAL
        #
        # NO contamos, pero tampoco olvidamos
        # de qué lado venía.
        # ==========================================

        if abs(distance) < self.margin:

            return None

        current_stable_side = raw_side

        # ==========================================
        # PRIMER LADO ESTABLE
        # ==========================================

        if state["stable_side"] is None:

            # Si apareció cerca de la línea y ahora
            # llegó al lado contrario al signo inicial,
            # significa que ya completó un cruce.
            if (
                state["origin_side"] is not None
                and
                state["origin_side"]
                != current_stable_side
            ):

                event = self._register_crossing(
                    current_stable_side
                )

                state[
                    "stable_side"
                ] = current_stable_side

                state[
                    "origin_side"
                ] = current_stable_side

                return event

            state[
                "stable_side"
            ] = current_stable_side

            state[
                "origin_side"
            ] = current_stable_side

            return None

        # ==========================================
        # SIGUE DEL MISMO LADO
        # ==========================================

        if (
            state["stable_side"]
            == current_stable_side
        ):

            return None

        # ==========================================
        # CRUCE CONFIRMADO
        # ==========================================

        event = self._register_crossing(
            current_stable_side
        )

        state[
            "stable_side"
        ] = current_stable_side

        state[
            "origin_side"
        ] = current_stable_side

        return event

    # ==========================================
    # REGISTRAR EVENTO
    # ==========================================

    def _register_crossing(
        self,
        destination_side
    ):

        if (
            destination_side
            == self.in_side
        ):

            self.entries += 1

            return "IN"

        self.exits += 1

        return "OUT"

    # ==========================================
    # CONFIGURACION
    # ==========================================

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