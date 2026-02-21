from sqlalchemy import Column, Integer, Text, ForeignKey
from app.database import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    chunk_text = Column(Text)
    chunk_index = Column(Integer)
    vector_id = Column(Integer, unique=True)   # ✅ ADD THIS
