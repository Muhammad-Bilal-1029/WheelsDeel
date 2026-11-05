from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, schemas, database, auth_utils
from .config import CORS_ORIGINS, FRONTEND_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Server start hotay hi tables ban jayen gi (SQLite ho ya MySQL)
    models.Base.metadata.create_all(bind=database.engine)
    yield


app = FastAPI(title="WheelDeal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- HEALTH CHECK ---

@app.get("/api/health")
def health(db: Session = Depends(database.get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": database.engine.dialect.name}


# --- AUTHENTICATION ROUTES ---

@app.post("/api/signup", response_model=schemas.UserResponse)
def signup(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    email = str(user.email).lower()

    # Check if username or email already exists
    existing = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or Email already registered")

    new_user = models.User(
        username=user.username,
        email=email,
        hashed_password=auth_utils.hash_password(user.password),
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or Email already registered")
    db.refresh(new_user)
    return new_user


@app.post("/api/login")
def login(user_data: schemas.UserLogin, db: Session = Depends(database.get_db)):
    # Username ya Email dono se check karega
    login_identifier = user_data.username_or_email.strip()
    db_user = db.query(models.User).filter(
        (models.User.username == login_identifier) |
        (models.User.email == login_identifier.lower())
    ).first()

    # Agar valid nahi hay toh customized denied error message
    if not db_user or not auth_utils.verify_password(user_data.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Denied! Credentials are not valid. Please sign up if you don't have an account."
        )

    # Token generate karna
    access_token = auth_utils.create_access_token(data={"sub": str(db_user.id)})
    return {"token": access_token, "username": db_user.username, "msg": "Login Successful!"}


# --- CAR ROUTES ---

@app.post("/api/cars", response_model=schemas.CarResponse)
def add_car(
    car: schemas.CarCreate,
    db: Session = Depends(database.get_db),
    current_user_id: int = Depends(auth_utils.get_current_user),
):
    # Yeh route sirf tab chalega jab headers mai valid Token pass hoga
    db_car = models.Car(**car.model_dump(), owner_id=current_user_id)
    db.add(db_car)
    db.commit()
    db.refresh(db_car)
    return db_car


@app.get("/api/cars", response_model=list[schemas.CarResponse])
def get_cars(brand: Optional[str] = None, db: Session = Depends(database.get_db)):
    query = db.query(models.Car)
    if brand:
        query = query.filter(models.Car.brand.ilike(f"%{brand}%"))
    return query.order_by(models.Car.id.desc()).all()


# --- FRONTEND (same server se serve hoga) ---
# Yeh sab API routes ke BAAD aana chahiye, warna /api/* ko overshadow kar dega.

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/carhtml/index.html")


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
