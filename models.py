from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Date, Text
from sqlalchemy.orm import relationship
from db import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(128), nullable=False)  # Armazena hash da senha, não a senha em si

    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    buckets = relationship("Bucket", back_populates="user", cascade="all, delete-orphan")
    giants = relationship("Giant", back_populates="user", cascade="all, delete-orphan")
    movements = relationship("Movement", back_populates="user", cascade="all, delete-orphan")
    bills = relationship("Bill", back_populates="user", cascade="all, delete-orphan")
    giant_payments = relationship("GiantPayment", back_populates="user", cascade="all, delete-orphan")

class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    monthly_income  = Column(Float, default=0.0)
    monthly_expense = Column(Float, default=0.0)

    user = relationship("User", back_populates="profile")

class Bucket(Base):
    __tablename__ = "buckets"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    description = Column(String(200), default="")
    percent = Column(Float, nullable=False)
    balance = Column(Float, default=0.0)
    type = Column(String(20), default="generic")

    user = relationship("User", back_populates="buckets")
    movements = relationship("Movement", back_populates="bucket")

class Giant(Base):
    __tablename__ = "giants"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    total_to_pay = Column(Float, nullable=False)
    parcels = Column(Integer, default=0)
    priority = Column(Integer, default=1)
    status = Column(String(20), default="active")  # active, defeated
    weekly_goal = Column(Float, default=0.0)  # New field
    interest_rate = Column(Float, default=0.0)  # New field
    payoff_efficiency = Column(Float, default=0.0)  # New field

    user = relationship("User", back_populates="giants")
    payments = relationship("GiantPayment", back_populates="giant")

class GiantPayment(Base):
    __tablename__ = "giant_payments"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    user_id  = Column(Integer, ForeignKey("users.id",   ondelete="CASCADE"), nullable=False)
    giant_id = Column(Integer, ForeignKey("giants.id",  ondelete="CASCADE"), nullable=False)
    amount   = Column(Float, nullable=False)
    date     = Column(Date,  nullable=False)
    note     = Column(Text, default="")

    user = relationship("User", back_populates="giant_payments")
    giant = relationship("Giant", back_populates="payments")

class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bucket_id = Column(Integer, ForeignKey("buckets.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String(20), nullable=False)  # Receita, Despesa
    amount = Column(Float, nullable=False)
    description = Column(String(200), default="")
    date = Column(Date, nullable=False)

    user = relationship("User", back_populates="movements")
    bucket = relationship("Bucket", back_populates="movements")

class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    is_critical = Column(Boolean, default=False)
    paid = Column(Boolean, default=False)

    user = relationship("User", back_populates="bills")
