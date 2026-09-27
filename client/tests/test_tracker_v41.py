import unittest

from app.detection.tracker import Tracker


def detection(x1, y1, x2, y2, point):
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "confidence": 0.90,
        "point": point
    }


class TrackerV41Tests(unittest.TestCase):

    def test_median_uses_real_detections(self):
        tracker = Tracker(
            max_missing=3,
            max_distance=100
        )

        tracker.update([
            detection(0, 0, 40, 100, (20, 40))
        ])
        tracker.update([
            detection(1, 1, 41, 101, (21, 43))
        ])
        result = tracker.update([
            detection(2, 2, 42, 102, (22, 39))
        ])[0]

        self.assertEqual(
            result["point"],
            (21, 40)
        )

    def test_short_occlusion_keeps_same_id(self):
        tracker = Tracker(
            max_missing=3,
            max_distance=100
        )

        first_id = tracker.update([
            detection(0, 0, 40, 100, (20, 40))
        ])[0]["id"]

        tracker.update([])
        tracker.update([])

        second_id = tracker.update([
            detection(6, 4, 46, 104, (26, 44))
        ])[0]["id"]

        self.assertEqual(
            first_id,
            second_id
        )

    def test_real_motion_increases_displacement(self):
        tracker = Tracker(
            max_missing=3,
            max_distance=100
        )

        tracker.update([
            detection(0, 0, 40, 100, (20, 40))
        ])
        result = tracker.update([
            detection(20, 20, 60, 120, (40, 60))
        ])[0]

        self.assertGreater(
            result["max_displacement"],
            20
        )


if __name__ == "__main__":
    unittest.main()
