"""
Run this script ONCE to correctly index all SEM-V students.
Usage: cd backend && python insert_results.py
"""
import sys, os, json
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.scrape_source import ScrapeSource
from app.models.chat_history import ChatSession, ChatTurn
from app.models.audit_log import AuditLog
from app.document.faiss_manager import save_index
from app.document.result_extractor import (
    make_result_chunk_text,
    parse_result_from_tables,
)
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

PDF_PATH = r"C:\Users\Rahul Varma\Desktop\sem6\backend2\data\8282a98ab5409c11dab4db7c32ea90de90fbefd96414b0ede1e4f5f081d42eb2_DATA-SCIENCE-SEM-V-C-SCHEME-REG-NOV-2025.pdf"
SEMESTER = "SEM-V"

def parse_pdf(pdf_data: bytes, semester: str) -> list[dict]:
    # Shared extraction logic (same as runtime processing.py).
    return parse_result_from_tables(pdf_data, semester, min_students=1)


def make_chunk_text(s: dict) -> str:
    return make_result_chunk_text(s)


# ── Find PDF ──────────────────────────────────────────────────────────────────
if not os.path.exists(PDF_PATH):
    for root, dirs, files in os.walk("data"):
        for fn in files:
            if "SEM-V" in fn and fn.endswith(".pdf"):
                PDF_PATH = os.path.join(root, fn)
                break
if not os.path.exists(PDF_PATH):
    print(f"❌ PDF not found. Put it in the 'data' folder.")
    sys.exit(1)

print(f"📄 Parsing: {PDF_PATH}")
with open(PDF_PATH, "rb") as f:
    pdf_data = f.read()

students = parse_pdf(pdf_data, SEMESTER)
print(f"\n✅ Parsed {len(students)} students")

# Verify marks
zero_marks = [s for s in students if s["marks"] == "0"]
if zero_marks:
    print(f"⚠️  {len(zero_marks)} students have marks=0: {[s['seat_no'] for s in zero_marks]}")
else:
    print("✅ All students have marks")

# ── DB operations ─────────────────────────────────────────────────────────────
db = SessionLocal()

doc = (db.query(Document)
         .filter(Document.filename.ilike(f"%{os.path.basename(PDF_PATH)}%"))
         .first()
       or db.query(Document).filter(Document.filename.ilike("%SEM-V%")).first())

if not doc:
    print("❌ No matching document in DB. Upload the PDF from Admin panel first.")
    db.close()
    sys.exit(1)

print(f"📁 Document: id={doc.id} | {doc.filename}")

# Delete ALL old chunks for this document
deleted = db.query(DocumentChunk).filter(
    DocumentChunk.document_id == doc.id
).delete()
print(f"🗑️  Deleted {deleted} old chunks")
db.commit()

# Insert new chunks
for i, s in enumerate(students):
    db.add(DocumentChunk(
        document_id  = doc.id,
        chunk_text   = make_chunk_text(s),
        chunk_index  = i,
        vector_id    = None,
        department   = "DS",
        content_type = "RESULT",
        semester     = s["semester"],
        subject_data = json.dumps(s),
    ))
    db.flush()

db.commit()
print(f"✅ Inserted {len(students)} chunks")

# ── Rebuild FAISS ─────────────────────────────────────────────────────────────
all_chunks = db.query(DocumentChunk).all()
texts = [c.chunk_text for c in all_chunks]
ids   = [c.id for c in all_chunks]

print(f"🧠 Generating embeddings for {len(texts)} chunks...")
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
embeddings = np.array(embeddings).astype("float32")

base  = faiss.IndexFlatIP(embeddings.shape[1])
index = faiss.IndexIDMap(base)
index.add_with_ids(embeddings, np.array(ids, dtype="int64"))
save_index(index)

for c in all_chunks:
    c.vector_id = c.id
db.commit()
db.close()

print(f"\n🎉 Done! FAISS rebuilt with {index.ntotal} vectors")
print("Restart uvicorn and test searches.")
