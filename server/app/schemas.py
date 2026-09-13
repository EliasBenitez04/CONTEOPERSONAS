from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CountEventCreate(BaseModel):
    event_uuid: UUID
    branch_id: int = Field(gt=0)
    camera_name: str = Field(min_length=1, max_length=100)
    track_id: int | None = None
    event_type: Literal["IN", "OUT"]
    occurred_at: datetime


class CountEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_uuid: str
    branch_id: int
    camera_name: str
    track_id: int | None
    event_type: str
    occurred_at: datetime
    received_at: datetime
    duplicate: bool = False


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class CountSummary(BaseModel):
    branch_id: int
    camera_name: str | None
    entries: int
    exits: int
    inside: int
