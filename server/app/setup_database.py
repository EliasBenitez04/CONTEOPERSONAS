import psycopg2
from psycopg2 import sql
from sqlalchemy import func, select, text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.auth import hash_password
from app.models import User


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
        "users, branches, cameras, count_events"
    )


def ensure_initial_admin():
    database = SessionLocal()

    try:
        user_count = database.scalar(
            select(func.count(User.id))
        ) or 0

        if user_count > 0:
            print(
                f"[AUTH] Usuarios existentes: {user_count}"
            )
            return

        admin = User(
            username=settings.ADMIN_USERNAME.lower(),
            full_name=settings.ADMIN_FULL_NAME,
            password_hash=hash_password(
                settings.ADMIN_PASSWORD
            ),
            role="ADMIN",
            active=True,
            must_change_password=True
        )

        database.add(admin)
        database.commit()

        print("[AUTH] Administrador inicial creado.")
        print(
            "[AUTH] Usuario temporal: "
            f"{settings.ADMIN_USERNAME}"
        )
        print(
            "[AUTH] Clave temporal:   "
            f"{settings.ADMIN_PASSWORD}"
        )
        print(
            "[AUTH] Se exigira cambiar la clave "
            "en el primer ingreso."
        )

    finally:
        database.close()


def main():
    print(
        "[DB] Preparando PostgreSQL "
        f"{settings.PG_HOST}:{settings.PG_PORT}"
    )

    ensure_database_exists()
    create_tables()
    ensure_initial_admin()

    print(
        "[DB] PostgreSQL listo para recibir conteos."
    )


if __name__ == "__main__":
    main()
