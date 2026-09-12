from ultralytics import YOLO

from app.detection.tracker import Tracker


class PersonDetector:

    def __init__(
        self,
        model_path="yolov8n.pt",
        confidence=0.22,
        imgsz=640
    ):
        self.model = YOLO(
            model_path
        )

        self.confidence = float(
            confidence
        )

        self.imgsz = int(
            imgsz
        )

        self.tracker = Tracker(
            max_missing=15,
            max_distance=170
        )

        print(
            "[YOLO] Modelo cargado."
        )

        print(
            "[TRACKER] ID inmediato habilitado."
        )

    def track(self, frame):
        """
        Detecta personas con YOLO y luego mantiene un ID local.

        No usamos result.boxes.id porque ByteTrack puede tardar varios
        frames en confirmar un ID. En una puerta con poco espacio eso
        hace que una persona cruce la linea antes de tener ID.
        """

        results = self.model.predict(
            source=frame,
            classes=[0],
            conf=self.confidence,
            imgsz=self.imgsz,
            max_det=30,
            verbose=False
        )

        detections = []

        if not results:
            return self.tracker.update(
                detections
            )

        result = results[0]

        if (
            result.boxes is None
            or len(result.boxes) == 0
        ):
            return self.tracker.update(
                detections
            )

        boxes = (
            result.boxes.xyxy
            .cpu()
            .tolist()
        )

        confidences = (
            result.boxes.conf
            .cpu()
            .tolist()
        )

        for box, confidence in zip(
            boxes,
            confidences
        ):
            x1, y1, x2, y2 = box

            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            width = max(
                1,
                x2 - x1
            )

            height = max(
                1,
                y2 - y1
            )

            point_x = (
                x1 + (width // 2)
            )

            point_y = (
                y2
                - max(
                    2,
                    int(height * 0.06)
                )
            )

            detections.append({
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "confidence": float(
                    confidence
                ),
                "point": (
                    point_x,
                    point_y
                )
            })

        return self.tracker.update(
            detections
        )

    def reset_tracker(self):
        self.tracker.reset()
