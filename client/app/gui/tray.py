import ctypes
import sys
import threading
import time

import pystray
from PIL import Image, ImageDraw


class TrayController:
    """Controla el icono de bandeja y la ventana OpenCV en Windows."""

    SW_HIDE = 0
    SW_SHOW = 5
    SW_RESTORE = 9
    WM_CHAR = 0x0102

    def __init__(self, window_title: str):
        self.window_title = str(window_title)
        self.enabled = sys.platform == "win32"

        self._show_requested = threading.Event()
        self._exit_requested = threading.Event()
        self._icon = None
        self._thread = None

        self._user32 = ctypes.windll.user32 if self.enabled else None

    def _make_icon_image(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (5, 5, 59, 59),
            radius=12,
            fill=(32, 32, 32, 255)
        )
        draw.ellipse(
            (16, 16, 48, 48),
            fill=(0, 190, 120, 255)
        )
        draw.ellipse(
            (26, 26, 38, 38),
            fill=(255, 255, 255, 255)
        )
        return image

    def start(self):
        if not self.enabled or self._icon is not None:
            return

        menu = pystray.Menu(
            pystray.MenuItem(
                "Mostrar",
                self._on_show,
                default=True
            ),
            pystray.MenuItem(
                "Configurar linea",
                self._on_configure
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Salir",
                self._on_exit
            )
        )

        self._icon = pystray.Icon(
            "ContePersonas",
            self._make_icon_image(),
            "ContePersonas - Sistema Camara",
            menu
        )

        self._thread = threading.Thread(
            target=self._icon.run,
            daemon=True,
            name="ContePersonasTray"
        )
        self._thread.start()
        print("[TRAY] Icono de bandeja iniciado.")

    def stop(self):
        icon = self._icon
        self._icon = None

        if icon is not None:
            try:
                icon.stop()
            except Exception as error:
                print(f"[TRAY] Error cerrando icono: {error}")

        self._thread = None

    def _delayed_restore(self):
        # Cuando el usuario cerro la X, OpenCV puede necesitar uno o dos ciclos
        # de imshow() para recrear el HWND. Reintentamos para recuperar foco.
        for delay in (0.05, 0.18, 0.35):
            time.sleep(delay)
            if self.restore_window():
                return

    def _on_show(self, icon=None, item=None):
        self._show_requested.set()
        self.restore_window()
        threading.Thread(
            target=self._delayed_restore,
            daemon=True,
            name="ContePersonasRestore"
        ).start()

    def _on_configure(self, icon=None, item=None):
        # Ademas de restaurar, enviamos una 'c' directamente al HWND de OpenCV.
        # Asi la configuracion funciona aunque Windows no entregue foco de
        # teclado al primer intento despues de sacar la app de la bandeja.
        self._show_requested.set()

        def configure_when_visible():
            for delay in (0.12, 0.25, 0.45, 0.75):
                time.sleep(delay)
                self.restore_window()
                hwnd = self._find_window()
                if hwnd:
                    self._user32.PostMessageW(
                        hwnd,
                        self.WM_CHAR,
                        ord("c"),
                        0
                    )
                    return

        threading.Thread(
            target=configure_when_visible,
            daemon=True,
            name="ContePersonasConfigureLine"
        ).start()

    def _on_exit(self, icon=None, item=None):
        self._exit_requested.set()

    def consume_show_request(self) -> bool:
        if not self._show_requested.is_set():
            return False

        self._show_requested.clear()
        return True

    def exit_requested(self) -> bool:
        return self._exit_requested.is_set()

    def _find_window(self):
        if not self.enabled:
            return None

        hwnd = self._user32.FindWindowW(
            None,
            self.window_title
        )
        return hwnd or None

    def window_exists(self) -> bool:
        return self._find_window() is not None

    def is_minimized(self) -> bool:
        hwnd = self._find_window()
        if not hwnd:
            return False

        return bool(self._user32.IsIconic(hwnd))

    def hide_window(self):
        hwnd = self._find_window()
        if not hwnd:
            return False

        self._user32.ShowWindow(hwnd, self.SW_HIDE)
        return True

    def restore_window(self):
        hwnd = self._find_window()
        if not hwnd:
            return False

        self._user32.ShowWindow(hwnd, self.SW_RESTORE)
        self._user32.ShowWindow(hwnd, self.SW_SHOW)
        self._user32.BringWindowToTop(hwnd)

        try:
            self._user32.SetForegroundWindow(hwnd)
            self._user32.SetActiveWindow(hwnd)
            self._user32.SetFocus(hwnd)
        except Exception:
            pass

        return True
