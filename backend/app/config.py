"""Central configuration for WheelDeal.

Sab settings .env file se aati hain (backend/.env). Agar .env nahi hai
to defaults use hote hain: SQLite database + auto-generated secret key.
"""
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent          # .../WheelDeal/backend
FRONTEND_DIR = BASE_DIR.parent / "frontend"                # .../WheelDeal/frontend

load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        raise RuntimeError(f"{name} ek number hona chahiye (mila: {raw!r}).")


# --- Database -------------------------------------------------------------
# SQLite (default):  sqlite:///.../wheeldeal.db
# MySQL:             mysql+pymysql://user:password@localhost:3306/wheeldeal?charset=utf8mb4
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{(BASE_DIR / 'wheeldeal.db').as_posix()}"


# --- Secret key -----------------------------------------------------------
MIN_SECRET_KEY_LENGTH = 32


def _check_key_strength(key: str, source: str) -> str:
    if len(key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"Secret key ({source}) bohot choti hai: kam az kam {MIN_SECRET_KEY_LENGTH} characters chahiye. "
            "Khali chor do to khud strong key ban jayegi, ya ye chalao: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return key


def _restrict_file_permissions(path: Path) -> None:
    # Best effort: sirf owner padh/likh sake (Windows par limited asar hota hai)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _load_secret_key() -> str:
    """Env var -> .secret_key file -> naya generate karke file mai save.

    File mai save karne se server restart par tokens invalid nahi hote.
    """
    from_env = os.getenv("WHEELDEAL_SECRET_KEY", "").strip()
    if from_env:
        return _check_key_strength(from_env, "WHEELDEAL_SECRET_KEY")

    key_file = BASE_DIR / ".secret_key"
    if key_file.exists():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            _restrict_file_permissions(key_file)
            return _check_key_strength(stored, ".secret_key file")

    new_key = secrets.token_urlsafe(48)
    key_file.write_text(new_key, encoding="utf-8")
    _restrict_file_permissions(key_file)
    return new_key


SECRET_KEY = _load_secret_key()

# --- Login session --------------------------------------------------------
# Session ek HttpOnly cookie mai rehta hai (JavaScript usay nahi padh sakti).
# Chota rakho: 8-24 ghantay theek hai. Upper limit 7 din.
TOKEN_EXPIRE_HOURS = min(_env_int("TOKEN_EXPIRE_HOURS", 24), 24 * 7)
# auto = HTTPS request par Secure flag lagay. HTTPS proxy ke peeche ho to "true" likho.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "auto").strip().lower()
# True sirf tab karo jab server kisi trusted reverse proxy (nginx etc.) ke peeche ho,
# warna koi bhi X-Forwarded-For fake karke rate limit bypass kar sakta hai.
TRUST_PROXY = _env_bool("TRUST_PROXY", False)

# --- CORS -----------------------------------------------------------------
# Comma separated list, e.g. "https://mysite.com,https://www.mysite.com"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
# Cookies cross-origin tab hi chalti hain jab origins explicitly listed hon ("*" nahi)
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

# --- Email verification ---------------------------------------------------
REQUIRE_EMAIL_VERIFICATION = _env_bool("REQUIRE_EMAIL_VERIFICATION", True)
# Verification link ka base URL, e.g. https://mysite.com  (production mai zaroor set karo)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _env_int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USER
SMTP_STARTTLS = _env_bool("SMTP_STARTTLS", True)
SMTP_SSL = _env_bool("SMTP_SSL", False)          # port 465 wale servers ke liye

if SMTP_HOST and not PUBLIC_BASE_URL:
    raise RuntimeError(
        "SMTP_HOST set hai lekin PUBLIC_BASE_URL khali hai. Verification link fake Host header se "
        "na ban sake is liye .env mai PUBLIC_BASE_URL likho (e.g. https://mysite.com)."
    )
if SMTP_HOST and not SMTP_FROM:
    raise RuntimeError("SMTP_HOST set hai lekin SMTP_FROM (ya SMTP_USER) khali hai.")

# Origins jinse unsafe (POST) requests ko allow karna hai (CSRF check ke liye)
ALLOWED_ORIGINS = {o for o in CORS_ORIGINS if o != "*"}
if PUBLIC_BASE_URL:
    _parsed = urlparse(PUBLIC_BASE_URL)
    if _parsed.scheme and _parsed.netloc:
        ALLOWED_ORIGINS.add(f"{_parsed.scheme}://{_parsed.netloc}")

# --- Abuse limits ---------------------------------------------------------
# (limit, window in seconds). Sab DB mai count hote hain, is liye multiple workers mai bhi sahi chalte hain.
SIGNUP_LIMIT_PER_IP = (5, 3600)             # 5 signups / ghanta / IP
LOGIN_LIMIT_PER_IP = (30, 600)              # 30 login attempts / 10 min / IP
LOGIN_FAIL_LIMIT_PER_ACCOUNT_IP = (5, 900)  # 5 galat password / 15 min / (account + IP)
LOGIN_FAIL_LIMIT_PER_ACCOUNT = (20, 3600)   # 20 galat password / ghanta / account (kisi bhi IP se)
RESEND_LIMIT_PER_IP = (5, 3600)
RESEND_LIMIT_PER_EMAIL = (3, 3600)

MAX_ADS_PER_HOUR = _env_int("MAX_ADS_PER_HOUR", 5)
MAX_ADS_PER_DAY = _env_int("MAX_ADS_PER_DAY", 15)
MAX_ADS_PER_USER = _env_int("MAX_ADS_PER_USER", 100)
