from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.auth.hash import hash_password, verify_password
from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.utils.email import generate_otp, get_otp_expiry
from app.utils.email_service import send_otp_email
from app.config import settings
from app.logger import logger

router = APIRouter()


# ─── Request / Response Schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "student"
    department: Optional[str] = None
    full_name: Optional[str] = None
    admin_key: Optional[str] = None


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
    otp: str
    new_password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ─── Register ─────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, req: Request, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if request.role.lower() == "admin":
        if not request.admin_key or request.admin_key != settings.ADMIN_SECRET_KEY:
            raise HTTPException(status_code=403, detail="Invalid admin secret key")

    # Password strength check
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    otp = generate_otp()
    expiry = get_otp_expiry()

    new_user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role.lower(),
        department=request.department or "GENERAL",
        full_name=request.full_name,
        is_verified=False,
        is_active=True,
        otp_code=otp,
        otp_expiry=expiry,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if not send_otp_email(request.email, otp):
        db.delete(new_user)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to send OTP email")

    logger.info(f"User registered: {request.email} | role={request.role}")
    return {"message": "Registered successfully. Please verify OTP sent to your email."}


# ─── Verify OTP ───────────────────────────────────────────────────────────────

@router.post("/verify-otp")
def verify_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return {"message": "Email already verified"}
    if user.otp_code != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if not user.otp_expiry or user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

    user.is_verified = True
    user.otp_code = None
    user.otp_expiry = None
    db.commit()

    logger.info(f"Email verified: {request.email}")
    return {"message": "Email verified successfully"}


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    # Generic error to prevent email enumeration
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account has been deactivated")

    user.last_login = datetime.utcnow()
    db.commit()

    token_data = {"user_id": user.id, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"Login: {request.email} | role={user.role}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role,
        "department": user.department,
    }


# ─── Refresh Token ────────────────────────────────────────────────────────────

@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    from jose import JWTError
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("user_id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_data = {"user_id": user.id, "role": user.role}
    return {"access_token": create_access_token(token_data), "token_type": "bearer"}


# ─── Forgot Password ──────────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    # Don't reveal whether email exists
    if user:
        otp = generate_otp()
        user.otp_code = otp
        user.otp_expiry = get_otp_expiry()
        db.commit()
        send_otp_email(request.email, otp)
        logger.info(f"Password reset OTP sent: {request.email}")
    return {"message": "If this email is registered, a reset OTP has been sent."}


# ─── Verify Reset OTP ─────────────────────────────────────────────────────────

@router.post("/verify-reset-otp")
def verify_reset_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.otp_code) != str(request.otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if not user.otp_expiry or user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")
    return {"message": "OTP verified. Proceed to reset password."}


# ─── Reset Password ───────────────────────────────────────────────────────────

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.otp_code) != str(request.otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if not user.otp_expiry or user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.password_hash = hash_password(request.new_password)
    user.otp_code = None
    user.otp_expiry = None
    db.commit()

    logger.info(f"Password reset: {request.email}")
    return {"message": "Password updated successfully"}


# ─── Resend OTP ───────────────────────────────────────────────────────────────

@router.post("/resend-otp")
def resend_otp(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expiry = get_otp_expiry()
    db.commit()

    if not send_otp_email(request.email, otp):
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return {"message": "OTP resent successfully"}
