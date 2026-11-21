"""Demo controls: the demo clock, "Simulate next day" and "Reset demo"."""

from fastapi import APIRouter

from app.deps import DB, ManagerUser, StaffUser
from app.schemas import SimulationResult
from app.seed import reset_demo
from app.services import demo_state
from app.simulation import simulate_next_day

router = APIRouter(tags=["demo"])


@router.get("/demo/clock")
async def clock(db: DB) -> dict:
    state = await demo_state(db)
    return {"demo_now": state.demo_now, "simulated_days": state.simulated_days}


@router.post("/simulate/next-day", response_model=SimulationResult)
async def next_day(db: DB, _: StaffUser) -> SimulationResult:
    return await simulate_next_day(db)


@router.post("/demo/reset")
async def reset(db: DB, _: ManagerUser) -> dict:
    await reset_demo(db)
    state = await demo_state(db)
    return {"demo_now": state.demo_now, "message": "Demo data was reset to the starting point."}
