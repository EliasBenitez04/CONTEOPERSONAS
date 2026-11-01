import unittest

from app.detection.counter import LineCounter
from app.detection.head_geometry import estimate_head_geometry


class HeadGeometryTests(unittest.TestCase):
    def test_head_box_and_anchor_are_inside_frame(self):
        box, point = estimate_head_geometry(100, 100, 400, 500, 640, 480)
        x1, y1, x2, y2 = box
        self.assertLess(x1, x2)
        self.assertLess(y1, y2)
        self.assertEqual(point[0], (x1 + x2) // 2)
        self.assertLess(point[1], y1)
        self.assertTrue(0 <= point[0] < 640)

    def test_border_clipping(self):
        box, point = estimate_head_geometry(-20, -30, 50, 90, 100, 70)
        self.assertGreaterEqual(min(box), 0)
        self.assertLess(box[2], 100)
        self.assertLess(box[3], 70)
        self.assertGreaterEqual(point[1], 0)

    def test_head_crossing_in_and_out_symmetric(self):
        counter = LineCounter(points=[(0, 100), (500, 100)], margin=18)
        counter.stable_frames = 2
        counter.destination_frames = 2
        points = [50, 55, 60, 65, 73, 95, 110, 125, 143, 154, 164]
        inbound = [
            counter.update(1, (150, y), (150, y + 65)) for y in points
        ]
        outbound = [
            counter.update(2, (250, y), (250, y + 65))
            for y in reversed(points)
        ]
        self.assertEqual([e for e in inbound if e], ["IN"])
        self.assertEqual([e for e in outbound if e], ["OUT"])


if __name__ == "__main__":
    unittest.main()
