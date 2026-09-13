from urllib.parse import quote

from fastapi import Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import session_user_from_request
from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog


class WebAuthMiddleware(BaseHTTPMiddleware):
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

    async def dispatch(self, request: Request, call_next):
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
            return await call_next(request)

        database = SessionLocal()
        user = None
        try:
            user = session_user_from_request(request, database)
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

            is_change_path = (
                path == "/change-password"
                or path == "/api/auth/change-password"
                or path == "/api/auth/me"
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

            response = await call_next(request)

            if self._should_audit(request):
                try:
                    database.add(
                        AuditLog(
                            user_id=user.id,
                            username=user.username,
                            action=self._action_name(request),
                            method=request.method,
                            path=path,
                            status_code=response.status_code,
                            ip_address=(
                                request.client.host
                                if request.client else None
                            ),
                            details=(
                                request.url.query[:1000]
                                if request.url.query else None
                            )
                        )
                    )
                    database.commit()
                except Exception as error:
                    database.rollback()
                    print("[AUDIT] No se pudo registrar:", error)

            return response
        finally:
            database.close()

    @staticmethod
    def _should_audit(request: Request):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return True
        return request.url.path == "/api/reports/export.csv"

    @staticmethod
    def _action_name(request: Request):
        path = request.url.path
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
        return f"{request.method} {path}"

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
