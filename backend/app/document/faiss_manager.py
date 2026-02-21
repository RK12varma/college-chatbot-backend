import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.models.chunk import DocumentChunk

FAISS_INDEX_PATH = "faiss.index"
dimension = 384

# Load embedding model once
model = SentenceTransformer("all-MiniLM-L6-v2")

# Load or create FAISS index
if os.path.exists(FAISS_INDEX_PATH):
    index = faiss.read_index(FAISS_INDEX_PATH)
else:
    base_index = faiss.IndexFlatL2(dimension)
    index = faiss.IndexIDMap(base_index)
    faiss.write_index(index, FAISS_INDEX_PATH)


def get_index():
    return index


def save_index():
    faiss.write_index(index, FAISS_INDEX_PATH)


# =====================================================
# SEARCH SIMILAR CHUNKS
# =====================================================
def search_similar_chunks(question: str, db: Session, top_k: int = 5):
    """
    1. Convert question to embedding
    2. Search FAISS
    3. Fetch chunk text from DB
    """

    if index.ntotal == 0:
        return []

    # Create query embedding
    query_vector = model.encode([question])
    query_vector = np.array(query_vector).astype("float32")

    # Search FAISS
    distances, ids = index.search(query_vector, top_k)

    chunk_texts = []

    for chunk_id in ids[0]:
        if chunk_id == -1:
            continue

        chunk = db.query(DocumentChunk).filter(
            DocumentChunk.id == int(chunk_id)
        ).first()

        if chunk:
            chunk_texts.append(chunk.chunk_text)

    return chunk_texts