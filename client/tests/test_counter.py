import unittest

from app.detection.counter import LineCounter


class LineCounterTests(unittest.TestCase):

    def setUp(self):
        # Linea vertical de abajo hacia arriba.
        # signed_distance > 0 queda a la derecha.
        self.counter = LineCounter(
            point1=(0, 100),
            point2=(0, 0),
            in_side=1,
            margin=18
        )

    def _cross(self, track_id, xs):
        events = []

        for x in xs:
            event = self.counter.update(
                track_id,
                (x, 50)
            )

            if event:
                events.append(event)

        return events

    def test_positive_destination_counts_as_in(self):
        events = self._cross(
            1,
            [-30, -10, 0, 10, 30]
        )

        self.assertEqual(events, ["IN"])
        self.assertEqual(self.counter.entries, 1)
        self.assertEqual(self.counter.exits, 0)

    def test_inverting_direction_swaps_existing_counts(self):
        self._cross(
            1,
            [-30, -10, 0, 10, 30]
        )

        changed = self.counter.set_in_side(
            -1,
            swap_counts=True
        )

        self.assertTrue(changed)
        self.assertEqual(self.counter.in_side, -1)
        self.assertEqual(self.counter.entries, 0)
        self.assertEqual(self.counter.exits, 1)

    def test_after_inversion_negative_destination_is_in(self):
        self.counter.set_in_side(
            -1,
            swap_counts=True
        )

        events = self._cross(
            2,
            [30, 10, 0, -10, -30]
        )

        self.assertEqual(events, ["IN"])
        self.assertEqual(self.counter.entries, 1)
        self.assertEqual(self.counter.exits, 0)


if __name__ == "__main__":
    unittest.main()
