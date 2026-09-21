import ctypes
import math

import cv2

from app.config.camera_config import (
    get_line_points,
    load_camera_config,
    save_camera_config
)
from app.detection.counter import LineCounter


MAIN_WINDOW_NAME = "ContePersonas - Sistema Camara"
SCREEN_MARGIN_X = 36
SCREEN_MARGIN_Y = 100


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
    """
    Ajusta proporcionalmente al area visible del monitor.

    No usa 1280x720 ni limita el escalado a 1.0: una camara pequena puede
    ocupar mas pantalla y una camara grande se reduce, siempre conservando su
    relacion de aspecto.
    """
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
        available_height / float(height)
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
    """Ajusta la vista principal al monitor actual conservando el ratio."""
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
        self.config = load_camera_config()

        # Todos los puntos se guardan en coordenadas REALES del stream.
        self.points = []
        self.original_frame = None
        self.frame = None
        self.preview_width = 0
        self.preview_height = 0

        self.editing_started = False
        self.drawing = False
        self.minimum_point_distance = 10.0

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

        interpolation = (
            cv2.INTER_AREA
            if self.preview_width < width or self.preview_height < height
            else cv2.INTER_LINEAR
        )

        return cv2.resize(
            frame,
            (self.preview_width, self.preview_height),
            interpolation=interpolation
        )

    def _restore_main_window_size(self):
        if self.original_frame is None:
            return

        width, height = fitted_frame_size(self.original_frame)

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

    def _start_new_trace_if_needed(self):
        if self.editing_started:
            return

        # El primer toque reemplaza la linea anterior. Asi no hace falta hacer
        # un primer guardado intermedio ni borrar manualmente la linea vieja.
        self.points = []
        self.editing_started = True

    def _append_preview_point(self, x, y, force=False):
        self._start_new_trace_if_needed()
        point = self._preview_to_original(x, y)

        if self.points and not force:
            last_x, last_y = self.points[-1]
            distance = math.hypot(
                point[0] - last_x,
                point[1] - last_y
            )
            if distance < self.minimum_point_distance:
                return False

        if not self.points or point != self.points[-1]:
            self.points.append(point)
            return True

        return False

    def mouse_event(
        self,
        event,
        x,
        y,
        flags,
        param
    ):
        changed = False

        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            changed = self._append_preview_point(x, y, force=True)

        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            if flags & cv2.EVENT_FLAG_LBUTTON:
                changed = self._append_preview_point(x, y, force=False)

        elif event == cv2.EVENT_LBUTTONUP:
            if self.drawing:
                changed = self._append_preview_point(x, y, force=True) or changed
            self.drawing = False

        elif event == cv2.EVENT_RBUTTONDOWN:
            self.drawing = False
            if self.editing_started and self.points:
                self.points.pop()
                changed = True

        if changed:
            self.draw()

    @staticmethod
    def _representative_segment(points):
        best = None
        best_length = -1.0

        for index in range(len(points) - 1):
            p1 = points[index]
            p2 = points[index + 1]
            length = math.hypot(
                p2[0] - p1[0],
                p2[1] - p1[1]
            )
            if length > best_length:
                best_length = length
                best = (p1, p2)

        return best

    @staticmethod
    def _direction_positions(
        p1,
        p2,
        offset=60
    ):
        x1, y1 = p1
        x2, y2 = p2

        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0
        dx = x2 - x1
        dy = y2 - y1

        length = max(
            1.0,
            math.hypot(dx, dy)
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
        if len(self.points) < 2:
            return

        segment = self._representative_segment(self.points)
        if segment is None:
            return

        positive, negative = self._direction_positions(
            segment[0],
            segment[1]
        )

        # Usa exactamente la misma distancia firmada que el contador real.
        # De esta forma lo que se ve como IN/OUT coincide con lo que se guarda.
        counter = LineCounter(
            points=self.points,
            in_side=self.config["in_side"],
            margin=self.config.get("margin", 18)
        )
        positive_score = (
            counter.signed_distance(positive)
            * counter.in_side
        )
        negative_score = (
            counter.signed_distance(negative)
            * counter.in_side
        )

        if positive_score >= negative_score:
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
        canvas = self.original_frame.copy()
        overlay = canvas.copy()

        cv2.rectangle(
            overlay,
            (12, 12),
            (650, 214),
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

        for index, point in enumerate(self.points):
            cv2.circle(
                canvas,
                point,
                6,
                (0, 255, 255),
                -1
            )

            if index > 0:
                cv2.line(
                    canvas,
                    self.points[index - 1],
                    point,
                    (255, 0, 255),
                    3
                )

        self._draw_direction_labels(canvas)

        cv2.putText(
            canvas,
            "CONFIGURAR TRAZADO",
            (25, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2
        )

        cv2.putText(
            canvas,
            "Click: puntos | Arrastrar: curva/polilinea",
            (25, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (230, 230, 230),
            2
        )

        cv2.putText(
            canvas,
            "Boton derecho / U: deshacer ultimo punto",
            (25, 104),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (230, 230, 230),
            2
        )

        cv2.putText(
            canvas,
            "R: empezar de cero | I: invertir IN / OUT",
            (25, 136),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (0, 255, 255),
            2
        )

        cv2.putText(
            canvas,
            "S/ENTER: guardar | Q/ESC: cancelar",
            (25, 168),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (0, 255, 0),
            2
        )

        cv2.putText(
            canvas,
            f"Puntos actuales: {len(self.points)}",
            (25, 198),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2
        )

        self.frame = self._resize_for_preview(canvas)

    def run(self, frame):
        self.original_frame = frame.copy()
        self._set_preview_geometry()

        self.points = [
            self._clamp_original_point(point)
            for point in get_line_points(self.config)
        ]
        self.editing_started = False
        self.drawing = False
        self.draw()

        window_name = "CONFIGURAR LINEA"

        # El frame ya esta ajustado al monitor; AUTOSIZE evita una segunda
        # escala interna y mantiene exacta la conversion mouse -> stream.
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
            cv2.imshow(window_name, self.frame)

            key = cv2.waitKey(20) & 0xFF

            if key in (ord("q"), 27):
                break

            if key == ord("i"):
                self.config["in_side"] = (
                    -1
                    if int(self.config["in_side"]) >= 0
                    else 1
                )
                self.draw()
                print("[CONFIG] IN/OUT invertido.")
                continue

            if key == ord("r"):
                self.points = []
                self.editing_started = True
                self.draw()
                print("[CONFIG] Trazado reiniciado.")
                continue

            if key == ord("u"):
                if self.points:
                    self.points.pop()
                    self.editing_started = True
                    self.draw()
                continue

            if key in (ord("s"), 13):
                if len(self.points) < 2:
                    print(
                        "[CONFIG] El trazado necesita al menos 2 puntos."
                    )
                    continue

                compact = [self.points[0]]
                for point in self.points[1:]:
                    if point != compact[-1]:
                        compact.append(point)

                if len(compact) < 2:
                    print(
                        "[CONFIG] El trazado necesita al menos 2 puntos distintos."
                    )
                    continue

                self.config["line"] = {
                    "x1": compact[0][0],
                    "y1": compact[0][1],
                    "x2": compact[-1][0],
                    "y2": compact[-1][1],
                    "points": [
                        [point[0], point[1]]
                        for point in compact
                    ]
                }

                save_camera_config(self.config)
                saved = True

                print(
                    "[CONFIG] Trazado guardado desde el primer guardado "
                    f"con {len(compact)} puntos."
                )
                break

        cv2.destroyWindow(window_name)
        self._restore_main_window_size()

        return self.config if saved else None
