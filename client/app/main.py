import math

import cv2

from app.camera.rtsp import RTSPCamera
from app.config.settings import settings, ENV_FILE
from app.config.camera_config import (
    get_line_points,
    load_camera_config,
    normalize_camera_config,
    save_camera_config
)
from app.gui.line_config import LineConfigurator, fit_main_window
from app.gui.tray import TrayController
from app.detection.detector import PersonDetector
from app.detection.counter import LineCounter
from app.database.database import LocalDatabase, AsyncEventWriter
from app.database.models import CountEvent
from app.api.client import APIClient
from app.api.sync import EventSynchronizer


WINDOW_TITLE = "ContePersonas - Sistema Camara"


def representative_segment(points):
    best = None
    best_length = -1.0

    for index in range(len(points) - 1):
        p1 = points[index]
        p2 = points[index + 1]
        length = math.hypot(
            p2[0] - p1[0],
            p2[1] - p1[1]
        )
        if length > best_length:
            best_length = length
            best = (p1, p2)

    return best


def direction_positions(p1, p2, offset=58):
    x1, y1 = p1
    x2, y2 = p2
    mid_x = (x1 + x2) / 2.0
    mid_y = (y1 + y2) / 2.0
    dx = x2 - x1
    dy = y2 - y1
    length = max(1.0, math.hypot(dx, dy))
    nx = -dy / length
    ny = dx / length
    return (
        (int(mid_x + nx * offset), int(mid_y + ny * offset)),
        (int(mid_x - nx * offset), int(mid_y - ny * offset))
    )


def draw_direction_labels(frame, counter, points):
    segment = representative_segment(points)
    if segment is None:
        return

    positive, negative = direction_positions(
        segment[0],
        segment[1]
    )

    if counter.in_side == 1:
        in_pos = positive
        out_pos = negative
    else:
        in_pos = negative
        out_pos = positive

    cv2.putText(
        frame, "IN", in_pos,
        cv2.FONT_HERSHEY_SIMPLEX, 0.90, (0, 255, 0), 3
    )
    cv2.putText(
        frame, "OUT", out_pos,
        cv2.FONT_HERSHEY_SIMPLEX, 0.90, (0, 70, 255), 3
    )


def draw_counting_path(frame, counter, points):
    for index in range(len(points) - 1):
        cv2.line(
            frame,
            points[index],
            points[index + 1],
            (255, 0, 255),
            3
        )

    draw_direction_labels(
        frame,
        counter,
        points
    )


def draw_panel(frame, session_in, session_out, today_in, today_out):
    overlay = frame.copy()
    cv2.rectangle(overlay, (12, 12), (405, 205), (18, 18, 18), -1)
    cv2.addWeighted(overlay, 0.74, frame, 0.26, 0, frame)

    cv2.putText(
        frame, "CONTEO - SESION", (28, 42),
        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2
    )
    cv2.putText(
        frame, f"ENTRADAS: {session_in}", (28, 78),
        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 255, 0), 2
    )
    cv2.putText(
        frame, f"SALIDAS:  {session_out}", (28, 112),
        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 70, 255), 2
    )
    inside = max(0, today_in - today_out)
    cv2.putText(
        frame, f"DENTRO:   {inside}", (28, 146),
        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 255, 255), 2
    )
    cv2.putText(
        frame, f"HOY: IN {today_in} | OUT {today_out}", (28, 181),
        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (220, 220, 220), 2
    )


def normalize_remote_config(remote, fallback_config=None):
    remote_line = dict(remote.get("line") or {})

    # Compatibilidad con servidores V3 anteriores: si todavia no devuelven
    # points, no colapsamos una polilinea local recien calibrada a 2 puntos.
    if not remote_line.get("points") and fallback_config is not None:
        fallback_points = get_line_points(fallback_config)
        if len(fallback_points) > 2:
            remote_line["points"] = [
                [point[0], point[1]]
                for point in fallback_points
            ]

    return normalize_camera_config(
        {
            "line": remote_line,
            "in_side": 1 if int(remote.get("in_side", 1)) >= 0 else -1,
            "margin": max(1, int(remote.get("margin", 18))),
            "confidence": float(remote.get("confidence", 0.22)),
            "config_version": int(remote.get("config_version", 0))
        }
    )


