"""
chat/routes.py â€” CollegeAI Chat API (Enhanced)
Features:
  1. Web Search Augmentation (SerpAPI + DuckDuckGo fallback)
  2. Confidence-threshold routing
  3. Strict Source Attribution
  4. Response + Embedding Cache
  5. Parallel Processing (FAISS + BM25 + web search run concurrently)
  6. PDF Download Integration
  7. Advanced Student Name Matching
"""
import re
import json
import time
import os
import concurrent.futures
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.chat_history import ChatSession, ChatTurn
from app.llm.gemini_service import generate_answer
from app.logger import logger

# â”€â”€ Feature modules â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from app.chat.cache import (
    get_cached_response, set_cached_response,
    get_cache_stats,
)
from app.chat.hybrid_search import hybrid_search
from app.chat.web_search import web_search, should_search

router = APIRouter()


# â”€â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

PDF_URL_RE = re.compile(r"https?://\S+?\.pdf", re.IGNORECASE)

PDF_KEYWORDS = [
    "question paper","question papers","qp","previous paper","previous papers",
    "past paper","past papers","model paper","exam paper",
    "download","pdf link","get pdf","share pdf",
    "newsletter",
]

SEM_MAP = {
    "3":"SEM-III","iii":"SEM-III",
    "4":"SEM-IV", "iv": "SEM-IV",
    "5":"SEM-V",  "v":  "SEM-V",
    "6":"SEM-VI", "vi": "SEM-VI",
    "7":"SEM-VII","vii":"SEM-VII",
    "8":"SEM-VIII","viii":"SEM-VIII",
}

# Confidence threshold: below this score â†’ trigger web search augmentation
FAISS_CONFIDENCE_THRESHOLD = 0.35
# For broad/exploratory queries (career/resources/opportunities), require stronger local confidence
# before skipping web augmentation.
WEB_AUGMENT_CONFIDENCE_THRESHOLD = 0.55
EXPLORATORY_QUERY_KEYWORDS = {
    "career", "opportunities", "resource", "resources", "roadmap",
    "salary", "job", "internship", "future scope", "certification",
    "learn", "learning", "skills",
}


# â”€â”€â”€ Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class QuestionRequest(BaseModel):
    question:   str
    session_id: Optional[int] = None
    use_web:    bool = True


class ChatResponse(BaseModel):
    answer: str
    session_id: int
    sources: List[str]
    sources_detail: List[Dict[str, Any]]
    pdfs: List[Dict[str, Any]]
    web: Dict[str, Any]
    from_cache: bool
    latency_ms: float
    confidence: float


# â”€â”€â”€ PDF Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _is_pdf_request(question: str) -> bool:
    q = question.lower()
    if any(kw in q for kw in PDF_KEYWORDS):
        return True
    # Treat direct filename queries like "SCOE-Examination-Policies_R.pdf" as PDF requests.
    if ".pdf" in q or PDF_URL_RE.search(question):
        return True
    return False


def _score_pdf_relevance(query: str, text: str, filename: str) -> int:
    """Score PDF relevance based on query terms in filename and text"""
    q_lower = query.lower()
    q_words = [w for w in q_lower.split() if len(w) >= 3]
    score = 0
    
    # Check filename
    f_lower = filename.lower()
    for w in q_words:
        if w in f_lower:
            score += 3
        if w in text[:500].lower():
            score += 1
    
    # Check semester match
    sem_match = re.search(r"SEM[-\s]*([VIX]+|\d+)", query, re.IGNORECASE)
    if sem_match:
        sem = sem_match.group(0).upper()
        if sem in filename.upper():
            score += 5
    
    return score


