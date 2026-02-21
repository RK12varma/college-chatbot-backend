from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.document.search import search_similar_chunks
from app.llm.gemini_service import generate_answer
from app.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.document.faiss_manager import get_index

router = APIRouter()


# -------------------------------
# Request Schema
# -------------------------------
class QuestionRequest(BaseModel):
    question: str


# -------------------------------
# Ask Question Route
# -------------------------------
@router.post("/ask")
def ask_question(data: QuestionRequest, user=Depends(get_current_user)):

    question = data.question.strip()

    if not question:
        return {
            "question": question,
            "answer": "Question cannot be empty."
        }

    # 1️⃣ Retrieve relevant vector IDs from FAISS
    vector_ids = search_similar_chunks(question, top_k=8)

    if not vector_ids:
        return {
            "question": question,
            "answer": "No relevant information found in uploaded documents."
        }

    # 2️⃣ Fetch actual chunks from DB
    db: Session = SessionLocal()

    try:
        results = db.query(DocumentChunk).filter(
            DocumentChunk.id.in_(vector_ids)
        ).all()
    finally:
        db.close()

    if not results:
        return {
            "question": question,
            "answer": "No relevant information found in uploaded documents."
        }

    # 3️⃣ Build context and collect sources
    context_parts = []
    source_documents = set()

    for chunk in results:
        context_parts.append(chunk.chunk_text)

        # Ensure relationship exists
        if hasattr(chunk, "document") and chunk.document:
            source_documents.add(chunk.document.filename)

    context = "\n\n".join(context_parts)

    if not context.strip():
        return {
            "question": question,
            "answer": "No relevant information found in uploaded documents."
        }

    # 4️⃣ Generate answer using LLM
    answer = generate_answer(question, context)

    return {
        "question": question,
        "answer": answer,
        "sources": list(source_documents)
    }


# -------------------------------
# Debug: View stored chunks
# -------------------------------
@router.get("/debug-chunks")
def debug_chunks():

    db: Session = SessionLocal()

    try:
        chunks = db.query(DocumentChunk).all()
        return {
            "total_chunks": len(chunks),
            "sample": [c.chunk_text[:200] for c in chunks[:2]]
        }
    finally:
        db.close()


# -------------------------------
# Debug: FAISS index info
# -------------------------------
@router.get("/debug-faiss")
def debug_faiss():
    try:
        index = get_index()
        return {
            "total_vectors": index.ntotal,
            "dimension": index.d
        }
    except Exception as e:
        return {"error": str(e)}