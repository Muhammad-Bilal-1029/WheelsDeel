"""Chhoti si automatic migration.

SQLAlchemy ka create_all() purani tables mai naye columns nahi jodta. Is liye server start par
yeh check karta hay ke `users` table mai naye columns hain ya nahi, aur nahi hon to jod deta hay.
Purane users bilkul safe rehte hain (unka data delete nahi hota).
"""
import logging

from sqlalchemy import inspect, text

from .utils import normalize_username

logger = logging.getLogger("uvicorn.error")

INDEX_NAME = "ix_users_username_normalized"


def run_migrations(engine) -> None:
    insp = inspect(engine)
    if not insp.has_table("users"):
        return

    columns = {col["name"] for col in insp.get_columns("users")}

    with engine.begin() as conn:
        if "token_version" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
            logger.warning("Migration: users.token_version add hua.")

        if "email_verified" not in columns:
            # Purane users ko verified maan lete hain, warna woh sab achanak login nahi kar sakte
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 1"))
            logger.warning("Migration: users.email_verified add hua (purane users verified maane gaye).")

        if "username_normalized" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN username_normalized VARCHAR(160) NULL"))
            logger.warning("Migration: users.username_normalized add hua.")

    _backfill_username_normalized(engine)
    _lowercase_emails(engine)
    _ensure_unique_index(engine)


def _backfill_username_normalized(engine) -> None:
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, username FROM users WHERE username_normalized IS NULL ORDER BY id")
        ).fetchall()
        if not rows:
            return

        taken = {
            r[0] for r in conn.execute(
                text("SELECT username_normalized FROM users WHERE username_normalized IS NOT NULL")
            )
        }
        for user_id, username in rows:
            value = normalize_username(username)
            if value in taken:
                # Purane DB mai "Bob" aur "bob" dono hon to dusre ko alag value dete hain taake unique index ban sake
                value = f"{value}~{user_id}"
                logger.warning(
                    "Migration: username %r ka lookalike pehle se maujood hay (id=%s). "
                    "Isay manually dekh lo.", username, user_id,
                )
            taken.add(value)
            conn.execute(
                text("UPDATE users SET username_normalized = :v WHERE id = :i"),
                {"v": value[:160], "i": user_id},
            )


def _lowercase_emails(engine) -> None:
    """Login email ko lowercase kar ke match karta hay, is liye stored emails bhi lowercase hone chahiye."""
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET email = LOWER(email) WHERE email <> LOWER(email)"))
    except Exception as exc:  # unique conflict (do emails sirf case mai alag) ya aur masla
        logger.warning("Migration: emails lowercase nahi ho sake: %s", exc)


def _ensure_unique_index(engine) -> None:
    insp = inspect(engine)
    existing = {idx["name"] for idx in insp.get_indexes("users")}
    if INDEX_NAME in existing:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE UNIQUE INDEX {INDEX_NAME} ON users (username_normalized)"))
        logger.warning("Migration: unique index %s ban gaya.", INDEX_NAME)
    except Exception as exc:
        logger.warning("Migration: unique index nahi ban saka: %s", exc)
