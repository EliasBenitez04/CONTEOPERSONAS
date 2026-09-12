from ultralytics import YOLO


class PersonDetector:

    def __init__(
        self,
        model_path="yolov8n.pt",
        confidence=0.30,
        imgsz=640
    ):

        self.model = YOLO(
            model_path
        )

        self.confidence = confidence
        self.imgsz = imgsz

        print("[YOLO] Modelo cargado.")

    def track(self, frame):

        results = self.model.track(
            source=frame,
            persist=True,
            classes=[0],
            conf=self.confidence,
            imgsz=self.imgsz,
            tracker="bytetrack.yaml",
            verbose=False
        )

        persons = []

        if not results:
            return persons

        result = results[0]

        if result.boxes is None:
            return persons

        if result.boxes.id is None:
            return persons

        boxes = (
            result.boxes.xyxy
            .cpu()
            .tolist()
        )

        ids = (
            result.boxes.id
            .int()
            .cpu()
            .tolist()
        )

        confidences = (
            result.boxes.conf
            .cpu()
            .tolist()
        )

        for box, track_id, confidence in zip(
            boxes,
            ids,
            confidences
        ):

            x1, y1, x2, y2 = box

            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            # Punto inferior central
            point_x = (
                x1 + x2
            ) // 2

            point_y = y2

            persons.append({
                "id": int(track_id),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "confidence": float(confidence),
            
                "point": (
                    (x1 + x2) // 2,
                    (y1 + y2) // 2
                )
            })

        return persons