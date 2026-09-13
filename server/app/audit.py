from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_database
from app.models import AuditLog


router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/admin/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={"user": request.state.user}
    )


@router.get("/api/admin/audit")
def audit_data(
    limit: int = Query(default=300, ge=1, le=2000),
    database: Session = Depends(get_database)
):
    rows = database.scalars(
        select(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "username": row.username,
            "action": row.action,
            "method": row.method,
            "path": row.path,
            "status_code": row.status_code,
            "ip_address": row.ip_address,
            "details": row.details,
            "created_at": row.created_at.isoformat()
        }
        for row in rows
    ]
