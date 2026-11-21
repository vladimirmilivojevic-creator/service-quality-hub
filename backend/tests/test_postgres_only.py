"""Checks that only make sense on PostgreSQL (CI). SQLite runs one writer at a time anyway."""

import asyncio
import os

import pytest

from app.db import SessionLocal
from app.services import next_key

pytestmark = pytest.mark.skipif(
    os.environ["DATABASE_URL"].startswith("sqlite"), reason="row locks only exist on PostgreSQL"
)


def test_parallel_requests_never_get_the_same_ticket_number(client):
    """Regression test: next_key reads and increments the counter under SELECT ... FOR UPDATE."""

    async def take_key() -> str:
        async with SessionLocal() as db:
            key = await next_key(db, "problem")
            await asyncio.sleep(0.2)  # keep the transaction open so the other request has to wait
            await db.commit()
            return key

    async def run() -> list[str]:
        return await asyncio.gather(*(take_key() for _ in range(5)))

    keys = asyncio.run(run())
    assert len(set(keys)) == 5
