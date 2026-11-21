"""Natural voices: the list for Settings, and the recordings themselves."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from .. import tts
from ..db import get_db
from ..models import User
from ..security import get_current_user

router = APIRouter(prefix="/api/tts", tags=["voices"])


def chosen_voice(user: User) -> str:
    return user.voice if user.voice == "device" or user.voice in tts.VOICES else tts.DEFAULT_VOICE


@router.get("/voices")
def list_voices(user: User = Depends(get_current_user)):
    return {
        "available": tts.enabled(),
        "selected": chosen_voice(user),
        "default": tts.DEFAULT_VOICE,
        "voices": [
            {"id": v.id, "label": v.label, "accent": v.accent, "gender": v.gender, "lang": v.lang}
            for v in tts.VOICES.values()
        ],
    }


@router.get("")
def speak(
    text: str = Query(min_length=1, max_length=tts.MAX_CHARS),
    voice: str = tts.DEFAULT_VOICE,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if voice not in tts.VOICES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown voice")
    if not tts.enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Natural voices are not set up")
    try:
        audio = tts.get_clip(db, voice, text.strip(), user_id=user.id)
    except tts.TtsError as exc:
        status_code = 429 if "limit" in str(exc) else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code, "Couldn't make the recording right now") from exc
    # The same voice + text always gives the same recording, so the browser may keep it.
    return Response(audio, media_type="audio/mpeg",
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})
