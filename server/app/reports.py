import csv
import io
from collections import OrderedDict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_database
from app.models import Branch, Camera, CountEvent


router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
LOCAL_TIMEZONE = ZoneInfo("America/Asuncion")


def _normalize_range(start_date: date, end_date: date):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha hasta no puede ser menor que la fecha desde"
        )
    if (end_date - start_date).days > 366:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El rango máximo permitido es de 366 días"
        )

    start_local = datetime.combine(start_date, time.min, tzinfo=LOCAL_TIMEZONE)
    end_local = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=LOCAL_TIMEZONE
    )
    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc)
    )


def _build_event_query(
    start_date: date,
    end_date: date,
    branch_id: int | None,
    camera_id: int | None,
    event_type: str | None
):
    start_utc, end_utc = _normalize_range(start_date, end_date)
    query = (
        select(CountEvent)
        .options(
            selectinload(CountEvent.branch),
            selectinload(CountEvent.camera)
        )
        .where(
            CountEvent.occurred_at >= start_utc,
            CountEvent.occurred_at < end_utc
        )
    )

    if branch_id is not None:
        query = query.where(CountEvent.branch_id == branch_id)
    if camera_id is not None:
        query = query.where(CountEvent.camera_id == camera_id)
    if event_type:
        normalized_type = event_type.upper().strip()
        if normalized_type not in ("IN", "OUT"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="event_type debe ser IN u OUT"
            )
        query = query.where(CountEvent.event_type == normalized_type)
    return query


def _local_datetime(value: datetime):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TIMEZONE)


def _empty_bucket():
    return {"in": 0, "out": 0}


def _append_event(bucket, event_type):
    if event_type == "IN":
        bucket["in"] += 1
    elif event_type == "OUT":
        bucket["out"] += 1


def _series(mapping: OrderedDict | dict):
    return {
        "labels": list(mapping.keys()),
        "in": [row["in"] for row in mapping.values()],
        "out": [row["out"] for row in mapping.values()]
    }


@router.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    database: Session = Depends(get_database)
):
    branches = database.scalars(
        select(Branch).order_by(Branch.id.asc())
    ).all()
    cameras = database.scalars(
        select(Camera).order_by(Camera.branch_id.asc(), Camera.name.asc())
    ).all()
    today = datetime.now(LOCAL_TIMEZONE).date()

    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={
            "user": request.state.user,
            "branches": branches,
            "cameras": cameras,
            "default_start": (today - timedelta(days=6)).isoformat(),
            "default_end": today.isoformat()
        }
    )


