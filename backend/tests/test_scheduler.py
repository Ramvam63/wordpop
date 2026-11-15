from datetime import UTC, datetime, timedelta

from pywebpush import WebPushException

from app.models import Category, PushSubscription, User, Word
from app.notifications import build_payload, is_due
from app.scheduler import run_once
from app.srs import INTERVALS, apply_answer

# Wednesday 2026-11-11 15:00 UTC == 10:00 in Toronto
WED_10AM_TORONTO = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)


def make_user(**kw) -> User:
    defaults = dict(
        email="u@example.com",
        password_hash="x",
        timezone="America/Toronto",
        notify_every_minutes=60,
        active_start_hour=9,
        active_end_hour=21,
        active_days="0123456",
        daily_limit=10,
        notified_today=0,
        quiz_notifications=False,
    )
    defaults.update(kw)
    return User(**defaults)


def test_is_due_respects_active_hours_in_user_timezone():
    u = make_user()
    assert is_due(u, WED_10AM_TORONTO)
    # 13:00 UTC is 08:00 in Toronto -> before the window
    assert not is_due(u, WED_10AM_TORONTO.replace(hour=13))
    # same instant but a user in Tokyo (00:00 there) -> outside the window
    assert not is_due(make_user(timezone="Asia/Tokyo"), WED_10AM_TORONTO)


def test_is_due_respects_days_pause_frequency_and_limit():
    now = WED_10AM_TORONTO
    assert not is_due(make_user(active_days="56"), now)  # weekends only, today is Wednesday
    assert not is_due(make_user(paused_until=now + timedelta(hours=2)), now)
    assert not is_due(make_user(last_notified_at=now - timedelta(minutes=20)), now)
    assert is_due(make_user(last_notified_at=now - timedelta(minutes=60)), now)
    assert not is_due(make_user(notified_today=10, notified_today_date="2026-11-11"), now)
    assert is_due(make_user(notified_today=10, notified_today_date="2026-11-10"), now)  # new day


def test_spaced_repetition_boxes():
    w = Word(text="x", meaning="y", box=0, times_correct=0, times_wrong=0)
    now = WED_10AM_TORONTO
    apply_answer(w, True, now)
    assert w.box == 1 and w.due_at == now + INTERVALS[1]
    apply_answer(w, True, now)
    assert w.box == 2
    apply_answer(w, False, now)
    assert w.box == 0 and w.due_at == now + INTERVALS[0]


def test_quiz_notification_hides_meaning():
    w = Word(id=1, text="brave", meaning="not afraid", example="", phonetic="")
    assert "not afraid" in build_payload(make_user(), w)["body"]
    assert "not afraid" not in build_payload(make_user(quiz_notifications=True), w)["body"]


def _seed(db, **user_kw):
    user = make_user(**user_kw)
    db.add(user)
    db.flush()
    on = Category(user_id=user.id, name="IELTS", notify=True)
    off = Category(user_id=user.id, name="Movies", notify=False)
    db.add_all([on, off])
    db.add(Word(user_id=user.id, text="muted", meaning="m", categories=[off],
                due_at=WED_10AM_TORONTO - timedelta(days=9)))
    db.add(Word(user_id=user.id, text="ielts", meaning="i", categories=[on],
                due_at=WED_10AM_TORONTO - timedelta(days=1)))
    db.add(PushSubscription(user_id=user.id, endpoint="https://push/1", p256dh="k", auth="a"))
    db.commit()
    return user


def test_run_once_sends_only_words_from_enabled_categories(session_factory):
    sent = []
    with session_factory() as db:
        _seed(db)
        stats = run_once(db, now=WED_10AM_TORONTO, sender=lambda sub, p: sent.append(p))
        assert stats["sent"] == 1
        assert sent[0]["title"].startswith("📒 ielts")  # the more overdue "muted" word is skipped
        user = db.query(User).one()
        assert user.notified_today == 1

        # Running again 15 minutes later should not send (frequency is 60 min)
        stats = run_once(db, now=WED_10AM_TORONTO + timedelta(minutes=15), sender=lambda s, p: sent.append(p))
        assert stats["sent"] == 0 and len(sent) == 1


def test_expired_subscription_is_removed(session_factory):
    class Gone:
        status_code = 410

    def failing_sender(sub, payload):
        raise WebPushException("gone", response=Gone())

    with session_factory() as db:
        _seed(db)
        stats = run_once(db, now=WED_10AM_TORONTO, sender=failing_sender)
        assert stats["sent"] == 0
        assert db.query(PushSubscription).count() == 0
