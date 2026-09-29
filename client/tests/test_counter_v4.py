import unittest

from app.detection.counter import LineCounter


class LineCounterV41Tests(unittest.TestCase):

    def make_counter(self):
        return LineCounter(
            points=[(0, 100), (500, 100)],
            in_side=1,
            margin=18
        )

    @staticmethod
    def feed(counter, track_id, points):
        events = []
        for point in points:
            event = counter.update(track_id, point)
            if event:
                events.append(event)
        return events

    @staticmethod
    def feed_with_movement(
        counter,
        track_id,
        samples
    ):
        events = []

        for point, movement_point in samples:
            event = counter.update(
                track_id,
                point,
                movement_point
            )

            if event:
                events.append(event)

        return events

    def test_normal_in_counts_once(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, 65), (100, 70), (100, 78),
                (100, 95), (100, 108),
                (100, 120), (100, 125)
            ]
        )
        self.assertEqual(events, ["IN"])

    def test_normal_out_counts_once(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, 135), (100, 130), (100, 120),
                (100, 105), (100, 92),
                (100, 80), (100, 75)
            ]
        )
        self.assertEqual(events, ["OUT"])

    def test_jitter_inside_corridor_does_not_count(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, 70), (100, 75),
                (100, 94), (100, 102), (100, 97),
                (100, 104), (100, 96), (100, 103),
                (100, 75), (100, 70)
            ]
        )
        self.assertEqual(events, [])

    def test_touch_and_return_does_not_count(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, 65), (100, 70),
                (100, 92), (100, 101),
                (100, 90), (100, 75), (100, 70)
            ]
        )
        self.assertEqual(events, [])

    def test_birth_inside_neutral_then_leave_does_not_count(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, 99), (100, 96),
                (100, 88), (100, 78),
                (100, 70), (100, 65)
            ]
        )
        self.assertEqual(events, [])

    def test_same_transit_cannot_duplicate(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            529,
            [
                (100, 65), (100, 70),
                (100, 95), (100, 120), (100, 125),
                (100, 130), (100, 122), (100, 128)
            ]
        )
        self.assertEqual(events, ["IN"])

    def test_real_in_then_real_out_is_allowed(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, 65), (100, 70),
                (100, 95), (100, 120), (100, 125),
                (100, 130), (100, 135), (100, 130),
                (100, 120), (100, 105), (100, 92),
                (100, 80), (100, 75), (100, 70)
            ]
        )
        self.assertEqual(events, ["IN", "OUT"])

    def test_crouch_and_stand_on_line_does_not_count(self):
        counter = self.make_counter()

        events = self.feed_with_movement(
            counter,
            7,
            [
                ((100, 70), (100, 180)),
                ((100, 72), (100, 181)),
                ((100, 88), (100, 180)),
                ((100, 105), (100, 181)),
                ((100, 122), (100, 182)),
                ((100, 125), (100, 181)),
                ((100, 108), (100, 180)),
                ((100, 92), (100, 181)),
                ((100, 72), (100, 180)),
                ((100, 70), (100, 181)),
            ]
        )

        self.assertEqual(events, [])

    def test_fast_torso_jitter_with_static_feet_does_not_count(self):
        counter = self.make_counter()

        events = self.feed_with_movement(
            counter,
            8,
            [
                ((100, 70), (100, 180)),
                ((100, 72), (100, 181)),
                ((100, 125), (100, 180)),
                ((100, 128), (100, 182)),
                ((100, 70), (100, 181)),
                ((100, 68), (100, 180)),
                ((100, 126), (100, 181)),
                ((100, 130), (100, 182)),
            ]
        )

        self.assertEqual(events, [])

    def test_real_walk_counts_when_feet_progress_too(self):
        counter = self.make_counter()

        events = self.feed_with_movement(
            counter,
            9,
            [
                ((100, 65), (100, 170)),
                ((100, 70), (100, 175)),
                ((100, 88), (100, 185)),
                ((100, 104), (100, 198)),
                ((100, 122), (100, 215)),
                ((100, 128), (100, 225)),
            ]
        )

        self.assertEqual(events, ["IN"])

    def test_real_out_counts_when_feet_progress_back(self):
        counter = self.make_counter()

        events = self.feed_with_movement(
            counter,
            10,
            [
                ((100, 135), (100, 225)),
                ((100, 130), (100, 220)),
                ((100, 112), (100, 210)),
                ((100, 98), (100, 195)),
                ((100, 80), (100, 178)),
                ((100, 72), (100, 168)),
            ]
        )

        self.assertEqual(events, ["OUT"])

    def test_crossing_outside_segment_does_not_count(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (600, 65), (600, 70),
                (600, 95), (600, 120), (600, 125)
            ]
        )
        self.assertEqual(events, [])

    def test_large_jump_does_not_create_crossing(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, -250), (100, -245),
                (100, 350), (100, 360)
            ]
        )
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
