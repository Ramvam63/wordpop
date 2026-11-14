"""Spaced repetition using a simple Leitner box system.

Each word sits in a box 0..6. Answering "I knew it" moves it up a box and
pushes the next review further away; "I forgot" sends it back to box 0 so it
comes back soon.
"""

from datetime import UTC, datetime, timedelta

from .models import Word

# Wait time before a word is due again, per box.
INTERVALS = [
    timedelta(minutes=10),
    timedelta(days=1),
    timedelta(days=2),
    timedelta(days=4),
    timedelta(days=7),
    timedelta(days=15),
    timedelta(days=30),
]
MAX_BOX = len(INTERVALS) - 1
MASTERED_BOX = 5


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tz info; treat naive datetimes as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def apply_answer(word: Word, knew: bool, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if knew:
        word.box = min(word.box + 1, MAX_BOX)
        word.times_correct += 1
    else:
        word.box = 0
        word.times_wrong += 1
    word.due_at = now + INTERVALS[word.box]
    word.last_reviewed_at = now


def is_mastered(word: Word) -> bool:
    return word.box >= MASTERED_BOX
