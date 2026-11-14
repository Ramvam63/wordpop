import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db import init_db
from app.models import PasswordResetToken
from app.routers import auth


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "send_email", lambda to, subject, text, html=None: sent.append((to, text)))
    return sent


def token_from(outbox) -> str:
    return re.search(r"token=([\w-]+)", outbox[-1][1]).group(1)


def test_forgot_password_sends_a_link(user_client, outbox):
    r = user_client.post("/api/auth/forgot-password", json={"email": "LEARNER@example.com"})
    assert r.status_code == 200
    assert len(outbox) == 1 and outbox[0][0] == "learner@example.com"
    assert "/#/reset?token=" in outbox[0][1]


def test_unknown_email_gets_the_same_answer_and_no_email(client, outbox):
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200 and "If an account exists" in r.json()["message"]
    assert outbox == []


def test_reset_changes_password_and_signs_out_old_sessions(client, outbox):
    client.post("/api/auth/signup", json={"email": "a@example.com", "password": "old-password"})
    old_cookie = client.cookies.get("wordpop_session")

    client.post("/api/auth/forgot-password", json={"email": "a@example.com"})
    r = client.post("/api/auth/reset-password", json={"token": token_from(outbox), "password": "new-password"})
    assert r.status_code == 200 and r.json()["email"] == "a@example.com"
    assert client.get("/api/auth/me").status_code == 200  # signed in with the new session

    # The session from before the reset no longer works
    client.cookies.clear()
    client.cookies.set("wordpop_session", old_cookie)
    assert client.get("/api/auth/me").status_code == 401

    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "old-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "new-password"}).status_code == 200


def test_reset_link_works_only_once(user_client, outbox):
    user_client.post("/api/auth/forgot-password", json={"email": "learner@example.com"})
    token = token_from(outbox)
    assert user_client.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-1"}).status_code == 200
    assert user_client.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-2"}).status_code == 400


def test_expired_link_is_rejected(user_client, outbox, session_factory):
    user_client.post("/api/auth/forgot-password", json={"email": "learner@example.com"})
    with session_factory() as db:
        rec = db.query(PasswordResetToken).one()
        rec.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    r = user_client.post("/api/auth/reset-password", json={"token": token_from(outbox), "password": "brand-new-1"})
    assert r.status_code == 400


def test_only_a_hash_of_the_token_is_stored(user_client, outbox, session_factory):
    user_client.post("/api/auth/forgot-password", json={"email": "learner@example.com"})
    with session_factory() as db:
        assert db.query(PasswordResetToken).one().token_hash != token_from(outbox)


def test_reset_emails_are_rate_limited(user_client, outbox):
    for _ in range(5):
        user_client.post("/api/auth/forgot-password", json={"email": "learner@example.com"})
    assert len(outbox) == auth.MAX_RESET_EMAILS_PER_HOUR


def test_existing_database_gets_new_columns():
    """A database created before this feature (no password_changed_at) is upgraded on start."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255), password_hash VARCHAR(255))"))
    init_db(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert "password_changed_at" in columns
    assert inspect(engine).has_table("password_reset_tokens")
