from pathlib import Path

import torch
from ultralytics import YOLO

from app.detection.tracker import Tracker
from app.paths import resource_path


class PersonDetector:

    def __init__(
        self,
        model_path="yolov8n.pt",
        confidence=0.22,
        imgsz=640,
        cpu_threads=2
    ):
        resolved_model = Path(model_path)
        if not resolved_model.is_absolute():
            resolved_model = resource_path(str(resolved_model))

        self.confidence = float(confidence)
        self.imgsz = self._normalize_imgsz(imgsz)
        self.cpu_threads = max(1, int(cpu_threads))

        self.cuda_enabled = bool(torch.cuda.is_available())
        self.device = 0 if self.cuda_enabled else "cpu"
        self.use_half = self.cuda_enabled

        if self.cuda_enabled:
            torch.backends.cudnn.benchmark = True
        else:
            # Evita que PyTorch ocupe todos los nucleos del equipo. En una
            # notebook esto reduce mucho el pico de CPU y deja Windows usable.
            try:
                torch.set_num_threads(self.cpu_threads)
            except RuntimeError:
                pass

            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                pass

        self.model = YOLO(str(resolved_model))

        self.tracker = Tracker(
            max_missing=15,
            max_distance=170
        )

        print(f"[YOLO] Modelo cargado: {resolved_model}")
        self._print_device()
        print(f"[YOLO] Tamano de inferencia: {self.imgsz}")
        if not self.cuda_enabled:
            print(f"[YOLO] Hilos CPU maximos: {self.cpu_threads}")
        print("[TRACKER] ID inmediato habilitado.")

    @staticmethod
    def _normalize_imgsz(imgsz):
        value = max(320, int(imgsz))
        # YOLO trabaja mejor con dimensiones divisibles por 32.
        return max(320, (value // 32) * 32)

    def _print_device(self):
        if self.cuda_enabled:
            print("[YOLO] Dispositivo: CUDA / FP16")
        else:
            print("[YOLO] Dispositivo: CPU / FP32")

    def _disable_cuda(self, reason):
        if not self.cuda_enabled:
            return

        print(
            "[YOLO] CUDA fallo en esta PC. "
            "Se cambia automaticamente a CPU."
        )
        print(f"[YOLO] Motivo CUDA: {reason}")

        self.cuda_enabled = False
        self.device = "cpu"
        self.use_half = False

        try:
            torch.set_num_threads(self.cpu_threads)
        except RuntimeError:
            pass

        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass

        try:
            torch.cuda.empty_cache()
        except Exception:
            pass

        self._print_device()
        print(f"[YOLO] Hilos CPU maximos: {self.cpu_threads}")

    def _predict(self, frame):
        return self.model.predict(
            source=frame,
            classes=[0],
            conf=self.confidence,
            imgsz=self.imgsz,
            max_det=30,
            verbose=False,
            device=self.device,
            half=self.use_half
        )

    def set_confidence(self, confidence):
        value = float(confidence)
        self.confidence = min(0.99, max(0.01, value))
        print(
            "[YOLO] Confianza actualizada: "
            f"{self.confidence:.2f}"
        )

    def set_imgsz(self, imgsz):
        value = self._normalize_imgsz(imgsz)
        if value == self.imgsz:
            return

        self.imgsz = value
        print(f"[YOLO] Tamano de inferencia: {self.imgsz}")

    def track(self, frame):
        try:
            results = self._predict(frame)
        except Exception as error:
            if not self.cuda_enabled:
                raise

            self._disable_cuda(error)
            results = self._predict(frame)

        detections = []
        if not results:
            return self.tracker.update(detections)

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return self.tracker.update(detections)

        boxes = result.boxes.xyxy.cpu().tolist()
        confidences = result.boxes.conf.cpu().tolist()

        for box, confidence in zip(boxes, confidences):
            x1, y1, x2, y2 = box
            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            point_x = x1 + (width // 2)
            point_y = y2 - max(2, int(height * 0.06))

            detections.append({
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "confidence": float(confidence),
                "point": (point_x, point_y)
            })

        return self.tracker.update(detections)

    def reset_tracker(self):
        self.tracker.reset()
