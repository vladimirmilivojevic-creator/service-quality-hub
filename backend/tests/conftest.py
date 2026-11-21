"""Test setup.

Tests use SQLite by default (no services needed). CI runs the same tests against PostgreSQL by
setting DATABASE_URL. Every test starts from the same seeded demo data, so tests are independent.
With SQLite the database is seeded once and the file is copied for every test (much faster).
"""

import asyncio
import os
import shutil
from pathlib import Path

# Settings are read at import time, so configure the environment first.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ["DB_POOL"] = "false"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["SEED_DEMO_DATA"] = "false"  # the fixtures below seed the database

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo  # noqa: E402

PASSWORD = "demo1234"
IS_SQLITE = os.environ["DATABASE_URL"].startswith("sqlite")
SQLITE_FILE = Path("test.db")
SQLITE_TEMPLATE = Path("test-template.db")
SAMPLES = Path(__file__).resolve().parents[2] / "samples"


async def _reset_and_seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed_demo(db)


@pytest.fixture(scope="session")
def seeded_template():
    if IS_SQLITE:
        asyncio.run(_reset_and_seed())
        shutil.copy(SQLITE_FILE, SQLITE_TEMPLATE)
        yield
        SQLITE_TEMPLATE.unlink(missing_ok=True)
    else:
        yield


@pytest.fixture
def client(seeded_template):
    if IS_SQLITE:
        shutil.copy(SQLITE_TEMPLATE, SQLITE_FILE)
    else:
        asyncio.run(_reset_and_seed())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Run a coroutine with a database session, for tests that look at the database directly."""

    def run(coro_factory):
        async def runner():
            async with SessionLocal() as db:
                return await coro_factory(db)

        return asyncio.run(runner())

    return run


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def sqm(client):
    return login(client, "sqm@valdora.example")


@pytest.fixture
def plant_lead(client):
    return login(client, "it.innfeld@valdora.example")


@pytest.fixture
def management(client):
    return login(client, "cio@valdora.example")


@pytest.fixture
def supplier(client):
    return login(client, "supplier.alpnet@valdora.example")


def plant_id(client: TestClient, headers: dict, code: str) -> int:
    return next(p["id"] for p in client.get("/plants", headers=headers).json() if p["code"] == code)


def service_id(client: TestClient, headers: dict, prefix: str) -> int:
    return next(s["id"] for s in client.get("/services", headers=headers).json() if s["name"].startswith(prefix))


def provider_id(client: TestClient, headers: dict, short_name: str, month: str = "2026-10") -> int:
    rows = client.get(f"/suppliers?month={month}", headers=headers).json()["rows"]
    return next(r["provider_id"] for r in rows if r["short_name"] == short_name)
