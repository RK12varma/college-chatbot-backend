import pdfplumber
from docx import Document as DocxDocument
import xml.etree.ElementTree as ET
from sentence_transformers import SentenceTransformer
import numpy as np

from app.document.faiss_manager import get_index, save_index
from app.database import SessionLocal
from app.models.chunk import DocumentChunk


# =====================================================
# LOAD EMBEDDING MODEL
# =====================================================

model = SentenceTransformer("all-MiniLM-L6-v2")


# =====================================================
# EXTRACT TEXT
# =====================================================

def extract_text(file_path, file_type):

    if file_type == "pdf":
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text

    elif file_type == "docx":
        doc = DocxDocument(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    elif file_type == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    elif file_type == "xml":
        tree = ET.parse(file_path)
        root = tree.getroot()
        return ET.tostring(root, encoding="unicode")

    return ""


# =====================================================
# CHUNK TEXT
# =====================================================

def chunk_text(text, chunk_size=400):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))

    return chunks


# =====================================================
# CREATE EMBEDDINGS
# =====================================================

def create_embeddings(text_chunks):
    """
    Returns float32 normalized embeddings.
    """

    embeddings = model.encode(
        text_chunks,
        normalize_embeddings=True  # 🔥 Keep consistent with search
    )

    return np.array(embeddings).astype("float32")


# =====================================================
# SAVE TO FAISS
# =====================================================

def save_to_faiss(embeddings, ids):

    index = get_index()

    ids = np.array(ids)

    # Defensive dimension check
    if embeddings.shape[1] != index.d:
        raise ValueError(
            f"Embedding dimension {embeddings.shape[1]} "
            f"does not match FAISS dimension {index.d}"
        )

    index.add_with_ids(embeddings, ids)

    save_index()


# =====================================================
# FULL DOCUMENT PROCESSING PIPELINE
# =====================================================

def process_pdf(file_path, document_id):
    """
    Full pipeline:
    1. Extract text
    2. Chunk text
    3. Store chunks in DB
    4. Generate embeddings
    5. Store vectors in FAISS using real DB IDs
    """

    db = SessionLocal()

    try:
        # 1️⃣ Extract text
        text = extract_text(file_path, "pdf")

        if not text.strip():
            return {"status": "error", "message": "No text extracted"}

        # 2️⃣ Chunk text
        chunks = chunk_text(text)

        if not chunks:
            return {"status": "error", "message": "No chunks created"}

        db_chunks = []
        vector_ids = []

        # 3️⃣ Save chunks in DB FIRST
        for i, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=document_id,
                chunk_text=chunk,
                chunk_index=i
            )

            db.add(db_chunk)
            db.flush()  # Get ID immediately

            vector_ids.append(db_chunk.id)
            db_chunks.append(chunk)

        db.commit()

        # 4️⃣ Generate embeddings
        embeddings = create_embeddings(db_chunks)

        # 5️⃣ Store in FAISS
        save_to_faiss(embeddings, vector_ids)

        return {
            "status": "success",
            "chunks_processed": len(chunks)
        }

    finally:
        db.close()