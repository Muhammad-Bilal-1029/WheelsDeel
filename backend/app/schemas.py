from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# User Schemas
class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

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

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str

# Car Schemas
class CarCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1886, le=date.today().year + 1)
    price: float = Field(gt=0, allow_inf_nan=False)
    seller_phone: str = Field(min_length=3, max_length=32)

class CarResponse(CarCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
