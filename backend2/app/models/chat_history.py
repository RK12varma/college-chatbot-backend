from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from sqlalchemy.dialects.postgresql import JSONB


class ChatSession(Base):
    """Groups chat turns into a conversation session."""
    __tablename__ = "chat_sessions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    title      = Column(String(255), nullable=True)   # auto-derived from first question
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    turns = relationship("ChatTurn", back_populates="session", cascade="all, delete-orphan")
    user  = relationship("User")


class ChatTurn(Base):
    """Single question-answer pair inside a session."""
    __tablename__ = "chat_turns"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role        = Column(String(16), nullable=False)  # "user" | "assistant"
    content     = Column(Text, nullable=False)
    sources     = Column(JSONB, nullable=True)           # JSON list of filenames
    created_at  = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="turns")
