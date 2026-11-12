import re
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Sirf English letters/digits: Urdu/Cyrillic jaise lookalike characters se fake usernames nahi ban sakte
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
# Brand/model: letters, digits, space aur . - / + & ( ) '  (HTML tags jaise < > allow nahi)
CAR_TEXT_RE = re.compile(r"^\w[\w .\-/+&()']*$")
PHONE_RE = re.compile(r"^\+?\d{7,15}$")


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
class CarCreate(BaseModel):
    """Nayi ad ki strict validation (sirf input par)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1900, le=date.today().year + 1)
    price: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    seller_phone: str = Field(min_length=7, max_length=32)

    @field_validator("brand", "model")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not CAR_TEXT_RE.fullmatch(value):
            raise ValueError("Only letters, numbers, spaces and . - / + & ( ) ' are allowed.")
        return value

    @field_validator("seller_phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        cleaned = re.sub(r"[\s\-()]", "", value)
        if not PHONE_RE.fullmatch(cleaned):
            raise ValueError("Enter a valid phone number (7-15 digits, optional leading +).")
        return cleaned


class CarResponse(BaseModel):
    """Response mai validation nahi: purani (pehle se save) ads bhi bina error ke dikhti rahen."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    model: str
    year: int
    price: float
    seller_phone: str
    owner_id: int
