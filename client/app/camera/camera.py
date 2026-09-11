import cv2


class Camera:

    def __init__(self, rtsp_url: str):

        self.rtsp_url = rtsp_url
        self.capture = None

    def connect(self) -> bool:

        self.disconnect()

        print("[CAMARA] Intentando conectar...")

        self.capture = cv2.VideoCapture(
            self.rtsp_url,
            cv2.CAP_FFMPEG
        )

        if not self.capture.isOpened():

            print("[CAMARA] No se pudo conectar.")

            self.disconnect()

            return False

        print("[CAMARA] Conexion exitosa.")

        return True

    def read(self):

        if self.capture is None:

            return False, None

        if not self.capture.isOpened():

            return False, None

        ret, frame = self.capture.read()

        if not ret:

            return False, None

        return True, frame

    def disconnect(self):

        if self.capture is not None:

            self.capture.release()
            self.capture = None

    def is_connected(self) -> bool:

        return (
            self.capture is not None
            and self.capture.isOpened()
        )