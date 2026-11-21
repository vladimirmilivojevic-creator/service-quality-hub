"""FastAPI dependencies: database session, current user and role checks (RBAC)."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(db: DB, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    try:
        payload = decode_access_token(token)
        user = await db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    """Dependency factory: allow only users with one of the given roles."""

    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role is not allowed to do this")
        return user

    return checker


# Who may do what (see the README role table):
StaffUser = Annotated[User, Depends(require_roles("sqm", "plant_lead", "management"))]  # read everything
EditorUser = Annotated[User, Depends(require_roles("sqm", "plant_lead"))]  # change tickets, problems, improvements
ManagerUser = Annotated[User, Depends(require_roles("sqm"))]  # catalogue, SLA policy, import, reset


def ensure_plant_scope(user: User, plant_id: int | None) -> None:
    """A plant IT lead may only change records of their own plant."""
    if user.role == "plant_lead" and plant_id != user.plant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Plant IT leads can only change records of their own plant")
