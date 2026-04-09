"""
cache.py — Multi-layer caching for CollegeAI
  Layer 1: Response cache  — caches full chat answers (question → answer+sources)
  Layer 2: Embedding cache — caches query embeddings
  Layer 3: BM25 token cache — caches tokenized corpus
"""
import re
import time
import hashlib
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional, Any

from app.logger import logger

# ─── Config ──────────────────────────────────────────────────────────────────
RESPONSE_CACHE_TTL  = int(__import__("os").getenv("RESPONSE_CACHE_TTL",  1800))  # 30 min
EMBEDDING_CACHE_TTL = int(__import__("os").getenv("EMBEDDING_CACHE_TTL", 3600))  # 1 hr
RESPONSE_CACHE_MAX  = int(__import__("os").getenv("RESPONSE_CACHE_MAX",  1000))
EMBEDDING_CACHE_MAX = int(__import__("os").getenv("EMBEDDING_CACHE_MAX", 500))


# ─── Thread-safe LRU cache ───────────────────────────────────────────────────

class TTLCache:
    """
    Thread-safe LRU cache with per-entry TTL.
    OrderedDict keeps insertion order; LRU eviction on overflow.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600, name: str = "cache"):
        self._store:   OrderedDict = OrderedDict()
        self._lock:    threading.RLock = threading.RLock()
        self.max_size  = max_size
        self.ttl       = ttl_seconds
        self.name      = name
        self.hits      = 0
        self.misses    = 0

    def _is_expired(self, entry: dict) -> bool:
        return datetime.utcnow() > entry["expires"]

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._store:
                self.misses += 1
                return None
            entry = self._store[key]
            if self._is_expired(entry):
                del self._store[key]
                self.misses += 1
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            self.hits += 1
            return entry["value"]

    def set(self, key: str, value: Any):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = {
                "value":   value,
                "expires": datetime.utcnow() + timedelta(seconds=self.ttl),
            }
            # LRU eviction
            while len(self._store) > self.max_size:
                evicted_key, _ = self._store.popitem(last=False)
                logger.debug(f"[{self.name}] LRU evict: {evicted_key[:40]}")

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()
            self.hits   = 0
            self.misses = 0

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "name":      self.name,
                "size":      len(self._store),
                "max_size":  self.max_size,
                "ttl":       self.ttl,
                "hits":      self.hits,
                "misses":    self.misses,
                "hit_rate":  round(self.hits / total, 3) if total else 0.0,
            }

    def evict_expired(self):
        """Purge all expired entries. Call periodically from scheduler."""
        now = datetime.utcnow()
        with self._lock:
            expired = [k for k, v in self._store.items() if now > v["expires"]]
            for k in expired:
                del self._store[k]
        if expired:
            logger.info(f"[{self.name}] Evicted {len(expired)} expired entries")


# ─── Singleton caches ─────────────────────────────────────────────────────────

response_cache  = TTLCache(max_size=RESPONSE_CACHE_MAX,  ttl_seconds=RESPONSE_CACHE_TTL,  name="response")
embedding_cache = TTLCache(max_size=EMBEDDING_CACHE_MAX, ttl_seconds=EMBEDDING_CACHE_TTL, name="embedding")


# ─── Response cache helpers ───────────────────────────────────────────────────

def _response_key(question: str) -> str:
    """Normalise question to improve cache hit rate."""
    normalised = re.sub(r"\s+", " ", question.strip().lower())
    normalised = re.sub(r"[?!.,;]+$", "", normalised)
    return hashlib.md5(normalised.encode()).hexdigest()


def get_cached_response(question: str) -> Optional[dict]:
    key    = _response_key(question)
    cached = response_cache.get(key)
    if cached:
        logger.debug(f"[ResponseCache] HIT: {question[:50]}")
    return cached


def set_cached_response(question: str, response: dict):
    """
    Cache a response. Do NOT cache PDF-only answers (they should always be live).
    Do NOT cache error/no-info responses.
    """
    answer = response.get("answer", "")
    if not answer or "No relevant information" in answer:
        return
    no_info_markers = [
        "i don't have that information yet",
        "please contact the college office",
        "couldn't find that student's result",
        "couldn't find syllabus subject names",
    ]
    if any(marker in answer.lower() for marker in no_info_markers):
        return
    # Do not cache transient upstream AI failures/rate-limit fallbacks.
    transient_errors = [
        "AI service is temporarily busy",
        "AI service error",
        "Please try again in a moment",
    ]
    if any(msg.lower() in answer.lower() for msg in transient_errors):
        return
    if response.get("pdfs"):  # PDF listings may change; skip cache
        return

    key = _response_key(question)
    response_cache.set(key, response)
    logger.debug(f"[ResponseCache] SET: {question[:50]}")


def invalidate_response_cache():
    """Call after new documents are uploaded/scraped."""
    response_cache.clear()
    logger.info("[ResponseCache] Cleared after document update")


# ─── Embedding cache helpers ──────────────────────────────────────────────────

def get_cached_embedding(text: str):
    key = hashlib.md5(text.encode()).hexdigest()
    return embedding_cache.get(key)


def set_cached_embedding(text: str, embedding):
    key = hashlib.md5(text.encode()).hexdigest()
    embedding_cache.set(key, embedding)


# ─── Stats endpoint ───────────────────────────────────────────────────────────

def get_cache_stats() -> dict:
    return {
        "response_cache":  response_cache.stats(),
        "embedding_cache": embedding_cache.stats(),
    }


def evict_all_expired():
    response_cache.evict_expired()
    embedding_cache.evict_expired()
