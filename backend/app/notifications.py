"""Web Push delivery and the "is this user due a notification?" rules."""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from .config import get_settings
from .models import PushSubscription, User, Word
from .srs import as_utc

log = logging.getLogger(__name__)

# A sender takes (subscription, payload) and raises WebPushException on failure.
Sender = Callable[[PushSubscription, dict], None]


def build_payload(user: User, word: Word) -> dict:
    title = f"📒 {word.text}"
    if word.phonetic:
        title += f"  {word.phonetic}"
    if user.quiz_notifications:
        body = "Do you remember what it means? Tap to check."
    else:
        body = word.meaning
        if word.example:
            body += f"\n\ne.g. {word.example}"
    return {"title": title, "body": body, "url": f"/#/quiz?word={word.id}", "tag": f"word-{word.id}"}


def webpush_sender(sub: PushSubscription, payload: dict) -> None:
    s = get_settings()
    webpush(
        subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
        data=json.dumps(payload),
        vapid_private_key=s.vapid_private_key,
        vapid_claims={"sub": s.vapid_subject},
        ttl=60 * 60,
    )


def send_to_user(db: Session, user: User, payload: dict, sender: Sender | None = None) -> int:
    """Send to every device of the user. Returns how many deliveries succeeded.
    Subscriptions the push service reports as gone (404/410) are removed."""
    sender = sender or webpush_sender
    delivered = 0
    for sub in list(user.subscriptions):
        try:
            sender(sub, payload)
            delivered += 1
        except WebPushException as exc:
            code = getattr(exc.response, "status_code", None)
            if code in (404, 410):
                log.info("Removing expired subscription %s", sub.id)
                db.delete(sub)
            else:
                log.warning("Push failed for user %s: %s", user.id, exc)
    db.commit()
    return delivered


def is_due(user: User, now: datetime) -> bool:
    """Apply the user's schedule: pause, active days, active hours, frequency, daily limit."""
    paused = as_utc(user.paused_until)
    if paused and paused > now:
        return False

    local = now.astimezone(ZoneInfo(user.timezone))
    if str(local.weekday()) not in (user.active_days or ""):
        return False
    if not (user.active_start_hour <= local.hour < user.active_end_hour):
        return False

    today = local.date().isoformat()
    sent_today = user.notified_today if user.notified_today_date == today else 0
    if sent_today >= user.daily_limit:
        return False

    last = as_utc(user.last_notified_at)
    # Small grace period so a 15-minute scheduler doesn't skip a whole interval.
    if last and now - last < timedelta(minutes=user.notify_every_minutes) - timedelta(minutes=5):
        return False
    return True


def record_sent(user: User, now: datetime) -> None:
    today = now.astimezone(ZoneInfo(user.timezone)).date().isoformat()
    if user.notified_today_date != today:
        user.notified_today_date, user.notified_today = today, 0
    user.notified_today += 1
    user.last_notified_at = now


def utcnow() -> datetime:
    return datetime.now(UTC)
