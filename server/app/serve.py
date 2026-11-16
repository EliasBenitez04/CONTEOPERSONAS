"""Arranque de Uvicorn optimizado para conexiones HTTP en Windows.

En Windows, ProactorEventLoop puede imprimir una cascada de WinError 10054
al recibir desconexiones TCP de clientes. El servidor HTTP solo necesita
operaciones de sockets, por lo que utilizamos SelectorEventLoop de forma
explicita sin politicas asyncio obsoletas (Python >= 3.12).
"""
import asyncio
import sys

import uvicorn


def run_server(server: uvicorn.Server, *, platform: str | None = None) -> None:
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        # La limpieza de sockets desconectados no usa proactor_events.py.
        # loop_factory evita set_event_loop_policy (obsoleto en Python 3.14).
        print("[SERVER] Windows: SelectorEventLoop para conexiones HTTP.")
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        server.run()


def main() -> None:
    config = uvicorn.Config(
        "app.web:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        loop="asyncio",
    )
    run_server(uvicorn.Server(config))


if __name__ == "__main__":
    main()
