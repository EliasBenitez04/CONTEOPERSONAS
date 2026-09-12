import cv2

from app.camera.rtsp import RTSPCamera
from app.config.settings import settings

from app.config.camera_config import (
    load_camera_config
)

from app.gui.line_config import (
    LineConfigurator
)

from app.detection.detector import (
    PersonDetector
)

from app.detection.counter import (
    LineCounter
)

from app.database.database import (
    LocalDatabase,
    AsyncEventWriter
)

from app.database.models import (
    CountEvent
)

def get_line(
    config
):

    p1 = (
        config["line"]["x1"],
        config["line"]["y1"]
    )

    p2 = (
        config["line"]["x2"],
        config["line"]["y2"]
    )

    return p1, p2


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

    config = (
        load_camera_config()
    )

    line_p1, line_p2 = (
        get_line(config)
    )

    counter = LineCounter(
        point1=line_p1,
        point2=line_p2,
        in_side=config["in_side"],
        margin=config["margin"]
    )
    
    # ==========================================
    # BASE DE DATOS LOCAL
    # ==========================================
    
    database = LocalDatabase()
    
    event_writer = AsyncEventWriter(
        database
    )
    
    today_totals = (
        database.get_today_totals(
            branch_id=settings.BRANCH_ID,
            camera_name=settings.CAMERA_NAME
        )
    )
    
    counter.set_counts(
        entries=today_totals["IN"],
        exits=today_totals["OUT"]
    )
    
    print(
        "[DB] Conteo recuperado del dia:"
    )
    
    print(
        f"     Entradas: "
        f"{today_totals['IN']}"
    )
    
    print(
        f"     Salidas: "
        f"{today_totals['OUT']}"
    )

    try:

        for frame in camera.start():

            persons = (
                detector.track(
                    frame
                )
            )

            # ==============================
            # LINEA
            # ==============================

            cv2.line(
                frame,
                line_p1,
                line_p2,
                (255, 0, 255),
                3
            )

            # ==============================
            # PERSONAS
            # ==============================

            for person in persons:

                track_id = (
                    person["id"]
                )

                point = (
                    person["point"]
                )

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
                    (
                        x1,
                        max(
                            20,
                            y1 - 10
                        )
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2
                )

                if event:

                    print(
                        f"[CONTEO] "
                        f"ID {track_id}: "
                        f"{event}"
                    )

                    count_event = (
                        CountEvent.create(
                            branch_id=(
                                settings.BRANCH_ID
                            ),
                            camera_name=(
                                settings.CAMERA_NAME
                            ),
                            track_id=track_id,
                            event_type=event
                        )
                    )

                    event_writer.enqueue(
                        count_event
                    )

            # ==============================
            # CONTADORES
            # ==============================

            cv2.putText(
                frame,
                f"ENTRADAS: {counter.entries}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"SALIDAS: {counter.exits}",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )
            
            people_inside = max(
                0,
                counter.entries
                -
                counter.exits
            )
            
            cv2.putText(
                frame,
                f"DENTRO: {people_inside}",
                (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 0),
                2
            )

            cv2.putText(
                frame,
                "C = configurar linea",
                (20, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            cv2.imshow(
                settings.CAMERA_NAME,
                frame
            )

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            if key == ord("q"):

                break

            # ==============================
            # CONFIGURAR LINEA
            # ==============================

            elif key == ord("c"):

                configurator = (
                    LineConfigurator()
                )

                new_config = (
                    configurator.run(
                        frame
                    )
                )

                if new_config:

                    config = (
                        new_config
                    )

                    (
                        line_p1,
                        line_p2
                    ) = get_line(
                        config
                    )

                    counter.set_line(
                        line_p1,
                        line_p2
                    )

                    counter.set_in_side(
                        config["in_side"]
                    )

                    print(
                        "[CONFIG] Nueva linea "
                        "aplicada."
                    )

    except KeyboardInterrupt:

        print(
            "\n[SISTEMA] Finalizando."
        )

    finally:

        camera.stop()
    
        event_writer.close()
    
        cv2.destroyAllWindows()


if __name__ == "__main__":

    main()