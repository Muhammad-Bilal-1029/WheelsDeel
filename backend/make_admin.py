"""Admin banane / hatane ka tool. Sirf server (is PC) par chalta hay, website se koi admin nahi ban sakta.

Istemal (backend folder mai, venv activate ho):
    python make_admin.py <username ya email>            -> admin banao
    python make_admin.py <username ya email> --remove   -> admin hata do
    python make_admin.py --list                          -> maujooda admins dekho

Ya project ke root se:  make_admin.bat <username ya email>
"""
import sys

from app import database, migrate, models
from app.utils import normalize_username


def find_user(db, identifier: str):
    normalized = normalize_username(identifier)
    return (
        db.query(models.User)
        .filter((models.User.username_normalized == normalized) | (models.User.email == identifier.strip().lower()))
        .first()
    )


def main(argv: list[str]) -> int:
    # Table/columns tayyar hon (naye column is_admin ke liye)
    models.Base.metadata.create_all(bind=database.engine)
    migrate.run_migrations(database.engine)

    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]

    with database.SessionLocal() as db:
        if "--list" in flags:
            admins = db.query(models.User).filter(models.User.is_admin.is_(True)).all()
            if not admins:
                print("Abhi koi admin nahi hay.")
            for u in admins:
                print(f"- {u.username} ({u.email})")
            return 0

        if len(args) != 1:
            print(__doc__)
            return 1

        user = find_user(db, args[0])
        if user is None:
            print(f"User '{args[0]}' nahi mila. Pehle website par signup karo, phir ye command chalao.")
            return 1

        if "--remove" in flags:
            user.is_admin = False
            db.commit()
            print(f"OK: {user.username} ab admin nahi hay.")
        else:
            user.is_admin = True
            user.is_banned = False
            db.commit()
            print(f"OK: {user.username} ab admin hay. Dobara login karo, phir menu mai 'Admin' dikhega.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
