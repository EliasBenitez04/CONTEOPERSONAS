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

    def connect(self) -> bool:

        self.disconnect()

        print("[CAMARA] Intentando conectar...")

        capture = cv2.VideoCapture(
            self.rtsp_url,
            cv2.CAP_FFMPEG
        )

        capture.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1
        )

        if not capture.isOpened():

            print("[CAMARA] No se pudo conectar.")

            capture.release()

            return False

        self.capture = capture
        self.running = True

        self.thread = threading.Thread(
            target=self._reader,
            daemon=True
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

        print(
            "[CAMARA] Primer frame recibido."
        )

        return True

    def _reader(self):

        consecutive_failures = 0

        while self.running:

            capture = self.capture

            if capture is None:
                break

            try:

                ret, frame = capture.read()

            except cv2.error as error:

                # Si estamos cerrando el programa,
                # no es un error real.
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

            if not ret or frame is None:

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

                self.frame = frame
                self.last_frame_time = time.time()

    def read(self):

        with self.lock:

            if self.frame is None:

                return False, None

            if (
                self.last_frame_time > 0
                and time.time()
                - self.last_frame_time
                > 3
            ):

                return False, None

            return (
                True,
                self.frame.copy()
            )

    def disconnect(self):

        # IMPORTANTE:
        # primero avisamos al thread
        # que debe terminar.
        self.running = False

        # Esperamos que salga de _reader()
        if (
            self.thread is not None
            and
            self.thread.is_alive()
            and
            self.thread
            != threading.current_thread()
        ):

            self.thread.join(
                timeout=2
            )

        self.thread = None

        # Recién ahora liberamos OpenCV
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
            and
            self.capture.isOpened()
            and
            self.running
        )