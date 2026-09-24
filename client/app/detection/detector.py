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
            max_missing=12,
            max_distance=150
        )
        self.counting_points = []

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
        print("[TRACKER] Prediccion de movimiento e IoU mejorados habilitados.")
        print("[YOLO] Motion gate de segundo plano habilitado.")

    @staticmethod
    def _normalize_imgsz(imgsz):
        # Mantiene 416 como 416. La version anterior convertia 416 -> 320 y
        # reducia demasiado el detalle de piernas/pies en cruces estrechos.
        value = max(320, min(512, int(imgsz)))
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
        # max_det=12 evita trabajo de NMS/tracking para detecciones que no son
        # realistas en una puerta y mantiene liviano el ejecutable.
        return self.model.predict(
            source=frame,
            classes=[0],
            conf=self.confidence,
            imgsz=self.imgsz,
            max_det=10,
            verbose=False,
            device=self.device,
            half=self.use_half
        )

    def _motion_region(self, frame):
        """Region amplia alrededor del trazado para el motion gate."""
        if len(self.counting_points) < 2:
            return frame

        height, width = frame.shape[:2]
        if height <= 0 or width <= 0:
            return frame

        xs = [point[0] for point in self.counting_points]
        ys = [point[1] for point in self.counting_points]

        pad_x = max(80, int(round(width * 0.10)))
        pad_top = max(120, int(round(height * 0.30)))
        pad_bottom = max(80, int(round(height * 0.18)))

        x1 = max(0, min(xs) - pad_x)
        x2 = min(width, max(xs) + pad_x)
        y1 = max(0, min(ys) - pad_top)
        y2 = min(height, max(ys) + pad_bottom)

        if x2 - x1 < 32 or y2 - y1 < 32:
            return frame

        return frame[y1:y2, x1:x2]

    def _background_motion_detected(self, frame):
        if self.cuda_enabled or self.imgsz > 416:
            return True

        now = time.monotonic()
        if now < self._activity_until:
            return True

        motion_frame = self._motion_region(frame)
        height, width = motion_frame.shape[:2]
        if height <= 0 or width <= 0:
            return True

        sample_width = 96
        sample_height = max(
            54,
            int(round(height * (sample_width / float(width))))
        )

        small = cv2.resize(
            motion_frame,
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

    def set_counting_line(self, points):
        normalized = []
        for point in points or []:
            if point is None or len(point) < 2:
                continue
            normalized.append((
                int(round(point[0])),
                int(round(point[1]))
            ))

        self.counting_points = normalized
        self._motion_previous = None
        self._activity_until = 0.0

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

        # Una sola transferencia CPU para coordenadas + confianza.
        rows = result.boxes.data.detach().cpu().tolist()

        frame_height, frame_width = frame.shape[:2]

        for row in rows:
            if len(row) < 5:
                continue

            x1, y1, x2, y2 = row[:4]
            confidence = row[4]
            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            width = max(1, x2 - x1)
            height = max(1, y2 - y1)

            # Punto de conteo: centro inferior REAL del bounding box. Este es
            # el punto que representa los pies y el unico usado para cruzar.
            point_x = max(
                0,
                min(frame_width - 1, x1 + (width // 2))
            )
            point_y = max(
                0,
                min(frame_height - 1, y2)
            )

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

        tracked = self.tracker.update(detections)
        return self._classify_countable(tracked, frame_height)

    @staticmethod
    def _intersection_area(a, b):
        ix1 = max(a["x1"], b["x1"])
        iy1 = max(a["y1"], b["y1"])
        ix2 = min(a["x2"], b["x2"])
        iy2 = min(a["y2"], b["y2"])
        return max(0, ix2 - ix1) * max(0, iy2 - iy1)

    def _classify_countable(self, persons, frame_height):
        """
        V4: filtro conservador para no contar ninos/bebes.

        No elimina detecciones del tracker: solo decide si ese ID puede generar
        IN/OUT. La escala minima depende de la altura del pie en la imagen para
        compensar perspectiva. Una deteccion pequena contenida dentro de una
        persona mayor y cuyo borde inferior queda alto se considera cargada.
        """
        for person in persons:
            person["countable"] = True
            person["count_filter"] = "ADULT"
            box_height = max(1, person["y2"] - person["y1"])
            foot_y = max(1, person["point"][1])

            # Perspectiva: cuanto mas abajo esta el pie, mayor debe ser una
            # persona adulta aparente. Limites evitan extremos por resolucion.
            min_adult_height = max(
                105.0,
                min(frame_height * 0.39, foot_y * 0.47)
            )
            if box_height < min_adult_height:
                person["countable"] = False
                person["count_filter"] = "SMALL_PERSON"

        # Bebe/persona pequena cargada: bbox mayormente contenido y sin llegar
        # al mismo nivel de piso que el adulto. No afecta al adulto portador.
        for small in persons:
            small_area = max(1, (small["x2"] - small["x1"]) * (small["y2"] - small["y1"]))
            for large in persons:
                if small["id"] == large["id"]:
                    continue
                large_area = max(1, (large["x2"] - large["x1"]) * (large["y2"] - large["y1"]))
                if large_area <= small_area * 1.55:
                    continue
                overlap = self._intersection_area(small, large) / float(small_area)
                floor_gap = large["y2"] - small["y2"]
                if overlap >= 0.72 and floor_gap >= max(35, int(frame_height * 0.045)):
                    small["countable"] = False
                    small["count_filter"] = "CARRIED_PERSON"
                    break

        return persons

    def reset_tracker(self):
        self.tracker.reset()
        self._motion_previous = None
        self._activity_until = 0.0
