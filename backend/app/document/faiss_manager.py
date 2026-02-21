import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.models.chunk import DocumentChunk

FAISS_INDEX_PATH = "faiss.index"
dimension = 384
SIMILARITY_THRESHOLD = 1.05  # 🔥 Safe cosine distance cutoff

# =====================================================
# LOAD EMBEDDING MODEL (ONCE)
# =====================================================

model = SentenceTransformer("all-MiniLM-L6-v2")

# =====================================================
# LOAD OR CREATE FAISS INDEX
# =====================================================

if os.path.exists(FAISS_INDEX_PATH):
    index = faiss.read_index(FAISS_INDEX_PATH)

    # Safety dimension check
    if index.d != dimension:
        raise ValueError(
            f"FAISS dimension mismatch. "
            f"Index: {index.d}, Expected: {dimension}"
        )
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

    # 🔥 Normalize embeddings (important for cosine-style behavior)
    query_vector = model.encode(
        [question],
        normalize_embeddings=True
    )

    query_vector = np.array(query_vector).astype("float32")

    # Search more than needed (for filtering)
    distances, ids = index.search(query_vector, top_k * 3)

    # 🔥 DEBUG: Print raw FAISS output
    print("Distances:", distances)
    print("Indices:", ids)

    chunk_texts = []

    for dist, chunk_id in zip(distances[0], ids[0]):

        if chunk_id == -1:
            continue

        # 🔥 Apply similarity threshold
        if dist > SIMILARITY_THRESHOLD:
            continue

        chunk = db.query(DocumentChunk).filter(
            DocumentChunk.id == int(chunk_id)
        ).first()

        if chunk:
            chunk_texts.append(chunk.chunk_text)

        if len(chunk_texts) >= top_k:
            break

    # 🔥 DEBUG: Print returned valid IDs (non -1)
    print("Returned IDs:", [int(i) for i in ids[0] if i != -1])

    return chunk_texts