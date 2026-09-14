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

        self.camera = Camera(
            rtsp_url
        )

        self.reconnect_seconds = (
            reconnect_seconds
        )

        self.max_fps = max(
            0.0,
            float(max_fps)
        )
        self.frame_interval = (
            1.0 / self.max_fps
            if self.max_fps > 0
            else 0.0
        )
        self.copy_frame = bool(copy_frame)

        self.running = False

    def start(self):

        self.running = True
        next_frame_at = 0.0

        while self.running:

            if not self.camera.is_connected():

                connected = (
                    self.camera.connect()
                )

                if not connected:

                    print(
                        "[RTSP] Reintentando "
                        f"en {self.reconnect_seconds}s..."
                    )

                    time.sleep(
                        self.reconnect_seconds
                    )

                    continue

                next_frame_at = 0.0

            if self.frame_interval > 0:
                now = time.monotonic()
                if next_frame_at > now:
                    time.sleep(
                        next_frame_at - now
                    )

            success, frame = (
                self.camera.read(
                    copy_frame=self.copy_frame
                )
            )

            if not success:

                print(
                    "[RTSP] No se reciben "
                    "frames actuales."
                )

                self.camera.disconnect()

                time.sleep(
                    self.reconnect_seconds
                )

                continue

            if self.frame_interval > 0:
                next_frame_at = (
                    time.monotonic()
                    + self.frame_interval
                )

            yield frame

    def stop(self):

        self.running = False

        self.camera.disconnect()
