from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CountEvent(Base):
    __tablename__ = "count_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    event_uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True
    )

    branch_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    camera_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )

    track_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    event_type: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        index=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


Index(
    "idx_count_events_branch_camera_date",
    CountEvent.branch_id,
    CountEvent.camera_name,
    CountEvent.occurred_at
)
