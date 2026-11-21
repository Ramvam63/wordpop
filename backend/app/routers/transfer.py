"""Export entries to a CSV file and import them from one."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import csv_io
from ..db import get_db
from ..models import Category, User, Word
from ..security import get_current_user

router = APIRouter(prefix="/api/words", tags=["import & export"])

MAX_FILE_CHARS = 2_000_000  # about 2 MB of text


class ImportIn(BaseModel):
    csv: str = Field(min_length=1, max_length=MAX_FILE_CHARS)
    category_id: int | None = None  # also put every imported entry in this category


@router.get("/export")
def export_csv(
    category_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Word).where(Word.user_id == user.id)
        .options(selectinload(Word.categories)).order_by(Word.created_at)
    )
    if category_id is not None:
        stmt = stmt.where(Word.categories.any(Category.id == category_id))
    rows = [
        {"text": w.text, "meaning": w.meaning, "example": w.example,
         "categories": "; ".join(c.name for c in w.categories)}
        for w in db.scalars(stmt)
    ]
    filename = f"wordpop-{date.today().isoformat()}.csv"
    return Response(
        csv_io.write_csv(rows).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def import_csv(data: ImportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    parsed = csv_io.read_csv(data.csv)
    if not parsed.rows and not parsed.errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The file has no entries")

    extra = None
    if data.category_id is not None:
        extra = db.get(Category, data.category_id)
        if not extra or extra.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")

    categories = {c.name.lower(): c for c in db.scalars(select(Category).where(Category.user_id == user.id))}
    existing = {t.lower() for t in db.scalars(select(Word.text).where(Word.user_id == user.id))}
    created_categories, added, duplicates = [], 0, 0

    for row in parsed.rows:
        if row.text.lower() in existing:
            duplicates += 1
            continue
        existing.add(row.text.lower())
        word_categories = []
        for name in row.categories:
            category = categories.get(name.lower())
            if category is None:
                category = Category(user_id=user.id, name=name)
                db.add(category)
                categories[name.lower()] = category
                created_categories.append(name)
            word_categories.append(category)
        if extra is not None and extra not in word_categories:
            word_categories.append(extra)
        word = Word(user_id=user.id, text=row.text, meaning=row.meaning, example=row.example,
                    categories=word_categories)
        word.sync_phonetic()
        db.add(word)
        added += 1

    db.commit()
    total = db.scalar(select(func.count()).select_from(Word).where(Word.user_id == user.id))
    return {
        "added": added,
        "duplicates": duplicates,
        "categories_created": created_categories,
        "errors": parsed.errors[:50],
        "total_entries": total,
    }
