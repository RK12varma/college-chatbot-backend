import numpy as np
from sentence_transformers import SentenceTransformer
from app.document.faiss_manager import get_index


# =====================================================
# LOAD EMBEDDING MODEL
# =====================================================

model = SentenceTransformer("all-MiniLM-L6-v2")


# =====================================================
# SEARCH SIMILAR CHUNKS (RETURNS IDS)
# =====================================================

def search_similar_chunks(question: str, top_k: int = 5):

    index = get_index()

    # If index is empty
    if index.ntotal == 0:
        print("FAISS index is empty.")
        return []

    # Encode + normalize (must match indexing)
    question_vector = model.encode(
        [question],
        normalize_embeddings=True
    )

    question_vector = np.array(question_vector).astype("float32")

    # Search
    distances, indices = index.search(question_vector, top_k)

    print("Distances:", distances)
    print("Indices:", indices)

    # Extract valid IDs
    valid_ids = [
        int(chunk_id)
        for chunk_id in indices[0]
        if chunk_id != -1
    ]

    print("Returned IDs:", valid_ids)

    return valid_ids