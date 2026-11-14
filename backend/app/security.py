"""Password hashing, session tokens and the current-user dependency."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User

COOKIE_NAME = "wordpop_session"
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "ver": user.session_version or 0,
        "iat": now,
        "exp": now + timedelta(days=s.session_days),
    }
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM)


def _read_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _read_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        version = int(payload.get("ver", 0))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again") from None
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if version != (user.session_version or 0):
        # The password was changed after this session started (e.g. via "Forgot password?").
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in again")

    # Track activity (at most once every 10 minutes) for retention analytics.
    now = datetime.now(UTC)
    last = user.last_active_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if last is None or now - last > timedelta(minutes=10):
        user.last_active_at = now
        db.commit()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.email.lower() not in get_settings().admin_emails:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user
