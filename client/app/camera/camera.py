import cv2
import threading
import time


class Camera:

    def __init__(self, rtsp_url: str):
        self.rtsp_url = rtsp_url

        self.capture = None
        self.frame = None

        self.running = False
        self.thread = None

        self.lock = threading.Lock()
        self.last_frame_time = 0

        # Frecuencia maxima a la que convertimos el frame decodificado a BGR
        # y lo publicamos al detector. grab() sigue vaciando el RTSP para no
        # acumular latencia, pero retrieve()/swscale no corre a 25/30 FPS.
        self.output_fps = 0.0
        self.output_interval = 0.0

    def set_output_fps(self, fps: float):
        value = max(0.0, float(fps))
        with self.lock:
            self.output_fps = value
            self.output_interval = (
                1.0 / value
                if value > 0
                else 0.0
            )

    def _open_capture(self):
        params = []

        # OpenCV 4.x permite solicitar aceleracion por hardware y limitar los
        # threads del decoder al abrir FFmpeg. Si el backend/equipo no lo
        # soporta, se hace fallback automatico al modo clasico.
        if (
            hasattr(cv2, "CAP_PROP_HW_ACCELERATION")
            and hasattr(cv2, "VIDEO_ACCELERATION_ANY")
        ):
            params.extend([
                int(cv2.CAP_PROP_HW_ACCELERATION),
                int(cv2.VIDEO_ACCELERATION_ANY)
            ])

        if hasattr(cv2, "CAP_PROP_N_THREADS"):
            params.extend([
                int(cv2.CAP_PROP_N_THREADS),
                1
            ])

        capture = None

        if params:
            try:
                capture = cv2.VideoCapture(
                    self.rtsp_url,
                    cv2.CAP_FFMPEG,
                    params
                )
            except (TypeError, cv2.error):
                capture = None

        if capture is None or not capture.isOpened():
            if capture is not None:
                capture.release()

            capture = cv2.VideoCapture(
                self.rtsp_url,
                cv2.CAP_FFMPEG
            )

        capture.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1
        )

        return capture

    def connect(self) -> bool:
        self.disconnect()

        print("[CAMARA] Intentando conectar...")

        capture = self._open_capture()

        if not capture.isOpened():
            print("[CAMARA] No se pudo conectar.")
            capture.release()
            return False

        self.capture = capture
        self.running = True

        self.thread = threading.Thread(
            target=self._reader,
            daemon=True,
            name="ContePersonasRTSP"
        )
        self.thread.start()

        print("[CAMARA] Conexion exitosa.")

        timeout = time.time() + 5

        while (
            self.running
            and self.frame is None
            and time.time() < timeout
        ):
            time.sleep(0.05)

        if self.frame is None:
            print(
                "[CAMARA] No se recibio "
                "el primer frame."
            )
            self.disconnect()
            return False

        print("[CAMARA] Primer frame recibido.")
        return True

    def _reader(self):
        consecutive_failures = 0
        next_retrieve_at = 0.0

        while self.running:
            capture = self.capture
            if capture is None:
                break

            try:
                grabbed = capture.grab()
            except cv2.error as error:
                if not self.running:
                    break

                print(
                    "[CAMARA] Error leyendo RTSP:",
                    error
                )
                consecutive_failures += 1
                time.sleep(0.05)
                continue

            if not self.running:
                break

            if not grabbed:
                consecutive_failures += 1

                if consecutive_failures >= 30:
                    print(
                        "[CAMARA] Demasiados "
                        "frames fallidos."
                    )
                    self.running = False
                    break

                time.sleep(0.01)
                continue

            consecutive_failures = 0

            with self.lock:
                output_interval = self.output_interval

            now = time.monotonic()
            if (
                output_interval > 0
                and next_retrieve_at > now
            ):
                # grab() mantiene el stream al dia sin convertir cada frame a
                # BGR. Esa conversion era una carga innecesaria permanente.
                continue

            try:
                ret, frame = capture.retrieve()
            except cv2.error as error:
                if not self.running:
                    break

                print(
                    "[CAMARA] Error convirtiendo frame RTSP:",
                    error
                )
                consecutive_failures += 1
                continue

            if not ret or frame is None:
                consecutive_failures += 1
                continue

            now = time.monotonic()
            next_retrieve_at = (
                now + output_interval
                if output_interval > 0
                else 0.0
            )

            with self.lock:
                self.frame = frame
                self.last_frame_time = time.time()

    def read(self, copy_frame: bool = True):
        with self.lock:
            if self.frame is None:
                return False, None

            if (
                self.last_frame_time > 0
                and time.time() - self.last_frame_time > 3
            ):
                return False, None

            frame = self.frame

            if copy_frame:
                frame = frame.copy()

            return True, frame

    def disconnect(self):
        self.running = False

        if (
            self.thread is not None
            and self.thread.is_alive()
            and self.thread != threading.current_thread()
        ):
            self.thread.join(timeout=2)

        self.thread = None

        capture = self.capture
        self.capture = None

        if capture is not None:
            try:
                capture.release()
            except cv2.error:
                pass

        with self.lock:
            self.frame = None
            self.last_frame_time = 0

    def is_connected(self) -> bool:
        return (
            self.capture is not None
            and self.capture.isOpened()
            and self.running
        )
