import logging
import posixpath
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import unquote

import jwt
from fastapi import (
    BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response, status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import admin, auth_utils, cars, config, database, mailer, migrate, models, ratelimit, schemas
from .utils import normalize_username, utcnow

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Server start hotay hi tables ban jayen gi (SQLite ho ya MySQL), purane DB mai naye columns jud jayen ge
    models.Base.metadata.create_all(bind=database.engine)
    migrate.run_migrations(database.engine)
    with database.SessionLocal() as db:
        ratelimit.cleanup(db)
    yield


app = FastAPI(title="WheelDeal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)


def _public_base_url(request: Request) -> str:
    return config.PUBLIC_BASE_URL or str(request.base_url).rstrip("/")

def _verification_link(request: Request, user: models.User) -> str:
    token = auth_utils.create_email_token(user)
    return f"{_public_base_url(request)}/api/verify-email?token={token}"


# --- HEALTH CHECK ---

@app.get("/api/health")
def health(db: Session = Depends(database.get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": database.engine.dialect.name}


# --- AUTHENTICATION ROUTES ---

@app.post("/api/signup", response_model=schemas.SignupResponse)
def signup(
    user: schemas.UserCreate,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(database.get_db),
):
    ratelimit.hit(db, "signup_ip", ratelimit.client_ip(request), config.SIGNUP_LIMIT_PER_IP)

    email = str(user.email).lower()
    username_normalized = normalize_username(user.username)

    # Username (case-insensitive) ya email pehle se ho to reject
    existing = db.query(models.User).filter(
        or_(
            models.User.username_normalized == username_normalized,
            models.User.username == user.username,
            models.User.email == email,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or Email already registered")

    new_user = models.User(
        username=user.username,
        username_normalized=username_normalized,
        email=email,
        hashed_password=auth_utils.hash_password(user.password),
        email_verified=not config.REQUIRE_EMAIL_VERIFICATION,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or Email already registered")
    db.refresh(new_user)

    if config.REQUIRE_EMAIL_VERIFICATION:
        background.add_task(mailer.send_verification_email, new_user.email, _verification_link(request, new_user))

    return schemas.SignupResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        verification_required=config.REQUIRE_EMAIL_VERIFICATION,
        msg=(
            "Account created. Please verify your email using the link we sent you, then log in."
            if config.REQUIRE_EMAIL_VERIFICATION else "Account created. Please log in."
        ),
    )


@app.get("/api/verify-email", response_class=HTMLResponse, include_in_schema=False)
def verify_email(
    response: Response,
    token: str = Query(max_length=2000),
    db: Session = Depends(database.get_db),
):
    def page(message: str, ok: bool, code: int) -> HTMLResponse:
        color = "#166534" if ok else "#b91c1c"
        html = (
            "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            "<title>WheelDeal - Email verification</title></head>"
            "<body style='font-family:system-ui,sans-serif;max-width:480px;margin:15vh auto;padding:0 1rem;text-align:center'>"
            f"<h2 style='color:{color}'>{message}</h2>"
            "<p><a href='/carhtml/login.html'>Go to login</a></p></body></html>"
        )
        # Token URL mai hay: referrer ke zariye leak na ho aur page cache na ho
        return HTMLResponse(html, status_code=code, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    try:
        payload = auth_utils.decode_token(token, "verify")
        user = db.get(models.User, int(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        return page("This verification link is invalid or has expired.", False, 400)

    if user is None or user.email != payload.get("email"):
        return page("This verification link is invalid or has expired.", False, 400)

    if not user.email_verified:
        user.email_verified = True
        db.commit()
    return page("Email verified! You can now log in.", True, 200)


@app.post("/api/resend-verification")
def resend_verification(
    body: schemas.ResendVerification,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(database.get_db),
):
    email = str(body.email).lower()
    ratelimit.hit(db, "resend_ip", ratelimit.client_ip(request), config.RESEND_LIMIT_PER_IP)
    ratelimit.hit(db, "resend_email", ratelimit.hash_key(email), config.RESEND_LIMIT_PER_EMAIL)

    user = db.query(models.User).filter(models.User.email == email).first()
    if user and not user.email_verified and config.REQUIRE_EMAIL_VERIFICATION:
        background.add_task(mailer.send_verification_email, user.email, _verification_link(request, user))

    # Hamesha same jawab: pata nahi chalta ke email registered hay ya nahi
    return {"msg": "If this email is registered and not verified yet, a new verification link has been sent."}


@app.post("/api/login")
def login(
    user_data: schemas.UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(database.get_db),
):
    ip = ratelimit.client_ip(request)
    identifier = user_data.username_or_email.strip()
    normalized = normalize_username(identifier)
    account_key = ratelimit.hash_key(normalized)
    account_ip_key = ratelimit.hash_key(normalized, ip)

    # Brute-force rokne ke 3 raste: IP ke hisab se, (account+IP) ke hisab se, aur sirf account ke hisab se
    ratelimit.hit(db, "login_ip", ip, config.LOGIN_LIMIT_PER_IP)
    ratelimit.check(db, "login_fail_acct_ip", account_ip_key, *config.LOGIN_FAIL_LIMIT_PER_ACCOUNT_IP)
    ratelimit.check(db, "login_fail_acct", account_key, *config.LOGIN_FAIL_LIMIT_PER_ACCOUNT)

    candidates = db.query(models.User).filter(
        or_(
            models.User.username_normalized == normalized,
            models.User.username == identifier,
            models.User.email == identifier.lower(),
        )
    ).all()
    db_user = next(
        (u for u in candidates if auth_utils.verify_password(user_data.password, u.hashed_password)), None
    )

    # Agar valid nahi hay toh customized denied error message
    if db_user is None:
        ratelimit.record(db, "login_fail_acct_ip", account_ip_key)
        ratelimit.record(db, "login_fail_acct", account_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Try Again! Username/Emails or Password are not valid. Please sign up if you don't have an account.",
        )

    if db_user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended. Please contact the site administrators.",
        )

    if config.REQUIRE_EMAIL_VERIFICATION and not db_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first. Check your inbox for the verification link.",
        )

    ratelimit.clear(db, "login_fail_acct_ip", account_ip_key)

    # Token JSON mai nahi jata, sirf HttpOnly cookie mai (JavaScript usay chura nahi sakti)
    auth_utils.set_session_cookie(response, request, auth_utils.create_access_token(db_user))
    response.headers["Cache-Control"] = "no-store"
    return {"username": db_user.username, "msg": "Login Successful!"}


@app.post("/api/logout")
def logout(request: Request, response: Response, db: Session = Depends(database.get_db)):
    auth_utils.enforce_csrf(request)
    user = auth_utils.get_user_from_request(request, db)
    if user is not None:
        # Token version badhane se is user ke sab purane tokens server par bekaar ho jate hain
        user.token_version += 1
        db.commit()
    auth_utils.clear_session_cookie(response)
    return {"msg": "Logged out"}


@app.get("/api/me")
def me(response: Response, user: models.User = Depends(auth_utils.get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {
        "id": user.id,
        "username": user.username,
        "email_verified": user.email_verified,
        "is_admin": user.is_admin,
    }


# --- CAR ROUTES ---
# List / detail / create / edit / delete / My Ads / photos: cars.py mai hain.
# Yahan sirf report aur status ke endpoints hain.

@app.post("/api/cars/{car_id}/report")
def report_car(
    car_id: int,
    body: schemas.ReportCreate,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(auth_utils.get_current_user),
):
    if config.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before reporting ads.")

    car = db.get(models.Car, car_id)
    if car is None or car.is_hidden or car.is_deleted:
        raise HTTPException(status_code=404, detail="Ad not found.")
    if car.owner_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot report your own ad.")

    ratelimit.check(db, "report_user", str(user.id), *config.REPORT_LIMIT_PER_USER)

    already = db.query(models.AdReport.id).filter(
        models.AdReport.car_id == car.id, models.AdReport.reporter_id == user.id
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="You have already reported this ad.")

    db.add(models.AdReport(
        car_id=car.id, reporter_id=user.id, reason=body.reason, details=body.details,
        status="open", created_at=utcnow(),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already reported this ad.")

    ratelimit.record(db, "report_user", str(user.id))
    return {"msg": "Thank you! Your report was sent to the moderators."}


@app.patch("/api/cars/{car_id}/status", response_model=schemas.CarResponse)
def update_car_status(
    car_id: int,
    body: schemas.CarStatusUpdate,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(auth_utils.get_current_user),
):
    car = db.get(models.Car, car_id)
    if car is None or car.is_deleted:
        raise HTTPException(status_code=404, detail="Car not found.")
    if car.is_hidden:
        raise HTTPException(status_code=403, detail="This ad was removed by the moderators.")
    # Sirf ad ka maalik apni ad ka status badal sakta hay
    if car.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You can only change the status of your own ads.")

    car.status = body.status
    db.commit()
    db.refresh(car)
    return car


@app.get("/api/analytics")
def get_analytics(
    db: Session = Depends(database.get_db),
    _user: models.User = Depends(auth_utils.get_current_user),   # login zaroori
):
    # Asli counts: status ke hisab se group kar ke
    rows = (
        db.query(models.Car.status, func.count(models.Car.id))
        .filter(models.Car.is_hidden.is_(False), models.Car.is_deleted.is_(False))
        .group_by(models.Car.status)
        .all()
    )
    counts = {status_name: count for status_name, count in rows}
    return {
        "total_listings": sum(counts.values()),
        "available_cars": counts.get("available", 0),
        "pending_cars": counts.get("pending", 0),
        "sold_cars": counts.get("sold", 0),
    }


# --- LOGIN-GATE: bina login ke sirf login/signup page dikhen ---
# Deny-by-default: jo cheez neeche PUBLIC list mai nahi, woh login ke baad hi milti hay.

PUBLIC_EXACT_PATHS = {
    "/", "/carhtml/login.html", "/carhtml/signup.html",
    "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect",
}
PUBLIC_PREFIXES = ("/api/", "/css/", "/js/","/images/")   # /api/* ko apni dependencies protect karti hain


def _is_public_path(raw_path: str) -> bool:
    # Windows par \ bhi path separator hay aur "INDEX.HTML" / "index.html." bhi wohi file hoti hay,
    # is liye path ko normalize karte hain taake tricks se gate bypass na ho.
    path = _normalize_path(raw_path)
    if not path.startswith("/"):
        return False
    return path in PUBLIC_EXACT_PATHS or path.startswith(PUBLIC_PREFIXES)


def _normalize_path(raw_path: str) -> str:
    return posixpath.normpath(unquote(raw_path).replace("\\", "/")).lower().rstrip(". ")


def _session_info(request: Request) -> Optional[bool]:
    """Valid session ho to user ka is_admin (True/False), warna None."""
    if not request.cookies.get(auth_utils.COOKIE_NAME):
        return None
    with database.SessionLocal() as db:
        user = auth_utils.get_user_from_request(request, db)
        return None if user is None else bool(user.is_admin)


@app.middleware("http")
async def require_login_for_pages(request: Request, call_next):
    if _is_public_path(request.url.path):
        return await call_next(request)

    is_admin = await run_in_threadpool(_session_info, request)
    if is_admin is None:
        return RedirectResponse(url="/carhtml/login.html", status_code=302, headers={"Cache-Control": "no-store"})

    # admin.html sirf admin ko (asli rok /api/admin/* par hay; yeh non-admin ko khali page dikhne se bachata hay)
    if not is_admin and _normalize_path(request.url.path).rsplit("/", 1)[-1] == "admin.html":
        return RedirectResponse(url="/carhtml/index.html", status_code=302, headers={"Cache-Control": "no-store"})

    response = await call_next(request)
    if _normalize_path(request.url.path).startswith("/media/"):
        # Photos ke naam random aur kabhi nahi badalte: browser unhe cache kar sakta hay (sirf is user ke liye)
        response.headers["Cache-Control"] = "private, max-age=86400"
    else:
        # Logout ke baad Back button se purana page cache se na khule
        response.headers["Cache-Control"] = "no-store"
    return response


# --- FRONTEND (same server se serve hoga) ---
# Yeh sab API routes ke BAAD aana chahiye, warna /api/* ko overshadow kar dega.

app.include_router(admin.router)
app.include_router(cars.router)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/carhtml/index.html")


if config.FRONTEND_DIR.exists():
    # Photos (login ke baad hi milti hain: middleware /media/ ko bhi gate karta hay)
    app.mount("/media", StaticFiles(directory=config.UPLOAD_ROOT), name="media")
    app.mount("/carhtml", StaticFiles(directory=config.FRONTEND_DIR / "HTML"), name="frontend_html")
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR), name="frontend")
