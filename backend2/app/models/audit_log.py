from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from app.database import Base


class AuditLog(Base):
    """Tracks all significant admin & user actions for accountability."""
    __tablename__ = "audit_logs"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    action     = Column(String(128), nullable=False)   # e.g. "document.upload"
    resource   = Column(String(128), nullable=True)    # e.g. "document:42"
    detail     = Column(Text, nullable=True)           # JSON or text
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