def _lookup_saved_pdfs(question: str, db: Session) -> List[Dict[str, Any]]:
    """Search locally saved PDFs that match the query"""
    q_lower = question.lower()
    pdfs = []
    
    # Extract semester if present
    sem_match = re.search(r"SEM[-\s]*(V{1,3}I{0,3}|I{1,4}V?|\d+)", question, re.IGNORECASE)
    semester = sem_match.group(1).upper() if sem_match else None
    if semester and not semester.startswith("SEM"):
        semester = f"SEM-{semester}"
    
    # Query documents
    docs = db.query(Document).filter(
        Document.is_active == True,
        Document.file_type == "pdf"
    ).all()
    
    for doc in docs:
        filename = doc.filename or ""
        label = doc.source_label or filename
        score = _score_pdf_relevance(question, label, filename)
        
        if score > 0:
            # Check if file exists
            file_path = doc.file_path or ""
            if not os.path.exists(file_path):
                continue
                
            pdfs.append({
                "url": f"/document/download/{doc.id}",
                "label": label,
                "filename": filename,
                "score": score,
                "size_kb": round(os.path.getsize(file_path) / 1024, 1),
                "semester": doc.semester,
                "department": doc.department
            })
    
    pdfs.sort(key=lambda x: x["score"], reverse=True)
    return pdfs[:5]


def _lookup_question_papers(question: str, db) -> list[dict]:
    """Search question papers from database"""
    try:
        from app.models.question_paper import QuestionPaper
    except ImportError:
        return []

    q = question.lower()
    qp_triggers = [
        "question paper","question papers","previous paper","previous papers",
        "past paper","past papers","qp","model paper","exam paper",
    ]
    if not any(t in q for t in qp_triggers):
        return []

    sem_match = re.search(
        r"sem(?:ester)?[\s\-]*(viii|vii|vi(?!i)|v(?!i)|iv|iii|ii(?!i)|i(?!i|v)|[1-8])",
        q, re.IGNORECASE
    )
    detected_sem = SEM_MAP.get(sem_match.group(1).lower()) if sem_match else None
    year_match = re.search(r"\b(20\d{2})\b", q)
    detected_year = int(year_match.group(1)) if year_match else None
    detected_month = None
    month_patterns = {
        "jan":"January","feb":"February","mar":"March","apr":"April",
        "may":"May","jun":"June","jul":"July","aug":"August",
        "sep":"September","oct":"October","nov":"November","dec":"December",
    }
    for abbr, full in month_patterns.items():
        if abbr in q or full.lower() in q:
            detected_month = full
            break

    try:
        dbq = db.query(QuestionPaper)
        if detected_sem:   dbq = dbq.filter(QuestionPaper.semester == detected_sem)
        if detected_year:  dbq = dbq.filter(QuestionPaper.exam_year == detected_year)
        if detected_month: dbq = dbq.filter(QuestionPaper.exam_month == detected_month)

        papers = dbq.order_by(
            QuestionPaper.exam_year.desc(), QuestionPaper.semester
        ).limit(10).all()

        logger.info(f"QP DB lookup: sem={detected_sem} year={detected_year} â†’ {len(papers)} papers")
        return [
            {
                "url":      p.url,
                "label":    f"{p.semester} â€” {p.exam_label}",
                "filename": p.filename or p.url.split("/")[-1],
                "score":    10,
            }
            for p in papers
        ]
    except Exception as e:
        logger.warning(f"QP DB lookup error: {e}")
        return []


def _build_pdf_answer(pdfs: list[dict]) -> str:
    """Build answer text with PDF links"""
    if not pdfs:
        return "No documents found matching your request."
    if len(pdfs) == 1:
        return f"Here is the document you requested: **{pdfs[0]['label']}**. Click the download button below."
    names = ", ".join(f"**{p['label']}**" for p in pdfs[:3])
    extra = f" and {len(pdfs)-3} more" if len(pdfs) > 3 else ""
    return f"I found {len(pdfs)} relevant document(s): {names}{extra}. Use the download buttons below."


