from app.config import get_settings
from app.routers import tasks


def test_task_url_needs_the_secret(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cron_secret", "s3cret-value")
    calls = []
    monkeypatch.setattr(tasks, "_run_scheduler", lambda: calls.append(1))
    assert client.get("/api/tasks/send-notifications?key=wrong").status_code == 404
    assert client.get("/api/tasks/send-notifications").status_code == 422
    assert client.get("/api/tasks/send-notifications?key=s3cret-value").status_code == 200
    assert client.head("/api/tasks/send-notifications?key=s3cret-value").status_code == 200
    assert calls == [1, 1]


def test_task_url_is_off_without_a_secret(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cron_secret", "")
    assert client.get("/api/tasks/send-notifications?key=").status_code == 404
