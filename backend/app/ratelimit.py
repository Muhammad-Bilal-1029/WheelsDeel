"""DB-based rate limiter.

Memory mai nahi, DB mai count hota hay: server restart ya multiple workers (run_server.bat mai 2 hain)
se limit bypass nahi hoti.
"""
import hashlib
import math
import random
from datetime import timedelta

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from . import models
from .config import TRUST_PROXY
from .utils import utcnow


def client_ip(request: Request) -> str:
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:45]
    return (request.client.host if request.client else "unknown")[:45]


def hash_key(*parts: str) -> str:
    """Raw email/username rate table mai store nahi karte, sirf unka hash."""
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:40]


def _events(db: Session, bucket: str, key: str, window_seconds: int):
    since = utcnow() - timedelta(seconds=window_seconds)
    return (
        db.query(models.RateEvent.created_at)
        .filter(
            models.RateEvent.bucket == bucket,
            models.RateEvent.key == key,
            models.RateEvent.created_at >= since,
        )
        .order_by(models.RateEvent.created_at.asc())
        .all()
    )


def check(db: Session, bucket: str, key: str, limit: int, window_seconds: int) -> None:
    """Sirf dekhta hay. Limit paar ho chuki ho to 429 deta hay (record nahi karta)."""
    events = _events(db, bucket, key, window_seconds)
    if len(events) >= limit:
        # Jab sab se purana zaroori event window se bahar niklega tab dobara allow hoga
        blocking = events[len(events) - limit][0]
        wait = max(1, int((blocking + timedelta(seconds=window_seconds) - utcnow()).total_seconds()))
        minutes = math.ceil(wait / 60)
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Please try again in about {minutes} minute(s).",
            headers={"Retry-After": str(wait)},
        )


def record(db: Session, bucket: str, key: str) -> None:
    db.add(models.RateEvent(bucket=bucket, key=key, created_at=utcnow()))
    db.commit()
    if random.random() < 0.01:   # kabhi kabhi purana record saaf kar do
        cleanup(db)


def hit(db: Session, bucket: str, key: str, limit_window: tuple[int, int]) -> None:
    """check + record aik saath."""
    limit, window = limit_window
    check(db, bucket, key, limit, window)
    record(db, bucket, key)


def clear(db: Session, bucket: str, key: str) -> None:
    db.query(models.RateEvent).filter(
        models.RateEvent.bucket == bucket, models.RateEvent.key == key
    ).delete(synchronize_session=False)
    db.commit()


def cleanup(db: Session) -> None:
    cutoff = utcnow() - timedelta(days=2)
    db.query(models.RateEvent).filter(models.RateEvent.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
