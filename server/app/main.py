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
    version="2.2.0",
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


def event_to_response(
    event: CountEvent,
    duplicate: bool = False
):
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


def get_or_create_branch(
    database: Session,
    branch_id: int
):
    branch = database.get(
        Branch,
        branch_id
    )

    if branch is None:
        branch = Branch(
            id=branch_id,
            name=f"SUCURSAL_{branch_id}",
            active=True
        )

        database.add(branch)

        try:
            database.commit()
            database.refresh(branch)
        except IntegrityError:
            database.rollback()
            branch = database.get(
                Branch,
                branch_id
            )

    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la sucursal"
        )

    if not branch.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La sucursal esta inactiva"
        )

    return branch


def get_or_create_camera(
    database: Session,
    branch_id: int,
    camera_name: str
):
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la camara"
        )

    if not camera.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La camara esta inactiva"
        )

    camera.last_seen_at = datetime.now(timezone.utc)
    database.commit()
    database.refresh(camera)

    return camera


@app.get(
    "/",
    response_model=HealthResponse
)
def root():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "database": "PostgreSQL"
    }


@app.get(
    f"{settings.API_PREFIX}/health",
    response_model=HealthResponse
)
def health(
    database: Session = Depends(get_database)
):
    try:
        database.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Base de datos no disponible: {error}"
        ) from error

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "database": "PostgreSQL"
    }


@app.post(
    f"{settings.API_PREFIX}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_token)]
)
def create_branch(
    payload: BranchCreate,
    database: Session = Depends(get_database)
):
    existing = database.get(
        Branch,
        payload.id
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La sucursal ya existe"
        )

    branch = Branch(
        id=payload.id,
        name=payload.name.strip(),
        address=(
            payload.address.strip()
            if payload.address
            else None
        ),
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

    return branch


@app.get(
    f"{settings.API_PREFIX}/branches",
    response_model=list[BranchResponse],
    dependencies=[Depends(verify_api_token)]
)
def list_branches(
    database: Session = Depends(get_database)
):
    return database.scalars(
        select(Branch).order_by(
            Branch.id.asc()
        )
    ).all()


@app.post(
    f"{settings.API_PREFIX}/cameras",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_token)]
)
def create_camera(
    payload: CameraCreate,
    database: Session = Depends(get_database)
):
    branch = database.get(
        Branch,
        payload.branch_id
    )

    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sucursal no existe"
        )

    existing = database.scalar(
        select(Camera).where(
            Camera.branch_id == payload.branch_id,
            Camera.name == payload.name.strip()
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La camara ya existe en esta sucursal"
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
            detail="No se pudo crear la camara"
        ) from error

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
        query = query.where(
            Camera.branch_id == branch_id
        )

    query = query.order_by(
        Camera.branch_id.asc(),
        Camera.id.asc()
    )

    return database.scalars(query).all()


@app.post(
    f"{settings.API_PREFIX}/count-events",
    response_model=CountEventResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_token)]
)
def create_count_event(
    payload: CountEventCreate,
    database: Session = Depends(get_database)
):
    event_uuid = str(payload.event_uuid)

    existing = database.scalar(
        select(CountEvent).where(
            CountEvent.event_uuid == event_uuid
        )
    )

    if existing is not None:
        return event_to_response(
            existing,
            duplicate=True
        )

    get_or_create_branch(
        database,
        payload.branch_id
    )

    camera = get_or_create_camera(
        database,
        payload.branch_id,
        payload.camera_name
    )

    event = CountEvent(
        event_uuid=event_uuid,
        branch_id=payload.branch_id,
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
            select(CountEvent).where(
                CountEvent.event_uuid == event_uuid
            )
        )

        if existing is not None:
            return event_to_response(
                existing,
                duplicate=True
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo registrar el evento"
        )

    print(
        "[API] Evento recibido: "
        f"{event.event_type} | "
        f"Sucursal={event.branch_id} | "
        f"Camara={camera.name} | "
        f"Track={event.track_id} | "
        f"UUID={event.event_uuid}"
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
        query = query.where(
            CountEvent.branch_id == branch_id
        )

    if camera_name:
        query = query.where(
            Camera.name == camera_name.strip()
        )

    if event_type:
        query = query.where(
            CountEvent.event_type == event_type
        )

    query = query.order_by(
        CountEvent.id.desc()
    ).limit(limit)

    events = database.scalars(query).all()

    return [
        event_to_response(event)
        for event in events
    ]


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
        query_base = query_base.where(
            Camera.name == camera_name.strip()
        )

    entries = database.scalar(
        query_base.where(
            CountEvent.event_type == "IN"
        )
    ) or 0

    exits = database.scalar(
        query_base.where(
            CountEvent.event_type == "OUT"
        )
    ) or 0

    return {
        "branch_id": branch_id,
        "camera_name": camera_name.strip() if camera_name else None,
        "entries": int(entries),
        "exits": int(exits),
        "inside": max(0, int(entries) - int(exits))
    }


# Todas las capas web se registran en la app principal.
# De esta forma funcionan tanto con app.main:app como con app.web:app.
from app.admin import router as admin_router
from app.dashboard import router as dashboard_router
from app.reports import router as reports_router

app.include_router(dashboard_router)
app.include_router(admin_router)
app.include_router(reports_router)
