import cv2

from app.camera.rtsp import RTSPCamera
from app.config.settings import settings
from app.config.camera_config import (
    load_camera_config,
    save_camera_config
)
from app.gui.line_config import LineConfigurator
from app.detection.detector import PersonDetector
from app.detection.counter import LineCounter
from app.database.database import LocalDatabase, AsyncEventWriter
from app.database.models import CountEvent
from app.api.client import APIClient
from app.api.sync import EventSynchronizer


def get_line(config):
    return (
        (config["line"]["x1"], config["line"]["y1"]),
        (config["line"]["x2"], config["line"]["y2"])
    )


def direction_positions(p1, p2, offset=58):
    x1, y1 = p1
    x2, y2 = p2
    mid_x = (x1 + x2) / 2.0
    mid_y = (y1 + y2) / 2.0
    dx = x2 - x1
    dy = y2 - y1
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    nx = -dy / length
    ny = dx / length
    return (
        (int(mid_x + nx * offset), int(mid_y + ny * offset)),
        (int(mid_x - nx * offset), int(mid_y - ny * offset))
    )


def draw_direction_labels(frame, counter, line_p1, line_p2):
    positive, negative = direction_positions(line_p1, line_p2)
    if counter.in_side == 1:
        in_pos = positive
        out_pos = negative
    else:
        in_pos = negative
        out_pos = positive

    cv2.putText(
        frame, "OUT", in_pos,
        cv2.FONT_HERSHEY_SIMPLEX, 0.90, (0, 70, 255), 3
    )
    cv2.putText(
        frame, "IN", out_pos,
        cv2.FONT_HERSHEY_SIMPLEX, 0.90, (0, 255, 0), 3
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


def normalize_remote_config(remote):
    return {
        "line": {
            "x1": int(remote["line"]["x1"]),
            "y1": int(remote["line"]["y1"]),
            "x2": int(remote["line"]["x2"]),
            "y2": int(remote["line"]["y2"])
        },
        "in_side": 1 if int(remote.get("in_side", 1)) >= 0 else -1,
        "margin": max(1, int(remote.get("margin", 18))),
        "confidence": float(remote.get("confidence", 0.22)),
        "config_version": int(remote.get("config_version", 0))
    }


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
        normalize_remote_config(remote),
        branch_id,
        camera_name,
        True
    )


def main():
    print("=" * 60)
    print("SISTEMA DE CONTEO DE PERSONAS")
    print(f"CLIENTE V{settings.APP_VERSION}")
    print("=" * 60)

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
                "[CONFIG] Servidor no disponible al iniciar; "
                "se usa la configuracion local en cache."
            )

    camera = RTSPCamera(
        rtsp_url=settings.CAMERA_RTSP_URL,
        reconnect_seconds=settings.RECONNECT_SECONDS
    )

    detector = PersonDetector(
        model_path="yolov8n.pt",
        confidence=float(config.get("confidence", 0.22)),
        imgsz=640
    )

    line_p1, line_p2 = get_line(config)
    counter = LineCounter(
        point1=line_p1,
        point2=line_p2,
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

    try:
        for frame in camera.start():
            remote_update = synchronizer.pop_remote_config()
            if remote_update:
                config_candidate, branch_candidate, camera_candidate, applied = (
                    prepare_remote_config(
                        api_client,
                        config,
                        remote_update
                    )
                )
                runtime_branch_id = branch_candidate
                runtime_camera_name = camera_candidate

                if applied:
                    config = config_candidate
                    save_camera_config(config)

                    line_p1, line_p2 = get_line(config)
                    counter.set_line(line_p1, line_p2)
                    counter.set_in_side(
                        config["in_side"],
                        swap_counts=False
                    )
                    counter.margin = config["margin"]
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

            cv2.line(frame, line_p1, line_p2, (255, 0, 255), 3)
            draw_direction_labels(frame, counter, line_p1, line_p2)

            for person in persons:
                track_id = person["id"]
                point = person["point"]
                event = counter.update(track_id, point)

                x1 = person["x1"]
                y1 = person["y1"]
                x2 = person["x2"]
                y2 = person["y2"]

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame, point, 6, (0, 0, 255), -1)
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

            today_in = session_base_in + counter.entries
            today_out = session_base_out + counter.exits
            draw_panel(
                frame,
                counter.entries,
                counter.exits,
                today_in,
                today_out
            )

            footer = (
                "Configuracion remota | Q: salir"
                if settings.MANAGED_CLIENT
                else "C: configurar linea | Q: salir"
            )
            cv2.putText(
                frame,
                footer,
                (20, max(235, frame.shape[0] - 22)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (255, 255, 255),
                2
            )

            cv2.imshow(runtime_camera_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("c"):
                if settings.MANAGED_CLIENT:
                    print(
                        "[CONFIG] Cliente administrado: cambie la linea "
                        "desde el servidor central."
                    )
                    continue

                old_in_side = counter.in_side
                configurator = LineConfigurator()
                new_config = configurator.run(frame)
                if not new_config:
                    continue

                config = new_config
                line_p1, line_p2 = get_line(config)
                new_in_side = 1 if int(config["in_side"]) >= 0 else -1
                direction_changed = new_in_side != old_in_side

                event_writer.flush()
                if direction_changed:
                    database.swap_today_event_types(
                        branch_id=runtime_branch_id,
                        camera_name=runtime_camera_name
                    )
                    synchronizer.notify_new_event()

                counter.set_line(line_p1, line_p2)
                counter.set_in_side(
                    new_in_side,
                    swap_counts=direction_changed
                )
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
                    print("[CONFIG] Nueva linea aplicada.")

    except KeyboardInterrupt:
        print("\n[SISTEMA] Finalizando.")

    finally:
        camera.stop()
        event_writer.close()
        synchronizer.close(final_sync=True)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
