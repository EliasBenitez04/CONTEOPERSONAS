-- SISTEMA CAMARA - ESQUEMA CENTRAL POSTGRESQL 9.x
-- Referencia manual. start_server.bat crea las tablas automaticamente.

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
    CONSTRAINT ck_users_role CHECK (role IN ('ADMIN','SUPERVISOR','VIEWER'))
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

CREATE TABLE client_devices (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(64) NOT NULL UNIQUE,
    token_hash VARCHAR(64) NOT NULL,
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    camera_id INTEGER NOT NULL UNIQUE REFERENCES cameras(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    app_version VARCHAR(40),
    pending_events INTEGER NOT NULL DEFAULT 0,
    last_error VARCHAR(500),
    last_ip VARCHAR(64),
    last_seen_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE client_configs (
    id SERIAL PRIMARY KEY,
    client_device_id INTEGER NOT NULL UNIQUE REFERENCES client_devices(id),
    line_x1 INTEGER NOT NULL DEFAULT 640,
    line_y1 INTEGER NOT NULL DEFAULT 100,
    line_x2 INTEGER NOT NULL DEFAULT 640,
    line_y2 INTEGER NOT NULL DEFAULT 650,
    line_points TEXT,
    in_side INTEGER NOT NULL DEFAULT 1,
    margin INTEGER NOT NULL DEFAULT 18,
    confidence INTEGER NOT NULL DEFAULT 22,
    config_version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    CONSTRAINT ck_count_events_event_type CHECK (event_type IN ('IN','OUT'))
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(80),
    action VARCHAR(120) NOT NULL,
    method VARCHAR(12),
    path VARCHAR(255),
    status_code INTEGER,
    ip_address VARCHAR(64),
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_cameras_branch_id ON cameras(branch_id);
CREATE INDEX idx_client_devices_client_id ON client_devices(client_id);
CREATE INDEX idx_client_devices_branch_id ON client_devices(branch_id);
CREATE INDEX idx_client_devices_camera_id ON client_devices(camera_id);
CREATE INDEX idx_client_configs_client_device_id ON client_configs(client_device_id);
CREATE INDEX idx_count_events_event_uuid ON count_events(event_uuid);
CREATE INDEX idx_count_events_branch_id ON count_events(branch_id);
CREATE INDEX idx_count_events_camera_id ON count_events(camera_id);
CREATE INDEX idx_count_events_event_type ON count_events(event_type);
CREATE INDEX idx_count_events_occurred_at ON count_events(occurred_at);
CREATE INDEX idx_count_events_branch_camera_date ON count_events(branch_id, camera_id, occurred_at);
CREATE INDEX idx_audit_logs_user_date ON audit_logs(user_id, created_at);
