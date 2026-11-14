"""Notification settings, pause, and the progress page."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ReviewEvent, User, Word
from ..schemas import PauseIn, SettingsIn, SettingsOut
from ..security import get_current_user
from ..srs import MASTERED_BOX, as_utc

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/settings", response_model=SettingsOut)
def get_settings_(user: User = Depends(get_current_user)):
    return user


@router.put("/settings", response_model=SettingsOut)
def update_settings(
    data: SettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    return user


@router.post("/pause", response_model=SettingsOut)
def pause(data: PauseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.paused_until = (
        datetime.now(UTC) + timedelta(hours=data.hours) if data.hours else None
    )
    db.commit()
    return user


def compute_streak(days: set[date], today: date) -> int:
    """Consecutive days with at least one review, ending today (or yesterday)."""
    if today not in days:
        today -= timedelta(days=1)
    streak = 0
    while today in days:
        streak += 1
        today -= timedelta(days=1)
    return streak


@router.get("/progress")
def progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tz = ZoneInfo(user.timezone)
    now = datetime.now(UTC)
    today = now.astimezone(tz).date()

    words = list(db.scalars(select(Word).where(Word.user_id == user.id)))
    events = list(db.scalars(select(ReviewEvent).where(ReviewEvent.user_id == user.id)))

    local_days = [as_utc(e.created_at).astimezone(tz).date() for e in events]
    last7 = [today - timedelta(days=i) for i in range(6, -1, -1)]
    per_day = {d: 0 for d in last7}
    for d in local_days:
        if d in per_day:
            per_day[d] += 1

    correct = sum(1 for e in events if e.knew)
    hardest = sorted((w for w in words if w.times_wrong), key=lambda w: -w.times_wrong)[:5]

    return {
        "total_words": len(words),
        "mastered": sum(1 for w in words if w.box >= MASTERED_BOX),
        "learning": sum(1 for w in words if 0 < w.box < MASTERED_BOX),
        "new": sum(1 for w in words if w.box == 0),
        "due_now": sum(1 for w in words if as_utc(w.due_at) <= now),
        "reviews_total": len(events),
        "accuracy": round(100 * correct / len(events)) if events else None,
        "streak_days": compute_streak(set(local_days), today),
        "last_7_days": [{"date": d.isoformat(), "reviews": per_day[d]} for d in last7],
        "hardest": [
            {"id": w.id, "text": w.text, "times_wrong": w.times_wrong} for w in hardest
        ],
    }
