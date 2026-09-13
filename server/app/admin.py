from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_database
from app.models import Branch, Camera, CountEvent


router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

CAMERA_ONLINE_SECONDS = 45


class BranchAdminCreate(BaseModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    active: bool = True


class BranchAdminUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    active: bool = True


class CameraAdminCreate(BaseModel):
    branch_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


class CameraAdminUpdate(BaseModel):
    branch_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


def _clean_optional(value: str | None):
    if value is None:
        return None
    value = value.strip()
    return value or None


def _camera_online(camera: Camera):
    if not camera.active or camera.last_seen_at is None:
        return False

    last_seen = camera.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    return (
        datetime.now(timezone.utc) - last_seen
    ).total_seconds() <= CAMERA_ONLINE_SECONDS


@router.get("/admin/branches", response_class=HTMLResponse)
def branches_page(
    request: Request,
    database: Session = Depends(get_database)
):
    return templates.TemplateResponse(
        request=request,
        name="admin_branches.html",
        context={}
    )


@router.get("/admin/cameras", response_class=HTMLResponse)
def cameras_page(
    request: Request,
    database: Session = Depends(get_database)
):
    branches = database.scalars(
        select(Branch).order_by(Branch.id.asc())
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin_cameras.html",
        context={
            "branches": branches
        }
    )


@router.get("/api/admin/branches")
def admin_list_branches(
    database: Session = Depends(get_database)
):
    branches = database.scalars(
        select(Branch)
        .options(selectinload(Branch.cameras))
        .order_by(Branch.id.asc())
    ).all()

    result = []
    for branch in branches:
        result.append({
            "id": branch.id,
            "name": branch.name,
            "address": branch.address,
            "active": branch.active,
            "camera_count": len(branch.cameras),
            "active_camera_count": sum(
                1 for camera in branch.cameras
                if camera.active
            ),
            "created_at": branch.created_at.isoformat()
            if branch.created_at else None
        })

    return result


@router.post(
    "/api/admin/branches",
    status_code=status.HTTP_201_CREATED
)
def admin_create_branch(
    payload: BranchAdminCreate,
    database: Session = Depends(get_database)
):
    if database.get(Branch, payload.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una sucursal con ese ID"
        )

    branch = Branch(
        id=payload.id,
        name=payload.name.strip(),
        address=_clean_optional(payload.address),
        active=payload.active
    )
    database.add(branch)

    try:
        database.commit()
        database.refresh(branch)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo crear la sucursal"
        ) from error

    return {
        "status": "ok",
        "id": branch.id
    }


@router.put("/api/admin/branches/{branch_id}")
def admin_update_branch(
    branch_id: int,
    payload: BranchAdminUpdate,
    database: Session = Depends(get_database)
):
    branch = database.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sucursal no encontrada"
        )

    branch.name = payload.name.strip()
    branch.address = _clean_optional(payload.address)
    branch.active = payload.active

    database.commit()
    database.refresh(branch)

    return {
        "status": "ok",
        "id": branch.id
    }


@router.patch("/api/admin/branches/{branch_id}/toggle")
def admin_toggle_branch(
    branch_id: int,
    database: Session = Depends(get_database)
):
    branch = database.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sucursal no encontrada"
        )

    branch.active = not branch.active
    database.commit()

    return {
        "status": "ok",
        "active": branch.active
    }


@router.get("/api/admin/cameras")
def admin_list_cameras(
    branch_id: int | None = Query(default=None, gt=0),
    database: Session = Depends(get_database)
):
    query = (
        select(Camera)
        .options(selectinload(Camera.branch))
        .order_by(Camera.branch_id.asc(), Camera.id.asc())
    )

    if branch_id is not None:
        query = query.where(Camera.branch_id == branch_id)

    cameras = database.scalars(query).all()

    result = []
    for camera in cameras:
        event_count = database.scalar(
            select(func.count(CountEvent.id)).where(
                CountEvent.camera_id == camera.id
            )
        ) or 0

        last_seen = camera.last_seen_at
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        result.append({
            "id": camera.id,
            "branch_id": camera.branch_id,
            "branch_name": camera.branch.name,
            "name": camera.name,
            "active": camera.active,
            "online": _camera_online(camera),
            "last_seen_at": last_seen.isoformat() if last_seen else None,
            "event_count": int(event_count),
            "created_at": camera.created_at.isoformat()
            if camera.created_at else None
        })

    return result


@router.post(
    "/api/admin/cameras",
    status_code=status.HTTP_201_CREATED
)
def admin_create_camera(
    payload: CameraAdminCreate,
    database: Session = Depends(get_database)
):
    branch = database.get(Branch, payload.branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sucursal seleccionada no existe"
        )

    camera = Camera(
        branch_id=payload.branch_id,
        name=payload.name.strip(),
        active=payload.active
    )
    database.add(camera)

    try:
        database.commit()
        database.refresh(camera)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cámara con ese nombre en la sucursal"
        ) from error

    return {
        "status": "ok",
        "id": camera.id
    }


@router.put("/api/admin/cameras/{camera_id}")
def admin_update_camera(
    camera_id: int,
    payload: CameraAdminUpdate,
    database: Session = Depends(get_database)
):
    camera = database.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cámara no encontrada"
        )

    branch = database.get(Branch, payload.branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sucursal seleccionada no existe"
        )

    if payload.branch_id != camera.branch_id:
        event_count = database.scalar(
            select(func.count(CountEvent.id)).where(
                CountEvent.camera_id == camera.id
            )
        ) or 0

        if event_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "No se puede mover esta cámara porque ya tiene "
                    "eventos históricos registrados"
                )
            )

    camera.branch_id = payload.branch_id
    camera.name = payload.name.strip()
    camera.active = payload.active

    try:
        database.commit()
        database.refresh(camera)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cámara con ese nombre en la sucursal"
        ) from error

    return {
        "status": "ok",
        "id": camera.id
    }


@router.patch("/api/admin/cameras/{camera_id}/toggle")
def admin_toggle_camera(
    camera_id: int,
    database: Session = Depends(get_database)
):
    camera = database.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cámara no encontrada"
        )

    camera.active = not camera.active
    database.commit()

    return {
        "status": "ok",
        "active": camera.active
    }
