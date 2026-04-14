import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.limiter import limiter
from app.models import LoginRequest, TokenResponse, UserRegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_RATE_REGISTER = os.getenv("RATE_LIMIT_REGISTER", "5/minute")
_RATE_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "10/minute")


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(_RATE_REGISTER)
async def register(
    request: Request,
    body: UserRegisterRequest,
    conn: AsyncConnection = Depends(get_db),
):
    result = await conn.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email},
    )
    if result.fetchone():
        raise HTTPException(status_code=409, detail="email already registered")

    result = await conn.execute(
        text("""
            INSERT INTO users (name, email, password)
            VALUES (:name, :email, :pw)
            RETURNING *
        """),
        {"name": body.name, "email": body.email, "pw": hash_password(body.password)},
    )
    return dict(result.fetchone()._mapping)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_RATE_LOGIN)
async def login(
    request: Request,
    body: LoginRequest,
    conn: AsyncConnection = Depends(get_db),
):
    result = await conn.execute(
        text("SELECT * FROM users WHERE email = :email"),
        {"email": body.email},
    )
    row = result.fetchone()
    if not row or not verify_password(body.password, row._mapping["password"]):
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = create_token(str(row._mapping["id"]), row._mapping["email"])
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    result = await conn.execute(
        text("SELECT * FROM users WHERE id = :uid"),
        {"uid": current_user["user_id"]},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return dict(row._mapping)
