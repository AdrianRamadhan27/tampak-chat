"""Owner-only setup. Runtime services use an unprivileged database role."""

import asyncio
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from app.config import settings


def migrate() -> None:
    config = settings()
    if not config.migration_database_url:
        raise RuntimeError("Migration database URL is required for setup")
    with psycopg.connect(config.migration_database_url.get_secret_value()) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(76813042)")
        conn.execute("CREATE SCHEMA IF NOT EXISTS app")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app.schema_migrations "
            "(version text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
        )
        for path in sorted((Path(__file__).parents[1] / "migrations").glob("*.sql")):
            if not conn.execute(
                "SELECT 1 FROM app.schema_migrations WHERE version=%s", (path.name,)
            ).fetchone():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO app.schema_migrations(version) VALUES(%s)", (path.name,))
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='tampak_app'").fetchone():
            conn.execute(
                sql.SQL("CREATE ROLE tampak_app LOGIN PASSWORD {}").format(
                    sql.Literal(config.app_db_password.get_secret_value())
                )
            )
        conn.execute("GRANT USAGE ON SCHEMA app,public TO tampak_app")
        conn.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA app TO tampak_app")
        conn.execute("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA app TO tampak_app")
        conn.execute("GRANT EXECUTE ON FUNCTION app.soft_delete_owned(text,uuid) TO tampak_app")
        conn.execute("REVOKE ALL ON app.schema_migrations FROM tampak_app")
    print("Database migrations applied; application role has no DDL or superuser privileges.")


async def seed(refresh: bool = False, defer_embeddings: bool = False) -> None:
    from app.db import close_pool, open_pool
    from app.seed import refresh_seed_corpus, seed_database

    await open_pool()
    try:
        await (
            refresh_seed_corpus(defer_embeddings=defer_embeddings) if refresh else seed_database()
        )
    finally:
        await close_pool()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "migrate":
        migrate()
    elif command == "seed":
        asyncio.run(seed())
    elif command == "refresh-seed":
        asyncio.run(seed(refresh=True, defer_embeddings="--defer-embeddings" in sys.argv[2:]))
    elif command == "admin-password":
        import getpass

        password = getpass.getpass("New admin password (12+ characters): ")
        if len(password) < 12 or password != getpass.getpass("Repeat password: "):
            raise SystemExit("Passwords must match and contain at least 12 characters.")

        async def change():
            from app import db
            from app.auth import hasher

            await db.open_pool()
            try:
                await db.execute(
                    "UPDATE principals SET password_hash=%s WHERE kind='ADMIN' AND username=%s",
                    (hasher.hash(password), settings().admin_username),
                )
                await db.execute(
                    "DELETE FROM sessions WHERE principal_id IN (SELECT id FROM principals WHERE kind='ADMIN')"
                )
            finally:
                await db.close_pool()

        asyncio.run(change())
        print("Admin password changed. Existing admin sessions were revoked.")
    else:
        raise SystemExit(
            "Usage: python -m app.cli migrate|seed|refresh-seed [--defer-embeddings]|admin-password"
        )
