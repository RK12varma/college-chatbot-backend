import re
import time
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
    start_time = time.time()

    try:
        index = get_index()

        print("\n" + "=" * 70)
        print("🔎 SEARCH DEBUG START")
        print("Question:", question)
        print("Top K Requested:", top_k)

        # --------------------------------------------------
        # 1️⃣ Detect semester filter
        # --------------------------------------------------
        semester_filter = None
        sem_match = re.search(r"sem(?:ester)?\s*(\d+)", question, re.IGNORECASE)
        if sem_match:
            semester_filter = int(sem_match.group(1))
            print("🎓 Semester Filter Detected:", semester_filter)

        # --------------------------------------------------
        # 2️⃣ Detect subject filter
        # --------------------------------------------------
        subject_match = re.search(r"\b[A-Z]{2,6}\d{3,4}\b", question)
        subject_filter = subject_match.group(0) if subject_match else None

        if subject_filter:
            print("📘 Subject Code Filter Detected:", subject_filter)

        # --------------------------------------------------
        # 3️⃣ Build DB filter query
        # --------------------------------------------------
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
            print("✅ Filtered ID Count:", len(allowed_ids))
        else:
            allowed_ids = None
            print("🌍 No DB filtering applied (Global FAISS search)")

        # --------------------------------------------------
        # 4️⃣ Embed question
        # --------------------------------------------------
        question_embedding = model.encode(
            [question],
            normalize_embeddings=True
        ).astype("float32")

        # --------------------------------------------------
        # 5️⃣ FAISS Search
        # --------------------------------------------------
        search_k = top_k * 10  # search deeper
        distances, indices = index.search(question_embedding, search_k)

        print("\n📊 Raw FAISS Results")
        print("IDs:", indices[0])
        print("Distances:", distances[0])

        result_ids = []

        print("\n🔍 Filtering Logic:")

        for dist, idx in zip(distances[0], indices[0]):

            if idx == -1:
                continue

            # If DB filter exists, enforce it
            if allowed_ids is not None and idx not in allowed_ids:
                continue

            print(f"✅ Accepted ID {idx} (distance {dist:.4f})")
            result_ids.append(int(idx))

            if len(result_ids) >= top_k:
                break

        # --------------------------------------------------
        # 6️⃣ Fallback: If nothing matched DB filter
        # --------------------------------------------------
        if not result_ids:
            print("⚠ No matches after filtering — returning top_k raw FAISS")
            result_ids = [
                int(i) for i in indices[0][:top_k] if i != -1
            ]

        # --------------------------------------------------
        # 7️⃣ Print Final Results
        # --------------------------------------------------
        print("\n🏆 FINAL SELECTED IDS:", result_ids)

        for cid in result_ids:
            chunk = db.query(DocumentChunk).filter(
                DocumentChunk.id == cid
            ).first()

            if chunk:
                preview = chunk.chunk_text[:300].replace("\n", " ")
                print(f"\n🧾 Chunk ID {cid} Preview:")
                print(preview)
                print("-" * 60)

        total_time = time.time() - start_time
        print(f"\n⏱ Search Time: {total_time:.4f} seconds")
        print("🔎 SEARCH DEBUG END")
        print("=" * 70 + "\n")

        return result_ids

    except Exception as e:
        print("🚨 SEARCH ERROR:", str(e))
        return []

    finally:
        db.close()