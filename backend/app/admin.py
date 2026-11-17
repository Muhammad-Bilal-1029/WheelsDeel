"""Admin panel ke API endpoints (/api/admin/*).

Har endpoint par require_admin lagta hay: admin ka haq har request par DB se check hota hay.
POST requests ko CSRF check bhi get_current_user ke zariye milta hay.
Koi bhi action audit log (admin_actions table) mai record hota hay.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from . import auth_utils, database, models, schemas
from .utils import utcnow

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _iso(value) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


def _log(db: Session, admin: models.User, action: str, target_type: str, target_id: int, note: Optional[str] = None) -> None:
    db.add(models.AdminAction(
        admin_id=admin.id, action=action, target_type=target_type, target_id=target_id,
        note=(note or None) and note[:255], created_at=utcnow(),
    ))


def _note(body: Optional[schemas.ModerationNote]) -> Optional[str]:
    return body.note if body and body.note else None


def _open_report_counts(db: Session, car_ids: list[int]) -> dict[int, int]:
    if not car_ids:
        return {}
    rows = (
        db.query(models.AdReport.car_id, func.count(models.AdReport.id))
        .filter(models.AdReport.status == "open", models.AdReport.car_id.in_(car_ids))
        .group_by(models.AdReport.car_id)
        .all()
    )
    return {car_id: count for car_id, count in rows}


# --- Overview -------------------------------------------------------------

@router.get("/stats")
def stats(db: Session = Depends(database.get_db), _admin: models.User = Depends(auth_utils.require_admin)):
    return {
        "users": db.query(func.count(models.User.id)).scalar(),
        "banned_users": db.query(func.count(models.User.id)).filter(models.User.is_banned.is_(True)).scalar(),
        "ads_visible": db.query(func.count(models.Car.id)).filter(models.Car.is_hidden.is_(False), models.Car.is_deleted.is_(False)).scalar(),
        "ads_hidden": db.query(func.count(models.Car.id)).filter(models.Car.is_hidden.is_(True), models.Car.is_deleted.is_(False)).scalar(),
        "open_reports": db.query(func.count(models.AdReport.id)).filter(models.AdReport.status == "open").scalar(),
    }


# --- Reports --------------------------------------------------------------

@router.get("/reports")
def list_reports(
    status: Literal["open", "resolved", "dismissed", "all"] = "open",
    db: Session = Depends(database.get_db),
    _admin: models.User = Depends(auth_utils.require_admin),
):
    owner, reporter = aliased(models.User), aliased(models.User)
    query = (
        db.query(models.AdReport, models.Car, reporter, owner)
        .join(models.Car, models.AdReport.car_id == models.Car.id)
        .join(reporter, models.AdReport.reporter_id == reporter.id)
        .join(owner, models.Car.owner_id == owner.id)
    )
    if status != "all":
        query = query.filter(models.AdReport.status == status)
    rows = query.order_by(models.AdReport.id.desc()).limit(200).all()

    open_counts = _open_report_counts(db, list({car.id for _, car, _, _ in rows}))
    return [
        {
            "id": report.id,
            "status": report.status,
            "reason": report.reason,
            "details": report.details,
            "created_at": _iso(report.created_at),
            "reporter": {"id": reporter_user.id, "username": reporter_user.username},
            "car": {
                "id": car.id, "brand": car.brand, "model": car.model, "year": car.year,
                "price": car.price, "status": car.status, "is_hidden": car.is_hidden, "is_deleted": car.is_deleted,
                "open_reports": open_counts.get(car.id, 0),
            },
            "owner": {
                "id": owner_user.id, "username": owner_user.username,
                "is_banned": owner_user.is_banned, "is_admin": owner_user.is_admin,
            },
        }
        for report, car, reporter_user, owner_user in rows
    ]


@router.post("/reports/{report_id}/dismiss")
def dismiss_report(
    report_id: int,
    body: Optional[schemas.ModerationNote] = None,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(auth_utils.require_admin),
):
    report = db.get(models.AdReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    if report.status != "open":
        raise HTTPException(status_code=400, detail="This report was already handled.")

    report.status = "dismissed"
    report.resolved_by = admin.id
    report.resolved_at = utcnow()
    _log(db, admin, "dismiss_report", "report", report.id, _note(body))
    db.commit()
    return {"msg": "Report dismissed."}


# --- Ads ------------------------------------------------------------------

@router.get("/cars")
def list_cars(
    visibility: Literal["all", "visible", "hidden"] = "all",
    search: Optional[str] = Query(default=None, max_length=80),
    db: Session = Depends(database.get_db),
    _admin: models.User = Depends(auth_utils.require_admin),
):
    query = db.query(models.Car, models.User).join(models.User, models.Car.owner_id == models.User.id)
    if visibility == "visible":
        query = query.filter(models.Car.is_hidden.is_(False), models.Car.is_deleted.is_(False))
    elif visibility == "hidden":
        query = query.filter(models.Car.is_hidden.is_(True), models.Car.is_deleted.is_(False))
    if search and search.strip():
        like = f"%{search.strip()}%"
        query = query.filter(or_(models.Car.brand.ilike(like), models.Car.model.ilike(like)))
    rows = query.order_by(models.Car.id.desc()).limit(200).all()

    open_counts = _open_report_counts(db, [car.id for car, _ in rows])
    return [
        {
            "id": car.id, "brand": car.brand, "model": car.model, "year": car.year, "price": car.price,
            "status": car.status, "is_hidden": car.is_hidden, "is_deleted": car.is_deleted, "seller_phone": car.seller_phone,
            "open_reports": open_counts.get(car.id, 0),
            "owner": {"id": owner.id, "username": owner.username, "is_banned": owner.is_banned},
        }
        for car, owner in rows
    ]


@router.post("/cars/{car_id}/hide")
def hide_car(
    car_id: int,
    body: Optional[schemas.ModerationNote] = None,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(auth_utils.require_admin),
):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Ad not found.")

    car.is_hidden = True
    # Is ad ki sab open reports khud "resolved" ho jati hain
    resolved = (
        db.query(models.AdReport)
        .filter(models.AdReport.car_id == car.id, models.AdReport.status == "open")
        .update(
            {"status": "resolved", "resolved_by": admin.id, "resolved_at": utcnow()},
            synchronize_session=False,
        )
    )
    _log(db, admin, "hide_ad", "ad", car.id, _note(body))
    db.commit()
    return {"msg": f"Ad hidden. {resolved} open report(s) marked as resolved."}


@router.post("/cars/{car_id}/restore")
def restore_car(
    car_id: int,
    body: Optional[schemas.ModerationNote] = None,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(auth_utils.require_admin),
):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Ad not found.")
    car.is_hidden = False
    _log(db, admin, "restore_ad", "ad", car.id, _note(body))
    db.commit()
    return {"msg": "Ad restored."}


# --- Users ----------------------------------------------------------------

@router.get("/users")
def list_users(
    search: Optional[str] = Query(default=None, max_length=80),
    db: Session = Depends(database.get_db),
    _admin: models.User = Depends(auth_utils.require_admin),
):
    query = db.query(models.User)
    if search and search.strip():
        like = f"%{search.strip()}%"
        query = query.filter(or_(models.User.username.ilike(like), models.User.email.ilike(like)))
    users = query.order_by(models.User.id.desc()).limit(100).all()

    ad_counts = {}
    if users:
        rows = (
            db.query(models.Car.owner_id, func.count(models.Car.id))
            .filter(models.Car.owner_id.in_([u.id for u in users]))
            .group_by(models.Car.owner_id)
            .all()
        )
        ad_counts = {owner_id: count for owner_id, count in rows}

    return [
        {
            "id": u.id, "username": u.username, "email": u.email, "email_verified": u.email_verified,
            "is_admin": u.is_admin, "is_banned": u.is_banned, "ads": ad_counts.get(u.id, 0),
        }
        for u in users
    ]


@router.post("/users/{user_id}/ban")
def ban_user(
    user_id: int,
    body: Optional[schemas.ModerationNote] = None,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(auth_utils.require_admin),
):
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot ban yourself.")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="Admins cannot be banned.")

    target.is_banned = True
    target.token_version += 1          # unke saare login sessions foran khatam
    hidden = (
        db.query(models.Car)
        .filter(models.Car.owner_id == target.id, models.Car.is_hidden.is_(False))
        .update({"is_hidden": True}, synchronize_session=False)
    )
    note = _note(body)
    _log(db, admin, "ban_user", "user", target.id, f"{note + ' | ' if note else ''}hid {hidden} ad(s)")
    db.commit()
    return {"msg": f"User banned and logged out everywhere. {hidden} ad(s) hidden."}


@router.post("/users/{user_id}/unban")
def unban_user(
    user_id: int,
    body: Optional[schemas.ModerationNote] = None,
    db: Session = Depends(database.get_db),
    admin: models.User = Depends(auth_utils.require_admin),
):
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    target.is_banned = False
    _log(db, admin, "unban_user", "user", target.id, _note(body))
    db.commit()
    return {"msg": "User unbanned. Their hidden ads stay hidden until you restore them."}


# --- Audit log ------------------------------------------------------------

@router.get("/log")
def action_log(db: Session = Depends(database.get_db), _admin: models.User = Depends(auth_utils.require_admin)):
    rows = (
        db.query(models.AdminAction, models.User.username)
        .join(models.User, models.AdminAction.admin_id == models.User.id)
        .order_by(models.AdminAction.id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": a.id, "admin": username, "action": a.action, "target_type": a.target_type,
            "target_id": a.target_id, "note": a.note, "created_at": _iso(a.created_at),
        }
        for a, username in rows
    ]
