from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel

import os
from dotenv import load_dotenv

from app.database import SessionLocal
from app.models.user import User
from app.auth.hash import hash_password, verify_password
from app.auth.jwt_handler import create_access_token
from app.utils.email import generate_otp, get_otp_expiry
from app.utils.email_service import send_otp_email

load_dotenv()

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

router = APIRouter()


# =====================================================
# DATABASE SESSION
# =====================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str
    department: str
    admin_key: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str


# =====================================================
# REGISTER
# =====================================================

@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 🔐 Admin Secret Validation
    if request.role.lower() == "admin":
        if request.admin_key != ADMIN_SECRET_KEY:
            raise HTTPException(
                status_code=403,
                detail="Invalid admin secret key"
            )

    otp = generate_otp()
    expiry = get_otp_expiry()

    print("Generated OTP:", otp)

    # Admin approval logic
    if request.role == "admin":
        approved = False
    else:
        approved = True

    new_user = User(
    email=request.email,
    password_hash=hash_password(request.password),
    role=request.role,
    department=request.department,
    is_verified=False,
    otp_code=otp,
    otp_expiry=expiry
)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    email_sent = send_otp_email(request.email, otp)

    if not email_sent:
        db.delete(new_user)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to send OTP email")

    return {
        "message": "User registered successfully. Please verify OTP."
    }


# =====================================================
# VERIFY OTP
# =====================================================

@router.post("/verify-otp")
def verify_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "User already verified"}

    print("Entered OTP:", request.otp)
    print("Stored OTP:", user.otp_code)

    if user.otp_code != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.otp_expiry is None or user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    user.is_verified = True
    user.otp_code = None
    user.otp_expiry = None

    db.commit()

    return {"message": "Email verified successfully"}


# =====================================================
# LOGIN
# =====================================================

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email")

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    token = create_access_token({
        "user_id": user.id,
        "role": user.role
    })

    return {"access_token": token}


# =====================================================
# FORGOT PASSWORD — SEND OTP
# =====================================================

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = generate_otp()
    expiry = get_otp_expiry()

    print("Generated OTP:", otp)

    user.otp_code = otp
    user.otp_expiry = expiry

    db.commit()

    email_sent = send_otp_email(request.email, otp)

    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send OTP email")

    return {"message": "Password reset OTP sent to email"}


# =====================================================
# VERIFY RESET OTP
# =====================================================

@router.post("/verify-reset-otp")
def verify_reset_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    print("Entered OTP:", request.otp)
    print("Stored OTP:", user.otp_code)

    if str(user.otp_code) != str(request.otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.otp_expiry is None or user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    return {"message": "OTP verified successfully"}


# =====================================================
# RESET PASSWORD
# =====================================================

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(request.new_password)
    user.otp_code = None
    user.otp_expiry = None

    db.commit()

    return {"message": "Password updated successfully"}
