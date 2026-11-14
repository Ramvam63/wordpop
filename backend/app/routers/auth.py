from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, SignupIn, UserOut
from ..security import (
    COOKIE_NAME,
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id),
        max_age=s.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=s.secure_cookies,
    )


def _out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.is_admin = user.email.lower() in get_settings().admin_emails
    return out


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(data: SignupIn, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    tz = data.timezone if data.timezone in available_timezones() else "UTC"
    user = User(email=email, password_hash=hash_password(data.password), timezone=tz)
    db.add(user)
    db.commit()
    _set_session(response, user)
    return _out(user)


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    _set_session(response, user)
    return _out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _out(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete the account and all its data (words, categories, subscriptions)."""
    db.delete(user)
    db.commit()
    response.delete_cookie(COOKIE_NAME)
