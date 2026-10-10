"""NOVA — Authentication API Routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.config import get_settings
from app.database.database import get_db_session
from app.database.models import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Request / Response schemas ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(user_id: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="nova_session",
        value=token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        max_age=settings.jwt_expire_hours * 3600,
        path="/",
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse)
async def register(body: RegisterRequest, response: Response):
    """Create a new user account."""
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if not body.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")

    async with get_db_session() as session:
        # Check for existing user
        existing = await session.execute(select(User).where(User.email == body.email.lower().strip()))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="An account with this email already exists")

        user = User(
            id=str(uuid.uuid4()),
            name=body.name.strip(),
            email=body.email.lower().strip(),
            password_hash=_hash_password(body.password),
        )
        session.add(user)

    # Issue JWT cookie
    token = _create_token(user.id)
    _set_cookie(response, token)

    logger.info("user_registered", user_id=user.id, email=user.email)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at.isoformat() if user.created_at else datetime.now(timezone.utc).isoformat(),
    )


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, response: Response):
    """Authenticate and issue a session cookie."""
    async with get_db_session() as session:
        result = await session.execute(select(User).where(User.email == body.email.lower().strip()))
        user = result.scalar_one_or_none()

    if not user or not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(user.id)
    _set_cookie(response, token)

    logger.info("user_logged_in", user_id=user.id)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.post("/logout")
async def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie("nova_session", path="/")
    return {"ok": True}


@router.get("/me")
async def get_me(request: Request):
    """Return the currently authenticated user, or 401."""
    token = request.cookies.get("nova_session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = _decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    async with get_db_session() as session:
        result = await session.execute(select(User).where(User.id == payload["sub"]))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )
