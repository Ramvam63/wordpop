"""Send due vocabulary notifications to every user.

Run once (e.g. every 15 minutes from GitHub Actions or cron):
    python -m app.scheduler

Or keep it running in a loop (e.g. on a server):
    python -m app.scheduler --loop
"""

import argparse
import logging
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import get_settings
from .db import SessionLocal, init_db
from .models import PushSubscription, User
from .notifications import Sender, build_payload, is_due, record_sent, send_to_user, utcnow
from .services import pick_next_word

log = logging.getLogger("wordpop.scheduler")


def run_once(db: Session, now: datetime | None = None, sender: Sender | None = None) -> dict:
    now = now or utcnow()
    users = db.scalars(
        select(User)
        .where(User.subscriptions.any(PushSubscription.id.isnot(None)))
        .options(selectinload(User.subscriptions))
    ).all()

    stats = {"checked": len(users), "sent": 0, "skipped": 0}
    for user in users:
        if not is_due(user, now):
            stats["skipped"] += 1
            continue
        word = pick_next_word(db, user, only_notifiable=True, now=now)
        if word is None:
            stats["skipped"] += 1
            continue
        if send_to_user(db, user, build_payload(user, word), sender=sender):
            word.times_shown += 1
            record_sent(user, now)
            stats["sent"] += 1
        db.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Send due WordPop notifications")
    parser.add_argument("--loop", action="store_true", help="keep running every --interval minutes")
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not get_settings().vapid_private_key:
        raise SystemExit("VAPID_PRIVATE_KEY is not set - run scripts/generate_vapid_keys.py first")
    init_db()

    while True:
        with SessionLocal() as db:
            log.info("Run finished: %s", run_once(db))
        if not args.loop:
            break
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
