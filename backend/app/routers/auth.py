import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import available_timezones

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..mailer import password_reset_email, send_email
from ..models import PasswordResetToken, User
from ..schemas import ForgotPasswordIn, LoginIn, ResetPasswordIn, SignupIn, UserOut
from ..security import (
    COOKIE_NAME,
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("wordpop.auth")
MAX_RESET_EMAILS_PER_HOUR = 3


def _set_session(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        create_token(user),
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


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _send_reset_email(to: str, link: str, minutes: int) -> None:
    try:
        send_email(to, *password_reset_email(link, minutes))
    except Exception:  # never leak SMTP problems to the requester
        log.exception("Could not send password reset email")


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordIn, background: BackgroundTasks, db: Session = Depends(get_db)
):
    """Email a one-time reset link. Always answers the same way, so nobody can use
    this form to find out which emails have an account."""
    answer = {"ok": True, "message": "If an account exists for that email, we've sent a reset link."}
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user:
        return answer

    s = get_settings()
    now = datetime.now(UTC)
    recent = db.scalar(
        select(func.count())
        .select_from(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at >= now - timedelta(hours=1),
        )
    )
    if recent >= MAX_RESET_EMAILS_PER_HOUR:
        return answer

    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=now + timedelta(minutes=s.reset_token_minutes),
        )
    )
    db.commit()
    link = f"{s.app_url}/#/reset?token={token}"
    background.add_task(_send_reset_email, user.email, link, s.reset_token_minutes)
    return answer


@router.post("/reset-password", response_model=UserOut)
def reset_password(data: ResetPasswordIn, response: Response, db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(data.token))
    )
    expires = record.expires_at if record else None
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if not record or record.used_at is not None or expires < now:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This reset link is invalid or has expired. Please ask for a new one.",
        )

    user = db.get(User, record.user_id)
    user.password_hash = hash_password(data.password)
    user.password_changed_at = now
    user.session_version = (user.session_version or 0) + 1  # signs out every other device
    # Use up this link and any other unused links for the same account.
    for other in db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )
    ):
        other.used_at = now
    db.commit()
    _set_session(response, user)
    return _out(user)
