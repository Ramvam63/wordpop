"""Natural-sounding voices, generated on the server with Azure AI Speech (neural voices).

Four English voices - American and Canadian, a woman and a man. Each clip is generated once
and stored in the database (TtsClip), so repeat listens are instant and cost nothing.
Without AZURE_SPEECH_KEY the feature is off and the app falls back to the phone's own voices.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape, quoteattr

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import TtsClip

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Voice:
    id: str
    azure_name: str
    lang: str
    label: str
    accent: str
    gender: str


VOICES = {
    v.id: v
    for v in (
        Voice("ca-female", "en-CA-ClaraNeural", "en-CA", "Clara", "Canadian", "woman"),
        Voice("ca-male", "en-CA-LiamNeural", "en-CA", "Liam", "Canadian", "man"),
        Voice("us-female", "en-US-AvaNeural", "en-US", "Ava", "American", "woman"),
        Voice("us-male", "en-US-AndrewNeural", "en-US", "Andrew", "American", "man"),
    )
}
DEFAULT_VOICE = "ca-female"
MAX_CHARS = 600


class TtsError(Exception):
    pass


def enabled() -> bool:
    s = get_settings()
    return bool(s.azure_speech_key and s.azure_speech_region)


def clip_key(voice_id: str, text: str) -> str:
    return hashlib.sha256(f"{voice_id}\n{text}".encode()).hexdigest()


def synthesize(voice: Voice, text: str) -> bytes:
    """Call Azure and return MP3 bytes."""
    s = get_settings()
    ssml = (
        f"<speak version='1.0' xml:lang={quoteattr(voice.lang)}>"
        f"<voice name={quoteattr(voice.azure_name)}><prosody rate='-5%'>{escape(text)}</prosody></voice>"
        "</speak>"
    )
    try:
        r = httpx.post(
            f"https://{s.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1",
            content=ssml.encode(),
            headers={
                "Ocp-Apim-Subscription-Key": s.azure_speech_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                "User-Agent": "WordPop",
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise TtsError(f"speech service unreachable: {exc}") from exc
    if r.status_code != 200 or not r.content:
        raise TtsError(f"speech service answered {r.status_code}")
    return r.content


# Tests replace this to avoid real network calls.
_synthesize = synthesize


def get_clip(db: Session, voice_id: str, text: str, user_id: int | None = None) -> bytes:
    """Return the recording for this text, generating (and storing) it the first time."""
    voice = VOICES[voice_id]
    key = clip_key(voice_id, text)
    clip = db.get(TtsClip, key)
    if clip:
        return clip.audio

    limit = get_settings().tts_daily_limit
    since = datetime.now(UTC) - timedelta(days=1)
    made_today = db.scalar(
        select(func.count()).select_from(TtsClip)
        .where(TtsClip.created_by == user_id, TtsClip.created_at >= since)
    )
    if user_id is not None and made_today >= limit:
        raise TtsError("daily limit reached")

    audio = _synthesize(voice, text)
    db.add(TtsClip(key=key, voice=voice_id, audio=audio, created_by=user_id))
    db.commit()
    return audio
