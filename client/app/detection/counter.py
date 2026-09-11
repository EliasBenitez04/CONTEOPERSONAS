class LineCounter:

    def __init__(
        self,
        point1,
        point2,
        in_side=1,
        min_frames_between_counts=10
    ):
        self.point1 = point1
        self.point2 = point2

        # Indica qué lado matemático consideramos IN.
        # Puede ser 1 o -1.
        self.in_side = in_side

        self.entries = 0
        self.exits = 0

        # Último lado conocido de cada ID
        self.last_side = {}

        # Para evitar doble conteo inmediato
        self.last_count_frame = {}

        self.frame_number = 0
        self.min_frames_between_counts = (
            min_frames_between_counts
        )

    def _side_of_line(self, point):

        x, y = point

        x1, y1 = self.point1
        x2, y2 = self.point2

        value = (
            (x2 - x1) * (y - y1)
            -
            (y2 - y1) * (x - x1)
        )

        if value > 0:
            return 1

        if value < 0:
            return -1

        return 0

    def update(self, track_id, point):

        self.frame_number += 1

        current_side = self._side_of_line(
            point
        )

        if current_side == 0:
            return None

        previous_side = self.last_side.get(
            track_id
        )

        self.last_side[track_id] = (
            current_side
        )

        # Primera vez que vemos ese ID
        if previous_side is None:
            return None

        # Sigue del mismo lado
        if previous_side == current_side:
            return None

        # Protección contra doble conteo
        last_count = self.last_count_frame.get(
            track_id,
            -99999
        )

        if (
            self.frame_number - last_count
            <
            self.min_frames_between_counts
        ):
            return None

        self.last_count_frame[track_id] = (
            self.frame_number
        )

        # Entró al lado IN
        if current_side == self.in_side:

            self.entries += 1

            return "IN"

        # Salió del lado IN
        self.exits += 1

        return "OUT"

    def set_line(
        self,
        point1,
        point2
    ):

        self.point1 = point1
        self.point2 = point2

        self.last_side.clear()

    def invert_direction(self):

        self.in_side *= -1

        self.last_side.clear()