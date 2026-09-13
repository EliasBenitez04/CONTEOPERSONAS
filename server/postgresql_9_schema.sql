-- SISTEMA CAMARA - ESQUEMA CENTRAL POSTGRESQL 9.x
-- Este archivo es de referencia/manual.
-- start_server.bat crea la base y las tablas automaticamente.

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    full_name VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'VIEWER',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT ck_users_role
        CHECK (role IN ('ADMIN', 'SUPERVISOR', 'VIEWER'))
);

CREATE TABLE branches (
    id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    address VARCHAR(255),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cameras (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    name VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cameras_branch_name UNIQUE (branch_id, name)
);

CREATE TABLE count_events (
    id SERIAL PRIMARY KEY,
    event_uuid VARCHAR(36) NOT NULL UNIQUE,
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    camera_id INTEGER NOT NULL REFERENCES cameras(id),
    track_id INTEGER,
    event_type VARCHAR(3) NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_count_events_event_type
        CHECK (event_type IN ('IN', 'OUT'))
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_cameras_branch_id ON cameras(branch_id);
CREATE INDEX idx_count_events_event_uuid ON count_events(event_uuid);
CREATE INDEX idx_count_events_branch_id ON count_events(branch_id);
CREATE INDEX idx_count_events_camera_id ON count_events(camera_id);
CREATE INDEX idx_count_events_event_type ON count_events(event_type);
CREATE INDEX idx_count_events_occurred_at ON count_events(occurred_at);
CREATE INDEX idx_count_events_branch_camera_date
    ON count_events(branch_id, camera_id, occurred_at);
