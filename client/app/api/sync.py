import threading
import time

from app.api.client import APIClient
from app.database.database import LocalDatabase


class EventSynchronizer:

    def __init__(
        self,
        database: LocalDatabase,
        api_client: APIClient,
        interval_seconds: int = 5,
        batch_size: int = 100
    ):
        self.database = database
        self.api_client = api_client
        self.interval_seconds = max(
            1,
            int(interval_seconds)
        )
        self.batch_size = max(
            1,
            int(batch_size)
        )

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

        self.thread = threading.Thread(
            target=self._worker,
            daemon=True
        )

        self.thread.start()

        print(
            "[SYNC] Sincronizador iniciado."
        )

    def notify_new_event(self):
        self._wake_event.set()

    def sync_once(self):
        pending = (
            self.database.get_pending_events(
                limit=self.batch_size
            )
        )

        if not pending:
            return 0

        synchronized = 0

        for event in pending:
            if self._stop_event.is_set():
                break

            result = (
                self.api_client.send_count_event(
                    event
                )
            )

            if not result["success"]:
                print(
                    "[SYNC] Servidor no disponible o rechazo. "
                    f"Evento pendiente: {event['event_uuid']} | "
                    f"HTTP={result['status_code']} | "
                    f"{result['error']}"
                )

                # Se corta el lote para no golpear el servidor
                # con todos los pendientes si hay una falla general.
                break

            self.database.mark_as_synchronized(
                event["event_uuid"]
            )

            synchronized += 1

            print(
                "[SYNC] Evento sincronizado: "
                f"{event['event_type']} "
                f"ID={event.get('track_id')} "
                f"UUID={event['event_uuid']}"
            )

        return synchronized

    def _worker(self):
        while not self._stop_event.is_set():
            try:
                self.sync_once()

            except Exception as error:
                print(
                    "[SYNC] Error inesperado:",
                    error
                )

            self._wake_event.wait(
                timeout=self.interval_seconds
            )

            self._wake_event.clear()

    def close(
        self,
        final_sync=True
    ):
        if final_sync:
            try:
                self.sync_once()
            except Exception as error:
                print(
                    "[SYNC] Error en sincronizacion final:",
                    error
                )

        self._stop_event.set()
        self._wake_event.set()

        self.thread.join(
            timeout=max(
                5,
                self.interval_seconds + 1
            )
        )

        self.api_client.close()

        print(
            "[SYNC] Sincronizador detenido."
        )
