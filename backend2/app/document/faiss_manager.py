import os
import numpy as np
import faiss
from app.logger import logger

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "data/faiss_index.bin")
EMBEDDING_DIM    = 384   # all-MiniLM-L6-v2 output dimension

_index = None


def get_index() -> faiss.IndexIDMap:
    global _index
    if _index is not None:
        return _index

    if os.path.exists(FAISS_INDEX_PATH):
        try:
            _index = faiss.read_index(FAISS_INDEX_PATH)
            logger.info(f"FAISS index loaded from {FAISS_INDEX_PATH} "
                        f"| vectors={_index.ntotal}")
            return _index
        except Exception as e:
            logger.warning(f"Failed to load FAISS index: {e}. Creating fresh.")

    base   = faiss.IndexFlatIP(EMBEDDING_DIM)
    _index = faiss.IndexIDMap(base)
    logger.info("Created new FAISS IndexIDMap (Inner Product / cosine)")
    return _index


def save_index(index=None):
    global _index
    target = index or _index
    if target is None:
        return
    os.makedirs(os.path.dirname(FAISS_INDEX_PATH) or ".", exist_ok=True)
    faiss.write_index(target, FAISS_INDEX_PATH)
    _index = target
    logger.debug(f"FAISS index saved | vectors={target.ntotal}")


def reset_index():
    global _index
    base   = faiss.IndexFlatIP(EMBEDDING_DIM)
    _index = faiss.IndexIDMap(base)
    save_index()
    logger.info("FAISS index reset")
