# CONTEOPERSONAS V3

Sistema distribuido para conteo de personas por cámaras RTSP, diseñado para múltiples sucursales con operación offline y servidor central.

## Arquitectura

```text
CAMARA RTSP -> CLIENTE PYTHON/YOLO -> SQLite local
                                  -> HTTPS/API CENTRAL
                                  -> PostgreSQL
                                  -> Dashboard / Reportes
```

Cada instalación V3 usa un `CLIENT_ID` y `CLIENT_TOKEN` propio. El servidor asocia ese cliente a una sucursal/cámara y controla remotamente línea, sentido IN/OUT, margen y confianza YOLO.

## Funcionalidades

- YOLO + tracker local e IDs inmediatos.
- Conteo IN / OUT.
- SQLite offline con reintento automático.
- PostgreSQL central.
- FastAPI.
- Dashboard ejecutivo en tiempo real.
- Cámaras ONLINE/OFFLINE.
- Telemetría de clientes, versión, pendientes y errores.
- CRUD sucursales/cámaras.
- Registro seguro de clientes por token individual.
- Configuración remota.
- Reportes por rango/sucursal/cámara, tendencias diaria/semanal/mensual y CSV.
- Promedios, día/hora pico y ranking de sucursales.
- Login, usuarios y roles ADMIN/SUPERVISOR/VIEWER.
- Auditoría.
- Backups PostgreSQL, restauración y retención.
- Autoinicio/watchdog en Windows.
- Logs persistentes.
- Plantilla HTTPS con Caddy.
- Empaquetado PyInstaller e instalador `SetupContePersonas.exe`.

## Servidor

```powershell
cd server
.\start_server.bat
```

Accesos locales:

- Login: `http://127.0.0.1:8000/login`
- Dashboard: `http://127.0.0.1:8000/dashboard`
- Sucursales: `http://127.0.0.1:8000/admin/branches`
- Cámaras: `http://127.0.0.1:8000/admin/cameras`
- Clientes: `http://127.0.0.1:8000/admin/clients`
- Reportes: `http://127.0.0.1:8000/reports`
- Usuarios: `http://127.0.0.1:8000/users`
- Auditoría: `http://127.0.0.1:8000/admin/audit`

PostgreSQL se prepara automáticamente mediante `app.setup_database`.

## Cliente desde código fuente

Primera preparación:

```powershell
cd client
.\setup_client.bat
```

Configurar `client/.env` usando `.env.example`.

Ejecutar:

```powershell
.\run_client.bat
```

El cliente escribe en `client/logs/client.log` y conserva SQLite en `client/data/local.db`.

## Convertir un cliente a V3 administrado

1. Crear/confirmar sucursal y cámara.
2. Entrar a `/admin/clients`.
3. Registrar cliente para esa cámara.
4. Copiar el `CLIENT_ID` y `CLIENT_TOKEN` mostrados una sola vez.
5. Colocarlos en `client/.env` junto a la URL central.
6. Reiniciar el cliente.
7. Confirmar ONLINE, versión y pendientes en Dashboard/Clientes.

## Multi-sucursal

En PCs remotas usar una URL real del servidor, nunca `127.0.0.1`:

```env
API_URL=https://conteo.midominio.com/api
CLIENT_ID=...
CLIENT_TOKEN=...
```

El servidor ignora `BRANCH_ID`/`CAMERA_NAME` declarados por un cliente V3 y utiliza la asociación registrada centralmente.

## Automatización Windows

Cliente:

```powershell
client\install_autostart.bat
```

Servidor y backup diario (ejecutar como Administrador):

```powershell
server\scripts\install_server_autostart.bat
server\scripts\install_backup_task.bat
```

Los procesos automatizados incluyen watchdog para reiniciarse después de un fallo.

## Backups

Manual:

```powershell
server\scripts\backup_postgres.bat
```

Restaurar:

```powershell
server\scripts\restore_postgres.bat "C:\ruta\contepersonas_fecha.backup"
```

## Producción / HTTPS

Ver `deploy/PRODUCCION.md` y `deploy/Caddyfile.example`.

En producción:
- usar HTTPS;
- `SESSION_COOKIE_SECURE=1`;
- cambiar `SESSION_SECRET`;
- `ENABLE_DOCS=0`;
- restringir `TRUSTED_HOSTS`;
- no exponer PostgreSQL a Internet;
- usar un token distinto por cliente;
- el heartbeat V2 queda deshabilitado y los conteos V3 requieren identidad individual.

## Ejecutable e instalador

Generar solamente el cliente compilado:

```powershell
client\build_client.bat
```

Genera `client/dist/ContePersonas`.

Para generar el instalador completo es necesario tener Inno Setup 6 instalado:

```powershell
client\build_installer.bat
```

Salida:

```text
client\dist\installer\SetupContePersonas.exe
```

El instalador crea `.env` solo si todavía no existe, conserva configuración/SQLite en actualizaciones y puede habilitar autoinicio con watchdog.
