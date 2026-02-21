from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))

    chunk_text = Column(Text)
    chunk_index = Column(Integer)

    vector_id = Column(Integer, unique=True)

    # 🔥 New field for subject-wise data
    subject_data = Column(Text, nullable=True)  # JSON string

    document = relationship(
        "Document",
        back_populates="chunks"
    )