from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_database
from app.models import CountEvent
from app.schemas import (
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
    version="1.0.0",
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
        camera_name=event.camera_name,
        track_id=event.track_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        received_at=event.received_at,
        duplicate=duplicate
    )


@app.get(
    "/",
    response_model=HealthResponse
)
def root():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "database": "connected"
    }


@app.get(
    f"{settings.API_PREFIX}/health",
    response_model=HealthResponse
)
def health(
    database: Session = Depends(get_database)
):
    try:
        database.execute(select(1))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Base de datos no disponible: {error}"
        ) from error

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "database": "connected"
    }


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

    event = CountEvent(
        event_uuid=event_uuid,
        branch_id=payload.branch_id,
        camera_name=payload.camera_name.strip(),
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
        f"Camara={event.camera_name} | "
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
    query = select(CountEvent)

    if branch_id is not None:
        query = query.where(
            CountEvent.branch_id == branch_id
        )

    if camera_name:
        query = query.where(
            CountEvent.camera_name == camera_name.strip()
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
    filters = [
        CountEvent.branch_id == branch_id
    ]

    if camera_name:
        filters.append(
            CountEvent.camera_name == camera_name.strip()
        )

    entries = database.scalar(
        select(func.count(CountEvent.id)).where(
            *filters,
            CountEvent.event_type == "IN"
        )
    ) or 0

    exits = database.scalar(
        select(func.count(CountEvent.id)).where(
            *filters,
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
