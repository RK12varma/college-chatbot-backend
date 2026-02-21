from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import SessionLocal
from app.auth.dependencies import admin_required
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.scrape_source import ScrapeSource
from app.admin.scraper import scrape_all_sources

router = APIRouter()


# -------------------------
# DB Dependency
# -------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# Request Schemas
# -------------------------
class ScrapeSourceRequest(BaseModel):
    name: str
    url: str


# -------------------------
# Stats
# -------------------------
@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    user=Depends(admin_required)
):
    return {
        "users": db.query(User).count(),
        "documents": db.query(Document).count(),
        "chunks": db.query(DocumentChunk).count(),
    }


# -------------------------
# Documents
# -------------------------
@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    user=Depends(admin_required)
):
    documents = db.query(Document).all()

    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "department": doc.department,
            "semester": doc.semester,
            "subject": doc.subject,
        }
        for doc in documents
    ]


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user=Depends(admin_required)
):
    document = db.query(Document).filter(Document.id == doc_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == doc_id
    ).delete()

    db.delete(document)
    db.commit()

    return {"message": "Document deleted successfully"}


# -------------------------
# Users
# -------------------------
@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    user=Depends(admin_required)
):
    users = db.query(User).all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "department": u.department,
        }
        for u in users
    ]


# -------------------------
# Scrape
# -------------------------
@router.post("/scrape")
def scrape(
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    from app.admin.scraper import process_pdfs, extract_pdf_links

    sources = db.query(ScrapeSource).all()

    total_found = 0
    total_processed = 0

    for source in sources:
        pdf_links = extract_pdf_links(source.url)
        total_found += len(pdf_links)

        processed = process_pdfs(pdf_links, db, user.id)
        total_processed += processed

    return {
        "total_pdfs_found": total_found,
        "processed": total_processed,
    }


# -------------------------
# Sources
# -------------------------
@router.post("/sources")
def add_source(
    request: ScrapeSourceRequest,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    source = ScrapeSource(
        name=request.name,
        url=request.url,
    )

    db.add(source)
    db.commit()

    return {"message": "Source added successfully"}


@router.get("/sources")
def list_sources(
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    return db.query(ScrapeSource).all()


@router.delete("/sources/{source_id}")
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    source = db.query(ScrapeSource).filter(
        ScrapeSource.id == source_id
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    db.delete(source)
    db.commit()

    return {"message": "Source deleted"}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == user.id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    db.delete(target)
    db.commit()

    return {"message": "User deleted successfully"}

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == user.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    # Toggle role
    if target.role == "admin":
        target.role = "user"
    else:
        target.role = "admin"

    db.commit()

    return {
        "message": "Role updated successfully",
        "new_role": target.role
    }
