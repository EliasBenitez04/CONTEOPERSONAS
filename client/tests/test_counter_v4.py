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
                (100, 95), (100, 108), (100, 120),
                (100, 138), (100, 145), (100, 152)
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
                (100, 105), (100, 92), (100, 80),
                (100, 62), (100, 55), (100, 48)
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
                (100, 65), (100, 70), (100, 80),
                (100, 95), (100, 110), (100, 125),
                (100, 138), (100, 145), (100, 152),
                (100, 148), (100, 144), (100, 150)
            ]
        )
        self.assertEqual(events, ["IN"])

    def test_real_in_then_real_out_is_allowed(self):
        counter = self.make_counter()
        events = self.feed(
            counter,
            1,
            [
                (100, 65), (100, 70), (100, 80),
                (100, 95), (100, 110), (100, 125),
                (100, 138), (100, 145), (100, 152),
                (100, 155), (100, 150), (100, 145),
                (100, 130), (100, 112), (100, 95),
                (100, 80), (100, 62), (100, 55), (100, 48)
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
                ((100, 138), (100, 225)),
                ((100, 145), (100, 235)),
                ((100, 152), (100, 245)),
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
                ((100, 62), (100, 165)),
                ((100, 55), (100, 155)),
                ((100, 48), (100, 145)),
            ]
        )

        self.assertEqual(events, ["OUT"])

    def test_two_simultaneous_entries_count_twice(self):
        counter = self.make_counter()

        frames = [
            (
                ((90, 65), (90, 170)),
                ((150, 68), (150, 173))
            ),
            (
                ((90, 70), (90, 175)),
                ((150, 73), (150, 178))
            ),
            (
                ((90, 88), (90, 185)),
                ((150, 91), (150, 188))
            ),
            (
                ((90, 104), (90, 198)),
                ((150, 107), (150, 201))
            ),
            (
                ((90, 122), (90, 215)),
                ((150, 125), (150, 218))
            ),
            (
                ((90, 138), (90, 225)),
                ((150, 141), (150, 228))
            ),
            (
                ((90, 145), (90, 235)),
                ((150, 148), (150, 238))
            ),
            (
                ((90, 152), (90, 245)),
                ((150, 155), (150, 248))
            ),
        ]

        events = []

        for first, second in frames:
            for track_id, sample in (
                (301, first),
                (302, second)
            ):
                event = counter.update(
                    track_id,
                    sample[0],
                    sample[1]
                )
                if event:
                    events.append(event)

        self.assertEqual(
            counter.entries,
            2
        )
        self.assertEqual(
            counter.exits,
            0
        )
        self.assertEqual(
            events,
            ["IN", "IN"]
        )

    def test_simultaneous_in_and_out_are_independent(self):
        counter = self.make_counter()

        frames = [
            (
                ((100, 65), (100, 170)),
                ((130, 135), (130, 225))
            ),
            (
                ((100, 70), (100, 175)),
                ((130, 130), (130, 220))
            ),
            (
                ((100, 88), (100, 185)),
                ((130, 112), (130, 210))
            ),
            (
                ((100, 104), (100, 198)),
                ((130, 98), (130, 195))
            ),
            (
                ((100, 122), (100, 215)),
                ((130, 80), (130, 178))
            ),
            (
                ((100, 138), (100, 225)),
                ((130, 62), (130, 165))
            ),
            (
                ((100, 145), (100, 235)),
                ((130, 55), (130, 155))
            ),
            (
                ((100, 152), (100, 245)),
                ((130, 48), (130, 145))
            ),
        ]

        events = []

        for in_sample, out_sample in frames:
            event_in = counter.update(
                101,
                in_sample[0],
                in_sample[1]
            )
            if event_in:
                events.append(event_in)

            event_out = counter.update(
                202,
                out_sample[0],
                out_sample[1]
            )
            if event_out:
                events.append(event_out)

        self.assertEqual(
            counter.entries,
            1
        )
        self.assertEqual(
            counter.exits,
            1
        )
        self.assertEqual(
            sorted(events),
            ["IN", "OUT"]
        )

    def test_crossing_line_without_post_travel_does_not_count(self):
        counter = self.make_counter()

        events = self.feed_with_movement(
            counter,
            77,
            [
                ((100, 65), (100, 170)),
                ((100, 70), (100, 175)),
                ((100, 80), (100, 180)),
                ((100, 95), (100, 185)),
                ((100, 108), (100, 192)),
                ((100, 118), (100, 200)),
                ((100, 125), (100, 207)),
                ((100, 128), (100, 210)),
            ]
        )

        self.assertEqual(events, [])
        self.assertEqual(counter.entries, 0)

    def test_event_waits_for_three_frames_beyond_completion_margin(self):
        counter = self.make_counter()

        samples = [
            ((100, 65), (100, 170)),
            ((100, 70), (100, 175)),
            ((100, 80), (100, 180)),
            ((100, 95), (100, 185)),
            ((100, 108), (100, 195)),
            ((100, 125), (100, 210)),
            ((100, 138), (100, 225)),
            ((100, 145), (100, 235)),
        ]

        for point, movement in samples:
            self.assertIsNone(
                counter.update(
                    78,
                    point,
                    movement
                )
            )

        event = counter.update(
            78,
            (100, 152),
            (100, 245)
        )

        self.assertEqual(event, "IN")
        self.assertEqual(counter.entries, 1)

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
