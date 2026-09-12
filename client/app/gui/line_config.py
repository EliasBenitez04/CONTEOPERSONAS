import cv2

from app.config.camera_config import (
    load_camera_config,
    save_camera_config
)


class LineConfigurator:

    def __init__(self):

        self.config = load_camera_config()
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

        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if len(self.points) == 2:
            self.points = []

        self.points.append((x, y))
        self.draw()

    def _draw_direction_labels(self):

        if len(self.points) != 2:
            return

        p1, p2 = self.points

        x1, y1 = p1
        x2, y2 = p2

        mid_x = int((x1 + x2) / 2)
        mid_y = int((y1 + y2) / 2)

        dx = x2 - x1
        dy = y2 - y1
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)

        nx = -dy / length
        ny = dx / length
        offset = 55

        positive_pos = (
            int(mid_x + nx * offset),
            int(mid_y + ny * offset)
        )

        negative_pos = (
            int(mid_x - nx * offset),
            int(mid_y - ny * offset)
        )

        if self.config["in_side"] == 1:
            in_pos = positive_pos
            out_pos = negative_pos
        else:
            in_pos = negative_pos
            out_pos = positive_pos

        cv2.putText(
            self.frame,
            "IN",
            in_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2
        )

        cv2.putText(
            self.frame,
            "OUT",
            out_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 80, 255),
            2
        )

    def draw(self):

        self.frame = self.original_frame.copy()

        overlay = self.frame.copy()

        cv2.rectangle(
            overlay,
            (12, 12),
            (430, 165),
            (20, 20, 20),
            -1
        )

        cv2.addWeighted(
            overlay,
            0.72,
            self.frame,
            0.28,
            0,
            self.frame
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

            p1, p2 = self.points

            cv2.line(
                self.frame,
                p1,
                p2,
                (255, 0, 255),
                3
            )

            self._draw_direction_labels()

        cv2.putText(
            self.frame,
            "CONFIGURACION DE LINEA",
            (25, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2
        )

        cv2.putText(
            self.frame,
            "Click: seleccionar 2 puntos",
            (25, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (230, 230, 230),
            2
        )

        cv2.putText(
            self.frame,
            "I: invertir IN / OUT",
            (25, 104),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 255),
            2
        )

        cv2.putText(
            self.frame,
            "S: guardar | Q: cancelar",
            (25, 136),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 0),
            2
        )

    def run(self, frame):

        self.original_frame = frame.copy()

        line = self.config["line"]

        self.points = [
            (line["x1"], line["y1"]),
            (line["x2"], line["y2"])
        ]

        self.draw()

        window_name = "CONFIGURAR LINEA"

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

            key = cv2.waitKey(20) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("i"):

                self.config["in_side"] *= -1
                self.draw()

                print(
                    "[CONFIG] IN/OUT invertido."
                )

            elif key == ord("s"):

                if len(self.points) != 2:

                    print(
                        "[CONFIG] Seleccione 2 puntos."
                    )
                    continue

                p1, p2 = self.points

                self.config["line"] = {
                    "x1": p1[0],
                    "y1": p1[1],
                    "x2": p2[0],
                    "y2": p2[1]
                }

                save_camera_config(self.config)
                saved = True

                print(
                    "[CONFIG] Configuracion guardada."
                )

                break

        cv2.destroyWindow(window_name)

        return self.config if saved else None
