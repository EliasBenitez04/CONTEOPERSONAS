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
                    sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(
                        sql.Identifier(settings.PG_DATABASE)
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


def ensure_schema_upgrades():
    """Aplica cambios compatibles con PostgreSQL 9.5 sin borrar datos."""
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                "SELECT 1 "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name = 'client_configs' "
                "AND column_name = 'line_points'"
            )
        ).first()

        if exists is None:
            connection.execute(
                text(
                    "ALTER TABLE client_configs "
                    "ADD COLUMN line_points TEXT NULL"
                )
            )
            print(
                "[DB] Migracion aplicada: "
                "client_configs.line_points"
            )


def create_tables():
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    print(
        "[DB] Tablas verificadas: users, branches, cameras, "
        "client_devices, client_configs, count_events, audit_logs"
    )


def ensure_initial_admin():
    database = SessionLocal()
    try:
        user_count = database.scalar(
            select(func.count(User.id))
        ) or 0

        if user_count > 0:
            print(f"[AUTH] Usuarios existentes: {user_count}")
            return

        admin = User(
            username=settings.ADMIN_USERNAME.lower(),
            full_name=settings.ADMIN_FULL_NAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role="ADMIN",
            active=True,
            must_change_password=True
        )
        database.add(admin)
        database.commit()

        print("[AUTH] Administrador inicial creado.")
        print(f"[AUTH] Usuario temporal: {settings.ADMIN_USERNAME}")
        print(f"[AUTH] Clave temporal:   {settings.ADMIN_PASSWORD}")
        print("[AUTH] Se exigira cambiar la clave en el primer ingreso.")
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
    print("[DB] PostgreSQL V3 listo para recibir conteos.")


if __name__ == "__main__":
    main()
