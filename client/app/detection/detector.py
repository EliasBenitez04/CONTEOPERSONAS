from ultralytics import YOLO


class PersonDetector:

    def __init__(
        self,
        model_path="yolov8n.pt",
        confidence=0.40
    ):
        self.model = YOLO(model_path)
        self.confidence = confidence

        print("[YOLO] Modelo cargado.")

    def track(self, frame):

        results = self.model.track(
            source=frame,
            persist=True,
            classes=[0],
            conf=self.confidence,
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

        boxes = result.boxes.xyxy.cpu().tolist()
        ids = result.boxes.id.int().cpu().tolist()
        confs = result.boxes.conf.cpu().tolist()

        for box, track_id, confidence in zip(
            boxes,
            ids,
            confs
        ):
            x1, y1, x2, y2 = box

            point_x = int((x1 + x2) / 2)
            point_y = int(y2)

            persons.append({
                "id": track_id,
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2),
                "confidence": float(confidence),

                "point": (
                    point_x,
                    point_y
                )
            })

        return persons