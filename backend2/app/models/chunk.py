from sqlalchemy import Column, Integer, Text, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id           = Column(Integer, primary_key=True, index=True)
    document_id  = Column(Integer, ForeignKey("documents.id"))

    chunk_text   = Column(Text)
    chunk_index  = Column(Integer)
    vector_id    = Column(Integer, unique=True, nullable=True)

    # Classification metadata
    department   = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    semester     = Column(String, nullable=True)
    subject_data = Column(Text,   nullable=True)

    # Source URL for PDF download links
    source_url   = Column(String, nullable=True)   # ← NEW: original PDF/page URL

    document = relationship("Document", back_populates="chunks")