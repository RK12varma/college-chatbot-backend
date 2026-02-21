from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
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

    created_at = Column(DateTime, default=datetime.utcnow)

    file_path = Column(String)

    # 🔥 Relationship to chunks
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )