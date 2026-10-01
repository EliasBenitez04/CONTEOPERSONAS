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
        self.motion_gate_enabled = True

        # Motion gate exclusivo del perfil liviano. Cuando aparece movimiento
        # o una persona, mantenemos una ventana activa para que el tracker vea
        # varios frames consecutivos y no pierda el ID durante el cruce.
        self._motion_previous = None
        self._last_inference_at = 0.0
        self._activity_until = 0.0
        self._idle_refresh_seconds = 2.5
        self._motion_threshold = 25
        self._motion_ratio = 0.008
        self._motion_hold_seconds = 1.8
        self._person_hold_seconds = 2.5

        print(f"[YOLO] Modelo cargado: {resolved_model}")
        self._print_device()
        print(f"[YOLO] Tamano de inferencia: {self.imgsz}")
        if not self.cuda_enabled:
            print(f"[YOLO] Hilos CPU maximos: {self.cpu_threads}")
        print("[TRACKER] Prediccion de movimiento e IoU mejorados habilitados.")
        print(
            "[CONTEO] Ancla corporal: torso 42% + "
            "mediana de 3 detecciones reales."
        )
        print("[YOLO] Motion gate de segundo plano habilitado.")

    @staticmethod
    def _normalize_imgsz(imgsz):
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
        # COCO class 0 = person. Objetos de otras clases nunca entran al tracker.
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
        if (
            not self.motion_gate_enabled
            or self.cuda_enabled
        ):
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

    def set_motion_gate_enabled(self, enabled):
        value = bool(enabled)

        if value == self.motion_gate_enabled:
            return

        self.motion_gate_enabled = value
        self._motion_previous = None
        self._activity_until = 0.0

        print(
            "[YOLO] Motion gate: "
            f"{'ACTIVO' if value else 'DESACTIVADO'}"
        )

    def has_recent_activity(self):
        return (
            time.monotonic()
            < self._activity_until
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
            center_x = max(
                0,
                min(frame_width - 1, x1 + (width // 2))
            )

            # Tres referencias reales del mismo bbox. El conteo principal usa
            # torso porque es mas estable ante pies ocultos y estaturas distintas.
            head_y = y1 + int(round(height * 0.12))
            torso_y = y1 + int(round(height * 0.42))
            foot_y = y2

            head_point = (
                center_x,
                max(0, min(frame_height - 1, head_y))
            )
            torso_point = (
                center_x,
                max(0, min(frame_height - 1, torso_y))
            )
            foot_point = (
                center_x,
                max(0, min(frame_height - 1, foot_y))
            )

            detections.append({
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "confidence": float(confidence),
                "head_point": head_point,
                "point": torso_point,
                "foot_point": foot_point
            })

        if detections:
            self._activity_until = max(
                self._activity_until,
                now + self._person_hold_seconds
            )

        tracked = self.tracker.update(detections)
        return self._classify_countable(
            tracked,
            frame_height
        )

    @staticmethod
    def _intersection_area(a, b):
        ix1 = max(a["x1"], b["x1"])
        iy1 = max(a["y1"], b["y1"])
        ix2 = min(a["x2"], b["x2"])
        iy2 = min(a["y2"], b["y2"])
        return max(0, ix2 - ix1) * max(0, iy2 - iy1)

    @staticmethod
    def _velocity_cosine(person_a, person_b):
        velocity_a = person_a.get("velocity") or (0.0, 0.0)
        velocity_b = person_b.get("velocity") or (0.0, 0.0)

        ax = float(velocity_a[0])
        ay = float(velocity_a[1])
        bx = float(velocity_b[0])
        by = float(velocity_b[1])

        speed_a = (ax * ax + ay * ay) ** 0.5
        speed_b = (bx * bx + by * by) ** 0.5

        if speed_a < 2.0 or speed_b < 2.0:
            return None

        return max(
            -1.0,
            min(
                1.0,
                (ax * bx + ay * by)
                / (speed_a * speed_b)
            )
        )

    def _classify_countable(self, persons, frame_height):
        """
        Filtro conservador de conteo.

        - Usa el pie solo para estimar perspectiva/tamano.
        - Exige varias detecciones y desplazamiento real para evitar elementos
          estaticos con forma humana.
        - Mantiene el filtro de persona pequena/bebe cargado.
        """
        for person in persons:
            person["countable"] = True
            person["count_filter"] = "ADULT"

            box_height = max(
                1,
                person["y2"] - person["y1"]
            )
            foot_point = (
                person.get("foot_point")
                or (0, person["y2"])
            )
            foot_y = max(
                1,
                int(foot_point[1])
            )

            # Perspectiva: cuanto mas abajo aparece el pie, mayor debe ser el
            # bbox aparente para considerarlo adulto.
            min_adult_height = max(
                105.0,
                min(
                    frame_height * 0.39,
                    foot_y * 0.47
                )
            )
            if box_height < min_adult_height:
                person["countable"] = False
                person["count_filter"] = "SMALL_PERSON"
                continue

            # Un maniqui/remera mal clasificado por YOLO suele permanecer
            # estatico. Para habilitar conteo exigimos track confirmado y
            # desplazamiento real del bbox.
            min_motion = max(
                7.0,
                min(
                    20.0,
                    box_height * 0.04
                )
            )
            if (
                int(person.get("hits", 1)) < 2
                or float(
                    person.get(
                        "max_displacement",
                        0.0
                    )
                ) < min_motion
            ):
                person["countable"] = False
                person["count_filter"] = "UNCONFIRMED_STATIC"

        # Bebe/persona cargada. Se exige una diferencia corporal fuerte y,
        # si ambos tracks ya tienen velocidad, que se muevan en la misma
        # direccion. Esto evita filtrar un adulto que cruza detras de otro.
        for small in persons:
            small_width = max(
                1,
                small["x2"] - small["x1"]
            )
            small_height = max(
                1,
                small["y2"] - small["y1"]
            )
            small_area = max(
                1,
                small_width * small_height
            )
            small_center_y = (
                small["y1"]
                + small_height * 0.5
            )

            for large in persons:
                if small["id"] == large["id"]:
                    continue

                large_width = max(
                    1,
                    large["x2"] - large["x1"]
                )
                large_height = max(
                    1,
                    large["y2"] - large["y1"]
                )
                large_area = max(
                    1,
                    large_width * large_height
                )

                height_ratio = (
                    small_height
                    / float(large_height)
                )
                width_ratio = (
                    small_width
                    / float(large_width)
                )

                # Un adulto en perspectiva puede ser algo menor; un cargado
                # debe ser claramente mas pequeno en ambas dimensiones.
                if (
                    height_ratio > 0.62
                    or width_ratio > 0.78
                    or large_area <= small_area * 1.85
                ):
                    continue

                overlap = (
                    self._intersection_area(
                        small,
                        large
                    )
                    / float(small_area)
                )
                floor_gap = (
                    large["y2"]
                    - small["y2"]
                )
                upper_body_limit = (
                    large["y1"]
                    + large_height * 0.72
                )

                if (
                    overlap < 0.80
                    or floor_gap < max(
                        45,
                        int(frame_height * 0.055)
                    )
                    or small_center_y > upper_body_limit
                ):
                    continue

                velocity_cosine = (
                    self._velocity_cosine(
                        small,
                        large
                    )
                )

                # Dos adultos moviendose en sentidos opuestos nunca pueden
                # clasificarse como persona cargada.
                if (
                    velocity_cosine is not None
                    and velocity_cosine < 0.35
                ):
                    continue

                small["countable"] = False
                small["count_filter"] = "CARRIED_PERSON"
                break

        return persons

    def reset_tracker(self):
        self.tracker.reset()
        self._motion_previous = None
        self._activity_until = 0.0
