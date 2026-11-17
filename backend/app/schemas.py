import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

# Sirf English letters/digits: Urdu/Cyrillic jaise lookalike characters se fake usernames nahi ban sakte
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
# Brand/model/city/color: letters, digits, space aur . - / + & ( ) ' , (HTML tags jaise < > allow nahi)
CAR_TEXT_RE = re.compile(r"^\w[\w .\-/+&()',]*$")
PHONE_RE = re.compile(r"^\+?\d{7,15}$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

FuelType = Literal["petrol", "diesel", "hybrid", "electric", "cng", "lpg"]
Transmission = Literal["manual", "automatic"]
Condition = Literal["new", "used"]
CarStatus = Literal["available", "pending", "sold"]
SortOrder = Literal["newest", "oldest", "price_asc", "price_desc", "year_desc", "year_asc", "mileage_asc"]


# User Schemas
class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def username_charset(cls, value: str) -> str:
        if not USERNAME_RE.fullmatch(value):
            raise ValueError("Username can only contain English letters, numbers, dot, dash and underscore.")
        return value

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        # bcrypt sirf pehle 72 bytes leta hai (non-English chars 1 se zyada byte lete hain)
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password is too long (max 72 bytes).")
        return value


class UserLogin(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=72)


class ResendVerification(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str


class SignupResponse(UserResponse):
    verification_required: bool
    msg: str


# Car Schemas
class _CarValidators(BaseModel):
    """Ad ki fields ki shared safai/validation (naye ad aur edit dono ke liye). None allowed (optional fields)."""

    @field_validator("brand", "model", "city", "color", check_fields=False)
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        value = " ".join(value.split())
        if not value:
            return None
        if not CAR_TEXT_RE.fullmatch(value):
            raise ValueError("Only letters, numbers, spaces and . - / + & ( ) ' , are allowed.")
        return value

    @field_validator("seller_phone", check_fields=False)
    @classmethod
    def clean_phone(cls, value):
        if value is None:
            return None
        cleaned = re.sub(r"[\s\-()]", "", value)
        if not PHONE_RE.fullmatch(cleaned):
            raise ValueError("Enter a valid phone number (7-15 digits, optional leading +).")
        return cleaned

    @field_validator("description", check_fields=False)
    @classmethod
    def clean_description(cls, value):
        if value is None:
            return None
        value = CONTROL_CHARS_RE.sub("", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
        return value or None


class CarCreate(_CarValidators):
    """Nayi ad ki strict validation (sirf input par)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1900, le=date.today().year + 1)
    price: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    seller_phone: str = Field(min_length=7, max_length=32)
    city: str = Field(min_length=2, max_length=60)
    mileage: int = Field(ge=0, le=2_000_000)                      # km
    fuel_type: FuelType
    transmission: Transmission
    condition: Condition
    engine_cc: Optional[int] = Field(default=None, ge=50, le=10_000)
    color: Optional[str] = Field(default=None, max_length=40)
    description: Optional[str] = Field(default=None, max_length=2000)


REQUIRED_CAR_FIELDS = (
    "brand", "model", "year", "price", "seller_phone", "city", "mileage", "fuel_type", "transmission", "condition",
)


class CarUpdate(_CarValidators):
    """Ad edit: sirf wahi fields bhejo jo badalni hain. Zaroori fields ko khali (null) nahi kar sakte."""
    model_config = ConfigDict(str_strip_whitespace=True)

    brand: Optional[str] = Field(default=None, min_length=1, max_length=80)
    model: Optional[str] = Field(default=None, min_length=1, max_length=80)
    year: Optional[int] = Field(default=None, ge=1900, le=date.today().year + 1)
    price: Optional[float] = Field(default=None, gt=0, le=1_000_000_000, allow_inf_nan=False)
    seller_phone: Optional[str] = Field(default=None, min_length=7, max_length=32)
    city: Optional[str] = Field(default=None, min_length=2, max_length=60)
    mileage: Optional[int] = Field(default=None, ge=0, le=2_000_000)
    fuel_type: Optional[FuelType] = None
    transmission: Optional[Transmission] = None
    condition: Optional[Condition] = None
    engine_cc: Optional[int] = Field(default=None, ge=50, le=10_000)
    color: Optional[str] = Field(default=None, max_length=40)
    description: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_update(self):
        if not self.model_fields_set:
            raise ValueError("Nothing to update.")
        for name in REQUIRED_CAR_FIELDS:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be empty.")
        return self


class CarStatusUpdate(BaseModel):
    status: CarStatus


# --- Report ad / Admin ---
REPORT_REASONS = ("spam", "fake_or_scam", "wrong_info", "inappropriate", "other")


class ReportCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: Literal["spam", "fake_or_scam", "wrong_info", "inappropriate", "other"]
    details: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def other_needs_details(self):
        if not self.details:
            self.details = None
        if self.reason == "other" and (self.details is None or len(self.details) < 5):
            raise ValueError("Please describe the problem (at least 5 characters) when choosing 'other'.")
        return self


class ModerationNote(BaseModel):
    """Admin action ke saath optional wajah (audit log mai jati hay)."""
    model_config = ConfigDict(str_strip_whitespace=True)
    note: Optional[str] = Field(default=None, max_length=255)


class ImageOut(BaseModel):
    id: int
    url: str
    thumb_url: str


class CarResponse(BaseModel):
    """Response mai validation nahi: purani (pehle se save) ads bhi bina error ke dikhti rahen."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    model: str
    year: int
    price: float
    seller_phone: str
    status: str
    owner_id: int
    city: Optional[str] = None
    mileage: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    engine_cc: Optional[int] = None
    color: Optional[str] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    images: list[ImageOut] = []
    cover_thumb: Optional[str] = None
    seller_name: Optional[str] = None


class CarListResponse(BaseModel):
    items: list[CarResponse]
    total: int
