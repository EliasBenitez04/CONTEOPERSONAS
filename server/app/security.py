from urllib.parse import quote

from fastapi import Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import session_user_from_request
from app.database import SessionLocal


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

        protected = (
            path.startswith(self.AUTHENTICATED_PREFIXES)
            or path.startswith(self.SUPERVISOR_PREFIXES)
            or path.startswith(self.ADMIN_PREFIXES)
        )

        if not protected:
            return await call_next(request)

        database = SessionLocal()
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

            return await call_next(request)
        finally:
            database.close()

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
