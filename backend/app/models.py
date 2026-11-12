from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, text,
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # String ki length zaroori hai, warna MySQL mai table nahi banta
    username = Column(String(50), unique=True, index=True, nullable=False)
    # Lowercase + NFKC form: "Admin" aur "admin" ko ek hi account maanta hay (impersonation rokta hay).
    # Purane DB mai migrate.py isay bhar deta hay, is liye yahan nullable hay.
    username_normalized = Column(String(160), unique=True, index=True)
    email = Column(String(254), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # False ho to email verify hone tak login nahi ho sakta (agar REQUIRE_EMAIL_VERIFICATION on hay)
    email_verified = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    # Logout par +1 hota hay: purane tokens foran invalid ho jate hain (server-side revoke)
    token_version = Column(Integer, nullable=False, default=0, server_default=text("0"))

    # Relationship: Aik user bohot si cars ka ad laga sakta hai
    cars = relationship("Car", back_populates="owner")


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(80), index=True, nullable=False)
    model = Column(String(80), nullable=False)
    year = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    seller_phone = Column(String(32), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="cars")


class RateEvent(Base):
    """Rate limiting ka record (login, signup, ads). DB mai hay is liye restart/multi-worker par bhi kaam karta hay."""
    __tablename__ = "rate_events"

    id = Column(Integer, primary_key=True)
    bucket = Column(String(40), nullable=False)
    key = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (Index("ix_rate_events_lookup", "bucket", "key", "created_at"),)
