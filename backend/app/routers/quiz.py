from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ReviewEvent, User, Word
from ..schemas import AnswerIn, WordOut
from ..security import get_current_user
from ..services import pick_next_word
from ..srs import apply_answer

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.get("/next", response_model=WordOut | None)
def next_question(
    category_id: int | None = None,
    word_id: int | None = None,
    exclude_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Next word to review. `word_id` opens a specific word (e.g. from a notification)."""
    if word_id is not None:
        word = db.get(Word, word_id)
        if word and word.user_id == user.id:
            return word
    return pick_next_word(db, user, category_id=category_id, exclude_id=exclude_id)


@router.post("/answer", response_model=WordOut)
def answer(data: AnswerIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    word = db.get(Word, data.word_id)
    if not word or word.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Word not found")
    apply_answer(word, data.knew)
    db.add(ReviewEvent(user_id=user.id, word_id=word.id, knew=data.knew))
    db.commit()
    db.refresh(word)
    return word
