from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_database
from app.models import Branch, Camera, CountEvent
from app.schemas import (
    BranchCreate,
    BranchResponse,
    CameraCreate,
    CameraResponse,
    CountEventCreate,
    CountEventResponse,
    CountSummary,
    HealthResponse
)


security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="3.0.0",
    lifespan=lifespan
)


def verify_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
):
    if not settings.API_TOKEN:
        return

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or credentials.credentials != settings.API_TOKEN
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token invalido o ausente"
        )


def event_to_response(event: CountEvent, duplicate: bool = False):
    return CountEventResponse(
        id=event.id,
        event_uuid=event.event_uuid,
        branch_id=event.branch_id,
        camera_id=event.camera_id,
        camera_name=event.camera.name,
        track_id=event.track_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        received_at=event.received_at,
        duplicate=duplicate
    )


def get_or_create_branch(database: Session, branch_id: int):
    branch = database.get(Branch, branch_id)
    if branch is None:
        branch = Branch(id=branch_id, name=f"SUCURSAL_{branch_id}", active=True)
        database.add(branch)
        try:
            database.commit()
            database.refresh(branch)
        except IntegrityError:
            database.rollback()
            branch = database.get(Branch, branch_id)

    if branch is None:
        raise HTTPException(status_code=500, detail="No se pudo registrar la sucursal")
    if not branch.active:
        raise HTTPException(status_code=403, detail="La sucursal esta inactiva")
    return branch


def get_or_create_camera(database: Session, branch_id: int, camera_name: str):
    camera_name = camera_name.strip()
    camera = database.scalar(
        select(Camera).where(
            Camera.branch_id == branch_id,
            Camera.name == camera_name
        )
    )

    if camera is None:
        camera = Camera(
            branch_id=branch_id,
            name=camera_name,
            active=True,
            last_seen_at=datetime.now(timezone.utc)
        )
        database.add(camera)
        try:
            database.commit()
            database.refresh(camera)
        except IntegrityError:
            database.rollback()
            camera = database.scalar(
                select(Camera).where(
                    Camera.branch_id == branch_id,
                    Camera.name == camera_name
                )
            )

    if camera is None:
        raise HTTPException(status_code=500, detail="No se pudo registrar la camara")
    if not camera.active:
        raise HTTPException(status_code=403, detail="La camara esta inactiva")

    camera.last_seen_at = datetime.now(timezone.utc)
    database.commit()
    database.refresh(camera)
    return camera


@app.get("/", response_model=HealthResponse)
def root():
    return {"status": "ok", "service": settings.APP_NAME, "database": "PostgreSQL"}


@app.get(f"{settings.API_PREFIX}/health", response_model=HealthResponse)
def health(database: Session = Depends(get_database)):
    try:
        database.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Base de datos no disponible: {error}"
        ) from error
    return {"status": "ok", "service": settings.APP_NAME, "database": "PostgreSQL"}


@app.post(
    f"{settings.API_PREFIX}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_token)]
)
def create_branch(payload: BranchCreate, database: Session = Depends(get_database)):
    if database.get(Branch, payload.id) is not None:
        raise HTTPException(status_code=409, detail="La sucursal ya existe")

    branch = Branch(
        id=payload.id,
        name=payload.name.strip(),
        address=payload.address.strip() if payload.address else None,
        active=payload.active
    )
    database.add(branch)
    try:
        database.commit()
        database.refresh(branch)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la sucursal") from error
    return branch


@app.get(
    f"{settings.API_PREFIX}/branches",
    response_model=list[BranchResponse],
    dependencies=[Depends(verify_api_token)]
)
def list_branches(database: Session = Depends(get_database)):
    return database.scalars(select(Branch).order_by(Branch.id.asc())).all()