def _build_pdf_sources(pdfs: list[dict]) -> list[dict]:
    """Use matched PDF results directly for source attribution."""
    sources = []
    seen = set()
    for p in pdfs[:4]:
        label = (p.get("label") or p.get("filename") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        url = p.get("url")
        src_type = "document" if (url and "/document/download/" in str(url)) else "college_website"
        sources.append({"label": label, "type": src_type, "url": url})
    return sources




# â”€â”€â”€ Source Attribution (STRICT) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_source_label(doc) -> str:
    """Strict source label resolution"""
    if doc is None:
        return ""

    label = getattr(doc, "source_label", None)
    if label and label.strip():
        return label.strip()

    raw = getattr(doc, "filename", "") or ""
    if not raw:
        url = getattr(doc, "source_url", "") or ""
        if url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc or "College Website"
        return "College Website"

    raw = re.sub(r"\.pdf$", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"\s*-\s*", " â€” ", raw)
    return raw[:80].strip() if raw else "College Document"


def _build_strict_sources(
    ordered_chunks: list,
    answer:         str,
    question:       str,
    web_results:    list = None,
    web_used:       bool = False,
) -> list[dict]:
    """Build strict, deduplicated source list with type tagging"""
    q_lower = question.lower()
    sources = []
    seen = set()

    def _add(label: str, src_type: str, url: str = None):
        if not label or label in seen:
            return
        seen.add(label)
        sources.append({"label": label, "type": src_type, "url": url})

    # Web search sources
    if web_used and web_results:
        for r in web_results[:2]:
            title = r.get("title", "")[:80]
            url = r.get("url", "")
            if title:
                _add(title, "web", url)

    # Document sources
    is_result = any(w in q_lower for w in ["result", "marks", "sgpi", "pass", "fail"])
    is_syllabus = any(w in q_lower for w in ["syllabus", "curriculum", "subject", "subjects", "module", "course"])
    is_info = any(w in q_lower for w in [
        "topper", "activity", "placement", "fee",
        "timetable", "schedule", "notice", "event", "project"
    ])

    if is_result:
        # Look for semester in answer
        sem_match = re.search(r"\bSEM[-\s]*(V{1,3}I{0,3}|I{1,4}V?|\d+)\b", answer, re.IGNORECASE)
        sem_label = sem_match.group(0).upper().replace("  ", " ") if sem_match else "RESULT"
        if sem_match:
            sem_raw = sem_match.group(0).upper().replace(" ", "").replace("-", "")
            for chunk in ordered_chunks[:5]:
                if not chunk.document:
                    continue
                fname = (chunk.document.filename or "").upper().replace("-", "").replace(" ", "")
                if sem_raw in fname:
                    lbl = _get_source_label(chunk.document)
                    if lbl.lower().strip() in {"college - information", "college information"}:
                        lbl = f"Data Science - Result {sem_label}"
                    _add(lbl, "document", None)
                    break
        if not sources:
            # Fallback for result responses when file naming does not carry semester token.
            for chunk in ordered_chunks[:10]:
                if not chunk.document:
                    continue
                ctype = (chunk.content_type or "").upper()
                if ctype != "RESULT":
                    continue
                lbl = _get_source_label(chunk.document)
                if lbl.lower().strip() in {"college - information", "college information"}:
                    sem_src = (chunk.semester or sem_label).upper()
                    lbl = f"Data Science - Result {sem_src}"
                _add(lbl, "document", getattr(chunk.document, "source_url", None))
                break

    if is_syllabus and not sources:
        for chunk in ordered_chunks[:10]:
            if not chunk.document:
                continue
            ctype = (chunk.content_type or "").upper()
            fname = (chunk.document.filename or "").lower()
            if ctype == "SYLLABUS" or "syllabus" in fname or "curriculum" in fname:
                lbl = _get_source_label(chunk.document)
                _add(lbl, "document", getattr(chunk.document, "source_url", None))
                break

    # Fallback: use top chunk
    if not sources and ordered_chunks:
        for chunk in ordered_chunks[:3]:
            if chunk.document:
                lbl = _get_source_label(chunk.document)
                ft = chunk.document.file_type or "web"
                stype = "document" if ft == "pdf" else "college_website"
                _add(lbl, stype, getattr(chunk.document, "source_url", None))
                break

    return sources[:4]


# â”€â”€â”€ Parallel Processing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _run_parallel(question: str, use_web: bool, top_faiss_score: float, db) -> dict:
    """
    Sequential pipeline: docs first, web only as fallback.
    Step 1 - Hybrid search (FAISS + BM25)
    Step 2 - Web search only if docs weak/missing
    """
    results = {}

    # Step 1: Hybrid search always runs first
    try:
        results["hybrid"] = hybrid_search(question, top_k=10)
    except Exception as e:
        logger.error(f"[Pipeline] Hybrid search failed: {e}")
        results["hybrid"] = {"chunk_ids": [], "faiss_ids": [], "bm25_ids": [], "faiss_scores": []}

    chunk_ids = results["hybrid"].get("chunk_ids", [])
    faiss_hit_count = len(chunk_ids)
    doc_is_weak = faiss_hit_count == 0 or top_faiss_score < FAISS_CONFIDENCE_THRESHOLD
    q_lower = question.lower()
    query_prefers_web = any(k in q_lower for k in EXPLORATORY_QUERY_KEYWORDS)
    query_is_pdf = _is_pdf_request(question)
    web_intent = should_search(question, faiss_hit_count=faiss_hit_count, top_score=top_faiss_score)
    should_run_web = (
        use_web
        and not query_is_pdf
        and (
            query_prefers_web
            or (
                web_intent
                and (doc_is_weak or top_faiss_score < WEB_AUGMENT_CONFIDENCE_THRESHOLD)
            )
        )
    )

    # Step 2: Web search only when docs are weak/missing
    if should_run_web:
        logger.info(
            f"[Pipeline] Web augment enabled (hits={faiss_hit_count}, "
            f"score={top_faiss_score:.3f}, exploratory={query_prefers_web})"
        )
        try:
            import asyncio, inspect
            result = web_search(question, college_context=True)
            results["web"] = asyncio.run(result) if inspect.isawaitable(result) else result
        except Exception as e:
            logger.warning(f"[Pipeline] Web search failed: {e}")
            results["web"] = {"results": [], "context": "", "from_cache": False, "provider": "none"}
    else:
        logger.info(f"[Pipeline] Docs sufficient (hits={faiss_hit_count}, score={top_faiss_score:.3f}) -> skipping web")
        results["web"] = {"results": [], "context": "", "from_cache": False, "provider": "none"}

    return results


# â”€â”€â”€ Ask Question (Enhanced) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/ask", response_model=ChatResponse)
def ask_question(
    data: QuestionRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = data.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    t_start = time.time()

    # â”€â”€ 1. Response cache check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    q_lower = question.lower()
    is_exploratory_query = any(k in q_lower for k in EXPLORATORY_QUERY_KEYWORDS)
    bypass_cache = bool(data.use_web and is_exploratory_query and not _is_pdf_request(question))
    cached = None if bypass_cache else get_cached_response(question)
    if cached:
        if data.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == data.session_id,
                ChatSession.user_id == user.id,
            ).first()
        else:
            session = ChatSession(user_id=user.id, title=question[:80])
            db.add(session)
            db.flush()
        
        db.add(ChatTurn(session_id=session.id, role="user", content=question))
        db.add(ChatTurn(
            session_id=session.id,
            role="assistant",
            content=cached["answer"],
            sources=json.dumps([s["label"] if isinstance(s, dict) else s for s in cached.get("sources", [])]),
        ))
        db.commit()
        logger.info(f"[Cache] HIT for: {question[:50]}")
        
        return ChatResponse(**cached)

    # â”€â”€ 2. Session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if data.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == data.session_id,
            ChatSession.user_id == user.id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session = ChatSession(user_id=user.id, title=question[:80])
        db.add(session)
        db.flush()

    db.add(ChatTurn(session_id=session.id, role="user", content=question))

    # â”€â”€ 3. Quick FAISS score for confidence threshold â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    from app.document.search import search_similar_chunks_with_scores
    quick_scores = search_similar_chunks_with_scores(question, top_k=3)
    top_score = quick_scores[0]["score"] if quick_scores else 0.0

    # â”€â”€ 4. Parallel: Hybrid search + Web search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    parallel = _run_parallel(question, data.use_web, top_score, db)
    hybrid = parallel["hybrid"]
    web_data = parallel["web"]

    chunk_ids = hybrid["chunk_ids"]
    faiss_scores = hybrid.get("faiss_scores", [])
    web_results = web_data.get("results", [])
    web_context = web_data.get("context", "")
    web_used = bool(web_results)

    answer = ""
    sources = []
    pdfs = []
    web_info = {}

    # â”€â”€ 5. Check if PDF request â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    is_pdf_req = _is_pdf_request(question)
    
    if not chunk_ids and not web_used:
        # No results anywhere â€” check QP table then saved PDFs
        pdfs = _lookup_question_papers(question, db)
        if not pdfs and is_pdf_req:
            pdfs = _lookup_saved_pdfs(question, db)
        if pdfs:
            answer = _build_pdf_answer(pdfs)
            sources = _build_pdf_sources(pdfs)
        else:
            answer = "I don't have that information yet. Please contact the college office or try rephrasing your question."
    else:
        # Load chunks from DB
        ordered_chunks = []
        if chunk_ids:
            results = (
                db.query(DocumentChunk)
                .options(joinedload(DocumentChunk.document))
                .filter(DocumentChunk.id.in_(chunk_ids))
                .all()
            )
            id_to_chunk = {c.id: c for c in results}
            ordered_chunks = [id_to_chunk[i] for i in chunk_ids if i in id_to_chunk]

        # For result queries: search all chunks for name match
        from app.llm.gemini_service import _is_result_query, _is_syllabus_query
        if _is_result_query(question):
            skip = {"result", "marks", "sgpi", "pass", "fail", "show", "get", "what",
                    "the", "his", "her", "their", "my", "give", "tell", "find", "exam"}
            q_words = [w for w in question.lower().split() if len(w) >= 3 and w not in skip]

            # Result-specific fallback:
            # If hybrid retrieval misses the student chunk, search DS result chunks directly.
            seat_match = re.search(r"\bDS\s*\d{4}\b", question.upper())
            seat_query = seat_match.group(0).replace(" ", "") if seat_match else None

            if seat_query or q_words:
                result_query = (
                    db.query(DocumentChunk)
                    .options(joinedload(DocumentChunk.document))
                    .filter(DocumentChunk.department == "DS")
                    .filter(
                        or_(
                            DocumentChunk.content_type == "RESULT",
                            DocumentChunk.chunk_text.ilike("%Student Seat No:%"),
                        )
                    )
                )

                if seat_query:
                    result_query = result_query.filter(DocumentChunk.chunk_text.ilike(f"%{seat_query}%"))
                    fallback_chunks = result_query.limit(20).all()
                else:
                    or_filters = [DocumentChunk.chunk_text.ilike(f"%{w}%") for w in q_words]
                    fallback_chunks = result_query.filter(or_(*or_filters)).limit(200).all()
                    # Keep only strong name matches after DB prefilter.
                    fallback_chunks = [
                        c for c in fallback_chunks
                        if all(w in c.chunk_text.lower() for w in q_words)
                    ]

                if fallback_chunks:
                    existing_ids = {c.id for c in ordered_chunks}
                    ordered_chunks = fallback_chunks + [c for c in ordered_chunks if c.id not in existing_ids]
                elif q_words:
                    matched_chunks = [c for c in ordered_chunks if all(w in c.chunk_text.lower() for w in q_words)]
                    ordered_chunks = matched_chunks if matched_chunks else ordered_chunks

            local_context = "\n\n".join(c.chunk_text for c in ordered_chunks[:20])
        elif _is_syllabus_query(question):
            # Syllabus-specific fallback to avoid unrelated result/faculty chunks.
            sem_m = re.search(r"\bsem(?:ester)?[\s\-]*(viii|vii|vi|v|iv|iii|ii|i|[1-8])\b", question, re.IGNORECASE)
            sem_map = {
                "1": "SEM-I", "i": "SEM-I",
                "2": "SEM-II", "ii": "SEM-II",
                "3": "SEM-III", "iii": "SEM-III",
                "4": "SEM-IV", "iv": "SEM-IV",
                "5": "SEM-V", "v": "SEM-V",
                "6": "SEM-VI", "vi": "SEM-VI",
                "7": "SEM-VII", "vii": "SEM-VII",
                "8": "SEM-VIII", "viii": "SEM-VIII",
            }
            sem_query = sem_map.get(sem_m.group(1).lower()) if sem_m else None

            syllabus_query = (
                db.query(DocumentChunk)
                .options(joinedload(DocumentChunk.document))
                .filter(DocumentChunk.department == "DS")
                .filter(
                    or_(
                        DocumentChunk.content_type == "SYLLABUS",
                        DocumentChunk.chunk_text.ilike("%syllabus%"),
                        DocumentChunk.chunk_text.ilike("%course outcomes%"),
                        DocumentChunk.chunk_text.ilike("%teaching scheme%"),
                    )
                )
            )
            if sem_query:
                syllabus_query = syllabus_query.filter(
                    or_(
                        DocumentChunk.semester.ilike(f"%{sem_query}%"),
                        DocumentChunk.chunk_text.ilike(f"%{sem_query}%"),
                    )
                )

            fallback_chunks = syllabus_query.limit(120).all()
            # If exact semester filter misses, fallback to generic syllabus chunks
            # so answer layer can report available semesters instead of hard fail.
            if sem_query and not fallback_chunks:
                fallback_chunks = (
                    db.query(DocumentChunk)
                    .options(joinedload(DocumentChunk.document))
                    .filter(DocumentChunk.department == "DS")
                    .filter(
                        or_(
                            DocumentChunk.content_type == "SYLLABUS",
                            DocumentChunk.chunk_text.ilike("%syllabus%"),
                            DocumentChunk.chunk_text.ilike("%course outcomes%"),
                            DocumentChunk.chunk_text.ilike("%teaching scheme%"),
                        )
                    )
                    .limit(120)
                    .all()
                )

            if sem_query and fallback_chunks:
                sem_token = sem_query.upper()
                sem_filtered = []
                for c in fallback_chunks:
                    c_sem = (c.semester or "").upper()
                    c_text = (c.chunk_text or "").upper()
                    doc_name = ""
                    if c.document:
                        doc_name = f"{c.document.filename or ''} {c.document.source_label or ''}".upper()
                    if sem_token in c_sem or sem_token in c_text or sem_token in doc_name:
                        sem_filtered.append(c)
                if sem_filtered:
                    fallback_chunks = sem_filtered

            if fallback_chunks:
                existing_ids = {c.id for c in ordered_chunks}
                ordered_chunks = fallback_chunks + [c for c in ordered_chunks if c.id not in existing_ids]

            local_context = "\n\n".join(c.chunk_text for c in ordered_chunks[:20])
        else:
            local_context = "\n\n".join(c.chunk_text for c in ordered_chunks[:5])

        # Check for PDFs
        if is_pdf_req:
            pdfs = _lookup_question_papers(question, db)
            if not pdfs:
                pdfs = _lookup_saved_pdfs(question, db)
            if pdfs:
                answer = _build_pdf_answer(pdfs)
                sources = _build_pdf_sources(pdfs)

        if not answer:
            # Build combined context
            combined_context = local_context.strip()

            # Inject web context if local context is weak
            if web_used and (not combined_context or top_score < FAISS_CONFIDENCE_THRESHOLD):
                web_section = f"\n\n[Web Search Results]\n{web_context}"
                combined_context = (combined_context + web_section).strip()
                logger.info(f"[WebAug] Injecting web context (top_score={top_score:.3f})")
            elif web_used and top_score >= FAISS_CONFIDENCE_THRESHOLD:
                # Append web as supplementary only
                web_section = f"\n\n[Supplementary Web Info]\n{web_context[:800]}"
                combined_context = (combined_context + web_section).strip()

            if combined_context:
                answer = generate_answer(question, combined_context)
            else:
                answer = "I don't have that information yet. Please contact the college office."

        # Late web fallback: if local answer is still "no info", force web once
        # when web search is enabled (independent of FAISS score).
        no_info_answer = (
            "i don't have that information yet" in answer.lower()
            or "please contact the college office" in answer.lower()
        )
        if data.use_web and not is_pdf_req and not web_used and no_info_answer:
            try:
                import asyncio, inspect
                late_web = web_search(question, college_context=True)
                late_web_data = asyncio.run(late_web) if inspect.isawaitable(late_web) else late_web
                late_web_results = late_web_data.get("results", [])
                late_web_context = late_web_data.get("context", "")
                if late_web_context:
                    web_results = late_web_results
                    web_context = late_web_context
                    web_data = late_web_data
                    web_used = bool(web_results)
                    merged_context = (local_context.strip() + f"\n\n[Web Search Results]\n{web_context}").strip()
                    answer = generate_answer(question, merged_context)
                    logger.info("[WebAug] Late web fallback triggered after no-info local answer")
                else:
                    logger.info("[WebAug] Late web fallback returned no web context")
            except Exception as e:
                logger.warning(f"[WebAug] Late web fallback failed: {e}")

        # If response is web-backed (non-PDF query), do not attach local downloadable files.
        if web_used and not is_pdf_req:
            pdfs = []
        elif is_exploratory_query and data.use_web and not is_pdf_req:
            # Keep exploratory web-intent answers clean even if local docs answered.
            pdfs = []

        # Build strict source attribution only if not already set from PDF matches.
        if not sources:
            sources = _build_strict_sources(
                ordered_chunks, answer, question,
                web_results=web_results, web_used=web_used,
            )

        web_info = {
            "used": web_used,
            "provider": web_data.get("provider", "none"),
            "from_cache": web_data.get("from_cache", False),
            "count": len(web_results),
        }

    # â”€â”€ 6. Save chat turn â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    db.add(ChatTurn(
        session_id=session.id,
        role="assistant",
        content=answer,
        sources=json.dumps([s["label"] for s in sources]),
    ))
    db.commit()

    # â”€â”€ 7. Prepare response â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    response = {
        "session_id": session.id,
        "answer": answer,
        "sources": [s["label"] for s in sources],
        "sources_detail": sources,
        "pdfs": pdfs,
        "web": web_info,
        "from_cache": False,
        "latency_ms": round((time.time() - t_start) * 1000, 1),
        "confidence": round(float(top_score), 3),
    }
    if not bypass_cache:
        set_cached_response(question, response)

    logger.info(
        f"Chat | user={user.id} | session={session.id} | "
        f"pdfs={len(pdfs)} | sources={[s['label'] for s in sources]} | "
        f"web={web_used} | {response['latency_ms']}ms"
    )

    return ChatResponse(**response)


