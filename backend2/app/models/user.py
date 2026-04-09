from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default="student")   # student | admin
    department    = Column(String, nullable=True)
    semester      = Column(Integer, nullable=True)
    full_name     = Column(String, nullable=True)

    # ─── Account status ───────────────────────────────────────────────────────
    is_verified   = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)

    # ─── OTP ──────────────────────────────────────────────────────────────────
    otp_code      = Column(String, nullable=True)
    otp_expiry    = Column(DateTime, nullable=True)

    # ─── Timestamps ───────────────────────────────────────────────────────────
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_login    = Column(DateTime, nullable=True)