@router.get("/api/reports/data")
def reports_data(
    start_date: date = Query(),
    end_date: date = Query(),
    branch_id: int | None = Query(default=None, gt=0),
    camera_id: int | None = Query(default=None, gt=0),
    event_type: str | None = Query(default=None),
    detail_limit: int = Query(default=500, ge=1, le=2000),
    database: Session = Depends(get_database)
):
    query = _build_event_query(
        start_date, end_date, branch_id, camera_id, event_type
    )
    events = database.scalars(
        query.order_by(CountEvent.occurred_at.asc())
    ).all()

    entries = sum(1 for event in events if event.event_type == "IN")
    exits = sum(1 for event in events if event.event_type == "OUT")

    days = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)

    daily = OrderedDict(
        (day.isoformat(), _empty_bucket())
        for day in days
    )
    weekly: OrderedDict[str, dict] = OrderedDict()
    monthly: OrderedDict[str, dict] = OrderedDict()
    hourly = [_empty_bucket() for _ in range(24)]
    branch_totals: dict[int, dict] = {}

    for event in events:
        local_event = _local_datetime(event.occurred_at)
        day_key = local_event.date().isoformat()
        week_start = local_event.date() - timedelta(days=local_event.weekday())
        week_key = week_start.isoformat()
        month_key = local_event.strftime("%Y-%m")

        if day_key in daily:
            _append_event(daily[day_key], event.event_type)
        if week_key not in weekly:
            weekly[week_key] = _empty_bucket()
        if month_key not in monthly:
            monthly[month_key] = _empty_bucket()

        _append_event(weekly[week_key], event.event_type)
        _append_event(monthly[month_key], event.event_type)
        _append_event(hourly[local_event.hour], event.event_type)

        row = branch_totals.setdefault(
            event.branch_id,
            {
                "branch_id": event.branch_id,
                "branch_name": event.branch.name,
                "entries": 0,
                "exits": 0
            }
        )
        if event.event_type == "IN":
            row["entries"] += 1
        else:
            row["exits"] += 1

    branch_rows = []
    for row in branch_totals.values():
        row["inside"] = max(0, row["entries"] - row["exits"])
        row["traffic"] = row["entries"] + row["exits"]
        branch_rows.append(row)
    branch_rows.sort(key=lambda row: (-row["traffic"], row["branch_name"]))

    day_traffic = {
        key: value["in"] + value["out"]
        for key, value in daily.items()
    }
    peak_day = max(day_traffic, key=day_traffic.get) if events else None

    hour_traffic = [row["in"] + row["out"] for row in hourly]
    peak_hour = max(range(24), key=lambda h: hour_traffic[h]) if events else None

    days_count = max(1, len(days))
    total_traffic = entries + exits
    active_hours = max(1, sum(1 for value in hour_traffic if value > 0))

    detail_events = []
    for event in reversed(events[-detail_limit:]):
        local_event = _local_datetime(event.occurred_at)
        detail_events.append({
            "id": event.id,
            "date": local_event.date().isoformat(),
            "time": local_event.strftime("%H:%M:%S"),
            "branch_id": event.branch_id,
            "branch_name": event.branch.name,
            "camera_id": event.camera_id,
            "camera_name": event.camera.name,
            "track_id": event.track_id,
            "event_type": event.event_type,
            "occurred_at": local_event.isoformat()
        })

    return {
        "filters": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "branch_id": branch_id,
            "camera_id": camera_id,
            "event_type": event_type
        },
        "totals": {
            "entries": entries,
            "exits": exits,
            "inside": max(0, entries - exits),
            "events": len(events),
            "traffic": total_traffic
        },
        "insights": {
            "average_daily_traffic": round(total_traffic / days_count, 2),
            "average_daily_entries": round(entries / days_count, 2),
            "average_daily_exits": round(exits / days_count, 2),
            "average_active_hour_traffic": round(total_traffic / active_hours, 2),
            "peak_day": peak_day,
            "peak_day_traffic": day_traffic.get(peak_day, 0) if peak_day else 0,
            "peak_hour": (
                f"{peak_hour:02d}:00 - {(peak_hour + 1) % 24:02d}:00"
                if peak_hour is not None else None
            ),
            "peak_hour_traffic": hour_traffic[peak_hour] if peak_hour is not None else 0,
            "busiest_branch": branch_rows[0] if branch_rows else None
        },
        "daily": _series(daily),
        "weekly": _series(weekly),
        "monthly": _series(monthly),
        "hourly": {
            "labels": [f"{hour:02d}:00" for hour in range(24)],
            "in": [row["in"] for row in hourly],
            "out": [row["out"] for row in hourly]
        },
        "branches": branch_rows,
        "detail": detail_events,
        "detail_truncated": len(events) > detail_limit
    }


@router.get("/api/reports/export.csv")
def export_reports_csv(
    start_date: date = Query(),
    end_date: date = Query(),
    branch_id: int | None = Query(default=None, gt=0),
    camera_id: int | None = Query(default=None, gt=0),
    event_type: str | None = Query(default=None),
    database: Session = Depends(get_database)
):
    query = _build_event_query(
        start_date, end_date, branch_id, camera_id, event_type
    )
    events = database.scalars(
        query.order_by(CountEvent.occurred_at.asc())
    ).all()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "ID", "Fecha", "Hora", "Sucursal", "Camara",
        "Tipo", "Track ID", "UUID"
    ])

    for event in events:
        local_event = _local_datetime(event.occurred_at)
        writer.writerow([
            event.id,
            local_event.strftime("%d/%m/%Y"),
            local_event.strftime("%H:%M:%S"),
            event.branch.name,
            event.camera.name,
            event.event_type,
            event.track_id if event.track_id is not None else "",
            event.event_uuid
        ])

    filename = (
        f"reporte_conteo_{start_date.isoformat()}_"
        f"{end_date.isoformat()}.csv"
    )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
