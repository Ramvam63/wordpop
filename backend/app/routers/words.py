from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import dictionary
from ..db import get_db
from ..models import Category, User, Word
from ..schemas import WordIn, WordOut, WordUpdate
from ..security import get_current_user
from ..services import user_categories

router = APIRouter(prefix="/api", tags=["words"])


def _get_word(db: Session, user: User, word_id: int) -> Word:
    word = db.get(Word, word_id)
    if not word or word.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Word not found")
    return word


@router.get("/words", response_model=list[WordOut])
def list_words(
    category_id: int | None = None,
    q: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Word)
        .where(Word.user_id == user.id)
        .options(selectinload(Word.categories))
        .order_by(Word.created_at.desc())
    )
    if category_id is not None:
        stmt = stmt.where(Word.categories.any(Category.id == category_id))
    if q:
        stmt = stmt.where(Word.text.ilike(f"%{q.strip()}%"))
    return list(db.scalars(stmt))


@router.post("/words", response_model=WordOut, status_code=status.HTTP_201_CREATED)
def create_word(data: WordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    text = data.text.strip()
    exists = db.scalar(
        select(Word).where(Word.user_id == user.id, func.lower(Word.text) == text.lower())
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, f'"{text}" is already in your list')

    meaning, example, phonetic, audio = data.meaning.strip(), data.example.strip(), "", ""
    if not meaning or not example:
        found = dictionary.lookup(text)
        if found:
            meaning = meaning or found["meaning"]
            example = example or found["example"]
            phonetic, audio = found["phonetic"], found["audio_url"]
    if not meaning:
        raise HTTPException(
            422,
            "Couldn't find a meaning automatically - please type one",
        )

    word = Word(
        user_id=user.id,
        text=text,
        meaning=meaning,
        example=example,
        phonetic=phonetic,
        audio_url=audio,
        categories=user_categories(db, user, data.category_ids),
    )
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


@router.patch("/words/{word_id}", response_model=WordOut)
def update_word(
    word_id: int,
    data: WordUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    word = _get_word(db, user, word_id)
    if data.text is not None:
        word.text = data.text.strip()
    if data.meaning is not None:
        word.meaning = data.meaning.strip()
    if data.example is not None:
        word.example = data.example.strip()
    if data.category_ids is not None:
        word.categories = user_categories(db, user, data.category_ids)
    db.commit()
    db.refresh(word)
    return word


@router.delete("/words/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_word(word_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_word(db, user, word_id))
    db.commit()


@router.get("/dictionary/{word}")
def lookup_word(word: str, user: User = Depends(get_current_user)):
    """Preview what auto-fill would use, so the user can edit before saving."""
    found = dictionary.lookup(word)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No dictionary entry found")
    return found
