from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_database
from app.models import Branch, Camera, ClientDevice, CountEvent


router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
LOCAL_TIMEZONE = ZoneInfo("America/Asuncion")
CAMERA_ONLINE_SECONDS = 45
CLIENT_ONLINE_SECONDS = 60


class CameraHeartbeat(BaseModel):
    branch_id: int = Field(gt=0)
    camera_name: str = Field(min_length=1, max_length=100)


def _get_or_create_branch(database: Session, branch_id: int):
    branch = database.get(Branch, branch_id)
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
            branch = database.get(Branch, branch_id)
    return branch


def _get_or_create_camera(database: Session, branch_id: int, camera_name: str):
    camera_name = camera_name.strip()
    camera = database.scalar(
        select(Camera).where(
            Camera.branch_id == branch_id,
            Camera.name == camera_name
        )
    )
    if camera is None:
        camera = Camera(branch_id=branch_id, name=camera_name, active=True)
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
    return camera


def _today_bounds_utc():
    now_local = datetime.now(LOCAL_TIMEZONE)
    start_local = now_local.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
        now_local
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    database: Session = Depends(get_database)
):
    branches = database.scalars(
        select(Branch)
        .where(Branch.active.is_(True))
        .order_by(Branch.id.asc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "branches": branches,
            "user": request.state.user
        }
    )


# Heartbeat V2 mantenido durante la migracion.
@router.post("/api/cameras/heartbeat")
def camera_heartbeat(
    payload: CameraHeartbeat,
    database: Session = Depends(get_database)
):
    branch = _get_or_create_branch(database, payload.branch_id)
    if branch is None or not branch.active:
        raise HTTPException(status_code=403, detail="Sucursal inexistente o inactiva")

    camera = _get_or_create_camera(
        database, payload.branch_id, payload.camera_name
    )
    if camera is None or not camera.active:
        raise HTTPException(status_code=403, detail="Camara inexistente o inactiva")

    camera.last_seen_at = datetime.now(timezone.utc)
    database.commit()
    return {
        "status": "ok",
        "branch_id": payload.branch_id,
        "camera_name": payload.camera_name.strip()
    }


