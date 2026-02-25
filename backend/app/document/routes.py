import os
import hashlib
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.auth.dependencies import admin_required
from app.document.processing import (
    extract_text,
    chunk_text,
    create_embeddings,
    save_to_faiss,
)

UPLOAD_DIR = "data"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_file_hash(file_bytes: bytes):
    return hashlib.sha256(file_bytes).hexdigest()


@router.post("/upload")
def upload_document(
    department: str = None,
    semester: int = None,
    subject: str = None,
    file: UploadFile = File(...),
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):

    # Read file
    file_bytes = file.file.read()
    file_hash = generate_file_hash(file_bytes)

    # Duplicate check
    existing = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing:
        raise HTTPException(status_code=400, detail="File already exists")

    # Save file
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    file_type = file.filename.split(".")[-1].lower()

    # Save document metadata
    new_doc = Document(
        filename=file.filename,
        file_path=file_path,
        file_type=file_type,
        file_hash=file_hash,
        department=department or "GENERAL",
        semester=semester or 0,
        subject=subject or "GENERAL",
        uploaded_by=user.id,
    )

    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # Extract text
    text = extract_text(file_path, file_type)

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text")

    # Chunk text
    chunks = chunk_text(text)

    # 🔥 SAFE FALLBACK ADDED
    if not chunks:
        print("No structured chunks — saving full text as fallback")
        chunks = [{
            "text": text[:1000],
            "subject_json": None
        }]

    # Generate embeddings
    embeddings = create_embeddings([chunk["text"] for chunk in chunks])

    chunk_ids = []

    for i, chunk_obj in enumerate(chunks):

        db_chunk = DocumentChunk(
            document_id=new_doc.id,
            chunk_text=chunk_obj["text"],
            chunk_index=i,
            subject_data=chunk_obj["subject_json"],
        )

        db.add(db_chunk)
        db.flush()
        chunk_ids.append(db_chunk.id)

    db.commit()

    # Save to FAISS
    save_to_faiss(embeddings, chunk_ids)

    # Update vector_id
    for cid in chunk_ids:
        chunk = db.query(DocumentChunk).get(cid)
        chunk.vector_id = cid

    db.commit()

    return {
        "message": "File uploaded and indexed successfully",
        "document_id": new_doc.id,
        "chunks_created": len(chunks),
    }