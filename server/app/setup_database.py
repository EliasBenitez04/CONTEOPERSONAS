import psycopg2
from psycopg2 import sql
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401


def ensure_database_exists():
    connection = psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        dbname="postgres"
    )

    connection.autocommit = True

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (settings.PG_DATABASE,)
            )

            exists = cursor.fetchone() is not None

            if not exists:
                cursor.execute(
                    sql.SQL(
                        "CREATE DATABASE {} ENCODING 'UTF8'"
                    ).format(
                        sql.Identifier(
                            settings.PG_DATABASE
                        )
                    )
                )

                print(
                    "[DB] Base PostgreSQL creada: "
                    f"{settings.PG_DATABASE}"
                )
            else:
                print(
                    "[DB] Base PostgreSQL existente: "
                    f"{settings.PG_DATABASE}"
                )
    finally:
        connection.close()


def create_tables():
    Base.metadata.create_all(
        bind=engine
    )

    with engine.connect() as connection:
        connection.execute(
            text("SELECT 1")
        )

    print(
        "[DB] Tablas verificadas: "
        "branches, cameras, count_events"
    )


def main():
    print(
        "[DB] Preparando PostgreSQL "
        f"{settings.PG_HOST}:{settings.PG_PORT}"
    )

    ensure_database_exists()
    create_tables()

    print(
        "[DB] PostgreSQL listo para recibir conteos."
    )


if __name__ == "__main__":
    main()
