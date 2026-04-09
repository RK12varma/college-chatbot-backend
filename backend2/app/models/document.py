from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id           = Column(Integer, primary_key=True, index=True)
    filename     = Column(String)
    file_type    = Column(String)
    file_hash    = Column(String, unique=True)
    department   = Column(String)
    semester     = Column(Integer)
    subject      = Column(String)
    uploaded_by  = Column(Integer, ForeignKey("users.id"))
    file_path    = Column(String)
    created_at   = Column(DateTime, default=datetime.utcnow)
    source_url   = Column(String, nullable=True)
    last_checked = Column(DateTime, default=datetime.utcnow)
    is_active    = Column(Boolean, default=True)

    # ── New: clean label + dept tag for source display ────────────────────────
    source_label = Column(String(255), nullable=True)   # e.g. "Data Science - Faculty"
    dept_tag     = Column(String(50),  nullable=True)   # e.g. "DS", "CE", "MECH"

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )