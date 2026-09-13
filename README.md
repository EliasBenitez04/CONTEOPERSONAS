# CONTEOPERSONAS

Sistema distribuido para conteo de personas por camaras RTSP.

## Arquitectura

- `client/`: captura RTSP, YOLO, tracking, conteo IN/OUT, SQLite local y sincronizacion offline.
- `server/`: API central FastAPI para recibir, consultar y consolidar eventos.

## Ejecutar servidor central

Desde la raiz del proyecto:

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

El servidor queda disponible en:

- API: `http://127.0.0.1:8000`
- Salud: `http://127.0.0.1:8000/api/health`
- Swagger: `http://127.0.0.1:8000/docs`
- Eventos: `http://127.0.0.1:8000/api/count-events`

El servidor usa SQLite de forma predeterminada para desarrollo y crea automaticamente `server/data/server.db`.

Para PostgreSQL, copia `server/.env.example` a `server/.env` y cambia `DATABASE_URL`.

## Ejecutar cliente

En otra terminal:

```powershell
cd client
python -m app.main
```

El cliente guarda cada conteo primero en SQLite local. Luego intenta enviarlo a `POST /api/count-events`. Si el servidor esta fuera de linea, el evento permanece pendiente y se reintenta automaticamente.

## Endpoints principales

- `GET /api/health`
- `POST /api/count-events`
- `GET /api/count-events`
- `GET /api/summary?branch_id=1&camera_name=CAMARA_01`

`event_uuid` es unico en el servidor, por lo que los reintentos del cliente no generan eventos duplicados.
