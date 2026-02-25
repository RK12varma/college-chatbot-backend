from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON
from app.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))

    chunk_text = Column(Text)
    chunk_index = Column(Integer)

    vector_id = Column(Integer, unique=True)

    # 🔥 Now using native PostgreSQL JSON type
    subject_data = Column(JSON, nullable=True)

    document = relationship(
        "Document",
        back_populates="chunks"
    )