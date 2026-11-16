from urllib.parse import quote

from fastapi import Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth import session_user_from_request
from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog


class WebAuthMiddleware:
    AUTHENTICATED_PREFIXES = (
        "/dashboard",
        "/api/dashboard-data",
        "/change-password",
        "/api/auth/me",
        "/api/auth/change-password"
    )

    SUPERVISOR_PREFIXES = (
        "/reports",
        "/api/reports"
    )

    ADMIN_PREFIXES = (
        "/admin",
        "/users",
        "/api/admin",
        "/api/users",
        "/docs",
        "/redoc",
        "/openapi.json"
    )

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Middleware ASGI puro: evita la capa de streams de BaseHTTPMiddleware
        # que podia generar multiples CancelledError al cerrar Uvicorn.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        authorization = await self._authorize(request)
        if isinstance(authorization, Response):
            await authorization(scope, receive, send)
            return

        # Las APIs de las camaras siguen funcionando sin sesion de navegador.
        if authorization is None:
            await self.app(scope, receive, send)
            return

        user = authorization
        if not self._should_audit(request):
            await self.app(scope, receive, send)
            return

        path = request.url.path
        method = request.method
        ip_address = request.client.host if request.client else None
        details = request.url.query[:1000] if request.url.query else None

        async def send_with_audit(message: Message):
            if message["type"] == "http.response.start":
                # Auditar antes de enviar la respuesta, inclusive CSV en streaming.
                # No mantener una conexion a PostgreSQL durante el streaming.
                await run_in_threadpool(
                    self._write_audit, user.id, user.username, method,
                    path, message["status"], ip_address, details
                )
            await send(message)

        await self.app(scope, receive, send_with_audit)

    @staticmethod
    def _load_user(request: Request):
        with SessionLocal() as database:
            user = session_user_from_request(request, database)
            if user is not None:
                database.expunge(user)
            return user

    @staticmethod
    def _write_audit(user_id, username, method, path, status_code, ip_address, details):
        try:
            with SessionLocal() as audit_db:
                audit_db.add(AuditLog(
                    user_id=user_id,
                    username=username,
                    action=WebAuthMiddleware._action_name_for(method, path),
                    method=method,
                    path=path,
                    status_code=status_code,
                    ip_address=ip_address,
                    details=details
                ))
                audit_db.commit()
        except Exception as error:
            print("[AUDIT] No se pudo registrar:", error)

    async def _authorize(self, request: Request):
        path = request.url.path

        if settings.ENVIRONMENT == "production":
            if path == "/api/cameras/heartbeat":
                return JSONResponse(
                    status_code=status.HTTP_410_GONE,
                    content={
                        "detail": (
                            "Heartbeat V2 deshabilitado. Registre el cliente "
                            "desde Administracion > Clientes."
                        )
                    }
                )

            if (
                path == "/api/count-events"
                and request.method == "POST"
                and not request.headers.get("X-Client-ID")
                and not settings.API_TOKEN
            ):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "CLIENT_ID y CLIENT_TOKEN requeridos en produccion"
                    }
                )

            legacy_paths = (
                "/api/branches",
                "/api/cameras",
                "/api/summary"
            )
            legacy_read = (
                path == "/api/count-events"
                and request.method == "GET"
            )
            if (
                not settings.API_TOKEN
                and (
                    path in legacy_paths
                    or legacy_read
                )
            ):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": (
                            "API legacy deshabilitada en produccion. "
                            "Use la interfaz web autenticada."
                        )
                    }
                )

        protected = (
            path.startswith(self.AUTHENTICATED_PREFIXES)
            or path.startswith(self.SUPERVISOR_PREFIXES)
            or path.startswith(self.ADMIN_PREFIXES)
        )

        if not protected:
            return None

        # No mantener conexiones mientras FastAPI procesa la respuesta.
        # El usuario queda desacoplado del ORM para la autorizacion y las vistas.
        user = await run_in_threadpool(self._load_user, request)
        request.state.user = user
        if user is None:
            if path.startswith("/api/") or path == "/openapi.json":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Sesión requerida"}
                )
            next_path = quote(path, safe="/")
            return RedirectResponse(
                url=f"/login?next={next_path}",
                status_code=status.HTTP_303_SEE_OTHER
            )

        is_change_path = path in (
            "/change-password",
            "/api/auth/change-password",
            "/api/auth/me"
        )
        if user.must_change_password and not is_change_path:
            if path.startswith("/api/") or path == "/openapi.json":
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Debe cambiar su contraseña"}
                )
            return RedirectResponse(
                url="/change-password",
                status_code=status.HTTP_303_SEE_OTHER
            )

        if path.startswith(self.ADMIN_PREFIXES) and user.role != "ADMIN":
            return self._forbidden(path)

        if (
            path.startswith(self.SUPERVISOR_PREFIXES)
            and user.role not in ("ADMIN", "SUPERVISOR")
        ):
            return self._forbidden(path)

        # El endpoint maneja su propia sesion. La autenticacion no retiene
        # conexiones de base de datos mientras el handler procesa la solicitud.
        return user

    @staticmethod
    def _should_audit(request: Request):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return True
        return request.url.path == "/api/reports/export.csv"

    @staticmethod
    def _action_name_for(method: str, path: str):
        if path.startswith("/api/admin/clients"):
            return "Administración de cliente"
        if path.startswith("/api/admin/branches"):
            return "Administración de sucursal"
        if path.startswith("/api/admin/cameras"):
            return "Administración de cámara"
        if path.startswith("/api/users"):
            return "Administración de usuario"
        if path == "/api/reports/export.csv":
            return "Exportación de reporte"
        if path == "/api/auth/change-password":
            return "Cambio de contraseña"
        return f"{method} {path}"

    @staticmethod
    def _forbidden(path: str):
        if path.startswith("/api/") or path == "/openapi.json":
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "No tiene permisos para esta sección"}
            )

        return RedirectResponse(
            url="/dashboard?forbidden=1",
            status_code=status.HTTP_303_SEE_OTHER
        )
