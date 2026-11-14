"""Auto-fill meaning, example and pronunciation from the free Dictionary API."""

import logging
from urllib.parse import quote

import httpx

from .config import get_settings

log = logging.getLogger(__name__)


def lookup(word: str) -> dict | None:
    """Return {meaning, example, phonetic, audio_url, part_of_speech} or None."""
    word = word.strip()
    if not word:
        return None
    url = get_settings().dictionary_api + quote(word.lower())
    try:
        resp = httpx.get(url, timeout=6)
        if resp.status_code != 200:
            return None
        return parse(resp.json())
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Dictionary lookup failed for %r: %s", word, exc)
        return None


def parse(data: list) -> dict | None:
    if not isinstance(data, list) or not data:
        return None
    result = {"meaning": "", "example": "", "phonetic": "", "audio_url": "", "part_of_speech": ""}
    for entry in data:
        if not result["phonetic"]:
            result["phonetic"] = entry.get("phonetic") or ""
        for ph in entry.get("phonetics", []):
            if not result["phonetic"] and ph.get("text"):
                result["phonetic"] = ph["text"]
            if not result["audio_url"] and ph.get("audio"):
                result["audio_url"] = ph["audio"]
        for meaning in entry.get("meanings", []):
            for d in meaning.get("definitions", []):
                if not result["meaning"] and d.get("definition"):
                    result["meaning"] = d["definition"]
                    result["part_of_speech"] = meaning.get("partOfSpeech", "")
                if not result["example"] and d.get("example"):
                    result["example"] = d["example"]
    return result if result["meaning"] else None
