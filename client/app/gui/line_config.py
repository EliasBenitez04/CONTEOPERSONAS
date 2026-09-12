import cv2

from app.config.camera_config import (
    load_camera_config,
    save_camera_config
)


class LineConfigurator:

    def __init__(self):

        self.config = (
            load_camera_config()
        )

        self.points = []

        self.original_frame = None
        self.frame = None

    def mouse_event(
        self,
        event,
        x,
        y,
        flags,
        param
    ):

        if (
            event
            != cv2.EVENT_LBUTTONDOWN
        ):
            return

        # Si ya hay 2 puntos,
        # comenzar nuevamente
        if len(self.points) == 2:

            self.points = []

        self.points.append(
            (x, y)
        )

        self.draw()

    def draw(self):

        self.frame = (
            self.original_frame.copy()
        )

        for point in self.points:

            cv2.circle(
                self.frame,
                point,
                7,
                (0, 255, 255),
                -1
            )

        if len(self.points) == 2:

            p1 = self.points[0]
            p2 = self.points[1]

            cv2.line(
                self.frame,
                p1,
                p2,
                (255, 0, 255),
                3
            )

        cv2.putText(
            self.frame,
            "Click: seleccionar 2 puntos",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.putText(
            self.frame,
            "S: Guardar",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.putText(
            self.frame,
            "I: Invertir IN / OUT",
            (20, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

        cv2.putText(
            self.frame,
            "Q: Cancelar",
            (20, 140),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

    def run(
        self,
        frame
    ):

        self.original_frame = (
            frame.copy()
        )

        line = self.config["line"]

        self.points = [
            (
                line["x1"],
                line["y1"]
            ),
            (
                line["x2"],
                line["y2"]
            )
        ]

        self.draw()

        window_name = (
            "CONFIGURAR LINEA"
        )

        cv2.namedWindow(
            window_name,
            cv2.WINDOW_NORMAL
        )

        cv2.setMouseCallback(
            window_name,
            self.mouse_event
        )

        saved = False

        while True:

            cv2.imshow(
                window_name,
                self.frame
            )

            key = (
                cv2.waitKey(20)
                & 0xFF
            )

            if key == ord("q"):

                break

            elif key == ord("i"):

                self.config[
                    "in_side"
                ] *= -1

                print(
                    "[CONFIG] IN/OUT invertido."
                )

            elif key == ord("s"):

                if len(self.points) != 2:

                    print(
                        "[CONFIG] Seleccione "
                        "2 puntos."
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

                saved = True

                print(
                    "[CONFIG] Configuracion "
                    "guardada."
                )

                break

        cv2.destroyWindow(
            window_name
        )

        return (
            self.config
            if saved
            else None
        )