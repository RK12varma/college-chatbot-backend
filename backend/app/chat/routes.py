from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.document.search import search_similar_chunks
from app.llm.gemini_service import generate_answer
from app.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.document.faiss_manager import get_index


router = APIRouter()


# =====================================================
# REQUEST SCHEMA
# =====================================================

class QuestionRequest(BaseModel):
    question: str


# =====================================================
# ASK QUESTION ROUTE
# =====================================================

@router.post("/ask")
def ask_question(data: QuestionRequest, user=Depends(get_current_user)):

    question = data.question.strip()

    if not question:
        return {
            "question": question,
            "answer": "Question cannot be empty."
        }

    # 1️⃣ Retrieve vector IDs from FAISS
    vector_ids = search_similar_chunks(question, top_k=8)

    if not vector_ids:
        return {
            "question": question,
            "answer": "No relevant information found in uploaded documents."
        }

    db: Session = SessionLocal()

    try:
        # 🔥 EAGER LOAD document relationship to prevent lazy-loading after session close
        results = (
            db.query(DocumentChunk)
            .options(joinedload(DocumentChunk.document))
            .filter(DocumentChunk.id.in_(vector_ids))
            .all()
        )

        # Preserve FAISS similarity ranking order
        id_to_chunk = {chunk.id: chunk for chunk in results}
        ordered_chunks = [
            id_to_chunk[i] for i in vector_ids if i in id_to_chunk
        ]

        # Build context (Top 5 most relevant chunks)
        context_parts = [
            chunk.chunk_text for chunk in ordered_chunks[:5]
        ]

        context = "\n\n".join(context_parts)

        # Collect unique source filenames (SAFE because of eager loading)
        source_documents = list({
            chunk.document.filename
            for chunk in ordered_chunks
            if chunk.document
        })

    finally:
        db.close()

    if not context.strip():
        return {
            "question": question,
            "answer": "No relevant information found in uploaded documents."
        }

    # 2️⃣ Generate Answer from LLM
    answer = generate_answer(question, context)

    return {
        "question": question,
        "answer": answer,
        "sources": source_documents
    }


# =====================================================
# DEBUG: VIEW STORED CHUNKS
# =====================================================

@router.get("/debug-chunks")
def debug_chunks():

    db: Session = SessionLocal()

    try:
        chunks = db.query(DocumentChunk).all()

        return {
            "total_chunks": len(chunks),
            "sample": [c.chunk_text[:300] for c in chunks[:3]]
        }

    finally:
        db.close()


# =====================================================
# DEBUG: FAISS INDEX INFO
# =====================================================

@router.get("/debug-faiss")
def debug_faiss():

    try:
        index = get_index()

        return {
            "total_vectors": index.ntotal,
            "dimension": index.d
        }

    except Exception as e:
        return {
            "error": str(e)
        }