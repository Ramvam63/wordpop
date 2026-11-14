"""Ready-made word lists so new users get useful notifications on day one."""

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Category, User, Word
from ..security import get_current_user

router = APIRouter(prefix="/api/starter-lists", tags=["starter lists"])
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "starter_lists.json"


@lru_cache
def load_lists() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@router.get("")
def list_starter_lists():
    return [
        {"key": key, "name": v["name"], "description": v["description"], "count": len(v["words"])}
        for key, v in load_lists().items()
    ]


@router.post("/{key}/import")
def import_list(key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = load_lists().get(key)
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown list")

    category = db.scalar(
        select(Category).where(
            Category.user_id == user.id, func.lower(Category.name) == data["name"].lower()
        )
    )
    if not category:
        category = Category(user_id=user.id, name=data["name"], color=data["color"])
        db.add(category)
        db.flush()

    existing = {
        w.text.lower(): w for w in db.scalars(select(Word).where(Word.user_id == user.id))
    }
    added = 0
    for item in data["words"]:
        word = existing.get(item["text"].lower())
        if word is None:
            word = Word(
                user_id=user.id, text=item["text"], meaning=item["meaning"], example=item["example"]
            )
            db.add(word)
            added += 1
        if category not in word.categories:
            word.categories.append(category)
    db.commit()
    return {"category_id": category.id, "added": added, "total": len(data["words"])}
