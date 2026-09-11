import time

from app.camera.camera import Camera


class RTSPCamera:

    def __init__(
        self,
        rtsp_url: str,
        reconnect_seconds: int = 3
    ):

        self.camera = Camera(rtsp_url)

        self.reconnect_seconds = reconnect_seconds

        self.running = False

    def start(self):

        self.running = True

        while self.running:

            if not self.camera.is_connected():

                connected = self.camera.connect()

                if not connected:

                    print(
                        f"[RTSP] Reintentando en "
                        f"{self.reconnect_seconds} segundos..."
                    )

                    time.sleep(
                        self.reconnect_seconds
                    )

                    continue

            success, frame = self.camera.read()

            if not success:

                print(
                    "[RTSP] Se perdio la conexion "
                    "con la camara."
                )

                self.camera.disconnect()

                time.sleep(
                    self.reconnect_seconds
                )

                continue

            yield frame

    def stop(self):

        self.running = False

        self.camera.disconnect()