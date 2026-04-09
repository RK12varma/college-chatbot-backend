import re
import time
import numpy as np
import faiss
from sqlalchemy.orm import Session

from app.document.faiss_manager import get_index
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.database import SessionLocal
from app.logger import logger

from app.document.processing import get_model
from app.document.faiss_manager import save_index


# ─── Query expansion map ──────────────────────────────────────────────────────
QUERY_EXPANSIONS = [
    (r"\bhod\b",                          "head of department faculty professor data science"),
    (r"\bhead of dep",                    "head of department faculty professor HOD"),
    (r"\bdepartment head\b",              "head of department faculty professor HOD"),
    (r"\bfaculty name\b",                 "faculty members professors data science department list"),
    (r"\bfaculty list\b",                 "faculty members professors data science department list"),
    (r"\bstaff\b",                        "faculty members professors staff department"),
    (r"\bprofessor\b",                    "faculty professor assistant associate department"),
    (r"\bstudent\b.{0,20}\bresult\b|\bresult\b.{0,20}\bstudent\b",
     "student result semester marks pass fail"),
    (r"\bfee\b",                          "fee structure tuition amount semester"),
    (r"\bnotice\b",                       "notice circular announcement exam schedule"),
    (r"\btimetable\b",                    "timetable schedule exam time"),
    (r"\bsyllabus\b",                     "syllabus curriculum course subjects units"),
    (r"\bplacement\b",                    "placement recruit campus drive package company"),
    (r"\badmission\b",                    "admission eligibility apply cutoff merit"),
]


def _expand_query(question: str) -> str:
    expanded = question.strip()
    for pattern, extra in QUERY_EXPANSIONS:
        if re.search(pattern, expanded, re.IGNORECASE):
            expanded = expanded + " " + extra
            break

    name_match = re.search(
        r"\b([a-z]{3,})\s+([a-z]{3,})\s+(?:result|marks|semester|sgpi)\b",
        expanded, re.IGNORECASE
    )
    if name_match:
        first, last = name_match.group(1).upper(), name_match.group(2).upper()
        expanded = expanded + f" {last} {first} {first} {last}"

    return expanded


def search_similar_chunks_with_scores(question: str, top_k: int = 20) -> list[dict]:
    """
    Returns list of {"id": int, "score": float} sorted by score desc.
    Used by hybrid_search for RRF fusion.
    """
    db: Session = SessionLocal()
    start = time.time()

    try:
        index = get_index()
        if index is None or index.ntotal == 0:
            logger.warning("FAISS index is empty")
            return []

        expanded_question = _expand_query(question)
        if expanded_question != question:
            logger.info(f"Query expanded: '{question[:40]}' -> '{expanded_question[:60]}'")

        # Embedding — check cache first
        try:
            from app.chat.cache import get_cached_embedding, set_cached_embedding
            q_vec = get_cached_embedding(expanded_question)
            if q_vec is None:
                model = get_model()
                q_vec = model.encode(
                    [expanded_question], normalize_embeddings=True
                ).astype("float32")
                set_cached_embedding(expanded_question, q_vec)
        except ImportError:
            model = get_model()
            q_vec = model.encode(
                [expanded_question], normalize_embeddings=True
            ).astype("float32")

        distances, indices = index.search(q_vec, top_k * 4)

        results = []
        seen    = set()
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx in seen:
                continue
            seen.add(int(idx))
            results.append({"id": int(idx), "score": float(dist)})
            if len(results) >= top_k:
                break

        # Guard against stale FAISS index where returned IDs do not exist in DB.
        # This can happen when an old non-IDMap index file is reused.
        candidate_ids = [r["id"] for r in results]
        if candidate_ids:
            existing_ids = {
                row[0]
                for row in db.query(DocumentChunk.id)
                .filter(DocumentChunk.id.in_(candidate_ids))
                .all()
            }
            missing_ratio = 1.0 - (len(existing_ids) / len(candidate_ids))
            if missing_ratio > 0.5:
                logger.warning(
                    "FAISS ID mismatch detected (missing_ratio=%.2f). Rebuilding index from DB.",
                    missing_ratio,
                )
                _rebuild_faiss_from_db(db)
                index = get_index()
                distances, indices = index.search(q_vec, top_k * 4)
                results = []
                seen = set()
                for dist, idx in zip(distances[0], indices[0]):
                    if idx == -1 or idx in seen:
                        continue
                    seen.add(int(idx))
                    results.append({"id": int(idx), "score": float(dist)})
                    if len(results) >= top_k:
                        break

        elapsed = round((time.time() - start) * 1000, 1)
        logger.info(
            f"FAISS search | q='{question[:40]}' | "
            f"results={len(results)} | {elapsed}ms"
        )
        return results

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return []
    finally:
        db.close()


def search_similar_chunks(question: str, top_k: int = 8) -> list[int]:
    """Legacy API — returns only IDs."""
    results = search_similar_chunks_with_scores(question, top_k=top_k)
    return [r["id"] for r in results]


def _rebuild_faiss_from_db(db: Session) -> None:
    """Rebuild FAISS index using current DB chunk IDs."""
    rows = db.query(DocumentChunk.id, DocumentChunk.chunk_text).all()
    if not rows:
        logger.warning("FAISS rebuild skipped: no chunks in DB")
        return

    ids = np.array([r[0] for r in rows], dtype=np.int64)
    texts = [r[1] or "" for r in rows]

    model = get_model()
    emb = model.encode(texts, normalize_embeddings=True).astype("float32")

    idx = faiss.IndexIDMap(faiss.IndexFlatIP(emb.shape[1]))
    idx.add_with_ids(emb, ids)
    save_index(idx)
    logger.info(f"FAISS index rebuilt from DB | vectors={idx.ntotal}")