@app.post(
    f"{settings.API_PREFIX}/cameras",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_token)]
)
def create_camera(payload: CameraCreate, database: Session = Depends(get_database)):
    branch = database.get(Branch, payload.branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="La sucursal no existe")

    existing = database.scalar(
        select(Camera).where(
            Camera.branch_id == payload.branch_id,
            Camera.name == payload.name.strip()
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="La camara ya existe en esta sucursal")

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
        raise HTTPException(status_code=409, detail="No se pudo crear la camara") from error
    return camera


@app.get(
    f"{settings.API_PREFIX}/cameras",
    response_model=list[CameraResponse],
    dependencies=[Depends(verify_api_token)]
)
def list_cameras(
    branch_id: int | None = Query(default=None, gt=0),
    database: Session = Depends(get_database)
):
    query = select(Camera)
    if branch_id is not None:
        query = query.where(Camera.branch_id == branch_id)
    return database.scalars(
        query.order_by(Camera.branch_id.asc(), Camera.id.asc())
    ).all()


# La identidad del cliente V3 tiene prioridad sobre branch_id/camera_name del payload.
from app.machine import resolve_machine_auth


@app.post(
    f"{settings.API_PREFIX}/count-events",
    response_model=CountEventResponse,
    status_code=status.HTTP_201_CREATED
)
def create_count_event(
    payload: CountEventCreate,
    machine_client=Depends(resolve_machine_auth),
    database: Session = Depends(get_database)
):
    event_uuid = str(payload.event_uuid)
    existing = database.scalar(
        select(CountEvent).where(CountEvent.event_uuid == event_uuid)
    )
    if existing is not None:
        return event_to_response(existing, duplicate=True)

    if machine_client is not None:
        branch_id = machine_client.branch_id
        camera = database.get(Camera, machine_client.camera_id)
        if camera is None or not camera.active:
            raise HTTPException(status_code=403, detail="Camara del cliente no disponible")
        if not machine_client.branch.active:
            raise HTTPException(status_code=403, detail="Sucursal del cliente inactiva")
        camera.last_seen_at = datetime.now(timezone.utc)
    else:
        # Compatibilidad con cliente V2 durante la migracion.
        branch_id = payload.branch_id
        get_or_create_branch(database, branch_id)
        camera = get_or_create_camera(database, branch_id, payload.camera_name)

    event = CountEvent(
        event_uuid=event_uuid,
        branch_id=branch_id,
        camera_id=camera.id,
        track_id=payload.track_id,
        event_type=payload.event_type,
        occurred_at=payload.occurred_at
    )
    database.add(event)

    try:
        database.commit()
        database.refresh(event)
    except IntegrityError:
        database.rollback()
        existing = database.scalar(
            select(CountEvent).where(CountEvent.event_uuid == event_uuid)
        )
        if existing is not None:
            return event_to_response(existing, duplicate=True)
        raise HTTPException(status_code=409, detail="No se pudo registrar el evento")

    print(
        "[API] Evento recibido: "
        f"{event.event_type} | Sucursal={event.branch_id} | "
        f"Camara={camera.name} | Track={event.track_id} | UUID={event.event_uuid}"
    )
    return event_to_response(event)


@app.get(
    f"{settings.API_PREFIX}/count-events",
    response_model=list[CountEventResponse],
    dependencies=[Depends(verify_api_token)]
)
def list_count_events(
    branch_id: int | None = Query(default=None, gt=0),
    camera_name: str | None = Query(default=None),
    event_type: str | None = Query(default=None, pattern="^(IN|OUT)$"),
    limit: int = Query(default=100, ge=1, le=500),
    database: Session = Depends(get_database)
):
    query = select(CountEvent).join(Camera)
    if branch_id is not None:
        query = query.where(CountEvent.branch_id == branch_id)
    if camera_name:
        query = query.where(Camera.name == camera_name.strip())
    if event_type:
        query = query.where(CountEvent.event_type == event_type)
    query = query.order_by(CountEvent.id.desc()).limit(limit)
    return [event_to_response(event) for event in database.scalars(query).all()]


@app.get(
    f"{settings.API_PREFIX}/summary",
    response_model=CountSummary,
    dependencies=[Depends(verify_api_token)]
)
def count_summary(
    branch_id: int = Query(gt=0),
    camera_name: str | None = Query(default=None),
    database: Session = Depends(get_database)
):
    query_base = select(func.count(CountEvent.id)).join(Camera).where(
        CountEvent.branch_id == branch_id
    )
    if camera_name:
        query_base = query_base.where(Camera.name == camera_name.strip())

    entries = database.scalar(query_base.where(CountEvent.event_type == "IN")) or 0
    exits = database.scalar(query_base.where(CountEvent.event_type == "OUT")) or 0
    return {
        "branch_id": branch_id,
        "camera_name": camera_name.strip() if camera_name else None,
        "entries": int(entries),
        "exits": int(exits),
        "inside": max(0, int(entries) - int(exits))
    }


from app.admin import router as admin_router
from app.auth import router as auth_router
from app.dashboard import router as dashboard_router
from app.machine import router as machine_router
from app.reports import router as reports_router
from app.security import WebAuthMiddleware

app.add_middleware(WebAuthMiddleware)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
app.include_router(machine_router)
app.include_router(reports_router)
