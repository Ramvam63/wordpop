import os
import sys
from pathlib import Path

import pytest

# Use an isolated in-memory database and no real dictionary calls during tests.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-1234"
os.environ["ADMIN_EMAILS"] = "admin@example.com"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import dictionary  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

FAKE_DICTIONARY = {
    "serendipity": {
        "meaning": "finding something good without looking for it",
        "example": "Meeting her was pure serendipity.",
        "phonetic": "/ˌsɛrənˈdɪpɪti/",
        "audio_url": "",
        "part_of_speech": "noun",
    }
}


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(dictionary, "lookup", lambda w: FAKE_DICTIONARY.get(w.lower()))
    yield factory
    app.dependency_overrides.clear()


@pytest.fixture()
def client(session_factory):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user_client(client):
    r = client.post(
        "/api/auth/signup",
        json={"email": "learner@example.com", "password": "secret123", "timezone": "America/Toronto"},
    )
    assert r.status_code == 201, r.text
    return client
