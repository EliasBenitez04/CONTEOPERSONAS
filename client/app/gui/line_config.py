import cv2

from app.config.camera_config import (
    load_camera_config,
    save_camera_config
)


MAIN_WINDOW_NAME = "ContePersonas - Sistema Camara"
PREVIEW_MAX_WIDTH = 1280
PREVIEW_MAX_HEIGHT = 720


class LineConfigurator:

    def __init__(self):
        self.config = (
            load_camera_config()
        )

        self.points = []

        self.original_frame = None
        self.frame = None

    @staticmethod
    def _preview_size(frame):
        height, width = frame.shape[:2]

        if width <= 0 or height <= 0:
            return (
                PREVIEW_MAX_WIDTH,
                PREVIEW_MAX_HEIGHT
            )

        scale = min(
            PREVIEW_MAX_WIDTH / float(width),
            PREVIEW_MAX_HEIGHT / float(height),
            1.0
        )

        return (
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale)))
        )

    @staticmethod
    def _window_flags():
        flags = cv2.WINDOW_NORMAL

        if hasattr(cv2, "WINDOW_KEEPRATIO"):
            flags |= cv2.WINDOW_KEEPRATIO

        return flags

    @classmethod
    def _prepare_window(cls, window_name, frame):
        width, height = cls._preview_size(frame)

        cv2.namedWindow(
            window_name,
            cls._window_flags()
        )

        cv2.resizeWindow(
            window_name,
            width,
            height
        )

    def _restore_main_preview(self):
        if self.original_frame is None:
            return

        # La vista principal se creaba implicitamente con WINDOW_AUTOSIZE,
        # mientras que el editor usa WINDOW_NORMAL. Al cerrar el editor,
        # OpenCV volvia a mostrar el frame a tamano nativo y parecia un zoom.
        # La recreamos en modo redimensionable con el mismo limite del editor.
        try:
            cv2.destroyWindow(
                MAIN_WINDOW_NAME
            )
            cv2.waitKey(1)
        except cv2.error:
            pass

        self._prepare_window(
            MAIN_WINDOW_NAME,
            self.original_frame
        )

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

        if len(self.points) == 2:
            self.points = []

        self.points.append(
            (x, y)
        )

        self.draw()

    @staticmethod
    def _direction_positions(
        p1,
        p2,
        offset=60
    ):
        x1, y1 = p1
        x2, y2 = p2

        mid_x = (
            x1 + x2
        ) / 2.0

        mid_y = (
            y1 + y2
        ) / 2.0

        dx = x2 - x1
        dy = y2 - y1

        length = max(
            1.0,
            (dx * dx + dy * dy) ** 0.5
        )

        nx = -dy / length
        ny = dx / length

        positive = (
            int(mid_x + nx * offset),
            int(mid_y + ny * offset)
        )

        negative = (
            int(mid_x - nx * offset),
            int(mid_y - ny * offset)
        )

        return positive, negative

    def _draw_direction_labels(self):
        if len(self.points) != 2:
            return

        positive, negative = (
            self._direction_positions(
                self.points[0],
                self.points[1]
            )
        )

        if int(self.config["in_side"]) >= 0:
            in_pos = positive
            out_pos = negative
        else:
            in_pos = negative
            out_pos = positive

        cv2.putText(
            self.frame,
            "IN",
            in_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.95,
            (0, 255, 0),
            3
        )

        cv2.putText(
            self.frame,
            "OUT",
            out_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.95,
            (0, 70, 255),
            3
        )

    def draw(self):
        self.frame = (
            self.original_frame.copy()
        )

        overlay = self.frame.copy()

        cv2.rectangle(
            overlay,
            (12, 12),
            (470, 170),
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
            cv2.line(
                self.frame,
                self.points[0],
                self.points[1],
                (255, 0, 255),
                3
            )

            self._draw_direction_labels()

        cv2.putText(
            self.frame,
            "CONFIGURAR LINEA",
            (25, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2
        )

        cv2.putText(
            self.frame,
            "Click: marcar 2 puntos",
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

    def run(
        self,
        frame
    ):
        self.original_frame = (
            frame.copy()
        )

        line = self.config[
            "line"
        ]

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

        self._prepare_window(
            window_name,
            self.original_frame
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

            if key == ord("i"):
                self.config[
                    "in_side"
                ] = (
                    -1
                    if int(
                        self.config[
                            "in_side"
                        ]
                    ) >= 0
                    else 1
                )

                self.draw()

                print(
                    "[CONFIG] IN/OUT invertido."
                )

                continue

            if key == ord("s"):
                if len(self.points) != 2:
                    print(
                        "[CONFIG] Seleccione 2 puntos."
                    )
                    continue

                p1 = self.points[0]
                p2 = self.points[1]

                self.config[
                    "line"
                ] = {
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
                    "[CONFIG] Configuracion guardada."
                )

                break

        cv2.destroyWindow(
            window_name
        )

        self._restore_main_preview()

        return (
            self.config
            if saved
            else None
        )
