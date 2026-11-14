"""Shared logic used by the API and the notification scheduler."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Category, User, Word
from .srs import as_utc


def notifiable(word: Word) -> bool:
    """A word is sent as a notification if it has no categories,
    or if at least one of its categories has notifications switched on."""
    return not word.categories or any(c.notify for c in word.categories)


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

    Overdue words come first (oldest due date first). If nothing is due,
    the word that will be due soonest is used, so there is always something
    to practise.
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
        words = [w for w in words if notifiable(w)]
    if exclude_id is not None and len(words) > 1:
        words = [w for w in words if w.id != exclude_id]
    if not words:
        return None
    words.sort(key=lambda w: (as_utc(w.due_at), w.times_shown))
    return words[0]


def user_categories(db: Session, user: User, ids: list[int]) -> list[Category]:
    if not ids:
        return []
    return list(
        db.scalars(select(Category).where(Category.user_id == user.id, Category.id.in_(ids)))
    )
