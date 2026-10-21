from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api_schemas import HistoryOut
from app.db import get_db
from app.deps import get_current_user
from app.models import SearchHistory, User

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[HistoryOut])
def list_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    last = func.max(SearchHistory.created_at).label("last")
    rows = db.execute(
        select(SearchHistory.query, last)
        .where(SearchHistory.user_id == user.id)
        .group_by(SearchHistory.query)
        .order_by(last.desc())
        .limit(20)
    ).all()
    return [HistoryOut(query=r.query, searched_at=r.last) for r in rows]


@router.delete("", status_code=204)
def clear_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(SearchHistory).where(SearchHistory.user_id == user.id))
    db.commit()