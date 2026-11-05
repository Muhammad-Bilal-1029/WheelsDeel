from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # String ki length zaroori hai, warna MySQL mai table nahi banta
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(254), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Relationship: Aik user bohot si cars ka ad laga sakta hay
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
