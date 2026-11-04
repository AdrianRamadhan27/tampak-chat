import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
import psycopg
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from psycopg import sql

from app import auth, db
from app.config import ROOT, settings
from app.main import app
from app.worker import cleanup


@pytest.fixture(scope="session")
def test_environment():
    """Use an isolated database, private artifacts and key-free workers for every test run."""
    original = settings()
    if not original.migration_database_url:
        pytest.fail(
            "Integration tests require the local migration database URL to create a disposable database."
        )
    owner_url = original.migration_database_url.get_secret_value()
    database_name = "tampak_test_" + secrets.token_hex(8)

    def with_database(url):
        parts = urlsplit(url)
        return urlunsplit(
            (parts.scheme, parts.netloc, "/" + database_name, parts.query, parts.fragment)
        )

    directory = original.storage / "test-sessions" / database_name
    directory.mkdir(parents=True, mode=0o700)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        "TAMPAK_DATABASE_URL": with_database(original.database_url.get_secret_value()),
        "TAMPAK_MIGRATION_DATABASE_URL": with_database(owner_url),
        "TAMPAK_DATA_DIR": str(directory),
        "TAMPAK_MASTER_KEY": Fernet.generate_key().decode(),
        "TAMPAK_ADMIN_USERNAME": "admin",
        "TAMPAK_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "TAMPAK_CHAT_MODEL": "",
        "TAMPAK_CHAT_API_KEY": "",
        "TAMPAK_VISION_MODEL": "",
        "TAMPAK_VISION_API_KEY": "",
        "TAMPAK_OPENROUTER_API_KEY": "",
        "TAMPAK_EMBEDDING_INTERVAL_SECONDS": "0",
        "TAMPAK_TEST_API_URL": f"http://127.0.0.1:{port}",
    }
    previous = {key: os.environ.get(key) for key in environment}
    processes = []
    try:
        with psycopg.connect(owner_url, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
        os.environ.update(environment)
        settings.cache_clear()
        backend = Path(__file__).resolve().parents[1]
        for command in ["migrate", "seed"]:
            with (directory / f"{command}.log").open("w") as log:
                result = subprocess.run(
                    [sys.executable, "-m", "app.cli", command],
                    cwd=backend,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                if result.returncode:
                    pytest.fail(
                        f"Disposable test {command} failed. Inspect its private log in {directory}."
                    )
        commands = [
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            [sys.executable, "-m", "app.worker", "chat"],
            [sys.executable, "-m", "app.worker", "ingest"],
        ]
        for index, command in enumerate(commands):
            with (directory / f"service-{index}.log").open("w") as log:
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=backend,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                )
        ready = False
        for _ in range(150):
            try:
                if (
                    httpx.get(
                        environment["TAMPAK_TEST_API_URL"] + "/api/v1/health", timeout=1
                    ).status_code
                    == 200
                ):
                    ready = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        if not ready:
            pytest.fail("The disposable test API did not become ready.")
        yield environment
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        settings.cache_clear()
        assert database_name.startswith("tampak_test_")
        with psycopg.connect(owner_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(database_name)
                )
            )
        if directory.is_relative_to(ROOT / "runtime"):
            shutil.rmtree(directory, ignore_errors=True)


@pytest_asyncio.fixture(autouse=True)
async def database_pool(test_environment):
    await db.open_pool()
    yield
    await db.close_pool()


@pytest_asyncio.fixture
async def client():
    principal, token, csrf = db.new_id(), secrets.token_urlsafe(40), secrets.token_urlsafe(24)
    await db.execute(
        "INSERT INTO principals(id,kind,expires_at) VALUES(%s,'GUEST',%s)",
        (principal, db.now() + timedelta(hours=1)),
    )
    await db.execute(
        "INSERT INTO sessions(token_hash,principal_id,csrf_token,expires_at) VALUES(%s,%s,%s,%s)",
        (auth.token_hash(token), principal, csrf, db.now() + timedelta(hours=1)),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost:3010",
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3010"},
        cookies={auth.COOKIE: token},
    ) as client:
        client.principal_id = principal
        yield client
    await db.execute(
        "UPDATE principals SET expires_at=now()-interval '1 second' WHERE id=%s", (principal,)
    )
    await cleanup()


@pytest_asyncio.fixture
async def seed_dataset():
    return await db.one(
        "SELECT * FROM datasets WHERE bot_id='10000000-0000-4000-8000-000000000001' AND is_active LIMIT 1"
    )
