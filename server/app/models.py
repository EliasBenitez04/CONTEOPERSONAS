from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'SUPERVISOR', 'VIEWER')",
            name="ck_users_role"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    username: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
        index=True
    )

    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="VIEWER"
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=False
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )

    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    cameras: Mapped[list["Camera"]] = relationship(
        back_populates="branch"
    )

    events: Mapped[list["CountEvent"]] = relationship(
        back_populates="branch"
    )


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "name",
            name="uq_cameras_branch_name"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    branch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    branch: Mapped[Branch] = relationship(
        back_populates="cameras"
    )

    events: Mapped[list["CountEvent"]] = relationship(
        back_populates="camera"
    )


class CountEvent(Base):
    __tablename__ = "count_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('IN', 'OUT')",
            name="ck_count_events_event_type"
        ),
    )

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
        ForeignKey("branches.id"),
        nullable=False,
        index=True
    )

    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id"),
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

    branch: Mapped[Branch] = relationship(
        back_populates="events"
    )

    camera: Mapped[Camera] = relationship(
        back_populates="events"
    )


Index(
    "idx_count_events_branch_camera_date",
    CountEvent.branch_id,
    CountEvent.camera_id,
    CountEvent.occurred_at
)
