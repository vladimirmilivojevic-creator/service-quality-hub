from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.models import Plant, User
from app.schemas import Me, Token
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(db: DB, form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    user = await db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return Token(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=Me)
async def me(db: DB, user: CurrentUser) -> Me:
    plant = await db.get(Plant, user.plant_id) if user.plant_id else None
    return Me(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        title=user.title,
        role=user.role,
        plant_id=user.plant_id,
        plant_code=plant.code if plant else None,
        provider_id=user.provider_id,
    )
