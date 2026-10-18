from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import COOKIE_NAME, read_session_token


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in first.")
    return user
