"""Ready-made categories (Vocabulary, Idioms, French Basics, ...) users can add with one tap.

The lists hold no entries: everyone starts from scratch with their own words, and a
starter list only gives them a named, coloured category to file those words under."""

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Category, User
from ..security import get_current_user

router = APIRouter(prefix="/api/starter-lists", tags=["starter lists"])
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "starter_lists.json"


@lru_cache
def load_lists() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@router.get("")
def list_starter_lists():
    return [
        {"key": key, "name": v["name"], "description": v["description"], "color": v["color"]}
        for key, v in load_lists().items()
    ]


def find_starter_category(db: Session, user: User, key: str, data: dict) -> Category | None:
    """Find the user's category for this list: by its fixed key first, then by its current
    or any former name (lists can be renamed). A category still using a former default
    name is renamed to the current one; a name the user chose themselves is kept."""
    category = db.scalar(
        select(Category).where(Category.user_id == user.id, Category.starter_key == key)
    )
    if category:
        return category
    names = [data["name"], *data.get("aliases", [])]
    for name in names:
        category = db.scalar(
            select(Category).where(
                Category.user_id == user.id, func.lower(Category.name) == name.lower()
            )
        )
        if category:
            category.starter_key = key
            if category.name.lower() != data["name"].lower() and not db.scalar(
                select(Category).where(
                    Category.user_id == user.id, func.lower(Category.name) == data["name"].lower()
                )
            ):
                category.name = data["name"]
            return category
    return None


@router.post("/{key}/import")
def import_list(key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add the list's (empty) category. Safe to call twice: an existing one is reused."""
    data = load_lists().get(key)
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown list")

    category = find_starter_category(db, user, key, data)
    created = category is None
    if created:
        category = Category(user_id=user.id, name=data["name"], color=data["color"], starter_key=key)
        db.add(category)
    db.commit()
    return {"category_id": category.id, "name": category.name, "created": created}
