"""Cars ke endpoints: list (filters + sorting + pagination), detail, create, edit, delete, My Ads, photos.

Sab endpoints login ke peeche hain. Edit/delete/photos sirf ad ke maalik ke liye; POST/PATCH/DELETE par
CSRF check get_current_user ke zariye khud lagta hay.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import auth_utils, config, database, images, models, ratelimit, schemas
from .utils import utcnow

router = APIRouter(prefix="/api", tags=["cars"])

SORT_ORDERS = {
    "newest": lambda c: (c.id.desc(),),
    "oldest": lambda c: (c.id.asc(),),
    "price_asc": lambda c: (c.price.asc(), c.id.desc()),
    "price_desc": lambda c: (c.price.desc(), c.id.desc()),
    "year_desc": lambda c: (c.year.desc(), c.id.desc()),
    "year_asc": lambda c: (c.year.asc(), c.id.desc()),
    # Jin ads mai mileage nahi likha (purani) woh aakhir mai
    "mileage_asc": lambda c: (c.mileage.is_(None), c.mileage.asc(), c.id.desc()),
}


# --- helpers ---------------------------------------------------------------

def _like(value: str) -> str:
    """User ke text mai % aur _ ko normal character bana do (warna wildcard ban kar search ko sust kar sakte hain)."""
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _images_by_car(db: Session, car_ids: list[int]) -> dict[int, list[models.CarImage]]:
    if not car_ids:
        return {}
    rows = (
        db.query(models.CarImage)
        .filter(models.CarImage.car_id.in_(car_ids))
        .order_by(models.CarImage.car_id, models.CarImage.position, models.CarImage.id)
        .all()
    )
    grouped: dict[int, list[models.CarImage]] = {}
    for image in rows:
        grouped.setdefault(image.car_id, []).append(image)
    return grouped


def serialize(car: models.Car, car_images: list[models.CarImage], seller_name: Optional[str] = None) -> dict:
    return {
        "id": car.id, "brand": car.brand, "model": car.model, "year": car.year, "price": car.price,
        "seller_phone": car.seller_phone, "status": car.status, "owner_id": car.owner_id,
        "city": car.city, "mileage": car.mileage, "fuel_type": car.fuel_type,
        "transmission": car.transmission, "engine_cc": car.engine_cc, "color": car.color,
        "condition": car.condition, "description": car.description, "is_hidden": car.is_hidden,
        "images": [
            {"id": i.id, "url": images.media_url(i.filename), "thumb_url": images.media_url(i.filename, thumb=True)}
            for i in car_images
        ],
        "cover_thumb": images.media_url(car_images[0].filename, thumb=True) if car_images else None,
        "seller_name": seller_name,
    }


def serialize_many(db: Session, cars: list[models.Car]) -> list[dict]:
    grouped = _images_by_car(db, [c.id for c in cars])
    return [serialize(car, grouped.get(car.id, [])) for car in cars]


def _get_own_car(db: Session, car_id: int, user: models.User) -> models.Car:
    car = db.get(models.Car, car_id)
    if car is None or car.is_deleted:
        raise HTTPException(status_code=404, detail="Ad not found.")
    if car.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You can only change your own ads.")
    if car.is_hidden:
        raise HTTPException(status_code=403, detail="This ad was removed by the moderators.")
    return car


# --- list / detail ---------------------------------------------------------

@router.get("/cars", response_model=schemas.CarListResponse)
def list_cars(
    q: Optional[str] = Query(default=None, max_length=80),
    city: Optional[str] = Query(default=None, max_length=60),
    fuel_type: Optional[schemas.FuelType] = None,
    transmission: Optional[schemas.Transmission] = None,
    condition: Optional[schemas.Condition] = None,
    min_price: Optional[float] = Query(default=None, ge=0, le=1e10),
    max_price: Optional[float] = Query(default=None, ge=0, le=1e10),
    min_year: Optional[int] = Query(default=None, ge=1900, le=2100),
    max_year: Optional[int] = Query(default=None, ge=1900, le=2100),
    status: Optional[list[schemas.CarStatus]] = Query(default=None),
    sort: schemas.SortOrder = "newest",
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    db: Session = Depends(database.get_db),
    _user: models.User = Depends(auth_utils.get_current_user),   # login zaroori
):
    Car = models.Car
    query = db.query(Car).filter(Car.is_hidden.is_(False), Car.is_deleted.is_(False))

    if q and q.strip():
        like = _like(q)
        query = query.filter(or_(Car.brand.ilike(like, escape="\\"), Car.model.ilike(like, escape="\\")))
    if city and city.strip():
        query = query.filter(Car.city.ilike(_like(city), escape="\\"))
    if fuel_type:
        query = query.filter(Car.fuel_type == fuel_type)
    if transmission:
        query = query.filter(Car.transmission == transmission)
    if condition:
        query = query.filter(Car.condition == condition)
    if min_price is not None:
        query = query.filter(Car.price >= min_price)
    if max_price is not None:
        query = query.filter(Car.price <= max_price)
    if min_year is not None:
        query = query.filter(Car.year >= min_year)
    if max_year is not None:
        query = query.filter(Car.year <= max_year)
    if status:
        query = query.filter(Car.status.in_(status))

    total = query.count()
    cars = query.order_by(*SORT_ORDERS[sort](Car)).offset(offset).limit(limit).all()
    return {"items": serialize_many(db, cars), "total": total}


@router.get("/my/cars", response_model=list[schemas.CarResponse])
def my_cars(db: Session = Depends(database.get_db), user: models.User = Depends(auth_utils.get_current_user)):
    cars = (
        db.query(models.Car)
        .filter(models.Car.owner_id == user.id, models.Car.is_deleted.is_(False))
        .order_by(models.Car.id.desc())
        .all()
    )
    return serialize_many(db, cars)


@router.get("/cars/{car_id}", response_model=schemas.CarResponse)
def get_car(car_id: int, db: Session = Depends(database.get_db), user: models.User = Depends(auth_utils.get_current_user)):
    car = db.get(models.Car, car_id)
    if car is None or car.is_deleted:
        raise HTTPException(status_code=404, detail="Ad not found.")
    # Moderators ne hide ki hui ad sirf uska maalik ya admin dekh sakta hay
    if car.is_hidden and car.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=404, detail="Ad not found.")
    seller = db.get(models.User, car.owner_id)
    return serialize(car, _images_by_car(db, [car.id]).get(car.id, []), seller.username if seller else None)


# --- create / edit / delete ------------------------------------------------

@router.post("/cars", response_model=schemas.CarResponse)
def create_car(
    car: schemas.CarCreate,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(auth_utils.get_current_user),
):
    # Yeh route sirf tab chalega jab valid login session (cookie) hoga
    if config.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before posting ads.")

    active_ads = db.query(models.Car).filter(models.Car.owner_id == user.id, models.Car.is_deleted.is_(False)).count()
    if active_ads >= config.MAX_ADS_PER_USER:
        raise HTTPException(status_code=403, detail="You have reached the maximum number of ads allowed.")

    key = str(user.id)
    ratelimit.check(db, "ad_hour", key, config.MAX_ADS_PER_HOUR, 3600)
    ratelimit.check(db, "ad_day", key, config.MAX_ADS_PER_DAY, 86400)

    db_car = models.Car(**car.model_dump(), owner_id=user.id)
    db.add(db_car)
    db.commit()
    db.refresh(db_car)

    ratelimit.record(db, "ad_hour", key)
    ratelimit.record(db, "ad_day", key)
    return serialize(db_car, [])


@router.patch("/cars/{car_id}", response_model=schemas.CarResponse)
def edit_car(
    car_id: int,
    body: schemas.CarUpdate,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(auth_utils.get_current_user),
):
    car = _get_own_car(db, car_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(car, field, value)
    db.commit()
    db.refresh(car)
    return serialize(car, _images_by_car(db, [car.id]).get(car.id, []))


@router.delete("/cars/{car_id}")
def delete_car(car_id: int, db: Session = Depends(database.get_db), user: models.User = Depends(auth_utils.get_current_user)):
    car = _get_own_car(db, car_id, user)
    car.is_deleted = True      # row rehti hay (reports/moderation record ke liye), lekin kahin nazar nahi aati

    has_reports = db.query(models.AdReport.id).filter(models.AdReport.car_id == car.id).first() is not None
    removed_files = []
    if not has_reports:
        # Report nahi hui to photos bhi disk se hata do; report hui ho to admin ke liye bachi rehti hain
        for image in db.query(models.CarImage).filter(models.CarImage.car_id == car.id).all():
            removed_files.append(image.filename)
            db.delete(image)
    db.commit()
    for base in removed_files:
        images.delete_files(base)
    return {"msg": "Ad deleted."}


# --- photos ----------------------------------------------------------------

@router.post("/cars/{car_id}/images", response_model=schemas.ImageOut)
async def upload_image(
    car_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(auth_utils.get_current_user),
):
    """Aik photo (raw bytes, Content-Type: image/jpeg|png|webp). Aik se zyada photos ke liye dobara call karo."""
    car = _get_own_car(db, car_id, user)

    count = db.query(models.CarImage).filter(models.CarImage.car_id == car.id).count()
    if count >= config.MAX_IMAGES_PER_AD:
        raise HTTPException(status_code=400, detail=f"You can add at most {config.MAX_IMAGES_PER_AD} photos per ad.")

    ratelimit.check(db, "img_hour", str(user.id), *config.IMAGE_UPLOAD_LIMIT_PER_USER)

    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in images.ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG or WebP images are allowed.")

    max_bytes = config.MAX_IMAGE_BYTES
    too_big = HTTPException(status_code=413, detail=f"Photo is too large (max {max_bytes // (1024 * 1024)} MB).")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise too_big

    data = bytearray()
    async for chunk in request.stream():       # Content-Length jhoota ho ya chunked ho, tab bhi limit lagti hay
        data.extend(chunk)
        if len(data) > max_bytes:
            raise too_big
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")

    try:
        base = await run_in_threadpool(images.process_upload, bytes(data))
    except images.ImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    last_position = db.query(func.max(models.CarImage.position)).filter(models.CarImage.car_id == car.id).scalar()
    image = models.CarImage(
        car_id=car.id, filename=base, position=0 if last_position is None else last_position + 1, created_at=utcnow(),
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    ratelimit.record(db, "img_hour", str(user.id))
    return {"id": image.id, "url": images.media_url(base), "thumb_url": images.media_url(base, thumb=True)}


def _own_image(db: Session, car_id: int, image_id: int, user: models.User):
    car = _get_own_car(db, car_id, user)
    image = db.get(models.CarImage, image_id)
    if image is None or image.car_id != car.id:
        raise HTTPException(status_code=404, detail="Photo not found.")
    return car, image


def _renumber(db: Session, car_id: int) -> None:
    ordered = (
        db.query(models.CarImage).filter(models.CarImage.car_id == car_id)
        .order_by(models.CarImage.position, models.CarImage.id).all()
    )
    for index, image in enumerate(ordered):
        image.position = index


@router.delete("/cars/{car_id}/images/{image_id}")
def delete_image(car_id: int, image_id: int, db: Session = Depends(database.get_db), user: models.User = Depends(auth_utils.get_current_user)):
    car, image = _own_image(db, car_id, image_id, user)
    base = image.filename
    db.delete(image)
    db.flush()
    _renumber(db, car.id)
    db.commit()
    images.delete_files(base)
    return {"msg": "Photo deleted."}


@router.post("/cars/{car_id}/images/{image_id}/cover")
def make_cover(car_id: int, image_id: int, db: Session = Depends(database.get_db), user: models.User = Depends(auth_utils.get_current_user)):
    car, image = _own_image(db, car_id, image_id, user)
    ordered = (
        db.query(models.CarImage).filter(models.CarImage.car_id == car.id)
        .order_by(models.CarImage.position, models.CarImage.id).all()
    )
    for index, item in enumerate([image] + [i for i in ordered if i.id != image.id]):
        item.position = index
    db.commit()
    return {"msg": "Cover photo updated."}
