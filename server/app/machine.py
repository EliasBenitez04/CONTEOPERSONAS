import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    status
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_database
from app.models import Branch, Camera, ClientConfig, ClientDevice


router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ClientCreatePayload(BaseModel):
    branch_id: int = Field(gt=0)
    camera_id: int = Field(gt=0)


class ClientConfigPayload(BaseModel):
    line_x1: int = Field(ge=0)
    line_y1: int = Field(ge=0)
    line_x2: int = Field(ge=0)
    line_y2: int = Field(ge=0)
    in_side: int
    margin: int = Field(ge=1, le=300)
    confidence: int = Field(ge=1, le=99)


class ClientHeartbeatPayload(BaseModel):
    app_version: str | None = Field(default=None, max_length=40)
    pending_events: int = Field(default=0, ge=0)
    last_error: str | None = Field(default=None, max_length=500)


def hash_client_token(token: str):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_client_token(token: str, token_hash: str):
    return hmac.compare_digest(
        hash_client_token(token),
        token_hash
    )


def _extract_bearer(authorization: str | None):
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def resolve_machine_auth(
    x_client_id: str | None = Header(default=None, alias="X-Client-ID"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    database: Session = Depends(get_database)
):
    bearer = _extract_bearer(authorization)

    if x_client_id:
        client = database.scalar(
            select(ClientDevice)
            .options(
                selectinload(ClientDevice.branch),
                selectinload(ClientDevice.camera),
                selectinload(ClientDevice.config)
            )
            .where(ClientDevice.client_id == x_client_id.strip())
        )

        if (
            client is None
            or not client.active
            or bearer is None
            or not verify_client_token(bearer, client.token_hash)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales del cliente invalidas"
            )

        if not client.branch.active or not client.camera.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sucursal o camara inactiva"
            )

        return client

    if settings.API_TOKEN:
        if bearer != settings.API_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API token invalido o ausente"
            )

    return None


def _config_payload(client: ClientDevice, config: ClientConfig):
    return {
        "client_id": client.client_id,
        "branch_id": client.branch_id,
        "branch_name": client.branch.name,
        "camera_id": client.camera_id,
        "camera_name": client.camera.name,
        "config_version": int(config.config_version or 0),
        "bootstrap_required": int(config.config_version or 0) <= 0,
        "line": {
            "x1": config.line_x1,
            "y1": config.line_y1,
            "x2": config.line_x2,
            "y2": config.line_y2
        },
        "in_side": config.in_side,
        "margin": config.margin,
        "confidence": config.confidence / 100.0
    }


def _apply_config_values(config: ClientConfig, payload: ClientConfigPayload):
    config.line_x1 = payload.line_x1
    config.line_y1 = payload.line_y1
    config.line_x2 = payload.line_x2
    config.line_y2 = payload.line_y2
    config.in_side = 1 if payload.in_side >= 0 else -1
    config.margin = payload.margin
    config.confidence = payload.confidence
    config.updated_at = datetime.now(timezone.utc)


def client_to_dict(client: ClientDevice):
    config = client.config
    return {
        "id": client.id,
        "client_id": client.client_id,
        "branch_id": client.branch_id,
        "branch_name": client.branch.name,
        "camera_id": client.camera_id,
        "camera_name": client.camera.name,
        "active": client.active,
        "app_version": client.app_version,
        "pending_events": client.pending_events,
        "last_error": client.last_error,
        "last_ip": client.last_ip,
        "last_seen_at": (
            client.last_seen_at.isoformat()
            if client.last_seen_at else None
        ),
        "created_at": client.created_at.isoformat(),
        "config_version": config.config_version if config else 0,
        "bootstrap_required": bool(
            config is not None
            and int(config.config_version or 0) <= 0
        ),
        "config": {
            "line": {
                "x1": config.line_x1,
                "y1": config.line_y1,
                "x2": config.line_x2,
                "y2": config.line_y2
            },
            "in_side": config.in_side,
            "margin": config.margin,
            "confidence": config.confidence / 100.0
        } if config else None
    }


@router.get("/admin/clients", response_class=HTMLResponse)
def clients_page(
    request: Request,
    database: Session = Depends(get_database)
):
    branches = database.scalars(
        select(Branch).order_by(Branch.id.asc())
    ).all()
    cameras = database.scalars(
        select(Camera).order_by(Camera.branch_id.asc(), Camera.name.asc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "user": request.state.user,
            "branches": branches,
            "cameras": cameras
        }
    )


@router.get("/api/admin/clients")
def admin_list_clients(
    database: Session = Depends(get_database)
):
    clients = database.scalars(
        select(ClientDevice)
        .options(
            selectinload(ClientDevice.branch),
            selectinload(ClientDevice.camera),
            selectinload(ClientDevice.config)
        )
        .order_by(ClientDevice.id.asc())
    ).all()
    return [client_to_dict(client) for client in clients]


