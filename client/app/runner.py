import ctypes
import sys

from app.main import main
from app.utils.logging_setup import setup_client_logging


_MUTEX_HANDLE = None
_MUTEX_NAME = "Local\\SistemaCamara.ContePersonas"
_ERROR_ALREADY_EXISTS = 183


def acquire_single_instance() -> bool:
    global _MUTEX_HANDLE

    if sys.platform != "win32":
        return True

    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True
    )
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_wchar_p
    ]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [
        ctypes.c_void_p
    ]
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.CreateMutexW(
        None,
        False,
        _MUTEX_NAME
    )

    if not handle:
        # Si Windows no permite crear el mutex, no bloqueamos el cliente.
        return True

    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False

    _MUTEX_HANDLE = handle
    return True


if __name__ == "__main__":
    log_file = setup_client_logging()

    if not acquire_single_instance():
        print(
            "[CLIENT] Ya existe una instancia de ContePersonas. "
            "Esta ejecucion se cierra para evitar conteo duplicado."
        )
        raise SystemExit(0)

    print(f"[LOG] Archivo: {log_file}")
    main()
