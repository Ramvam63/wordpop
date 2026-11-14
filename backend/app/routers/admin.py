"""Product analytics for the app owner: sign-ups, activity and retention.

Only emails listed in ADMIN_EMAILS can call these endpoints.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PushSubscription, ReviewEvent, User, Word
from ..security import require_admin
from ..srs import as_utc

router = APIRouter(prefix="/api/admin", tags=["admin"])


def retention(users: list[User], days: int, now: datetime) -> int | None:
    """% of users (who signed up at least `days` ago) that were active `days`+ after signing up."""
    eligible = [u for u in users if now - as_utc(u.created_at) >= timedelta(days=days)]
    if not eligible:
        return None
    kept = [
        u
        for u in eligible
        if u.last_active_at and as_utc(u.last_active_at) - as_utc(u.created_at) >= timedelta(days=days)
    ]
    return round(100 * len(kept) / len(eligible))


@router.get("/stats")
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    users = list(db.scalars(select(User)))
    week_ago = now - timedelta(days=7)
    word_counts = dict(db.execute(select(Word.user_id, func.count()).group_by(Word.user_id)).all())
    with_push = db.scalar(select(func.count(func.distinct(PushSubscription.user_id))))

    return {
        "users_total": len(users),
        "signups_last_7_days": sum(1 for u in users if as_utc(u.created_at) >= week_ago),
        "active_last_7_days": sum(
            1 for u in users if u.last_active_at and as_utc(u.last_active_at) >= week_ago
        ),
        "users_with_notifications": with_push or 0,
        "users_with_10_plus_words": sum(1 for c in word_counts.values() if c >= 10),
        "avg_words_per_user": round(sum(word_counts.values()) / len(users), 1) if users else 0,
        "reviews_last_7_days": db.scalar(
            select(func.count()).select_from(ReviewEvent).where(ReviewEvent.created_at >= week_ago)
        ),
        "retention_day_1_pct": retention(users, 1, now),
        "retention_day_7_pct": retention(users, 7, now),
        "retention_day_28_pct": retention(users, 28, now),
    }
