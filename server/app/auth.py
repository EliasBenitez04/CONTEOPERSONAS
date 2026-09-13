import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import SessionLocal, get_database
from app.models import User


router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

COOKIE_NAME = "sistema_camara_session"
PASSWORD_ITERATIONS = 260000
ROLES = {"ADMIN", "SUPERVISOR", "VIEWER"}


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordPayload(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class UserCreatePayload(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(min_length=1, max_length=20)
    active: bool = True


class UserUpdatePayload(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=20)
    active: bool = True


class ResetPasswordPayload(BaseModel):
    password: str = Field(min_length=8, max_length=200)


def hash_password(password: str):
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS
    )

    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(derived).decode("ascii")
    )


def verify_password(password: str, encoded: str):
    try:
        algorithm, iterations, salt_b64, hash_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(hash_b64.encode("ascii"))
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations)
        )
        return hmac.compare_digest(derived, expected)
    except (ValueError, TypeError):
        return False


def _b64encode(raw: bytes):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def create_session_token(user: User):
    payload = {
        "uid": user.id,
        "exp": int(time.time()) + (settings.SESSION_HOURS * 3600)
    }
    body = _b64encode(
        json.dumps(
            payload,
            separators=(",", ":")
        ).encode("utf-8")
    )
    signature = hmac.new(
        settings.SESSION_SECRET.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256
    ).digest()
    return f"{body}.{_b64encode(signature)}"


def parse_session_token(token: str | None):
    if not token or "." not in token:
        return None

    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(
            settings.SESSION_SECRET.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256
        ).digest()
        supplied = _b64decode(signature)

        if not hmac.compare_digest(expected, supplied):
            return None

        payload = json.loads(
            _b64decode(body).decode("utf-8")
        )

        if int(payload.get("exp", 0)) < int(time.time()):
            return None

        return int(payload["uid"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def session_user_from_request(request: Request, database: Session):
    user_id = parse_session_token(
        request.cookies.get(COOKIE_NAME)
    )

    if user_id is None:
        return None

    user = database.get(User, user_id)
    if user is None or not user.active:
        return None

    return user


def user_to_dict(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
    }


def _normalize_role(role: str):
    role = role.upper().strip()
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rol inválido"
        )
    return role


def _normalize_username(username: str):
    username = username.strip().lower()
    if not username or " " in username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El usuario no puede estar vacío ni contener espacios"
        )
    return username


def _active_admin_count(database: Session):
    return int(
        database.scalar(
            select(func.count(User.id)).where(
                User.role == "ADMIN",
                User.active.is_(True)
            )
        ) or 0
    )


class WebAuthMiddleware(BaseHTTPMiddleware):
    PROTECTED_WEB_PREFIXES = (
        "/dashboard",
        "/reports",
        "/admin",
        "/users",
        "/change-password"
    )

    PROTECTED_API_PREFIXES = (
        "/api/dashboard-data",
        "/api/reports",
        "/api/admin",
        "/api/users",
        "/api/auth/me",
        "/api/auth/change-password"
    )

    ADMIN_PREFIXES = (
        "/admin",
        "/users",
        "/api/admin",
        "/api/users"
    )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        protected = (
            path.startswith(self.PROTECTED_WEB_PREFIXES)
            or path.startswith(self.PROTECTED_API_PREFIXES)
        )

        if not protected:
            return await call_next(request)

        database = SessionLocal()
        try:
            user = session_user_from_request(request, database)
            request.state.user = user

            if user is None:
                if path.startswith("/api/"):
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
                if path.startswith("/api/"):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Debe cambiar su contraseña"}
                    )
                return RedirectResponse(
                    url="/change-password",
                    status_code=status.HTTP_303_SEE_OTHER
                )

            if path.startswith(self.ADMIN_PREFIXES) and user.role != "ADMIN":
                if path.startswith("/api/"):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Permiso de administrador requerido"}
                    )
                return RedirectResponse(
                    url="/dashboard?forbidden=1",
                    status_code=status.HTTP_303_SEE_OTHER
                )

            return await call_next(request)
        finally:
            database.close()


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    database: Session = Depends(get_database)
):
    user = session_user_from_request(request, database)
    if user is not None:
        return RedirectResponse(
            url="/dashboard",
            status_code=status.HTTP_303_SEE_OTHER
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


@router.post("/api/auth/login")
def login(
    payload: LoginPayload,
    database: Session = Depends(get_database)
):
    username = payload.username.strip().lower()
    user = database.scalar(
        select(User).where(
            func.lower(User.username) == username
        )
    )

    if (
        user is None
        or not user.active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )

    user.last_login_at = datetime.now(timezone.utc)
    database.commit()

    token = create_session_token(user)
    response = JSONResponse({
        "status": "ok",
        "user": user_to_dict(user),
        "redirect": (
            "/change-password"
            if user.must_change_password
            else "/dashboard"
        )
    })
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(
        url="/login",
        status_code=status.HTTP_303_SEE_OTHER
    )
    response.delete_cookie(
        COOKIE_NAME,
        path="/"
    )
    return response


@router.get("/api/auth/me")
def auth_me(request: Request):
    user = request.state.user
    return user_to_dict(user)


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="change_password.html",
        context={"user": request.state.user}
    )