# â”€â”€â”€ File Access API (User Side) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/files")
def list_user_files(
    department: Optional[str] = None,
    semester: Optional[str] = None,
    file_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User-accessible file listing with download URLs"""
    q = db.query(Document).filter(Document.is_active == True)

    if department:
        q = q.filter(Document.department == department.upper())
    if semester:
        sem_clean = semester.upper()
        if not sem_clean.startswith("SEM"):
            sem_clean = SEM_MAP.get(semester.lower(), semester.upper())
        q = q.filter(Document.semester.ilike(f"%{sem_clean}%"))
    if file_type:
        q = q.filter(Document.file_type == file_type.lower())

    total = q.count()
    docs = q.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    def _doc_entry(d: Document) -> dict:
        is_pdf = d.file_type == "pdf"
        fp = d.file_path or ""
        has_file = is_pdf and (os.path.exists(fp) or
                               os.path.exists(os.path.join("data", "pdfs", os.path.basename(fp))))
        dl_url = f"/document/download/{d.id}" if has_file else None
        web_url = d.source_url if not has_file else None
        return {
            "id": d.id,
            "label": d.source_label or d.filename or "Document",
            "department": d.department,
            "semester": d.semester,
            "file_type": d.file_type,
            "download_url": dl_url,
            "web_url": web_url,
            "created_at": d.created_at,
        }

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "documents": [_doc_entry(d) for d in docs],
    }


@router.get("/pdfs")
def list_pdfs(
    department: Optional[str] = None,
    semester: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PDF library with download buttons"""
    q = db.query(Document).filter(
        Document.is_active == True,
        Document.file_type == "pdf",
    )

    if department:
        q = q.filter(Document.department == department.upper())
    if semester:
        q = q.filter(
            Document.source_label.ilike(f"%{semester}%") |
            Document.filename.ilike(f"%{semester}%")
        )
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            Document.source_label.ilike(pattern) |
            Document.filename.ilike(pattern)
        )

    total = q.count()
    docs = q.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for d in docs:
        fp = d.file_path or ""
        if not os.path.exists(fp):
            alt = os.path.join("data", "pdfs", d.filename or "")
            if os.path.exists(alt):
                fp = alt
            else:
                continue

        file_size_kb = round(os.path.getsize(fp) / 1024, 1)
        result.append({
            "id": d.id,
            "label": d.source_label or d.filename or "Document",
            "filename": os.path.basename(fp),
            "department": d.department,
            "semester": d.semester,
            "source_url": d.source_url,
            "download_url": f"/document/download/{d.id}",
            "size_kb": file_size_kb,
            "created_at": d.created_at,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pdfs": result,
    }


# â”€â”€â”€ Session Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/sessions")
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = db.query(ChatSession).filter(ChatSession.user_id == user.id).count()
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "sessions": [
            {"id": s.id, "title": s.title,
             "created_at": s.created_at, "updated_at": s.updated_at}
            for s in sessions
        ],
    }


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    turns = (
        db.query(ChatTurn)
        .filter(ChatTurn.session_id == session_id)
        .order_by(ChatTurn.created_at.asc())
        .all()
    )
    return {
        "session_id": session.id,
        "title": session.title,
        "turns": [
            {
                "role": t.role,
                "content": t.content,
                "sources": t.sources if isinstance(t.sources, list) else
                          (json.loads(t.sources) if t.sources else []),
                "pdfs": [],
                "created_at": t.created_at,
            }
            for t in turns
        ],
    }


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}


@router.delete("/sessions")
def delete_all_sessions(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user.id).all()
    deleted = len(sessions)
    if deleted == 0:
        return {"message": "No sessions found", "deleted": 0}

    for s in sessions:
        db.delete(s)
    db.commit()
    return {"message": "All sessions deleted", "deleted": deleted}


@router.get("/cache/stats")
def cache_stats(user=Depends(get_current_user)):
    """Returns cache hit rates and sizes for monitoring"""
    return get_cache_stats()

