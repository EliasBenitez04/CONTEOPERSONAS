from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="VIEWER")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    cameras: Mapped[list["Camera"]] = relationship(back_populates="branch")
    events: Mapped[list["CountEvent"]] = relationship(back_populates="branch")
    clients: Mapped[list["ClientDevice"]] = relationship(back_populates="branch")


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (
        UniqueConstraint("branch_id", "name", name="uq_cameras_branch_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("branches.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    branch: Mapped[Branch] = relationship(back_populates="cameras")
    events: Mapped[list["CountEvent"]] = relationship(back_populates="camera")
    client: Mapped["ClientDevice | None"] = relationship(
        back_populates="camera",
        uselist=False
    )


class ClientDevice(Base):
    __tablename__ = "client_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    branch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("branches.id"), nullable=False, index=True
    )
    camera_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cameras.id"), nullable=False, unique=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pending_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    branch: Mapped[Branch] = relationship(back_populates="clients")
    camera: Mapped[Camera] = relationship(back_populates="client")
    config: Mapped["ClientConfig | None"] = relationship(
        back_populates="client",
        uselist=False,
        cascade="all, delete-orphan"
    )


class ClientConfig(Base):
    __tablename__ = "client_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("client_devices.id"), nullable=False, unique=True, index=True
    )
    line_x1: Mapped[int] = mapped_column(Integer, nullable=False, default=640)
    line_y1: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    line_x2: Mapped[int] = mapped_column(Integer, nullable=False, default=640)
    line_y2: Mapped[int] = mapped_column(Integer, nullable=False, default=650)
    in_side: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    margin: Mapped[int] = mapped_column(Integer, nullable=False, default=18)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    client: Mapped[ClientDevice] = relationship(back_populates="config")


class CountEvent(Base):
    __tablename__ = "count_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('IN', 'OUT')",
            name="ck_count_events_event_type"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("branches.id"), nullable=False, index=True
    )
    camera_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cameras.id"), nullable=False, index=True
    )
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    branch: Mapped[Branch] = relationship(back_populates="events")
    camera: Mapped[Camera] = relationship(back_populates="events")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[str | None] = mapped_column(String(12), nullable=True)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )


Index(
    "idx_count_events_branch_camera_date",
    CountEvent.branch_id,
    CountEvent.camera_id,
    CountEvent.occurred_at
)
Index(
    "idx_client_devices_status",
    ClientDevice.active,
    ClientDevice.last_seen_at
)
Index(
    "idx_audit_logs_user_date",
    AuditLog.user_id,
    AuditLog.created_at
)