def prepare_remote_config(api_client, current_config, remote):
    branch_id = int(remote["branch_id"])
    camera_name = str(remote["camera_name"])

    if remote.get("bootstrap_required"):
        print(
            "[CONFIG] Primera vinculacion V3: publicando la "
            "configuracion local calibrada."
        )
        bootstrap = api_client.bootstrap_remote_config(current_config)
        if not bootstrap["success"]:
            print(
                "[CONFIG] No se pudo inicializar la configuracion central. "
                f"HTTP={bootstrap['status_code']} | {bootstrap['error']}"
            )
            return current_config, branch_id, camera_name, False

        remote = bootstrap["data"]
        print(
            "[CONFIG] Configuracion local adoptada por el servidor. "
            f"Version={remote.get('config_version', 1)}"
        )

    return (
        normalize_remote_config(remote, current_config),
        branch_id,
        camera_name,
        True
    )


def print_client_diagnostics():
    print(f"[CLIENT] ENV: {ENV_FILE}")
    print(f"[CLIENT] API: {settings.API_URL}")
    print(
        "[CLIENT] Segundo plano total: "
        f"{'SI' if settings.HEADLESS else 'NO'}"
    )
    print(
        "[CLIENT] Bandeja de Windows: "
        f"{'SI' if settings.TRAY_MODE and not settings.HEADLESS else 'NO'}"
    )
    print(
        "[CLIENT] Perfil visible solicitado: "
        f"{settings.PROCESS_FPS:g} FPS / {settings.YOLO_IMGSZ}px"
    )
    print(
        "[CLIENT] Perfil segundo plano solicitado: "
        f"{settings.BACKGROUND_PROCESS_FPS:g} FPS / "
        f"{settings.BACKGROUND_YOLO_IMGSZ}px"
    )
    print(
        "[CLIENT] El detector limita automaticamente la inferencia a "
        "512 px visible / 320 px segundo plano."
    )
    print(
        "[CLIENT] Hilos CPU YOLO: "
        f"{settings.YOLO_CPU_THREADS}"
    )

    if settings.MANAGED_CLIENT:
        client_preview = settings.CLIENT_ID
        if len(client_preview) > 12:
            client_preview = f"{client_preview[:8]}...{client_preview[-4:]}"
        print("[CLIENT] Modo V3 administrado: SI")
        print(f"[CLIENT] CLIENT_ID: {client_preview}")
        print("[CLIENT] Credencial de cliente configurada")
    else:
        print("[CLIENT] Modo V3 administrado: NO")
        print(
            "[CLIENT] Credenciales del cliente faltantes. "
            "El cliente no podra aparecer ONLINE en Clientes instalados."
        )


