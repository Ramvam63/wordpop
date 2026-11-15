from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import PushSubscription, User
from ..notifications import build_payload, send_to_user
from ..schemas import PushSubscriptionIn
from ..security import get_current_user
from ..services import pick_next_word

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/public-key")
def public_key():
    key = get_settings().vapid_public_key
    if not key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Push is not configured on the server")
    return {"key": key}


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(
    data: PushSubscriptionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    sub = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))
    if sub:  # same device re-subscribing, possibly after switching accounts
        sub.user_id, sub.p256dh, sub.auth = user.id, data.keys.p256dh, data.keys.auth
    else:
        db.add(
            PushSubscription(
                user_id=user.id, endpoint=data.endpoint, p256dh=data.keys.p256dh, auth=data.keys.auth
            )
        )
    db.commit()
    return {"ok": True}


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    data: PushSubscriptionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    sub = db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == data.endpoint, PushSubscription.user_id == user.id
        )
    )
    if sub:
        db.delete(sub)
        db.commit()


@router.post("/test")
def send_test(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send one word right now, ignoring the schedule - handy after enabling notifications."""
    if not user.subscriptions:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Notifications are not enabled on any device")
    word = pick_next_word(db, user, only_notifiable=True)
    payload = build_payload(user, word) if word else {
        "title": "WordPop is ready 🎉",
        "body": "Add your first word and it will show up here.",
        "url": "/#/words",
    }
    delivered = send_to_user(db, user, payload)
    if word and delivered:
        word.times_shown += 1
        word.last_notified_at = datetime.now(UTC)
        db.commit()
    return {"delivered": delivered}
