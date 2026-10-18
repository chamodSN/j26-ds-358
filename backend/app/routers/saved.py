from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_schemas import SavedIn, SavedOut
from app.db import get_db
from app.deps import get_current_user
from app.models import SavedItem, User

router = APIRouter(prefix="/api/saved", tags=["saved"])


@router.get("", response_model=list[SavedOut])
def list_saved(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SavedItem).where(SavedItem.user_id == user.id).order_by(SavedItem.created_at.desc())
    ).all()
    return [SavedOut.model_validate(r) for r in rows]


@router.post("", response_model=SavedOut, status_code=201)
def add_saved(body: SavedIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(
        select(SavedItem).where(SavedItem.user_id == user.id, SavedItem.item_id == body.item_id)
    )
    if existing:
        return SavedOut.model_validate(existing)
    row = SavedItem(user_id=user.id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return SavedOut.model_validate(row)


@router.delete("", status_code=204)
def remove_saved(
    item_id: str = Query(..., min_length=1, max_length=120),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(SavedItem).where(SavedItem.user_id == user.id, SavedItem.item_id == item_id)
    )
    if row:
        db.delete(row)
        db.commit()