@router.post("/api/auth/change-password")
def change_password(
    request: Request,
    payload: ChangePasswordPayload,
    database: Session = Depends(get_database)
):
    user = database.get(User, request.state.user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida"
        )

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta"
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La nueva contraseña debe ser diferente"
        )

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    database.commit()

    return {"status": "ok"}


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={"user": request.state.user}
    )


@router.get("/api/users")
def list_users(
    database: Session = Depends(get_database)
):
    users = database.scalars(
        select(User).order_by(User.id.asc())
    ).all()
    return [user_to_dict(user) for user in users]


@router.post(
    "/api/users",
    status_code=status.HTTP_201_CREATED
)
def create_user(
    payload: UserCreatePayload,
    database: Session = Depends(get_database)
):
    username = _normalize_username(payload.username)
    role = _normalize_role(payload.role)

    if database.scalar(
        select(User).where(func.lower(User.username) == username)
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya existe"
        )

    user = User(
        username=username,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=role,
        active=payload.active,
        must_change_password=True
    )
    database.add(user)

    try:
        database.commit()
        database.refresh(user)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo crear el usuario"
        ) from error

    return user_to_dict(user)


@router.put("/api/users/{user_id}")
def update_user(
    user_id: int,
    request: Request,
    payload: UserUpdatePayload,
    database: Session = Depends(get_database)
):
    user = database.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    new_role = _normalize_role(payload.role)
    current_user = request.state.user

    if user.id == current_user.id:
        if not payload.active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No puede desactivar su propio usuario"
            )
        if new_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No puede quitarse a sí mismo el rol ADMIN"
            )

    if (
        user.role == "ADMIN"
        and user.active
        and (new_role != "ADMIN" or not payload.active)
        and _active_admin_count(database) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debe existir al menos un administrador activo"
        )

    user.full_name = payload.full_name.strip()
    user.role = new_role
    user.active = payload.active
    database.commit()
    database.refresh(user)

    return user_to_dict(user)


@router.patch("/api/users/{user_id}/toggle")
def toggle_user(
    user_id: int,
    request: Request,
    database: Session = Depends(get_database)
):
    user = database.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    if user.id == request.state.user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puede desactivar su propio usuario"
        )

    if user.role == "ADMIN" and user.active and _active_admin_count(database) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debe existir al menos un administrador activo"
        )

    user.active = not user.active
    database.commit()

    return {
        "status": "ok",
        "active": user.active
    }


@router.post("/api/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    payload: ResetPasswordPayload,
    database: Session = Depends(get_database)
):
    user = database.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    user.password_hash = hash_password(payload.password)
    user.must_change_password = True
    database.commit()

    return {"status": "ok"}
