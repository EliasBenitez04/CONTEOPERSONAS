import unittest
from unittest.mock import patch

from app.detection.counter import LineCounter


class CounterRegressionTests(unittest.TestCase):
    def counter(self):
        counter = LineCounter(points=[(0, 100), (500, 100)], margin=18)
        counter.destination_frames = 2
        return counter

    def feed(self, counter, points):
        return [event for p in points if (event := counter.update(1, p))]

    def test_fast_crossing_both_directions(self):
        for direction, ys in [('IN', [65, 135, 145]), ('OUT', [135, 65, 55])]:
            with self.subTest(direction=direction):
                counter = self.counter()
                self.assertEqual(self.feed(counter, [(100, y) for y in ys]), [direction])

    def test_going_around_endpoint_is_not_a_crossing(self):
        # None of the observed consecutive segments intersects the line.
        counter = self.counter()
        path = [(480, 65), (520, 90), (520, 110), (480, 135), (470, 145)]
        self.assertEqual(self.feed(counter, path), [])

    def test_reacquired_id_after_long_gap_does_not_count(self):
        counter = self.counter()
        with patch('app.detection.counter.time.monotonic', return_value=100):
            counter.update(1, (100, 65))
        with patch('app.detection.counter.time.monotonic', return_value=110):
            self.assertEqual(self.feed(counter, [(100, 105), (100, 135), (100, 145)]), [])

    def test_jump_during_destination_confirmation_cancels(self):
        counter = self.counter()
        self.assertEqual(self.feed(counter, [(100, 65), (100, 95), (100, 110),
                                             (100, 135), (450, 140), (450, 145)]), [])
