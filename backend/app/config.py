"""Central configuration for WheelDeal.

Sab settings .env file se aati hain (backend/.env). Agar .env nahi hai
to defaults use hote hain: SQLite database + auto-generated secret key.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent          # .../WheelDeal/backend
FRONTEND_DIR = BASE_DIR.parent / "frontend"                # .../WheelDeal/frontend

load_dotenv(BASE_DIR / ".env")

# --- Database -------------------------------------------------------------
# SQLite (default):  sqlite:///.../wheeldeal.db
# MySQL:             mysql+pymysql://user:password@localhost:3306/wheeldeal?charset=utf8mb4
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{(BASE_DIR / 'wheeldeal.db').as_posix()}"


# --- Secret key -----------------------------------------------------------
def _load_secret_key() -> str:
    """Env var -> .secret_key file -> naya generate karke file mai save.

    File mai save karne se server restart par tokens invalid nahi hote.
    """
    from_env = os.getenv("WHEELDEAL_SECRET_KEY", "").strip()
    if from_env:
        return from_env

    key_file = BASE_DIR / ".secret_key"
    if key_file.exists():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored

    new_key = secrets.token_urlsafe(48)
    key_file.write_text(new_key, encoding="utf-8")
    return new_key


SECRET_KEY = _load_secret_key()
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))

# --- CORS -----------------------------------------------------------------
# Comma separated list, e.g. "https://mysite.com,https://www.mysite.com"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
