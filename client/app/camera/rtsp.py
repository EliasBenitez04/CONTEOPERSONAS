import time

from app.camera.camera import Camera


class RTSPCamera:

    def __init__(
        self,
        rtsp_url: str,
        reconnect_seconds: int = 3,
        max_fps: float = 0,
        copy_frame: bool = True
    ):
        self.camera = Camera(rtsp_url)

        self.reconnect_seconds = reconnect_seconds

        self.max_fps = 0.0
        self.frame_interval = 0.0
        self.set_max_fps(max_fps, announce=False)
        self.copy_frame = bool(copy_frame)

        self.running = False

    def set_max_fps(self, max_fps: float, announce: bool = True):
        value = max(0.0, float(max_fps))

        if abs(value - self.max_fps) < 0.001:
            return

        self.max_fps = value
        self.frame_interval = (
            1.0 / self.max_fps
            if self.max_fps > 0
            else 0.0
        )

        # El mismo limite se aplica dentro del reader RTSP para que OpenCV no
        # convierta a BGR todos los frames de una camara de 25/30 FPS cuando el
        # detector solo necesita 3 FPS en segundo plano.
        self.camera.set_output_fps(self.max_fps)

        if announce:
            if self.max_fps > 0:
                print(
                    "[RTSP] Procesamiento y conversion limitados a "
                    f"{self.max_fps:g} FPS."
                )
            else:
                print("[RTSP] Procesamiento sin limite de FPS.")

    def start(self):
        self.running = True
        next_frame_at = 0.0

        while self.running:
            if not self.camera.is_connected():
                connected = self.camera.connect()

                if not connected:
                    print(
                        "[RTSP] Reintentando "
                        f"en {self.reconnect_seconds}s..."
                    )
                    time.sleep(self.reconnect_seconds)
                    continue

                next_frame_at = 0.0

            frame_interval = self.frame_interval
            if frame_interval > 0:
                now = time.monotonic()
                if next_frame_at > now:
                    time.sleep(next_frame_at - now)

            success, frame = self.camera.read(
                copy_frame=self.copy_frame
            )

            if not success:
                print(
                    "[RTSP] No se reciben "
                    "frames actuales."
                )
                self.camera.disconnect()
                time.sleep(self.reconnect_seconds)
                continue

            frame_interval = self.frame_interval
            if frame_interval > 0:
                next_frame_at = (
                    time.monotonic() + frame_interval
                )
            else:
                next_frame_at = 0.0

            yield frame

    def stop(self):
        self.running = False
        self.camera.disconnect()
