import time

from app.camera.camera import Camera


class RTSPCamera:

    def __init__(
        self,
        rtsp_url: str,
        reconnect_seconds: int = 3
    ):

        self.camera = Camera(
            rtsp_url
        )

        self.reconnect_seconds = (
            reconnect_seconds
        )

        self.running = False

    def start(self):

        self.running = True

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

            success, frame = (
                self.camera.read()
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

            yield frame

            # Evita bucle excesivamente agresivo
            time.sleep(0.001)

    def stop(self):

        self.running = False

        self.camera.disconnect()