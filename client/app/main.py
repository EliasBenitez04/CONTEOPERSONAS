import cv2

from app.camera.rtsp import RTSPCamera
from app.config.settings import settings

from app.detection.detector import (
    PersonDetector
)

from app.detection.counter import (
    LineCounter
)


def main():

    print("=" * 60)
    print("SISTEMA DE CONTEO DE PERSONAS")
    print("=" * 60)

    if not settings.CAMERA_RTSP_URL:

        print(
            "[ERROR] CAMERA_RTSP_URL "
            "no configurado."
        )

        return

    camera = RTSPCamera(
        rtsp_url=settings.CAMERA_RTSP_URL,
        reconnect_seconds=settings.RECONNECT_SECONDS
    )

    detector = PersonDetector(
        model_path="yolov8n.pt",
        confidence=0.40
    )

    # ==========================================
    # LINEA DE PRUEBA
    # ==========================================

    line_p1 = (640, 100)
    line_p2 = (640, 650)

    counter = LineCounter(
        point1=line_p1,
        point2=line_p2,
        in_side=1
    )

    try:

        for frame in camera.start():

            persons = detector.track(
                frame
            )

            # ==========================================
            # DIBUJAR LINEA
            # ==========================================

            cv2.line(
                frame,
                line_p1,
                line_p2,
                (255, 0, 255),
                3
            )

            # ==========================================
            # MARCAR LADOS
            # ==========================================

            
            cv2.putText(
                frame,
                "OUT",
                (
                    line_p1[0] - 120,
                    line_p1[1] + 40
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

            cv2.putText(
                frame,
                "IN",
                (
                    line_p1[0] + 30,
                    line_p1[1] + 40
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

            # ==========================================
            # PERSONAS
            # ==========================================

            for person in persons:

                track_id = person["id"]

                x1 = person["x1"]
                y1 = person["y1"]
                x2 = person["x2"]
                y2 = person["y2"]

                point = person["point"]

                event = counter.update(
                    track_id,
                    point
                )

                # Bounding box temporal
                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                # Punto usado para cruzar línea
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
                        y1 - 10
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

                if event == "IN":

                    print(
                        f"[CONTEO] ID {track_id} "
                        "ENTRADA"
                    )

                elif event == "OUT":

                    print(
                        f"[CONTEO] ID {track_id} "
                        "SALIDA"
                    )

            # ==========================================
            # PANEL DE CONTEO
            # ==========================================

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

            cv2.imshow(
                settings.CAMERA_NAME,
                frame
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            # Presionando I invertimos
            # IN / OUT durante las pruebas
            elif key == ord("i"):

                counter.invert_direction()

                print(
                    "[CONFIG] Direccion "
                    "IN/OUT invertida."
                )

    except KeyboardInterrupt:

        print(
            "\n[SISTEMA] Finalizando."
        )

    finally:

        camera.stop()

        cv2.destroyAllWindows()


if __name__ == "__main__":

    main()