"""ServiceQualityHub API: SLA and service quality for a multi-site IT organisation."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.deps import DB
from app.routers import (
    auth,
    catalogue,
    changes,
    demo,
    imports,
    improvements,
    kpis,
    problems,
    reports,
    suppliers,
    tickets,
)
from app.seed import seed_if_empty

logging.basicConfig(level=logging.INFO)


_ready = False
_ready_lock = asyncio.Lock()


async def prepare_database() -> None:
    """Create tables and demo data once per process.

    Runs at startup, and again on the first request if the platform did not send the startup event
    (serverless platforms do not always run the ASGI lifespan).
    """
    global _ready
    async with _ready_lock:
        if _ready:
            return
        if settings.auto_create_tables:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        if settings.seed_demo_data:
            async with SessionLocal() as db:
                if await seed_if_empty(db):
                    logging.info("Demo data created")
        _ready = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await prepare_database()
    yield


app = FastAPI(
    title="ServiceQualityHub API",
    version="1.0.0",
    description=(
        "Service catalogue, SLA engine, KPIs, supplier scorecards, problem candidates, improvement register and "
        "monthly service review for the five plants of a fictional machinery manufacturer. "
        "Demo logins use the password demo1234 (POST /auth/login)."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def ensure_database(request: Request, call_next):
    if not _ready and request.url.path != "/health":
        await prepare_database()
    return await call_next(request)


for router in (
    auth.router,
    catalogue.router,
    tickets.router,
    kpis.router,
    suppliers.router,
    problems.router,
    changes.router,
    improvements.router,
    reports.router,
    imports.router,
    demo.router,
):
    app.include_router(router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness only. It does not touch the database, so keep-alive pings never wake the database up."""
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
async def health_db(db: DB) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
