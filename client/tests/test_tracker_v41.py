import unittest

from app.detection.tracker import Tracker


def detection(
    x1,
    y1,
    x2,
    y2,
    point,
    foot_point=None
):
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "confidence": 0.90,
        "point": point,
        "foot_point": (
            foot_point
            if foot_point is not None
            else point
        )
    }


def labeled_person(
    center_x,
    center_y,
    label,
    width=50,
    height=120
):
    x1 = center_x - width // 2
    y1 = center_y - height // 2
    x2 = center_x + width // 2
    y2 = center_y + height // 2

    item = detection(
        x1,
        y1,
        x2,
        y2,
        (
            center_x,
            int(round(y1 + height * 0.42))
        ),
        (
            center_x,
            y2
        )
    )
    item["label"] = label
    return item


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

    def test_movement_point_uses_real_foot_median(self):
        tracker = Tracker(
            max_missing=3,
            max_distance=100
        )

        tracker.update([
            detection(
                0, 0, 40, 100,
                (20, 40),
                (20, 90)
            )
        ])
        tracker.update([
            detection(
                1, 1, 41, 101,
                (21, 43),
                (21, 94)
            )
        ])
        result = tracker.update([
            detection(
                2, 2, 42, 102,
                (22, 39),
                (22, 91)
            )
        ])[0]

        self.assertEqual(
            result["movement_point"],
            (21, 91)
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


    def test_production_tracker_recovers_id_after_longer_occlusion(self):
        tracker = Tracker(
            max_missing=18,
            max_distance=165
        )

        first = tracker.update([
            labeled_person(100, 80, "A")
        ])[0]["id"]

        tracker.update([
            labeled_person(100, 95, "A")
        ])
        tracker.update([
            labeled_person(100, 110, "A")
        ])

        for _ in range(8):
            tracker.update([])

        recovered = tracker.update([
            labeled_person(102, 150, "A")
        ])[0]["id"]

        self.assertEqual(
            recovered,
            first
        )

    def test_two_people_opposite_directions_keep_ids(self):
        tracker = Tracker(
            max_missing=4,
            max_distance=130
        )

        frames = [
            [("A", 100, 70), ("B", 125, 190)],
            [("B", 125, 170), ("A", 100, 90)],
            [("A", 100, 110), ("B", 125, 150)],
            [("B", 125, 130), ("A", 100, 130)],
            [("A", 100, 150), ("B", 125, 110)],
            [("B", 125, 90), ("A", 100, 170)],
        ]

        expected_ids = {}

        for frame_index, frame in enumerate(frames):
            detections = [
                labeled_person(
                    center_x,
                    center_y,
                    label
                )
                for label, center_x, center_y in frame
            ]
            output = tracker.update(detections)
            current = {
                item["label"]: item["id"]
                for item in output
            }

            if frame_index == 0:
                expected_ids = current
                self.assertEqual(
                    set(expected_ids.keys()),
                    {"A", "B"}
                )
                continue

            self.assertEqual(
                current.get("A"),
                expected_ids["A"]
            )
            self.assertEqual(
                current.get("B"),
                expected_ids["B"]
            )

    def test_two_people_same_direction_keep_separate_ids(self):
        tracker = Tracker(
            max_missing=4,
            max_distance=130
        )

        frames = [
            [("A", 90, 70), ("B", 145, 75)],
            [("B", 145, 95), ("A", 90, 90)],
            [("A", 90, 110), ("B", 145, 115)],
            [("B", 145, 135), ("A", 90, 130)],
            [("A", 90, 150), ("B", 145, 155)],
        ]

        expected_ids = {}

        for frame_index, frame in enumerate(frames):
            output = tracker.update([
                labeled_person(
                    center_x,
                    center_y,
                    label
                )
                for label, center_x, center_y in frame
            ])
            current = {
                item["label"]: item["id"]
                for item in output
            }

            if frame_index == 0:
                expected_ids = current
                continue

            self.assertEqual(
                current.get("A"),
                expected_ids["A"]
            )
            self.assertEqual(
                current.get("B"),
                expected_ids["B"]
            )
            self.assertNotEqual(
                current.get("A"),
                current.get("B")
            )

    def test_merged_detection_between_opposite_tracks_is_suppressed(self):
        tracker = Tracker(
            max_missing=4,
            max_distance=130
        )

        warmup = [
            [("A", 100, 70), ("B", 125, 190)],
            [("A", 100, 90), ("B", 125, 170)],
            [("A", 100, 110), ("B", 125, 150)],
        ]

        expected_ids = {}

        for frame_index, frame in enumerate(warmup):
            output = tracker.update([
                labeled_person(
                    center_x,
                    center_y,
                    label
                )
                for label, center_x, center_y in frame
            ])
            current = {
                item["label"]: item["id"]
                for item in output
            }
            if frame_index == 0:
                expected_ids = current

        merged = labeled_person(
            112,
            130,
            "MERGED",
            width=75,
            height=150
        )
        merged_output = tracker.update([
            merged
        ])

        self.assertEqual(
            merged_output,
            []
        )

        output = tracker.update([
            labeled_person(100, 150, "A"),
            labeled_person(125, 110, "B")
        ])
        current = {
            item["label"]: item["id"]
            for item in output
        }

        self.assertEqual(
            current.get("A"),
            expected_ids["A"]
        )
        self.assertEqual(
            current.get("B"),
            expected_ids["B"]
        )

if __name__ == "__main__":
    unittest.main()