def main():
    print("=" * 60)
    print("SISTEMA DE CONTEO DE PERSONAS")
    print(f"CLIENTE V{settings.APP_VERSION}")
    print("=" * 60)
    print_client_diagnostics()

    api_client = APIClient(
        base_url=settings.API_URL,
        token=settings.API_TOKEN,
        timeout=settings.API_TIMEOUT_SECONDS,
        client_id=settings.CLIENT_ID,
        client_token=settings.CLIENT_TOKEN
    )

    runtime_branch_id = settings.BRANCH_ID
    runtime_camera_name = settings.CAMERA_NAME
    config = load_camera_config()

    if settings.MANAGED_CLIENT:
        initial_remote = api_client.get_remote_config()
        if initial_remote["success"]:
            config, runtime_branch_id, runtime_camera_name, applied = (
                prepare_remote_config(
                    api_client,
                    config,
                    initial_remote["data"]
                )
            )
            if applied:
                save_camera_config(config)
                print(
                    "[CONFIG] Configuracion central activa. "
                    f"Sucursal={runtime_branch_id} "
                    f"Camara={runtime_camera_name} "
                    f"Version={config.get('config_version', 0)}"
                )
        else:
            print(
                "[CONFIG] No se pudo validar el cliente V3 al iniciar. "
                f"HTTP={initial_remote['status_code']} | "
                f"{initial_remote['error']}"
            )
            if initial_remote["status_code"] in (401, 403):
                print(
                    "[CONFIG] Revise las credenciales generadas para ESTA "
                    "camara en Administracion > Clientes."
                )
            elif initial_remote["status_code"] == 404:
                print(
                    "[CONFIG] Revise API_URL. Debe terminar en /api y el "
                    "servidor debe estar actualizado a V3."
                )
            else:
                print(
                    "[CONFIG] Se continua con la configuracion local para "
                    "mantener el conteo offline."
                )

    initial_fps = (
        settings.BACKGROUND_PROCESS_FPS
        if settings.HEADLESS
        else settings.PROCESS_FPS
    )
    initial_imgsz = (
        min(settings.YOLO_IMGSZ, settings.BACKGROUND_YOLO_IMGSZ)
        if settings.HEADLESS
        else settings.YOLO_IMGSZ
    )

    camera = RTSPCamera(
        rtsp_url=settings.CAMERA_RTSP_URL,
        reconnect_seconds=settings.RECONNECT_SECONDS,
        max_fps=initial_fps,
        copy_frame=False
    )

    detector = PersonDetector(
        model_path="yolov8n.pt",
        confidence=float(config.get("confidence", 0.22)),
        imgsz=initial_imgsz,
        cpu_threads=settings.YOLO_CPU_THREADS
    )

    line_points = get_line_points(config)
    counter = LineCounter(
        points=line_points,
        in_side=config["in_side"],
        margin=config["margin"]
    )

    database = LocalDatabase()
    event_writer = AsyncEventWriter(database)
    synchronizer = EventSynchronizer(
        database=database,
        api_client=api_client,
        interval_seconds=settings.SYNC_INTERVAL_SECONDS,
        batch_size=settings.SYNC_BATCH_SIZE
    )

    today_totals = database.get_today_totals(
        branch_id=runtime_branch_id,
        camera_name=runtime_camera_name
    )
    session_base_in = int(today_totals["IN"])
    session_base_out = int(today_totals["OUT"])

    print("[DB] Historial del dia conservado:")
    print(f"     Entradas: {session_base_in}")
    print(f"     Salidas:  {session_base_out}")
    print("[SESION] Contadores iniciados en 0 / 0.")

    tray = None
    window_hidden = False
    restore_pending = False
    performance_mode = None

    if not settings.HEADLESS and settings.TRAY_MODE:
        tray = TrayController(WINDOW_TITLE)
        tray.start()

    try:
        for frame in camera.start():
            if tray is not None:
                if tray.exit_requested():
                    print("[TRAY] Salida solicitada desde el icono.")
                    break

                if tray.consume_show_request():
                    window_hidden = False
                    restore_pending = True
                    print("[TRAY] Restaurando ventana.")

            render_view = (
                not settings.HEADLESS
                and not window_hidden
            )

            # En segundo plano trabajamos directamente sobre el ultimo ndarray
            # publicado por la camara. Solo copiamos cuando vamos a dibujar.
            if render_view:
                frame = frame.copy()

            desired_mode = "visible" if render_view else "background"
            if desired_mode != performance_mode:
                if render_view:
                    fit_main_window(
                        WINDOW_TITLE,
                        frame
                    )
                    camera.set_max_fps(settings.PROCESS_FPS)
                    detector.set_imgsz(settings.YOLO_IMGSZ)
                    print("[RENDIMIENTO] Perfil visual activo.")
                else:
                    camera.set_max_fps(settings.BACKGROUND_PROCESS_FPS)
                    detector.set_imgsz(
                        min(
                            settings.YOLO_IMGSZ,
                            settings.BACKGROUND_YOLO_IMGSZ
                        )
                    )
                    print(
                        "[RENDIMIENTO] Perfil liviano de segundo plano activo."
                    )
                performance_mode = desired_mode

            remote_update = synchronizer.pop_remote_config()
            if remote_update:
                remote_version = int(remote_update.get("config_version", 0))
                current_version = int(config.get("config_version", 0))
                if (
                    not remote_update.get("bootstrap_required")
                    and remote_version <= current_version
                ):
                    remote_update = None

            if remote_update:
                new_config = normalize_remote_config(
                    remote_update,
                    config
                )
                runtime_branch_id = int(remote_update["branch_id"])
                runtime_camera_name = str(remote_update["camera_name"])
                config = new_config
                save_camera_config(config)

                line_points = get_line_points(config)
                counter.set_line(points=line_points)
                counter.set_in_side(config["in_side"], swap_counts=False)
                counter.set_margin(config["margin"])
                detector.set_confidence(config["confidence"])
                detector.reset_tracker()

                updated_totals = database.get_today_totals(
                    branch_id=runtime_branch_id,
                    camera_name=runtime_camera_name
                )
                session_base_in = max(
                    0,
                    int(updated_totals["IN"]) - counter.entries
                )
                session_base_out = max(
                    0,
                    int(updated_totals["OUT"]) - counter.exits
                )

                print(
                    "[CONFIG] Cambio remoto aplicado sin alterar "
                    "el historial ya registrado."
                )

            persons = detector.track(frame)

            if render_view:
                draw_counting_path(
                    frame,
                    counter,
                    line_points
                )

            for person in persons:
                track_id = person["id"]
                point = person["point"]
                event = counter.update(track_id, point)

                if render_view:
                    x1 = person["x1"]
                    y1 = person["y1"]
                    x2 = person["x2"]
                    y2 = person["y2"]

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )
                    cv2.circle(
                        frame,
                        point,
                        6,
                        (0, 0, 255),
                        -1
                    )
                    cv2.putText(
                        frame,
                        f"ID {track_id} {person['confidence']:.2f}",
                        (x1, max(22, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.62,
                        (0, 255, 0),
                        2
                    )

                if event:
                    print(f"[CONTEO] ID {track_id}: {event}")
                    count_event = CountEvent.create(
                        branch_id=runtime_branch_id,
                        camera_name=runtime_camera_name,
                        track_id=track_id,
                        event_type=event
                    )
                    event_writer.enqueue(count_event)
                    synchronizer.notify_new_event()

            if settings.HEADLESS:
                continue

            if window_hidden:
                cv2.waitKey(1)
                continue

            today_in = session_base_in + counter.entries
            today_out = session_base_out + counter.exits
            draw_panel(
                frame,
                counter.entries,
                counter.exits,
                today_in,
                today_out
            )

            if settings.TRAY_MODE:
                footer = (
                    "C: configurar trazado | Minimizar/X: iconos ocultos | Q: salir"
                )
            else:
                footer = "C: configurar trazado | Q: salir"

            cv2.putText(
                frame,
                footer,
                (20, max(235, frame.shape[0] - 22)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (255, 255, 255),
                2
            )

            cv2.imshow(WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF

            if tray is not None:
                if restore_pending:
                    tray.restore_window()
                    restore_pending = False

                if tray.is_minimized():
                    tray.hide_window()
                    window_hidden = True
                    print("[TRAY] Ventana minimizada a iconos ocultos.")
                    continue

                if not tray.window_exists():
                    window_hidden = True
                    print("[TRAY] Ventana cerrada: continua en iconos ocultos.")
                    continue

            if key == ord("q"):
                break

            if key == ord("c"):
                old_in_side = counter.in_side
                configurator = LineConfigurator()
                new_config = configurator.run(frame)
                if not new_config:
                    continue

                config = new_config

                if settings.MANAGED_CLIENT:
                    publish = api_client.update_remote_config(config)
                    if publish["success"]:
                        remote_saved = publish["data"]
                        config = normalize_remote_config(
                            remote_saved,
                            config
                        )
                        runtime_branch_id = int(remote_saved["branch_id"])
                        runtime_camera_name = str(remote_saved["camera_name"])
                        save_camera_config(config)
                        # Descarta una configuracion vieja que pudiera haber
                        # quedado en cola justo antes del guardado local.
                        synchronizer.pop_remote_config()
                        print(
                            "[CONFIG] Trazado guardado localmente y enviado "
                            "al servidor central. "
                            f"Version={config.get('config_version', 0)}"
                        )
                    else:
                        print(
                            "[CONFIG] Trazado guardado localmente, pero no se "
                            "pudo actualizar el servidor. "
                            f"HTTP={publish['status_code']} | {publish['error']}"
                        )

                line_points = get_line_points(config)
                new_in_side = 1 if int(config["in_side"]) >= 0 else -1
                direction_changed = new_in_side != old_in_side

                event_writer.flush()
                if direction_changed:
                    database.swap_today_event_types(
                        branch_id=runtime_branch_id,
                        camera_name=runtime_camera_name
                    )
                    synchronizer.notify_new_event()

                counter.set_line(points=line_points)
                counter.set_in_side(
                    new_in_side,
                    swap_counts=direction_changed
                )
                counter.set_margin(config["margin"])
                detector.set_confidence(config["confidence"])
                detector.reset_tracker()

                updated_totals = database.get_today_totals(
                    branch_id=runtime_branch_id,
                    camera_name=runtime_camera_name
                )
                session_base_in = max(
                    0,
                    int(updated_totals["IN"]) - counter.entries
                )
                session_base_out = max(
                    0,
                    int(updated_totals["OUT"]) - counter.exits
                )

                if direction_changed:
                    print(
                        "[CONFIG] IN/OUT invertido en vista, conteo "
                        "y registros locales de hoy."
                    )
                else:
                    print(
                        "[CONFIG] Nuevo trazado aplicado con "
                        f"{len(line_points)} puntos."
                    )

    except KeyboardInterrupt:
        print("\n[SISTEMA] Finalizando.")

    finally:
        camera.stop()
        event_writer.close()
        synchronizer.close(final_sync=True)
        api_client.close()

        if tray is not None:
            tray.stop()

        if not settings.HEADLESS:
            cv2.destroyAllWindows()
