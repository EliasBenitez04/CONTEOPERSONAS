import cv2

from app.camera.rtsp import RTSPCamera
from app.config.settings import settings
from app.config.camera_config import load_camera_config
from app.gui.line_config import LineConfigurator
from app.detection.detector import PersonDetector
from app.detection.counter import LineCounter
from app.database.database import LocalDatabase, AsyncEventWriter
from app.database.models import CountEvent


def get_line(config):

    p1 = (
        config["line"]["x1"],
        config["line"]["y1"]
    )

    p2 = (
        config["line"]["x2"],
        config["line"]["y2"]
    )

    return p1, p2


def normalize_side(value):

    return 1 if value >= 0 else -1


def draw_panel(frame, session_in, session_out, today_in, today_out):

    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (12, 12),
        (410, 218),
        (20, 20, 20),
        -1
    )

    cv2.addWeighted(
        overlay,
        0.72,
        frame,
        0.28,
        0,
        frame
    )

    cv2.putText(
        frame,
        "CONTEO - SESION ACTUAL",
        (28, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        f"ENTRADAS: {session_in}",
        (28, 78),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame,
        f"SALIDAS:  {session_out}",
        (28, 112),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (0, 80, 255),
        2
    )

    inside = max(0, session_in - session_out)

    cv2.putText(
        frame,
        f"DENTRO:   {inside}",
        (28, 146),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (0, 255, 255),
        2
    )

    cv2.putText(
        frame,
        f"HOY -> IN {today_in} | OUT {today_out}",
        (28, 181),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (210, 210, 210),
        2
    )

    cv2.putText(
        frame,
        "C: configurar linea y direccion",
        (28, 207),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (180, 180, 180),
        1
    )


def draw_direction_labels(frame, counter, line_p1, line_p2):

    x1, y1 = line_p1
    x2, y2 = line_p2

    mid_x = int((x1 + x2) / 2)
    mid_y = int((y1 + y2) / 2)

    dx = x2 - x1
    dy = y2 - y1

    length = max(1.0, (dx * dx + dy * dy) ** 0.5)

    # Normal positiva: coincide con signed_distance > 0.
    nx = -dy / length
    ny = dx / length

    offset = 48

    positive_pos = (
        int(mid_x + nx * offset),
        int(mid_y + ny * offset)
    )

    negative_pos = (
        int(mid_x - nx * offset),
        int(mid_y - ny * offset)
    )

    if counter.in_side == 1:
        in_pos = positive_pos
        out_pos = negative_pos
    else:
        in_pos = negative_pos
        out_pos = positive_pos

    cv2.putText(
        frame,
        "IN",
        in_pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame,
        "OUT",
        out_pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (0, 80, 255),
        2
    )


def main():

    print("=" * 60)
    print("SISTEMA DE CONTEO DE PERSONAS")
    print("=" * 60)

    camera = RTSPCamera(
        rtsp_url=settings.CAMERA_RTSP_URL,
        reconnect_seconds=settings.RECONNECT_SECONDS
    )

    detector = PersonDetector(
        model_path="yolov8n.pt",
        confidence=0.30,
        imgsz=640
    )

    config = load_camera_config()
    line_p1, line_p2 = get_line(config)

    counter = LineCounter(
        point1=line_p1,
        point2=line_p2,
        in_side=config["in_side"],
        margin=config["margin"]
    )

    # counter.entries/exits representan SOLO esta ejecucion.
    # El historial diario permanece guardado en SQLite.
    database = LocalDatabase()
    event_writer = AsyncEventWriter(database)

    today_totals = database.get_today_totals(
        branch_id=settings.BRANCH_ID,
        camera_name=settings.CAMERA_NAME
    )

    session_base_in = today_totals["IN"]
    session_base_out = today_totals["OUT"]

    print("[DB] Historial del dia conservado:")
    print(f"     Entradas: {session_base_in}")
    print(f"     Salidas:  {session_base_out}")
    print("[SESION] Contador visual iniciado en 0 / 0.")

    try:

        for frame in camera.start():

            persons = detector.track(frame)

            cv2.line(
                frame,
                line_p1,
                line_p2,
                (255, 0, 255),
                3
            )

            draw_direction_labels(
                frame,
                counter,
                line_p1,
                line_p2
            )

            for person in persons:

                track_id = person["id"]
                point = person["point"]

                event = counter.update(
                    track_id,
                    point
                )

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
                    f"ID {track_id}",
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2
                )

                if event:

                    print(
                        f"[CONTEO] ID {track_id}: {event}"
                    )

                    count_event = CountEvent.create(
                        branch_id=settings.BRANCH_ID,
                        camera_name=settings.CAMERA_NAME,
                        track_id=track_id,
                        event_type=event
                    )

                    event_writer.enqueue(count_event)

            today_in = session_base_in + counter.entries
            today_out = session_base_out + counter.exits

            draw_panel(
                frame,
                counter.entries,
                counter.exits,
                today_in,
                today_out
            )

            cv2.imshow(
                settings.CAMERA_NAME,
                frame
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("c"):

                previous_in_side = counter.in_side

                configurator = LineConfigurator()
                new_config = configurator.run(frame)

                if new_config:

                    config = new_config
                    line_p1, line_p2 = get_line(config)

                    new_in_side = normalize_side(
                        config["in_side"]
                    )

                    direction_changed = (
                        new_in_side != previous_in_side
                    )

                    counter.set_line(
                        line_p1,
                        line_p2
                    )

                    if direction_changed:

                        # Aseguramos que no quede ningun evento viejo en
                        # la cola antes de reclasificar el dia completo.
                        event_writer.flush()

                        database.swap_today_event_types(
                            branch_id=settings.BRANCH_ID,
                            camera_name=settings.CAMERA_NAME
                        )

                        # Intercambia tambien los conteos de esta sesion.
                        counter.set_in_side(
                            new_in_side,
                            swap_counts=True
                        )

                        # El acumulado previo al inicio de esta ejecucion
                        # pertenece al mismo dia y tambien debe invertirse.
                        session_base_in, session_base_out = (
                            session_base_out,
                            session_base_in
                        )

                        print(
                            "[CONFIG] Direccion invertida: "
                            "vista, sesion y registros de hoy actualizados."
                        )

                    else:

                        counter.set_in_side(
                            new_in_side,
                            swap_counts=False
                        )

                        print(
                            "[CONFIG] Nueva linea aplicada "
                            "sin cambiar la direccion."
                        )

    except KeyboardInterrupt:

        print("\n[SISTEMA] Finalizando.")

    finally:

        camera.stop()
        event_writer.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
