import sys
import types
import unittest


try:
    from app.detection.detector import PersonDetector
except ModuleNotFoundError:
    # El filtro probado aqui no necesita OpenCV/Torch/YOLO. En CI core se
    # simulan esos imports para ejecutar la logica sin descargar ~GB de deps.
    sys.modules.setdefault(
        "cv2",
        types.ModuleType("cv2")
    )
    sys.modules.setdefault(
        "torch",
        types.ModuleType("torch")
    )

    ultralytics_stub = types.ModuleType(
        "ultralytics"
    )
    ultralytics_stub.YOLO = object
    sys.modules.setdefault(
        "ultralytics",
        ultralytics_stub
    )

    from app.detection.detector import PersonDetector


def person(
    track_id,
    x1,
    y1,
    x2,
    y2,
    velocity
):
    return {
        "id": track_id,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "confidence": 0.90,
        "foot_point": (
            int(round((x1 + x2) / 2)),
            y2
        ),
        "hits": 6,
        "max_displacement": 80.0,
        "velocity": velocity
    }


class DetectorFilterV42Tests(unittest.TestCase):

    def setUp(self):
        self.detector = PersonDetector.__new__(
            PersonDetector
        )

    def test_opposite_adults_are_not_carried_person(self):
        far_adult = person(
            1,
            450,
            320,
            600,
            620,
            (0.0, -12.0)
        )
        near_adult = person(
            2,
            400,
            250,
            700,
            750,
            (0.0, 12.0)
        )

        result = self.detector._classify_countable(
            [
                far_adult,
                near_adult
            ],
            1080
        )

        by_id = {
            item["id"]: item
            for item in result
        }

        self.assertTrue(
            by_id[1]["countable"]
        )
        self.assertNotEqual(
            by_id[1]["count_filter"],
            "CARRIED_PERSON"
        )
        self.assertTrue(
            by_id[2]["countable"]
        )

    def test_smaller_adult_same_direction_is_not_carried(self):
        far_adult = person(
            1,
            460,
            300,
            610,
            620,
            (0.0, 10.0)
        )
        near_adult = person(
            2,
            400,
            250,
            700,
            750,
            (0.0, 12.0)
        )

        result = self.detector._classify_countable(
            [
                far_adult,
                near_adult
            ],
            1080
        )

        by_id = {
            item["id"]: item
            for item in result
        }

        self.assertTrue(
            by_id[1]["countable"]
        )
        self.assertEqual(
            by_id[1]["count_filter"],
            "ADULT"
        )

    def test_contained_person_moving_with_adult_can_be_filtered(self):
        carried = person(
            1,
            485,
            350,
            575,
            540,
            (0.0, 10.0)
        )
        adult = person(
            2,
            400,
            250,
            700,
            750,
            (0.0, 12.0)
        )

        result = self.detector._classify_countable(
            [
                carried,
                adult
            ],
            1080
        )

        by_id = {
            item["id"]: item
            for item in result
        }

        self.assertFalse(
            by_id[1]["countable"]
        )
        self.assertEqual(
            by_id[1]["count_filter"],
            "CARRIED_PERSON"
        )
        self.assertTrue(
            by_id[2]["countable"]
        )




class InferencePrecisionTests(unittest.TestCase):
    """El warning de half no debe repetirse por cada imagen procesada."""

    @staticmethod
    def make_detector(use_half):
        class StubModel:
            def __init__(self):
                self.options = None

            def predict(self, **kwargs):
                self.options = kwargs
                return []

        detector = PersonDetector.__new__(PersonDetector)
        detector.model = StubModel()
        detector.device = 0 if use_half else "cpu"
        detector.use_half = use_half
        detector.confidence = 0.4
        detector.imgsz = 416
        return detector

    def test_cpu_omits_deprecated_half(self):
        detector = self.make_detector(False)
        detector._predict("frame")
        self.assertNotIn("half", detector.model.options)
        self.assertNotIn("quantize", detector.model.options)
        self.assertEqual(detector.model.options["device"], "cpu")

    def test_cuda_uses_quantize_when_supported(self):
        from unittest.mock import patch

        cfg = types.ModuleType("ultralytics.cfg")
        cfg.DEFAULT_CFG_DICT = {"quantize": None}
        with patch.dict(sys.modules, {"ultralytics.cfg": cfg}):
            detector = self.make_detector(True)
            detector._predict("frame")
            self.assertEqual(detector.model.options["quantize"], 16)
            self.assertNotIn("half", detector.model.options)

    def test_cuda_legacy_uses_half_only_if_necessary(self):
        from unittest.mock import patch

        cfg = types.ModuleType("ultralytics.cfg")
        cfg.DEFAULT_CFG_DICT = {"half": False}
        with patch.dict(sys.modules, {"ultralytics.cfg": cfg}):
            detector = self.make_detector(True)
            detector._predict("frame")
            self.assertIs(detector.model.options["half"], True)
            self.assertNotIn("quantize", detector.model.options)


if __name__ == "__main__":
    unittest.main()
