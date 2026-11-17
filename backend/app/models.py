from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import relationship
from .database import Base

CAR_STATUSES = ("available", "pending", "sold")


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
    # Admin banane ka tareeqa: sirf server par `python make_admin.py <username>` (website se koi admin nahi ban sakta)
    is_admin = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    # Ban hone par login nahi ho sakta aur purane sessions bekaar ho jate hain
    is_banned = Column(Boolean, nullable=False, default=False, server_default=text("0"))

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
    # available / pending / sold (sirf owner badal sakta hay)
    status = Column(String(16), nullable=False, default="available", server_default=text("'available'"))
    # Admin ad ko hide kar sakta hay (delete nahi hoti, restore ho sakti hay). Hidden ad listing/analytics mai nahi aati.
    is_hidden = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    # Owner ad delete kare to row nahi hat'ti (reports/evidence ke liye), sirf is_deleted=True hoti hay
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("0"))

    # --- Ad ki details (purani ads mai khali/NULL hoti hain) ---
    city = Column(String(60), index=True)
    mileage = Column(Integer)                 # km
    fuel_type = Column(String(16))            # petrol / diesel / hybrid / electric / cng / lpg
    transmission = Column(String(16))         # manual / automatic
    engine_cc = Column(Integer)
    color = Column(String(40))
    condition = Column("car_condition", String(16))   # new / used (DB mai car_condition: 'condition' MySQL ka reserved word hay)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="cars")


class CarImage(Base):
    """Ad ki photos. File ka naam random hay: <filename>.jpg (bari) aur <filename>_t.jpg (thumbnail)."""
    __tablename__ = "car_images"

    id = Column(Integer, primary_key=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    filename = Column(String(64), nullable=False, unique=True)
    position = Column(Integer, nullable=False, default=0)    # 0 = cover photo
    created_at = Column(DateTime, nullable=False)


class RateEvent(Base):
    """Rate limiting ka record (login, signup, ads). DB mai hay is liye restart/multi-worker par bhi kaam karta hay."""
    __tablename__ = "rate_events"

    id = Column(Integer, primary_key=True)
    bucket = Column(String(40), nullable=False)
    key = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (Index("ix_rate_events_lookup", "bucket", "key", "created_at"),)


class AdReport(Base):
    """Users ki taraf se kisi ad ki shikayat."""
    __tablename__ = "ad_reports"

    id = Column(Integer, primary_key=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reason = Column(String(24), nullable=False)
    details = Column(String(500))
    status = Column(String(12), nullable=False, default="open", index=True)   # open / resolved / dismissed
    created_at = Column(DateTime, nullable=False)
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)

    # Aik user aik ad ko sirf aik dafa report kar sakta hay
    __table_args__ = (UniqueConstraint("car_id", "reporter_id", name="uq_ad_reports_car_reporter"),)


class AdminAction(Base):
    """Admin ne kya kiya: koi bhi moderation action yahan record hota hay (audit log)."""
    __tablename__ = "admin_actions"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(32), nullable=False)
    target_type = Column(String(16), nullable=False)   # ad / user / report
    target_id = Column(Integer, nullable=False)
    note = Column(String(255))
    created_at = Column(DateTime, nullable=False)
