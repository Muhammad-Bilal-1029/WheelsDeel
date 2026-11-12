"""Chhote shared helpers (kisi aur module par depend nahi karte)."""
import unicodedata
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC datetime (DB mai naive UTC store hota hai)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_username(value: str) -> str:
    """Case-insensitive aur lookalike-safe form: 'Admin', 'admin', 'ＡＤＭＩＮ' sab ek hi ban jate hain."""
    return unicodedata.normalize("NFKC", value).strip().lower()
