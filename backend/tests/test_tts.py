import pytest

from app import tts
from app.config import get_settings


@pytest.fixture()
def azure(monkeypatch):
    """Pretend Azure is configured; record what would be sent instead of calling it."""
    calls = []

    def fake(voice, text):
        calls.append((voice.azure_name, text))
        return b"ID3-fake-mp3"

    s = get_settings()
    monkeypatch.setattr(s, "azure_speech_key", "test-key")
    monkeypatch.setattr(s, "azure_speech_region", "canadacentral")
    monkeypatch.setattr(tts, "_synthesize", fake)
    return calls


def test_voices_list_and_default(user_client):
    r = user_client.get("/api/tts/voices").json()
    assert r["available"] is False and r["selected"] == "ca-female"
    assert {(v["accent"], v["gender"]) for v in r["voices"]} == {
        ("Canadian", "woman"), ("Canadian", "man"), ("American", "woman"), ("American", "man"),
    }


def test_without_azure_the_app_falls_back(user_client):
    assert user_client.get("/api/tts", params={"text": "Hello"}).status_code == 503


def test_clip_is_generated_once_then_reused(user_client, azure):
    for _ in range(3):
        r = user_client.get("/api/tts", params={"text": "Obviously", "voice": "ca-male"})
        assert r.status_code == 200 and r.content == b"ID3-fake-mp3"
        assert r.headers["content-type"] == "audio/mpeg"
    assert azure == [("en-CA-LiamNeural", "Obviously")]  # Azure called only once

    user_client.get("/api/tts", params={"text": "Obviously", "voice": "us-female"})
    assert azure[-1] == ("en-US-AvaNeural", "Obviously")  # another voice is another clip


def test_bad_requests(user_client, azure):
    assert user_client.get("/api/tts", params={"text": "Hi", "voice": "robot"}).status_code == 404
    assert user_client.get("/api/tts", params={"text": "x" * 601}).status_code == 422
    assert azure == []


def test_daily_limit(user_client, azure, monkeypatch):
    monkeypatch.setattr(get_settings(), "tts_daily_limit", 2)
    codes = [user_client.get("/api/tts", params={"text": f"word {i}"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]
    assert user_client.get("/api/tts", params={"text": "word 0"}).status_code == 200  # cached: free


def test_voice_choice_is_saved(user_client):
    assert user_client.put("/api/me/settings", json={"voice": "us-male"}).status_code == 200
    assert user_client.get("/api/tts/voices").json()["selected"] == "us-male"
    assert user_client.put("/api/me/settings", json={"voice": "robot"}).status_code == 422


def test_ssml_is_escaped(monkeypatch):
    sent = {}

    class Resp:
        status_code, content = 200, b"mp3"

    monkeypatch.setattr(get_settings(), "azure_speech_key", "k")
    monkeypatch.setattr(get_settings(), "azure_speech_region", "eastus")
    monkeypatch.setattr(tts.httpx, "post", lambda url, **kw: sent.update(url=url, **kw) or Resp())
    tts.synthesize(tts.VOICES["us-female"], "Tom & Jerry <3")
    assert sent["url"] == "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1"
    assert b"Tom &amp; Jerry &lt;3" in sent["content"] and b"en-US-AvaNeural" in sent["content"]