@router.get("/api/dashboard-data")
def dashboard_data(
    branch_id: int | None = Query(default=None, gt=0),
    database: Session = Depends(get_database)
):
    start_utc, end_utc, now_local = _today_bounds_utc()
    now_utc = datetime.now(timezone.utc)

    event_query = (
        select(CountEvent)
        .options(
            selectinload(CountEvent.camera),
            selectinload(CountEvent.branch)
        )
        .where(
            CountEvent.occurred_at >= start_utc,
            CountEvent.occurred_at < end_utc
        )
    )
    if branch_id is not None:
        event_query = event_query.where(CountEvent.branch_id == branch_id)

    events = database.scalars(
        event_query.order_by(CountEvent.occurred_at.asc())
    ).all()

    entries = sum(1 for event in events if event.event_type == "IN")
    exits = sum(1 for event in events if event.event_type == "OUT")

    hourly_in = [0] * 24
    hourly_out = [0] * 24
    branch_activity = {}

    for event in events:
        occurred_at = event.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        hour = occurred_at.astimezone(LOCAL_TIMEZONE).hour

        if event.event_type == "IN":
            hourly_in[hour] += 1
        else:
            hourly_out[hour] += 1

        row = branch_activity.setdefault(
            event.branch_id,
            {"name": event.branch.name, "entries": 0, "exits": 0}
        )
        if event.event_type == "IN":
            row["entries"] += 1
        else:
            row["exits"] += 1

    traffic_per_hour = [
        hourly_in[index] + hourly_out[index]
        for index in range(24)
    ]
    peak_hour = max(range(24), key=lambda h: traffic_per_hour[h]) if events else None

    busiest = None
    if branch_activity:
        branch_id_peak, row = max(
            branch_activity.items(),
            key=lambda item: item[1]["entries"] + item[1]["exits"]
        )
        busiest = {
            "branch_id": branch_id_peak,
            "branch_name": row["name"],
            "entries": row["entries"],
            "exits": row["exits"],
            "traffic": row["entries"] + row["exits"]
        }

    camera_query = (
        select(Camera)
        .options(selectinload(Camera.branch))
        .where(Camera.active.is_(True))
        .order_by(Camera.branch_id.asc(), Camera.name.asc())
    )
    if branch_id is not None:
        camera_query = camera_query.where(Camera.branch_id == branch_id)
    cameras = database.scalars(camera_query).all()

    camera_rows = []
    online_count = 0
    for camera in cameras:
        last_seen = camera.last_seen_at
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        online = bool(
            last_seen
            and (now_utc - last_seen).total_seconds() <= CAMERA_ONLINE_SECONDS
        )
        online_count += int(online)
        camera_rows.append({
            "id": camera.id,
            "branch_id": camera.branch_id,
            "branch_name": camera.branch.name,
            "name": camera.name,
            "online": online,
            "last_seen_at": (
                last_seen.astimezone(LOCAL_TIMEZONE).isoformat()
                if last_seen else None
            )
        })

    client_query = (
        select(ClientDevice)
        .options(
            selectinload(ClientDevice.branch),
            selectinload(ClientDevice.camera)
        )
        .where(ClientDevice.active.is_(True))
        .order_by(ClientDevice.branch_id.asc(), ClientDevice.id.asc())
    )
    if branch_id is not None:
        client_query = client_query.where(ClientDevice.branch_id == branch_id)
    clients = database.scalars(client_query).all()

    clients_online = 0
    pending_total = 0
    clients_with_errors = 0
    client_rows = []
    for client in clients:
        last_seen = client.last_seen_at
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        online = bool(
            last_seen
            and (now_utc - last_seen).total_seconds() <= CLIENT_ONLINE_SECONDS
        )
        clients_online += int(online)
        pending_total += int(client.pending_events or 0)
        clients_with_errors += int(bool(client.last_error))
        client_rows.append({
            "client_id": client.client_id,
            "branch_name": client.branch.name,
            "camera_name": client.camera.name,
            "online": online,
            "app_version": client.app_version,
            "pending_events": client.pending_events,
            "last_error": client.last_error,
            "last_seen_at": (
                last_seen.astimezone(LOCAL_TIMEZONE).isoformat()
                if last_seen else None
            )
        })

    recent_events = []
    for event in reversed(events[-15:]):
        occurred_at = event.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        recent_events.append({
            "id": event.id,
            "branch_id": event.branch_id,
            "branch_name": event.branch.name,
            "camera_name": event.camera.name,
            "track_id": event.track_id,
            "event_type": event.event_type,
            "occurred_at": occurred_at.astimezone(LOCAL_TIMEZONE).isoformat()
        })

    return {
        "date": now_local.date().isoformat(),
        "updated_at": now_local.isoformat(),
        "branch_id": branch_id,
        "totals": {
            "entries": entries,
            "exits": exits,
            "inside": max(0, entries - exits),
            "cameras": len(cameras),
            "cameras_online": online_count,
            "cameras_offline": max(0, len(cameras) - online_count),
            "clients": len(clients),
            "clients_online": clients_online,
            "pending_events": pending_total,
            "clients_with_errors": clients_with_errors
        },
        "insights": {
            "peak_hour": (
                f"{peak_hour:02d}:00 - {(peak_hour + 1) % 24:02d}:00"
                if peak_hour is not None else None
            ),
            "peak_hour_traffic": (
                traffic_per_hour[peak_hour]
                if peak_hour is not None else 0
            ),
            "busiest_branch": busiest
        },
        "hourly": {
            "labels": [f"{hour:02d}:00" for hour in range(24)],
            "in": hourly_in,
            "out": hourly_out
        },
        "cameras": camera_rows,
        "clients": client_rows,
        "recent_events": recent_events
    }
