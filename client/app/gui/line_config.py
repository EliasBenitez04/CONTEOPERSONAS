import cv2

from app.config.camera_config import (
    load_camera_config,
    save_camera_config
)


class LineConfigurator:

    def __init__(self):

        self.points = []

        self.frame = None
        self.original_frame = None

        self.config = load_camera_config()

    def mouse_event(
        self,
        event,
        x,
        y,
        flags,
        param
    ):

        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if len(self.points) >= 2:
            self.points = []

        self.points.append(
            (x, y)
        )

        self.draw()

    def draw(self):

        if self.original_frame is None:
            return

        self.frame = self.original_frame.copy()

        for point in self.points:

            cv2.circle(
                self.frame,
                point,
                6,
                (0, 255, 255),
                -1
            )

        if len(self.points) == 2:

            cv2.line(
                self.frame,
                self.points[0],
                self.points[1],
                (255, 0, 255),
                3
            )

        cv2.putText(
            self.frame,
            "Click 2 puntos para definir la linea",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            self.frame,
            "S = Guardar | I = Invertir IN/OUT | Q = Salir",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

    def run(self, frame):

        self.original_frame = frame.copy()

        current_line = self.config["line"]

        self.points = [
            (
                current_line["x1"],
                current_line["y1"]
            ),
            (
                current_line["x2"],
                current_line["y2"]
            )
        ]

        self.draw()

        window_name = "CONFIGURAR LINEA"

        cv2.namedWindow(
            window_name
        )

        cv2.setMouseCallback(
            window_name,
            self.mouse_event
        )

        while True:

            cv2.imshow(
                window_name,
                self.frame
            )

            key = cv2.waitKey(20) & 0xFF

            if key == ord("q"):

                break

            elif key == ord("i"):

                self.config["in_side"] *= -1

                print(
                    "[CONFIG] IN/OUT invertido."
                )

            elif key == ord("C"):

                if len(self.points) != 2:

                    print(
                        "[CONFIG] Debes seleccionar 2 puntos."
                    )

                    continue

                p1 = self.points[0]
                p2 = self.points[1]

                self.config["line"] = {
                    "x1": p1[0],
                    "y1": p1[1],
                    "x2": p2[0],
                    "y2": p2[1]
                }

                save_camera_config(
                    self.config
                )

                print(
                    "[CONFIG] Linea guardada correctamente."
                )

                break

        cv2.destroyWindow(
            window_name
        )