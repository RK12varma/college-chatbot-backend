"""
hybrid_search.py — Fixed BM25 Tokenization
"""
import re
import math
import time
import threading
import numpy as np
from collections import defaultdict
from typing import Optional, List, Tuple, Dict, Any

from app.logger import logger

# ─── Config ──────────────────────────────────────────────────────────────────
BM25_K1 = 1.5
BM25_B = 0.75
RRF_K = 60
TOP_K_BM25 = 20
TOP_K_FAISS = 20
TOP_K_FINAL = 10

# ─── BM25 Corpus Cache ────────────────────────────────────────────────────────
_bm25_lock = threading.Lock()
_bm25_corpus: Optional["BM25Index"] = None
_bm25_built_at: float = 0.0
_BM25_TTL = 300


def _tokenize(text: str) -> list[str]:
    """
    FIXED: Proper tokenization that extracts meaningful words from chunks.
    """
    if not text:
        return []
    
    tokens = []
    text_lower = text.lower()
    
    # 1. Extract student names (preserve as tokens)
    name_match = re.search(r'student name:\s*([^|\n]+)', text_lower, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).strip()
        # Add individual name parts
        for part in name.split():
            if len(part) >= 2:
                tokens.append(part)
    
    # 2. Extract name search field (contains all name variations)
    search_match = re.search(r'name search:\s*([^\n]+)', text_lower, re.IGNORECASE)
    if search_match:
        search_text = search_match.group(1).strip()
        # Split by | and extract words
        for variant in search_text.split('|'):
            for word in variant.strip().split():
                if len(word) >= 2 and word not in tokens:
                    tokens.append(word)
    
    # 3. Extract seat number
    seat_match = re.search(r'seat no:\s*(\w+)', text_lower, re.IGNORECASE)
    if seat_match:
        seat = seat_match.group(1).strip()
        if seat:
            tokens.append(seat)
    
    # 4. Extract semester
    sem_match = re.search(r'semester:\s*([^\n]+)', text_lower, re.IGNORECASE)
    if sem_match:
        sem = sem_match.group(1).strip()
        if sem:
            tokens.append(sem)
    
    # 5. Extract result
    result_match = re.search(r'result:\s*([^\n]+)', text_lower, re.IGNORECASE)
    if result_match:
        result = result_match.group(1).strip()
        if result:
            tokens.append(result)
    
    # 6. Extract all other words from the text
    # Remove the special fields we already processed
    cleaned_text = re.sub(r'student seat no:.*?\n', '', text_lower, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'student name:.*?\n', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'name search:.*?\n', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'semester:.*?\n', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'sgpi:.*?\n', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'total marks:.*?\n', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'overall result:.*?\n', '', cleaned_text, flags=re.IGNORECASE)
    
    # Tokenize remaining text
    words = re.findall(r'\b[a-z]{2,}\b', cleaned_text)
    
    # Filter stopwords (expanded)
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'in', 'of', 'to', 'for', 'is', 'are',
        'was', 'were', 'it', 'this', 'that', 'with', 'on', 'at', 'by', 'from',
        'be', 'as', 'have', 'has', 'not', 'no', 'do', 'did', 'can', 'will',
        'would', 'should', 'could', 'may', 'what', 'who', 'where', 'when',
        'how', 'which', 'show', 'get', 'give', 'tell', 'me', 'my', 'our',
        'their', 'your', 'his', 'her', 'its', 'we', 'us', 'them', 'she', 'he'
    }
    
    for w in words:
        if w not in stopwords and w not in tokens:
            tokens.append(w)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tokens = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)
    
    logger.debug(f"[BM25] Tokenized: {len(unique_tokens)} tokens from '{text[:100]}...'")
    return unique_tokens


class BM25Index:
    """In-memory BM25 index over DocumentChunk texts"""
    
    def __init__(self, chunk_ids: list[int], corpus: list[str]):
        self.chunk_ids = chunk_ids
        self.N = len(corpus)
        self.avgdl = 0.0
        self.df: dict = defaultdict(int)
        self.tf: list = []
        self.corpus = corpus

        if self.N == 0:
            return

        total_len = 0
        tokenized = []
        
        logger.info(f"[BM25] Building index with {self.N} documents...")
        
        for i, doc in enumerate(corpus):
            tokens = _tokenize(doc)
            tokenized.append(tokens)
            total_len += len(tokens)
            for term in set(tokens):
                self.df[term] += 1
        
        self.avgdl = total_len / self.N
        
        for tokens in tokenized:
            freq: dict = defaultdict(int)
            for t in tokens:
                freq[t] += 1
            self.tf.append(dict(freq))
        
        logger.info(f"[BM25] Index built: {self.N} docs, vocab={len(self.df)}, avgdl={self.avgdl:.1f}")
        if self.df:
            # Show top 10 terms for debugging
            top_terms = sorted(self.df.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info(f"[BM25] Top terms: {', '.join([f'{t}({c})' for t, c in top_terms])}")
    
    def score(self, query: str, top_k: int = TOP_K_BM25) -> list[tuple[int, float]]:
        """Return [(chunk_id, bm25_score)] sorted descending."""
        if self.N == 0:
            return []
        
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        
        scores = np.zeros(self.N, dtype=np.float32)
        for term in query_tokens:
            if term not in self.df:
                continue
            idf = math.log((self.N - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1)
            for i, tf_dict in enumerate(self.tf):
                f = tf_dict.get(term, 0)
                if f == 0:
                    continue
                dl = sum(tf_dict.values())
                num = f * (BM25_K1 + 1)
                den = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / self.avgdl)
                scores[i] += idf * (num / den)
        
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_indices if scores[i] > 0]
    
    def get_chunk_text(self, chunk_id: int) -> str:
        """Get original chunk text by ID"""
        try:
            idx = self.chunk_ids.index(chunk_id)
            return self.corpus[idx]
        except ValueError:
            return ""