@router.post(
    "/api/admin/clients",
    status_code=status.HTTP_201_CREATED
)
def admin_create_client(
    payload: ClientCreatePayload,
    database: Session = Depends(get_database)
):
    branch = database.get(Branch, payload.branch_id)
    camera = database.get(Camera, payload.camera_id)

    if branch is None or camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sucursal o camara no encontrada"
        )

    if camera.branch_id != branch.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La camara no pertenece a la sucursal seleccionada"
        )

    existing = database.scalar(
        select(ClientDevice).where(
            ClientDevice.camera_id == camera.id
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La camara ya tiene un cliente registrado"
        )

    raw_token = secrets.token_urlsafe(32)
    client = ClientDevice(
        client_id=str(uuid.uuid4()),
        token_hash=hash_client_token(raw_token),
        branch_id=branch.id,
        camera_id=camera.id,
        active=True
    )
    database.add(client)

    try:
        database.flush()
        config = ClientConfig(
            client_device_id=client.id,
            line_x1=640,
            line_y1=100,
            line_x2=640,
            line_y2=650,
            in_side=1,
            margin=18,
            confidence=22,
            config_version=0
        )
        database.add(config)
        database.commit()
        database.refresh(client)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo registrar el cliente"
        ) from error

    return {
        "status": "ok",
        "client_id": client.client_id,
        "client_token": raw_token,
        "branch_id": branch.id,
        "camera_name": camera.name,
        "warning": (
            "El token se muestra una sola vez. Al conectar por primera vez, "
            "el cliente conservara y publicara su configuracion local actual."
        )
    }


@router.put("/api/admin/clients/{client_id}/config")
def admin_update_client_config(
    client_id: int,
    payload: ClientConfigPayload,
    database: Session = Depends(get_database)
):
    client = database.scalar(
        select(ClientDevice)
        .options(selectinload(ClientDevice.config))
        .where(ClientDevice.id == client_id)
    )
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado"
        )

    config = client.config
    if config is None:
        config = ClientConfig(client_device_id=client.id, config_version=0)
        database.add(config)

    _apply_config_values(config, payload)
    config.config_version = max(1, int(config.config_version or 0) + 1)
    database.commit()

    return {
        "status": "ok",
        "config_version": config.config_version
    }


@router.post("/api/admin/clients/{client_id}/rotate-token")
def admin_rotate_client_token(
    client_id: int,
    database: Session = Depends(get_database)
):
    client = database.get(ClientDevice, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado"
        )

    raw_token = secrets.token_urlsafe(32)
    client.token_hash = hash_client_token(raw_token)
    database.commit()

    return {
        "status": "ok",
        "client_id": client.client_id,
        "client_token": raw_token,
        "warning": "El token anterior dejo de ser valido."
    }


@router.patch("/api/admin/clients/{client_id}/toggle")
def admin_toggle_client(
    client_id: int,
    database: Session = Depends(get_database)
):
    client = database.get(ClientDevice, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado"
        )
    client.active = not client.active
    database.commit()
    return {"status": "ok", "active": client.active}


@router.get("/api/client/config")
def client_config(
    client: ClientDevice | None = Depends(resolve_machine_auth)
):
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CLIENT_ID requerido para configuracion remota"
        )

    config = client.config
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El cliente no tiene configuracion"
        )

    return _config_payload(client, config)


@router.put("/api/client/config")
def client_update_config(
    payload: ClientConfigPayload,
    client: ClientDevice | None = Depends(resolve_machine_auth),
    database: Session = Depends(get_database)
):
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CLIENT_ID requerido para actualizar configuracion"
        )

    managed_client = database.scalar(
        select(ClientDevice)
        .options(
            selectinload(ClientDevice.branch),
            selectinload(ClientDevice.camera),
            selectinload(ClientDevice.config)
        )
        .where(ClientDevice.id == client.id)
    )

    config = managed_client.config
    if config is None:
        config = ClientConfig(
            client_device_id=managed_client.id,
            config_version=0
        )
        database.add(config)

    _apply_config_values(config, payload)
    config.config_version = max(1, int(config.config_version or 0) + 1)
    database.commit()
    database.refresh(config)

    return _config_payload(managed_client, config)


@router.post("/api/client/bootstrap-config")
def bootstrap_client_config(
    payload: ClientConfigPayload,
    client: ClientDevice | None = Depends(resolve_machine_auth),
    database: Session = Depends(get_database)
):
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CLIENT_ID requerido"
        )

    managed_client = database.scalar(
        select(ClientDevice)
        .options(
            selectinload(ClientDevice.branch),
            selectinload(ClientDevice.camera),
            selectinload(ClientDevice.config)
        )
        .where(ClientDevice.id == client.id)
    )
    config = managed_client.config
    if config is None:
        config = ClientConfig(
            client_device_id=managed_client.id,
            config_version=0
        )
        database.add(config)

    if int(config.config_version or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La configuracion central ya fue inicializada"
        )

    _apply_config_values(config, payload)
    config.config_version = 1
    database.commit()
    database.refresh(config)

    return _config_payload(managed_client, config)


@router.post("/api/client/heartbeat")
def client_heartbeat(
    request: Request,
    payload: ClientHeartbeatPayload,
    client: ClientDevice | None = Depends(resolve_machine_auth),
    database: Session = Depends(get_database)
):
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CLIENT_ID requerido para heartbeat V3"
        )

    now = datetime.now(timezone.utc)
    managed_client = database.get(ClientDevice, client.id)
    camera = database.get(Camera, client.camera_id)

    managed_client.app_version = payload.app_version
    managed_client.pending_events = payload.pending_events
    managed_client.last_error = payload.last_error
    managed_client.last_ip = request.client.host if request.client else None
    managed_client.last_seen_at = now
    camera.last_seen_at = now
    database.commit()

    return {
        "status": "ok",
        "server_time": now.isoformat(),
        "config_version": (
            client.config.config_version
            if client.config else 0
        )
    }
