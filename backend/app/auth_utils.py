from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import models
from .config import (
    ALLOWED_ORIGINS, COOKIE_SECURE, SECRET_KEY, TOKEN_EXPIRE_HOURS, TRUST_PROXY,
)
from .database import get_db

ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72
COOKIE_NAME = "wheeldeal_session"
CSRF_HEADER_NAME = "x-requested-with"
CSRF_HEADER_VALUE = "WheelDeal"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EMAIL_TOKEN_HOURS = 24


# --- Passwords -------------------------------------------------------------

def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError("Password is too long (max 72 bytes).")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    raw = plain_password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, hashed_password.encode("utf-8"))
    except ValueError:
        return False


# --- Tokens ----------------------------------------------------------------

def _encode(payload: dict, hours: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + timedelta(hours=hours)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user: models.User) -> str:
    # tv = token_version: logout par user.token_version badhta hay aur purane tokens kaam nahi karte
    return _encode({"sub": str(user.id), "tv": user.token_version, "typ": "access"}, TOKEN_EXPIRE_HOURS)


def create_email_token(user: models.User) -> str:
    return _encode({"sub": str(user.id), "email": user.email, "typ": "verify"}, EMAIL_TOKEN_HOURS)


def decode_token(token: str, expected_type: str) -> dict:
    """Galat/expired/doosri qism ka token ho to jwt.PyJWTError raise hota hay."""
    payload = jwt.decode(
        token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "typ"]}
    )
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


# --- Session cookie --------------------------------------------------------

def _cookie_should_be_secure(request: Request) -> bool:
    if COOKIE_SECURE == "true":
        return True
    if COOKIE_SECURE == "false":
        return False
    if request.url.scheme == "https":
        return True
    if TRUST_PROXY:
        return request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"
    return False


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=TOKEN_EXPIRE_HOURS * 3600,
        httponly=True,                       # JavaScript (XSS) is cookie ko nahi padh sakti
        samesite="lax",
        secure=_cookie_should_be_secure(request),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


# --- CSRF ------------------------------------------------------------------

def enforce_csrf(request: Request) -> None:
    """Cookie se login hone ki wajah se POST requests ko dusri websites se bachana.

    Browser same-origin POST par Origin bhejta hay: woh is server ka (ya allow-listed) hona chahiye.
    Origin na ho (non-browser client) to custom header zaroori hay jo dusri site bina CORS ke nahi bhej sakti.
    """
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin:
        same_host = urlparse(origin).netloc == request.headers.get("host", "")
        if not same_host and origin not in ALLOWED_ORIGINS:
            raise HTTPException(status_code=403, detail="Cross-site request blocked.")
    elif request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=403, detail="Cross-site request blocked.")


# --- Current user ----------------------------------------------------------

def get_user_from_request(request: Request, db: Session) -> Optional[models.User]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = decode_token(token, "access")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None

    user = db.get(models.User, user_id)          # user delete ho gaya ho to None
    if user is None or payload.get("tv") != user.token_version:   # logout ke baad purana token bekaar
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = get_user_from_request(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in. Please log in again.")
    enforce_csrf(request)
    return user
