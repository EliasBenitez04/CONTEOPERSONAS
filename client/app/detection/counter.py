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
        self.in_side = 1 if int(in_side) >= 0 else -1
        self.entries = 0
        self.exits = 0
        self.states = {}
        self.set_margin(margin)

    def set_margin(self, margin):
        self.margin = max(6, int(margin))
        self.crossing_margin = max(
            4.0,
            self.margin * 0.28
        )
        self.rearm_margin = max(
            self.crossing_margin * 2.0,
            self.margin * 0.65
        )
        self.states.clear()
        return self.margin

    def signed_distance(self, point):
        px, py = point
        x1, y1 = self.point1
        x2, y2 = self.point2
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length == 0:
            return 0.0
        value = dx * (py - y1) - dy * (px - x1)
        return value / length

    @staticmethod
    def _sign(value):
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    def update(self, track_id, point):
        distance = self.signed_distance(point)
        side = self._sign(distance)
        if side == 0:
            return None

        if track_id not in self.states:
            self.states[track_id] = {
                "origin_side": side,
                "stable_side": None,
                "armed": False
            }

        state = self.states[track_id]
        if state["origin_side"] is None:
            state["origin_side"] = side

        if state["stable_side"] is None:
            if (
                side != state["origin_side"]
                and abs(distance) >= self.crossing_margin
            ):
                event = self._register_crossing(side)
                state["stable_side"] = side
                state["origin_side"] = side
                state["armed"] = False
                return event

            if abs(distance) >= self.rearm_margin:
                state["stable_side"] = side
                state["origin_side"] = side
                state["armed"] = True
            return None

        if not state["armed"]:
            if (
                side == state["stable_side"]
                and abs(distance) >= self.rearm_margin
            ):
                state["armed"] = True
            return None

        if side == state["stable_side"]:
            return None
        if abs(distance) < self.crossing_margin:
            return None

        event = self._register_crossing(side)
        state["stable_side"] = side
        state["origin_side"] = side
        state["armed"] = False
        return event

    def _register_crossing(self, destination_side):
        if destination_side == self.in_side:
            self.entries += 1
            return "IN"
        self.exits += 1
        return "OUT"

    def set_line(self, point1, point2):
        self.point1 = point1
        self.point2 = point2
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
