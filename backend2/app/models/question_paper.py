# backend/app/models/question_paper.py
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database import Base


class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id          = Column(Integer, primary_key=True, index=True)
    department  = Column(String(50),  nullable=False, default="DS")
    semester    = Column(String(20),  nullable=False)   # SEM-III, SEM-V etc
    exam_month  = Column(String(20),  nullable=False)   # May, December
    exam_year   = Column(Integer,     nullable=False)   # 2024, 2025
    exam_label  = Column(String(50),  nullable=False)   # "May-2025"
    url         = Column(Text,        nullable=False)   # direct PDF URL
    filename    = Column(String(255), nullable=True)
    source_page = Column(Text,        nullable=True)
    created_at  = Column(DateTime,    default=datetime.utcnow)
    updated_at  = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)