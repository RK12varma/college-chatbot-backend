import sys
sys.path.insert(0, ".")

# Must import ALL models so SQLAlchemy can resolve relationships
from app.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.scrape_source import ScrapeSource
from app.models.chat_history import ChatSession, ChatTurn
from app.models.audit_log import AuditLog
from app.document.processing import create_embeddings
from app.document.faiss_manager import save_index
import numpy as np
import faiss

print("Starting FAISS rebuild...")

db = SessionLocal()
chunks = db.query(DocumentChunk).all()
print(f"Total chunks in DB: {len(chunks)}")

if not chunks:
    print("No chunks found!")
    db.close()
    exit()

texts = [c.chunk_text for c in chunks]
ids   = [c.id for c in chunks]

print(f"Generating embeddings for {len(texts)} chunks...")
embeddings = create_embeddings(texts)

base  = faiss.IndexFlatIP(embeddings.shape[1])
index = faiss.IndexIDMap(base)
index.add_with_ids(embeddings, np.array(ids, dtype="int64"))

save_index(index)

# Update vector_id in DB to match chunk id
for c in chunks:
    c.vector_id = c.id
db.commit()
db.close()

print(f"✅ FAISS rebuilt with {index.ntotal} vectors")