from pathlib import Path
import time

import cv2
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
        cpu_threads=1
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

        try:
            cv2.setNumThreads(1)
        except Exception:
            pass

        if self.cuda_enabled:
            torch.backends.cudnn.benchmark = True
        else:
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
            max_missing=10,
            max_distance=150
        )

        # Motion gate exclusivo del perfil liviano. Cuando aparece movimiento
        # o una persona, mantenemos una ventana activa para que el tracker vea
        # varios frames consecutivos y no pierda el ID durante el cruce.
        self._motion_previous = None
        self._last_inference_at = 0.0
        self._activity_until = 0.0
        self._idle_refresh_seconds = 2.5
        self._motion_threshold = 25
        self._motion_ratio = 0.008
        self._motion_hold_seconds = 1.2
        self._person_hold_seconds = 2.0

        print(f"[YOLO] Modelo cargado: {resolved_model}")
        self._print_device()
        print(f"[YOLO] Tamano de inferencia: {self.imgsz}")
        if not self.cuda_enabled:
            print(f"[YOLO] Hilos CPU maximos: {self.cpu_threads}")
        print("[TRACKER] ID inmediato y punto suavizado habilitados.")
        print("[YOLO] Motion gate de segundo plano habilitado.")

    @staticmethod
    def _normalize_imgsz(imgsz):
        value = max(320, int(imgsz))
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
            max_det=20,
            verbose=False,
            device=self.device,
            half=self.use_half
        )

    def _background_motion_detected(self, frame):
        if self.cuda_enabled or self.imgsz > 416:
            return True

        now = time.monotonic()
        if now < self._activity_until:
            return True

        height, width = frame.shape[:2]
        if height <= 0 or width <= 0:
            return True

        sample_width = 128
        sample_height = max(
            72,
            int(round(height * (sample_width / float(width))))
        )

        small = cv2.resize(
            frame,
            (sample_width, sample_height),
            interpolation=cv2.INTER_AREA
        )
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        previous = self._motion_previous
        self._motion_previous = gray

        if previous is None or previous.shape != gray.shape:
            self._activity_until = now + self._motion_hold_seconds
            return True

        difference = cv2.absdiff(previous, gray)
        _, changed = cv2.threshold(
            difference,
            self._motion_threshold,
            255,
            cv2.THRESH_BINARY
        )

        changed_ratio = (
            cv2.countNonZero(changed)
            / float(changed.shape[0] * changed.shape[1])
        )

        if changed_ratio >= self._motion_ratio:
            self._activity_until = now + self._motion_hold_seconds
            return True

        return (
            now - self._last_inference_at
            >= self._idle_refresh_seconds
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
        self._motion_previous = None
        self._activity_until = 0.0
        print(f"[YOLO] Tamano de inferencia: {self.imgsz}")

    def track(self, frame):
        if not self._background_motion_detected(frame):
            return self.tracker.update([])

        try:
            results = self._predict(frame)
        except Exception as error:
            if not self.cuda_enabled:
                raise

            self._disable_cuda(error)
            results = self._predict(frame)

        now = time.monotonic()
        self._last_inference_at = now

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

        if detections:
            self._activity_until = max(
                self._activity_until,
                now + self._person_hold_seconds
            )

        return self.tracker.update(detections)

    def reset_tracker(self):
        self.tracker.reset()
        self._motion_previous = None
        self._activity_until = 0.0
