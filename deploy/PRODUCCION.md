# SISTEMA CAMARA - Produccion V3

## Servidor central

1. Ejecutar `server/start_server.bat` una vez para preparar `.venv`, PostgreSQL y tablas.
2. Cambiar `server/.env` a valores de produccion:

```env
ENVIRONMENT=production
PUBLIC_BASE_URL=https://conteo.midominio.com
ENABLE_DOCS=0
SESSION_COOKIE_SECURE=1
TRUSTED_HOSTS=conteo.midominio.com,127.0.0.1
SESSION_SECRET=UNA_CADENA_LARGA_ALEATORIA
PG_PASSWORD=CLAVE_REAL_POSTGRES
BACKUP_RETENTION_DAYS=30
```

3. Instalar HTTPS con Caddy usando `deploy/Caddyfile.example` como referencia.
4. Ejecutar como Administrador:
   - `server/scripts/install_server_autostart.bat`
   - `server/scripts/install_backup_task.bat`

## Alta de una sucursal/camara

1. Crear sucursal desde `/admin/branches`.
2. Crear camara desde `/admin/cameras`.
3. Ir a `/admin/clients` y registrar un cliente para esa camara.
4. Copiar `CLIENT_ID` y `CLIENT_TOKEN` mostrados una sola vez.

## PC de la sucursal

1. Copiar el proyecto cliente.
2. Ejecutar `client/setup_client.bat`.
3. Completar `client/.env`:

```env
CAMERA_RTSP_URL=rtsp://usuario:clave@IP_CAMARA:554/stream1
API_URL=https://conteo.midominio.com/api
CLIENT_ID=UUID_GENERADO_EN_SERVIDOR
CLIENT_TOKEN=TOKEN_GENERADO_EN_SERVIDOR
```

4. Ejecutar `client/run_client.bat`.
5. Confirmar en `/admin/clients` que aparece ONLINE, version y pendientes = 0.
6. Ejecutar `client/install_autostart.bat` como Administrador para iniciar al entrar a Windows.

## Configuracion remota

Desde `/admin/clients` el administrador puede cambiar:
- linea x1/y1/x2/y2;
- lado IN (+1/-1);
- margen;
- confianza YOLO.

El cliente consulta la configuracion periodicamente y la aplica sin reiniciar.

## Backups

`server/scripts/backup_postgres.bat` genera backups formato custom de PostgreSQL en `server/backups`.
La tarea diaria se instala con `install_backup_task.bat` y aplica retencion por `BACKUP_RETENTION_DAYS`.

## Seguridad

- No subir `.env` reales a Git.
- Cada PC debe usar su propio `CLIENT_ID` y `CLIENT_TOKEN`.
- Rotar el token desde `/admin/clients` si una PC se reemplaza o compromete.
- Usar HTTPS antes de conectar sucursales por Internet.
- Desactivar Swagger (`ENABLE_DOCS=0`) en produccion.
- Cambiar `SESSION_SECRET`, PostgreSQL y contraseña inicial del administrador.

## Puertos

- FastAPI interno: TCP 8000, preferentemente solo local al servidor.
- HTTPS publico: TCP 443.
- HTTP 80: solo para redireccion/certificado HTTPS.
- PostgreSQL 5432 no debe exponerse a Internet.
