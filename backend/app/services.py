"""Shared logic used by the API and the notification scheduler."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Category, User, Word
from .srs import as_utc


def uncategorized_on(user: User) -> bool:
    return user.notify_uncategorized is not False  # NULL (older accounts) counts as on


def notifiable(word: Word, user: User) -> bool:
    """A word is sent as a notification if at least one of its categories has
    notifications switched on, or - for a word with no category - if the user's
    "No category" switch is on."""
    if not word.categories:
        return uncategorized_on(user)
    return any(c.notify for c in word.categories)


def pick_next_word(
    db: Session,
    user: User,
    *,
    only_notifiable: bool = False,
    category_id: int | None = None,
    exclude_id: int | None = None,
    now: datetime | None = None,
) -> Word | None:
    """Choose the most useful word to review next.

    In the quiz: overdue words first (oldest due date first); if nothing is due,
    the word that will be due soonest, so there is always something to practise.

    For notifications (only_notifiable=True) the reminders rotate:
      1. words that are due for review come before words that aren't;
      2. among those, the word sent longest ago comes first (never-sent words first);
      3. ties are broken by the oldest due date.
    So every due word gets its turn, and answering in the quiz still decides
    when a word becomes due again.
    """
    now = now or datetime.now(UTC)
    stmt = (
        select(Word)
        .where(Word.user_id == user.id)
        .options(selectinload(Word.categories))
    )
    if category_id is not None:
        stmt = stmt.where(Word.categories.any(Category.id == category_id))
    words = list(db.scalars(stmt))
    if only_notifiable:
        words = [w for w in words if notifiable(w, user)]
    if exclude_id is not None and len(words) > 1:
        words = [w for w in words if w.id != exclude_id]
    if not words:
        return None
    if only_notifiable:
        never = datetime.min.replace(tzinfo=UTC)
        words.sort(key=lambda w: (
            as_utc(w.due_at) > now,               # due words first
            as_utc(w.last_notified_at) or never,  # least recently sent first
            as_utc(w.due_at),
        ))
    else:
        words.sort(key=lambda w: (as_utc(w.due_at), w.times_shown))
    return words[0]


def user_categories(db: Session, user: User, ids: list[int]) -> list[Category]:
    if not ids:
        return []
    return list(
        db.scalars(select(Category).where(Category.user_id == user.id, Category.id.in_(ids)))
    )
