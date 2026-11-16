"""Pruebas de regresion de autenticacion y auditoria ASGI, sin PostgreSQL."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.config import settings
from app.security import WebAuthMiddleware


async def asgi_response(scope, receive, send):
    # Verifica que el usuario autenticado llegue al endpoint.
    if scope["path"].startswith("/api/admin/") and "state" in scope:
        assert scope["state"].get("user") is not None
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def make_user(role="ADMIN", must_change_password=False):
    return SimpleNamespace(
        id=7, username="operador", role=role,
        must_change_password=must_change_password
    )


def request(path, method="GET", query=b""):
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": query,
        "root_path": "", "headers": [], "client": ("127.0.0.1", 51234),
        "server": ("localhost", 8000),
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(WebAuthMiddleware(asgi_response)(scope, receive, send))
    return next(m["status"] for m in messages if m["type"] == "http.response.start")


class SecurityASGITests(unittest.TestCase):
    def test_camera_apis_bypass_web_session(self):
        with patch.object(WebAuthMiddleware, "_load_user") as load:
            self.assertEqual(request("/api/client/config"), 200)
            self.assertEqual(request("/api/count-events/batch", method="POST"), 200)
            load.assert_not_called()

    def test_admin_requires_session(self):
        with patch.object(WebAuthMiddleware, "_load_user", return_value=None):
            self.assertEqual(request("/api/admin/clients"), 401)
            self.assertEqual(request("/admin/clients"), 303)

    def test_web_roles_preserved(self):
        with patch.object(WebAuthMiddleware, "_load_user", return_value=make_user("SUPERVISOR")):
            self.assertEqual(request("/reports"), 200)
            self.assertEqual(request("/api/admin/clients"), 403)
        with patch.object(WebAuthMiddleware, "_load_user", return_value=make_user("VIEWER")):
            self.assertEqual(request("/reports"), 303)
        with patch.object(WebAuthMiddleware, "_load_user", return_value=make_user("ADMIN")):
            self.assertEqual(request("/api/admin/clients"), 200)

    def test_password_change_required(self):
        with patch.object(WebAuthMiddleware, "_load_user", return_value=make_user(must_change_password=True)):
            self.assertEqual(request("/api/admin/clients"), 403)
            self.assertEqual(request("/change-password"), 200)

    def test_audit_write_once_per_protected_mutation(self):
        with patch.object(WebAuthMiddleware, "_load_user", return_value=make_user()):
            with patch.object(WebAuthMiddleware, "_write_audit") as audit:
                self.assertEqual(request("/api/admin/clients/3/config", method="PUT"), 200)
                audit.assert_called_once()
                args = audit.call_args.args
                self.assertEqual(args[:5], (7, "operador", "PUT", "/api/admin/clients/3/config", 200))
                audit.reset_mock()
                self.assertEqual(request("/api/reports/export.csv", query=b"start_date=2026-11-16"), 200)
                audit.assert_called_once()

    def test_production_legacy_guard_without_affecting_clients(self):
        with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "API_TOKEN", ""):
            self.assertEqual(request("/api/cameras/heartbeat", method="POST"), 410)
            self.assertEqual(request("/api/count-events", method="POST"), 401)
            self.assertEqual(request("/api/client/config"), 200)

    def test_cancellation_propagates_without_wrapping_exception(self):
        async def cancelled_endpoint(scope, receive, send):
            raise asyncio.CancelledError()

        async def perform():
            scope = {
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "method": "GET", "scheme": "http", "path": "/api/client/config",
                "root_path": "", "headers": [], "query_string": b"",
                "client": ("127.0.0.1", 1234), "server": ("localhost", 8000)
            }
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            async def send(message):
                pass
            await WebAuthMiddleware(cancelled_endpoint)(scope, receive, send)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(perform())


if __name__ == "__main__":
    unittest.main()
