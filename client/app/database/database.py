import sqlite3
import threading

from datetime import datetime
from pathlib import Path
from queue import Queue

from app.database.models import CountEvent


CLIENT_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

DATABASE_PATH = (
    CLIENT_DIR
    / "data"
    / "local.db"
)


class LocalDatabase:

    def __init__(
        self,
        database_path=DATABASE_PATH
    ):

        self.database_path = Path(
            database_path
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.initialize()

    # ==========================================
    # CONEXION
    # ==========================================

    def connect(self):

        connection = sqlite3.connect(
            self.database_path,
            timeout=10
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA journal_mode=WAL;"
        )

        connection.execute(
            "PRAGMA synchronous=NORMAL;"
        )

        connection.execute(
            "PRAGMA busy_timeout=10000;"
        )

        return connection

    # ==========================================
    # CREAR ESTRUCTURA
    # ==========================================

    def initialize(self):

        with self.connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS count_events
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    event_uuid TEXT NOT NULL UNIQUE,

                    branch_id INTEGER NOT NULL,

                    camera_name TEXT NOT NULL,

                    track_id INTEGER,

                    event_type TEXT NOT NULL
                        CHECK (
                            event_type IN ('IN', 'OUT')
                        ),

                    occurred_at TEXT NOT NULL,

                    synchronized INTEGER NOT NULL
                        DEFAULT 0
                        CHECK (
                            synchronized IN (0, 1)
                        ),

                    synced_at TEXT,

                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_count_events_sync
                ON count_events (
                    synchronized
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_count_events_branch_camera
                ON count_events (
                    branch_id,
                    camera_name,
                    occurred_at
                )
                """
            )

            connection.commit()

        print(
            f"[DB] SQLite lista: "
            f"{self.database_path}"
        )

    # ==========================================
    # INSERTAR EVENTO
    # ==========================================

    def insert_event(
        self,
        event: CountEvent
    ):

        with self.connect() as connection:

            connection.execute(
                """
                INSERT OR IGNORE INTO count_events
                (
                    event_uuid,
                    branch_id,
                    camera_name,
                    track_id,
                    event_type,
                    occurred_at,
                    synchronized
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_uuid,
                    event.branch_id,
                    event.camera_name,
                    event.track_id,
                    event.event_type,
                    event.occurred_at,
                    event.synchronized
                )
            )

            connection.commit()

    # ==========================================
    # TOTALES DEL DIA
    # ==========================================

    def get_today_totals(
        self,
        branch_id: int,
        camera_name: str
    ):

        today = (
            datetime.now()
            .astimezone()
            .date()
            .isoformat()
        )

        totals = {
            "IN": 0,
            "OUT": 0
        }

        with self.connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    event_type,
                    COUNT(*) AS total

                FROM count_events

                WHERE branch_id = ?
                AND camera_name = ?
                AND substr(
                    occurred_at,
                    1,
                    10
                ) = ?

                GROUP BY event_type
                """,
                (
                    branch_id,
                    camera_name,
                    today
                )
            ).fetchall()

        for row in rows:

            totals[
                row["event_type"]
            ] = row["total"]

        return totals

    # ==========================================
    # EVENTOS SIN SINCRONIZAR
    # ==========================================

    def get_pending_events(
        self,
        limit=100
    ):

        with self.connect() as connection:

            rows = connection.execute(
                """
                SELECT *

                FROM count_events

                WHERE synchronized = 0

                ORDER BY id ASC

                LIMIT ?
                """,
                (
                    limit,
                )
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ==========================================
    # MARCAR SINCRONIZADO
    # ==========================================

    def mark_as_synchronized(
        self,
        event_uuid: str
    ):

        synced_at = (
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        )

        with self.connect() as connection:

            connection.execute(
                """
                UPDATE count_events

                SET
                    synchronized = 1,
                    synced_at = ?

                WHERE event_uuid = ?
                """,
                (
                    synced_at,
                    event_uuid
                )
            )

            connection.commit()

    # ==========================================
    # ULTIMOS EVENTOS
    # ==========================================

    def get_recent_events(
        self,
        limit=20
    ):

        with self.connect() as connection:

            rows = connection.execute(
                """
                SELECT *

                FROM count_events

                ORDER BY id DESC

                LIMIT ?
                """,
                (
                    limit,
                )
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


# ==============================================
# ESCRITOR ASINCRONO
# ==============================================

class AsyncEventWriter:

    def __init__(
        self,
        database: LocalDatabase
    ):

        self.database = database

        self.queue = Queue()

        self.thread = threading.Thread(
            target=self._worker,
            daemon=True
        )

        self.thread.start()

        print(
            "[DB] Escritor asincrono iniciado."
        )

    def enqueue(
        self,
        event: CountEvent
    ):

        self.queue.put(
            event
        )

    def _worker(self):

        while True:

            event = self.queue.get()

            if event is None:

                self.queue.task_done()

                break

            try:

                self.database.insert_event(
                    event
                )

                print(
                    "[DB] Evento guardado: "
                    f"{event.event_type} "
                    f"ID={event.track_id}"
                )

            except Exception as error:

                print(
                    "[DB] Error guardando evento:",
                    error
                )

            finally:

                self.queue.task_done()

    def close(self):

        # Todo lo colocado antes del sentinel
        # se procesa primero.
        self.queue.put(
            None
        )

        self.thread.join(
            timeout=5
        )

        print(
            "[DB] Escritor detenido."
        )