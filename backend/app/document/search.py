import re
import numpy as np
from sqlalchemy.orm import Session

from app.document.faiss_manager import get_index
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.database import SessionLocal
from sentence_transformers import SentenceTransformer


model = SentenceTransformer("all-MiniLM-L6-v2")


def search_similar_chunks(question: str, top_k: int = 8):

    db: Session = SessionLocal()

    try:
        index = get_index()

        # -----------------------------
        # 1️⃣ Detect semester filter
        # -----------------------------
        semester_filter = None
        sem_match = re.search(r"sem(?:ester)?\s*(\d+)", question, re.IGNORECASE)
        if sem_match:
            semester_filter = int(sem_match.group(1))

        # -----------------------------
        # 2️⃣ Detect subject code filter
        # Example: DS5001, CS401 etc.
        # -----------------------------
        subject_match = re.search(r"\b[A-Z]{2,6}\d{3,4}\b", question)
        subject_filter = subject_match.group(0) if subject_match else None

        # -----------------------------
        # 3️⃣ Build base query
        # -----------------------------
        query = db.query(DocumentChunk)

        if semester_filter:
            query = query.join(Document).filter(
                Document.semester == semester_filter
            )

        if subject_filter:
            query = query.filter(
                DocumentChunk.chunk_text.contains(subject_filter)
            )

        filtered_chunks = query.all()

        if filtered_chunks:
            allowed_ids = {chunk.id for chunk in filtered_chunks}
        else:
            allowed_ids = None  # fallback to global search

        # -----------------------------
        # 4️⃣ Embed question
        # -----------------------------
        question_embedding = model.encode(
            [question],
            normalize_embeddings=True
        ).astype("float32")

        # -----------------------------
        # 5️⃣ FAISS Search + Distance Filtering (CRITICAL UPGRADE)
        # -----------------------------
        SIMILARITY_THRESHOLD = 1.05

        distances, indices = index.search(question_embedding, top_k * 5)

        result_ids = []

        for dist, idx in zip(distances[0], indices[0]):

            if idx == -1:
                continue

            # 🔥 FILTER BY DISTANCE
            if dist > SIMILARITY_THRESHOLD:
                continue

            if allowed_ids:
                if idx in allowed_ids:
                    result_ids.append(int(idx))
            else:
                result_ids.append(int(idx))

            if len(result_ids) >= top_k:
                break

        return result_ids

    finally:
        db.close()