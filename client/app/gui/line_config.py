import ctypes

import cv2

from app.config.camera_config import (
    load_camera_config,
    save_camera_config
)


MAIN_WINDOW_NAME = "ContePersonas - Sistema Camara"
SCREEN_MARGIN_X = 80
SCREEN_MARGIN_Y = 120


class _Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]


def _screen_work_area():
    """Devuelve el area util de Windows excluyendo la barra de tareas."""
    try:
        rect = _Rect()
        user32 = ctypes.windll.user32

        if user32.SystemParametersInfoW(
            48,
            0,
            ctypes.byref(rect),
            0
        ):
            width = int(rect.right - rect.left)
            height = int(rect.bottom - rect.top)

            if width > 0 and height > 0:
                return width, height
    except Exception:
        pass

    return None


def fitted_frame_size(frame):
    """Ajusta proporcionalmente al monitor sin usar un 1280x720 fijo."""
    height, width = frame.shape[:2]

    if width <= 0 or height <= 0:
        return 640, 480

    work_area = _screen_work_area()
    if work_area is None:
        return width, height

    screen_width, screen_height = work_area
    available_width = max(320, screen_width - SCREEN_MARGIN_X)
    available_height = max(240, screen_height - SCREEN_MARGIN_Y)

    scale = min(
        available_width / float(width),
        available_height / float(height),
        1.0
    )

    return (
        max(1, int(round(width * scale))),
        max(1, int(round(height * scale)))
    )


def _window_flags():
    flags = cv2.WINDOW_NORMAL

    if hasattr(cv2, "WINDOW_KEEPRATIO"):
        flags |= cv2.WINDOW_KEEPRATIO

    return flags


def fit_main_window(window_name, frame):
    """Prepara la vista principal para el monitor actual conservando ratio."""
    width, height = fitted_frame_size(frame)

    cv2.namedWindow(
        window_name,
        _window_flags()
    )

    cv2.resizeWindow(
        window_name,
        width,
        height
    )

    return width, height


class LineConfigurator:

    def __init__(self):
        self.config = (
            load_camera_config()
        )

        # Los puntos siempre se guardan en coordenadas REALES del stream.
        # La vista puede ser mas pequena dependiendo del monitor.
        self.points = []

        self.original_frame = None
        self.frame = None
        self.preview_width = 0
        self.preview_height = 0

    def _set_preview_geometry(self):
        self.preview_width, self.preview_height = (
            fitted_frame_size(self.original_frame)
        )

    def _clamp_original_point(self, point):
        height, width = self.original_frame.shape[:2]
        x, y = point

        return (
            max(0, min(width - 1, int(round(x)))),
            max(0, min(height - 1, int(round(y))))
        )

    def _preview_to_original(self, x, y):
        height, width = self.original_frame.shape[:2]

        if self.preview_width <= 0 or self.preview_height <= 0:
            return self._clamp_original_point((x, y))

        original_x = x * (width / float(self.preview_width))
        original_y = y * (height / float(self.preview_height))

        return self._clamp_original_point(
            (original_x, original_y)
        )

    def _resize_for_preview(self, frame):
        height, width = frame.shape[:2]

        if (
            width == self.preview_width
            and height == self.preview_height
        ):
            return frame

        return cv2.resize(
            frame,
            (self.preview_width, self.preview_height),
            interpolation=cv2.INTER_AREA
        )

    def _restore_main_window_size(self):
        """Restaura el HWND principal sin destruirlo ni fijarlo a 1280x720."""
        if self.original_frame is None:
            return

        width, height = fitted_frame_size(
            self.original_frame
        )

        try:
            if hasattr(cv2, "WND_PROP_AUTOSIZE"):
                cv2.setWindowProperty(
                    MAIN_WINDOW_NAME,
                    cv2.WND_PROP_AUTOSIZE,
                    0.0
                )

            cv2.resizeWindow(
                MAIN_WINDOW_NAME,
                width,
                height
            )
        except cv2.error:
            pass

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

        self.points.append(
            self._preview_to_original(x, y)
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

    def _draw_direction_labels(self, canvas):
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
            canvas,
            "IN",
            in_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.95,
            (0, 255, 0),
            3
        )

        cv2.putText(
            canvas,
            "OUT",
            out_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.95,
            (0, 70, 255),
            3
        )

    def draw(self):
        canvas = (
            self.original_frame.copy()
        )

        overlay = canvas.copy()

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
            canvas,
            0.28,
            0,
            canvas
        )

        for point in self.points:
            cv2.circle(
                canvas,
                point,
                7,
                (0, 255, 255),
                -1
            )

        if len(self.points) == 2:
            cv2.line(
                canvas,
                self.points[0],
                self.points[1],
                (255, 0, 255),
                3
            )

            self._draw_direction_labels(
                canvas
            )

        cv2.putText(
            canvas,
            "CONFIGURAR LINEA",
            (25, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2
        )

        cv2.putText(
            canvas,
            "Click: marcar 2 puntos",
            (25, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (230, 230, 230),
            2
        )

        cv2.putText(
            canvas,
            "I: invertir IN / OUT",
            (25, 104),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 255),
            2
        )

        cv2.putText(
            canvas,
            "S: guardar | Q: cancelar",
            (25, 136),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 0),
            2
        )

        self.frame = self._resize_for_preview(
            canvas
        )

    def run(
        self,
        frame
    ):
        self.original_frame = (
            frame.copy()
        )
        self._set_preview_geometry()

        line = self.config[
            "line"
        ]

        self.points = [
            self._clamp_original_point(
                (
                    line["x1"],
                    line["y1"]
                )
            ),
            self._clamp_original_point(
                (
                    line["x2"],
                    line["y2"]
                )
            )
        ]

        self.draw()

        window_name = (
            "CONFIGURAR LINEA"
        )

        # Mostramos ya un frame reducido al monitor, por eso AUTOSIZE deja
        # coordenadas de mouse exactas y evita una segunda escala de HighGUI.
        cv2.namedWindow(
            window_name,
            cv2.WINDOW_AUTOSIZE
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

        self._restore_main_window_size()

        return (
            self.config
            if saved
            else None
        )
