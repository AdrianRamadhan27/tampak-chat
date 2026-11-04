from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.config import settings


@dataclass(frozen=True)
class Scope:
    principal_id: str
    is_admin: bool = False


SYSTEM = Scope("00000000-0000-0000-0000-000000000001", True)
_pool: AsyncConnectionPool | None = None


async def open_pool() -> None:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            settings().database_url.get_secret_value(),
            min_size=1,
            max_size=6,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        await _pool.open(wait=True)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def connection(scope: Scope = SYSTEM) -> AsyncIterator[AsyncConnection]:
    if _pool is None:
        await open_pool()
    assert _pool is not None
    async with _pool.connection() as conn, conn.transaction():
        await conn.execute("SET LOCAL search_path TO app, public")
        await conn.execute(
            "SELECT set_config('app.principal_id', %s, true), set_config('app.is_admin', %s, true)",
            (scope.principal_id, "true" if scope.is_admin else "false"),
        )
        yield conn


async def one(query: str, params=(), scope: Scope = SYSTEM) -> dict[str, Any] | None:
    async with connection(scope) as conn:
        cursor = await conn.execute(query, params)
        return await cursor.fetchone()


async def many(query: str, params=(), scope: Scope = SYSTEM) -> list[dict[str, Any]]:
    async with connection(scope) as conn:
        cursor = await conn.execute(query, params)
        return list(await cursor.fetchall())


async def execute(query: str, params=(), scope: Scope = SYSTEM) -> int:
    async with connection(scope) as conn:
        cursor = await conn.execute(query, params)
        return cursor.rowcount


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value)


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


def serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serializable(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    from decimal import Decimal

    if isinstance(value, Decimal):
        return float(value)
    return value
