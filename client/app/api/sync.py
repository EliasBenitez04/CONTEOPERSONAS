import threading
import time

from app.api.client import APIClient
from app.config.settings import settings
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
        self.interval_seconds = max(1, int(interval_seconds))
        self.batch_size = max(1, int(batch_size))

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._config_lock = threading.Lock()
        self._sync_lock = threading.Lock()
        self._failures = 0
        self._retry_after = 0.0

        self._last_heartbeat_at = 0.0
        self._last_config_check_at = 0.0
        self._heartbeat_online = None
        self._last_error = None
        self._remote_config_version = 0
        self._pending_remote_config = None

        self.thread = threading.Thread(
            target=self._worker,
            daemon=True
        )
        self.thread.start()
        print("[SYNC] Sincronizador iniciado.")

    def notify_new_event(self):
        self._wake_event.set()

    def _sync_failure(self, result):
        self._failures += 1
        status = result.get("status_code")
        delay = (
            60.0 if status in (401, 403)
            else min(60.0, float(2 ** min(self._failures, 6)))
        )
        self._retry_after = time.monotonic() + delay
        self._last_error = (
            f"SYNC HTTP={status}: {str(result.get('error'))[:280]}"
        )[:500]
        print(f"[SYNC] Fallo HTTP={status}; proximo intento en {delay:g}s.")

    def sync_once(self):
        # El cierre y el worker nunca deben usar la misma Session HTTP a la vez.
        with self._sync_lock:
            if time.monotonic() < self._retry_after:
                return 0
            pending = self.database.get_pending_events(limit=min(100, self.batch_size))
            if not pending:
                return 0

            result = self.api_client.send_count_events_batch(pending)
            if not result["success"] and result["status_code"] in (404, 405):
                # Compatibilidad con servidores V4.2.1 sin endpoint de lotes.
                sent_uuids = []
                for event in pending:
                    item_result = self.api_client.send_count_event(event)
                    if not item_result["success"]:
                        self.database.mark_batch_synchronized(sent_uuids)
                        self._sync_failure(item_result)
                        return len(sent_uuids)
                    sent_uuids.append(event["event_uuid"])
                self.database.mark_batch_synchronized(sent_uuids)
                self._failures = 0
                self._retry_after = 0.0
                self._last_error = None
                print(f"[SYNC] {len(sent_uuids)} eventos enviados (API legacy).")
                return len(sent_uuids)

            if not result["success"]:
                self._sync_failure(result)
                return 0

            data = result.get("data")
            ack = data.get("accepted_uuids") if isinstance(data, dict) else None
            requested = {event["event_uuid"] for event in pending}
            if not isinstance(ack, list) or not all(
                isinstance(value, str) and value in requested for value in ack
            ):
                self._sync_failure({
                    "status_code": result.get("status_code"),
                    "error": "Confirmacion de lote invalida"
                })
                return 0

            accepted = set(ack)
            if accepted:
                self.database.mark_batch_synchronized(list(accepted))
            if len(accepted) != len(requested):
                self._sync_failure({
                    "status_code": result.get("status_code"),
                    "error": "Confirmacion parcial del lote"
                })
            else:
                self._failures = 0
                self._retry_after = 0.0
                self._last_error = None
            print(f"[SYNC] Lote confirmado: {len(accepted)}/{len(requested)}.")
            return len(accepted)

    def send_heartbeat_if_due(self, force=False):
        now = time.monotonic()
        if (
            not force
            and now - self._last_heartbeat_at
            < settings.HEARTBEAT_INTERVAL_SECONDS
        ):
            return

        self._last_heartbeat_at = now
        result = self.api_client.send_heartbeat(
            branch_id=settings.BRANCH_ID,
            camera_name=settings.CAMERA_NAME,
            app_version=settings.APP_VERSION,
            pending_events=self.database.count_pending_events(),
            last_error=self._last_error
        )

        is_online = bool(result["success"])
        if is_online != self._heartbeat_online:
            if is_online:
                print("[SYNC] Cliente ONLINE en servidor central.")
            else:
                print(
                    "[SYNC] Heartbeat sin respuesta. "
                    f"HTTP={result['status_code']} | "
                    f"{result['error']}"
                )

        self._heartbeat_online = is_online

    def fetch_remote_config_if_due(self, force=False):
        if not self.api_client.managed_client:
            return

        now = time.monotonic()
        if (
            not force
            and now - self._last_config_check_at
            < settings.REMOTE_CONFIG_INTERVAL_SECONDS
        ):
            return

        self._last_config_check_at = now
        result = self.api_client.get_remote_config()
        if not result["success"]:
            return

        config = result.get("data") or {}
        version = int(config.get("config_version", 0))

        if config.get("bootstrap_required"):
            with self._config_lock:
                self._pending_remote_config = config
            print(
                "[CONFIG] El servidor solicita adoptar la "
                "configuracion local actual."
            )
            return

        if version <= self._remote_config_version:
            return

        self._remote_config_version = version
        with self._config_lock:
            self._pending_remote_config = config

        print(
            "[CONFIG] Configuracion remota recibida. "
            f"Version={version}"
        )

    def pop_remote_config(self):
        with self._config_lock:
            config = self._pending_remote_config
            self._pending_remote_config = None
        return config

    def _worker(self):
        while not self._stop_event.is_set():
            try:
                self.send_heartbeat_if_due()
                self.fetch_remote_config_if_due()
                self.sync_once()
            except Exception as error:
                self._last_error = f"WORKER {error}"[:500]
                print("[SYNC] Error inesperado:", error)

            self._wake_event.wait(
                timeout=self.interval_seconds
            )
            self._wake_event.clear()

    def close(self, final_sync=True):
        self._stop_event.set()
        self._wake_event.set()
        self.thread.join(timeout=max(5, self.api_client.timeout * 4 + 2))
        if final_sync and not self.thread.is_alive():
            try:
                self.send_heartbeat_if_due(force=True)
                self.sync_once()
            except Exception as error:
                print("[SYNC] Error en sincronizacion final:", error)
        if not self.thread.is_alive():
            self.api_client.close()
        else:
            print("[SYNC] Worker sigue activo; se evita cerrar su sesion HTTP.")
        print("[SYNC] Sincronizador detenido.")
