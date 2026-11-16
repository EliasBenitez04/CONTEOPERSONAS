"""Pruebas del arranque de servidor HTTP, incluido Windows 3.14."""
import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from app import serve


class FakeServer:
    def __init__(self):
        self.started_on = None
        self.default_run_called = False

    async def serve(self):
        self.started_on = asyncio.get_running_loop()

    def run(self):
        self.default_run_called = True


class ServerRunnerTests(unittest.TestCase):
    def test_windows_uses_selector_event_loop(self):
        server = FakeServer()
        serve.run_server(server, platform="win32")
        self.assertIsInstance(server.started_on, asyncio.SelectorEventLoop)
        self.assertFalse(server.default_run_called)

    def test_other_platforms_keep_uvicorn_default(self):
        server = FakeServer()
        serve.run_server(server, platform="linux")
        self.assertTrue(server.default_run_called)
        self.assertIsNone(server.started_on)

    def test_main_preserves_production_address(self):
        with patch.object(serve.uvicorn, "Config") as config:
            with patch.object(serve.uvicorn, "Server") as server_class:
                with patch.object(serve, "run_server") as run:
                    serve.main()
        config.assert_called_once_with(
            "app.web:app", host="0.0.0.0", port=8000,
            workers=1, loop="asyncio"
        )
        server_class.assert_called_once_with(config.return_value)
        run.assert_called_once_with(server_class.return_value)

    def test_batch_files_run_windows_safe_entry_point(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("python -m app.serve", (root / "run_server.bat").read_text())
        self.assertIn("python -m app.serve", (root / "start_server.bat").read_text())


if __name__ == "__main__":
    unittest.main()
