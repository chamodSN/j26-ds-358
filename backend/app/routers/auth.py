from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_schemas import GoogleIn, LoginIn, RegisterIn, UserOut
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.security import (
    clear_session_cookie,
    hash_password,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        email=u.email,
        name=u.name,
        avatar_url=u.avatar_url,
        has_password=bool(u.password_hash),
        google_linked=bool(u.google_sub),
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(
        email=email,
        name=body.name.strip() or email.split("@")[0],
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user.id)
    return user_out(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        raise HTTPException(401, "Incorrect email or password.")
    if not user.password_hash:
        raise HTTPException(
            401, "This account uses Google sign-in. Use the Google button.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    set_session_cookie(response, user.id)
    return user_out(user)


@router.post("/google", response_model=UserOut)
def google_login(body: GoogleIn, response: Response, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not set up on the server.")
    try:
        info = id_token.verify_oauth2_token(
            body.credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise HTTPException(
            401, "Google sign-in could not be verified.") from None
    if not info.get("email_verified"):
        raise HTTPException(401, "Your Google email is not verified.")

    sub = info["sub"]
    email = info["email"].lower()
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=info.get(
                "name") or email.split("@")[0])
            db.add(user)
        user.google_sub = sub  # link Google to an existing email account too
    if not user.avatar_url and info.get("picture"):
        user.avatar_url = info["picture"]
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user.id)
    return user_out(user)


@router.post("/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)
