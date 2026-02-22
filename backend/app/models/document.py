from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String)
    file_type = Column(String)

    file_hash = Column(String, unique=True)

    department = Column(String)
    semester = Column(Integer)
    subject = Column(String)

    uploaded_by = Column(Integer, ForeignKey("users.id"))

    file_path = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 🔥 NEW FIELDS FOR SMART SCRAPER
    source_url = Column(String, nullable=True)  # original website link
    last_checked = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # 🔥 Relationship to chunks (UNCHANGED LOGIC)
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )