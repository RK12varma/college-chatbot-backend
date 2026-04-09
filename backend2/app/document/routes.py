"""
app/document/routes.py — Document Management with DS Department Focus
"""
import os
import re
import hashlib
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
import requests as req_lib
import urllib.parse

from app.database import get_db
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.audit_log import AuditLog
from app.auth.dependencies import admin_required, get_current_user
from app.document.processing import (
    process_document,
    process_website,
    reindex_result_document,
)
from app.document.auto_label import auto_label
from app.config import settings
from app.logger import logger

UPLOAD_DIR = settings.UPLOAD_DIR
MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter()

# ── holds the live crawl context for the most recent scrape job ───────────────


def _file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _log(db, user_id, action, resource=None, detail=None, ip=None):
    db.add(AuditLog(user_id=user_id, action=action, resource=resource,
                    detail=detail, ip_address=ip))
    db.commit()


# ─── Upload Document (DS Only) ────────────────────────────────────────────────

@router.post("/upload")
def upload_document(
    department: Optional[str] = None,
    semester: Optional[int] = None,
    subject: Optional[str] = None,
    file: UploadFile = File(...),
    req: Request = None,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    # Enforce Data Science department
    if department and department.upper() != "DS":
        raise HTTPException(
            status_code=400,
            detail="Only Data Science (DS) department documents are allowed"
        )

    file_bytes = file.file.read()

    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413,
            detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB} MB allowed.")

    allowed_types = {"pdf", "docx", "txt", "xml"}
    file_type = file.filename.rsplit(".", 1)[-1].lower()
    if file_type not in allowed_types:
        raise HTTPException(status_code=400,
            detail=f"Unsupported file type '{file_type}'. Allowed: {allowed_types}")

    file_hash = _file_hash(file_bytes)
    label_info = auto_label(file.filename)

    existing = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing:
        db.query(DocumentChunk).filter(DocumentChunk.document_id == existing.id).delete()
        db.commit()
        existing.source_label = label_info["source_label"]
        existing.dept_tag = "DS"
        existing.department = "DS"
        db.commit()
        new_doc = existing
        is_update = True
    else:
        original_name = os.path.basename(file.filename)
        base, ext = os.path.splitext(original_name)
        file_path = os.path.join(UPLOAD_DIR, original_name)
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(UPLOAD_DIR, f"{base}_{counter}{ext}")
            counter += 1

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        new_doc = Document(
            filename=file.filename,
            file_path=file_path,
            file_type=file_type,
            file_hash=file_hash,
            department="DS",
            semester=semester or 0,
            subject=subject or "DATA SCIENCE",
            uploaded_by=user.id,
            source_label=label_info["source_label"],
            dept_tag="DS",
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        is_update = False

    file_path = new_doc.file_path
    result = process_document(file_path, file_type, new_doc.id)

    if result["status"] == "error":
        if not is_update:
            db.delete(new_doc)
            db.commit()
            if os.path.exists(file_path):
                os.remove(file_path)
        raise HTTPException(status_code=400, detail=result["message"])

    _log(db, user.id, "document.upload", f"document:{new_doc.id}",
         detail=file.filename, ip=req.client.host if req else None)
    logger.info(
        f"{'Updated' if is_update else 'Uploaded'}: {file.filename} "
        f"| DS Department | chunks={result['chunks_processed']}"
    )

    return {
        "message": "File re-indexed successfully" if is_update else "File uploaded and indexed successfully",
        "document_id": new_doc.id,
        "filename": file.filename,
        "source_label": label_info["source_label"],
        "department": "DS",
        "chunks_created": result["chunks_processed"],
        "updated": is_update,
    }


# ─── Scrape Website (DS Only) — runs in background, returns job info ──────────

@router.post("/scrape")
def scrape_website(
    url: str,
    background_tasks: BackgroundTasks,
    req: Request = None,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    """
    Kick off a website scrape in the background.

    The scraper will:
      1. Extract full text from the start page immediately.
      2. Download + fully index the first 2 PDF/doc links on the page,
         then all remaining PDF/doc links on that page.
      3. Collect child HTML page links and put them in a pending-confirmation
         queue — they are NOT scraped automatically.

    Poll  GET /document/scrape/pending  to see which child pages were found.
    Call POST /document/scrape/confirm  to approve pages you want scraped.
    Call POST /document/scrape/reject   to discard pages you don't want.
    """
    url = url.split("#")[0].rstrip("/")

    if not url.startswith("http"):
        raise HTTPException(status_code=400,
            detail="URL must start with http:// or https://")

    label_info = auto_label(url, source_url=url)

    existing = db.query(Document).filter(Document.filename == url).first()
    if existing:
        deleted = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == existing.id
        ).delete()
        db.commit()
        existing.source_label = label_info["source_label"]
        existing.dept_tag = "DS"
        existing.department = "DS"
        db.commit()
        new_doc = existing
        is_update = True
        logger.info(f"Re-scraping: {url} | deleted {deleted} old chunks")
    else:
        new_doc = Document(
            filename=url,
            file_path=url,
            file_type="web",
            file_hash=hashlib.sha256(url.encode()).hexdigest(),
            department="DS",
            semester=0,
            subject="DATA SCIENCE",
            uploaded_by=user.id,
            source_url=url,
            source_label=label_info["source_label"],
            dept_tag="DS",
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        is_update = False

    doc_id = new_doc.id
    document_id_map = {"default": doc_id}

    def _run_scrape():
        result  = process_website(start_url=url, document_id_map=document_id_map)
        summary = result.get("summary", {})
        total   = sum(v for v in summary.values() if isinstance(v, int))
        logger.info(
            f"{'Re-scraped' if is_update else 'Scraped'}: {url} "
            f"| DS | chunks={total} "
            f"| skipped_irrelevant={summary.get('skipped_irrelevant', 0)}"
        )

    background_tasks.add_task(_run_scrape)

    _log(db, user.id, "document.scrape", f"document:{doc_id}",
         detail=url, ip=req.client.host if req else None)

    return {
        "message": "Scrape started. Poll /document/scrape/pending for child page links.",
        "document_id": doc_id,
        "source_label": label_info["source_label"],
        "department": "DS",
        "updated": is_update,
        "status": "running",
    }


# ─── List Documents (DS Only) ─────────────────────────────────────────────────

@router.get("/list")
def list_documents(
    department: Optional[str] = None,
    semester: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Document).filter(
        Document.is_active == True,
        Document.department == "DS"
    )

    if department and department.upper() != "DS":
        return {"total": 0, "page": page, "page_size": page_size, "documents": []}

    if semester is not None:
        q = q.filter(Document.semester == semester)

    def normalize_filename(name: str):
        if not name:
            return ""
        name = os.path.basename(name)
        name = re.sub(r'^[a-f0-9]+_', '', name)
        return name.lower().strip()

    all_docs = q.order_by(Document.created_at.desc()).all()
    seen = set()
    unique_docs = []

    for d in all_docs:
        clean_name = normalize_filename(d.filename)
        if clean_name not in seen:
            seen.add(clean_name)
            unique_docs.append(d)

    total = len(unique_docs)
    start = (page - 1) * page_size
    end   = start + page_size
    docs  = unique_docs[start:end]

    def _doc_info(d):
        is_pdf   = d.file_type == "pdf"
        has_file = bool(d.file_path and os.path.exists(d.file_path))
        dl_url   = f"/document/download/{d.id}" if (is_pdf and has_file) else None
        web_url  = d.source_url if not is_pdf else None
        return {
            "id":           d.id,
            "filename":     d.filename,
            "source_label": d.source_label or d.filename,
            "dept_tag":     "DS",
            "department":   "DS",
            "semester":     d.semester,
            "file_type":    d.file_type,
            "download_url": dl_url,
            "web_url":      web_url,
            "created_at":   d.created_at,
        }

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "documents": [_doc_info(d) for d in docs],
    }


# ─── Reindex Result Document ──────────────────────────────────────────────────

@router.post("/reindex/{doc_id}")
def reindex_document(
    doc_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    """Re-parse and re-index a result PDF for Data Science department"""
    result = reindex_result_document(document_id=doc_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ─── Download Document ────────────────────────────────────────────────────────

@router.get("/download/{doc_id}")
def download_document(
    doc_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve a locally uploaded PDF for download/view"""
    doc = db.query(Document).filter(
        Document.id == doc_id, Document.department == "DS"
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = doc.file_path or ""

    if not os.path.exists(file_path):
        alt = os.path.join(UPLOAD_DIR, doc.filename or "")
        if os.path.exists(alt):
            file_path = alt
        else:
            alt2 = os.path.join(UPLOAD_DIR, "pdfs", doc.filename or "")
            if os.path.exists(alt2):
                file_path = alt2
            else:
                raise HTTPException(status_code=404, detail="File not found on disk")

    clean_name = (doc.filename or "document.pdf").split("/")[-1].split("\\")[-1]
    if not clean_name.endswith(".pdf"):
        clean_name += ".pdf"

    return FileResponse(
        path=file_path,
        filename=clean_name,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{clean_name}"'},
    )


# ─── PDF Proxy ────────────────────────────────────────────────────────────────

@router.get("/proxy-pdf")
def proxy_pdf(
    url: str,
    user=Depends(get_current_user),
):
    """Proxy an external PDF through the backend"""
    decoded_url = urllib.parse.unquote(url)
    if not decoded_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        resp = req_lib.get(
            decoded_url,
            headers={"User-Agent": "Mozilla/5.0"},
            stream=True,
            timeout=30,
        )
        resp.raise_for_status()

        filename = decoded_url.split("/")[-1].split("?")[0] or "document.pdf"

        return StreamingResponse(
            resp.iter_content(chunk_size=8192),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        logger.error(f"PDF proxy error: {e}")
        raise HTTPException(status_code=502, detail=f"Could not fetch PDF: {str(e)}")


# ─── PDF Library (DS Only) ────────────────────────────────────────────────────

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
    """User-accessible PDF library - Data Science only"""
    q = db.query(Document).filter(
        Document.is_active == True,
        Document.file_type == "pdf",
        Document.department == "DS"
    )

    if department and department.upper() != "DS":
        return {"total": 0, "page": page, "page_size": page_size, "pdfs": []}

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
    docs  = q.order_by(Document.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    result = []
    for d in docs:
        fp = d.file_path or ""
        if not os.path.exists(fp):
            alt = os.path.join(UPLOAD_DIR, d.filename or "")
            if os.path.exists(alt):
                fp = alt
            else:
                alt2 = os.path.join(UPLOAD_DIR, "pdfs", d.filename or "")
                if os.path.exists(alt2):
                    fp = alt2
                else:
                    continue

        file_size_kb = round(os.path.getsize(fp) / 1024, 1)
        result.append({
            "id":           d.id,
            "label":        d.source_label or d.filename or "Document",
            "filename":     os.path.basename(fp),
            "department":   "DS",
            "semester":     d.semester,
            "source_url":   d.source_url,
            "download_url": f"/document/download/{d.id}",
            "size_kb":      file_size_kb,
            "created_at":   d.created_at,
        })

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "pdfs":      result,
    }