def _build_bm25_from_db() -> BM25Index:
    """Build BM25 index from database"""
    from app.database import SessionLocal
    from app.models.chunk import DocumentChunk
    
    db = SessionLocal()
    try:
        rows = db.query(DocumentChunk.id, DocumentChunk.chunk_text).all()
        logger.info(f"[BM25] Loading {len(rows)} chunks from database")
        
        chunk_ids = [r.id for r in rows]
        corpus = [r.chunk_text or "" for r in rows]
        
        # Log sample for debugging
        if corpus:
            logger.info(f"[BM25] Sample chunk: {corpus[0][:200]}...")
        
        return BM25Index(chunk_ids, corpus)
    except Exception as e:
        logger.error(f"[BM25] Failed to build index: {e}")
        return BM25Index([], [])
    finally:
        db.close()


def get_bm25_index(force_rebuild: bool = False) -> BM25Index:
    """Get cached BM25 index, rebuild if stale"""
    global _bm25_corpus, _bm25_built_at
    now = time.time()
    with _bm25_lock:
        if (
            _bm25_corpus is None
            or force_rebuild
            or (now - _bm25_built_at) > _BM25_TTL
        ):
            logger.info("[BM25] Building corpus index...")
            _bm25_corpus = _build_bm25_from_db()
            _bm25_built_at = now
    return _bm25_corpus


def invalidate_bm25():
    """Call after new documents are uploaded/scraped"""
    global _bm25_corpus
    with _bm25_lock:
        _bm25_corpus = None
    logger.info("[BM25] Index invalidated")


def hybrid_search(
    question: str,
    top_k: int = TOP_K_FINAL,
    use_bm25: bool = True,
    boost_results: bool = True,
) -> dict:
    """Run hybrid BM25 + FAISS search"""
    from app.document.search import search_similar_chunks_with_scores
    
    start = time.time()
    
    # ── FAISS semantic search ─────────────────────────────────────────────
    faiss_result = search_similar_chunks_with_scores(question, top_k=TOP_K_FAISS)
    faiss_ids = [r["id"] for r in faiss_result]
    faiss_scores = [r["score"] for r in faiss_result]
    
    logger.info(f"[HybridSearch] FAISS found {len(faiss_ids)} results")
    
    if not use_bm25:
        return {
            "chunk_ids": faiss_ids[:top_k],
            "faiss_ids": faiss_ids,
            "bm25_ids": [],
            "faiss_scores": faiss_scores,
            "bm25_scores": [],
        }
    
    # ── BM25 keyword search ───────────────────────────────────────────────
    bm25_idx = get_bm25_index()
    bm25_pairs = bm25_idx.score(question, top_k=TOP_K_BM25)
    bm25_ids = [cid for cid, _ in bm25_pairs]
    bm25_scores = [score for _, score in bm25_pairs]
    
    logger.info(f"[HybridSearch] BM25 found {len(bm25_ids)} results")
    
    # If BM25 found nothing, fall back to FAISS only
    if not bm25_pairs:
        logger.warning("[HybridSearch] BM25 returned no results, using FAISS only")
        return {
            "chunk_ids": faiss_ids[:top_k],
            "faiss_ids": faiss_ids,
            "bm25_ids": [],
            "faiss_scores": faiss_scores,
            "bm25_scores": [],
        }
    
    # ── RRF fusion ────────────────────────────────────────────────────────
    scores: dict[int, float] = defaultdict(float)
    
    # FAISS: rank 1 = best
    for rank, cid in enumerate(faiss_ids, start=1):
        scores[cid] += 1.0 / (RRF_K + rank)
    
    # BM25: rank by position
    for rank, (cid, _) in enumerate(bm25_pairs, start=1):
        scores[cid] += 1.0 / (RRF_K + rank)
    
    # Boost result documents for student queries
    if boost_results:
        q_lower = question.lower()
        is_student_query = any(w in q_lower for w in ["result", "marks", "sgpi"]) or len(q_lower.split()) >= 2
        
        if is_student_query:
            for cid in list(scores.keys()):
                chunk_text = bm25_idx.get_chunk_text(cid)
                if "Student Seat No:" in chunk_text or "Student Name:" in chunk_text:
                    scores[cid] *= 1.5
    
    merged_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)[:top_k]
    
    elapsed = round((time.time() - start) * 1000, 1)
    logger.info(
        f"[HybridSearch] q='{question[:40]}' | faiss={len(faiss_ids)} "
        f"bm25={len(bm25_ids)} merged={len(merged_ids)} | {elapsed}ms"
    )
    
    return {
        "chunk_ids": merged_ids,
        "faiss_ids": faiss_ids,
        "bm25_ids": bm25_ids,
        "faiss_scores": faiss_scores,
        "bm25_scores": bm25_scores,
    }