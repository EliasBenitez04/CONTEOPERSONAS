import unittest

from app.detection.counter import LineCounter


class LineCounterV4Tests(unittest.TestCase):
    def make_counter(self):
        return LineCounter(points=[(0, 100), (500, 100)], in_side=1, margin=18)

    @staticmethod
    def feed(counter, track_id, points):
        events = []
        for point in points:
            event = counter.update(track_id, point)
            if event:
                events.append(event)
        return events

    def test_normal_in_counts_once(self):
        c = self.make_counter()
        events = self.feed(c, 1, [(100, 70), (100, 75), (100, 82), (100, 108), (100, 120)])
        self.assertEqual(events, ["IN"])

    def test_normal_out_counts_once(self):
        c = self.make_counter()
        events = self.feed(c, 1, [(100, 130), (100, 125), (100, 118), (100, 92), (100, 80)])
        self.assertEqual(events, ["OUT"])

    def test_jitter_on_line_does_not_count(self):
        c = self.make_counter()
        events = self.feed(c, 1, [
            (100, 75), (100, 78), (100, 96), (100, 101), (100, 98),
            (100, 103), (100, 99), (100, 102), (100, 78), (100, 75)
        ])
        self.assertEqual(events, [])

    def test_touch_and_return_does_not_count(self):
        c = self.make_counter()
        events = self.feed(c, 1, [(100, 70), (100, 75), (100, 98), (100, 101), (100, 85), (100, 75)])
        self.assertEqual(events, [])

    def test_same_transit_cannot_duplicate(self):
        c = self.make_counter()
        events = self.feed(c, 529, [
            (100, 70), (100, 75), (100, 110), (100, 120),
            (100, 119), (100, 121), (100, 118), (100, 120)
        ])
        self.assertEqual(events, ["IN"])

    def test_real_in_then_real_out_is_allowed(self):
        c = self.make_counter()
        events = self.feed(c, 1, [
            (100, 70), (100, 75), (100, 110), (100, 120),
            (100, 125), (100, 128), (100, 130), (100, 125),
            (100, 90), (100, 78)
        ])
        self.assertEqual(events, ["IN", "OUT"])

    def test_crossing_outside_segment_does_not_count(self):
        c = self.make_counter()
        events = self.feed(c, 1, [(600, 70), (600, 75), (600, 110), (600, 125)])
        self.assertEqual(events, [])

    def test_large_bbox_jump_does_not_create_crossing(self):
        c = self.make_counter()
        events = self.feed(c, 1, [(100, -250), (100, -245), (100, 350), (100, 360)])
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
