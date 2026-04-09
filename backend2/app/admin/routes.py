import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.auth.dependencies import admin_required, get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.scrape_source import ScrapeSource
from app.models.audit_log import AuditLog
from app.models.chat_history import ChatSession, ChatTurn
from app.admin.scraper import scrape_all_sources
from app.logger import logger

router = APIRouter()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def log_action(db: Session, user_id: int, action: str, resource: str = None,
               detail: str = None, ip: str = None):
    db.add(AuditLog(user_id=user_id, action=action, resource=resource,
                    detail=detail, ip_address=ip))
    db.commit()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ScrapeSourceRequest(BaseModel):
    name: str
    url: str


class UserRoleRequest(BaseModel):
    role: str   # "student" | "admin"


class UserStatusRequest(BaseModel):
    is_active: bool


# ─── Dashboard Stats ─────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), user=Depends(admin_required)):
    total_chat_turns = db.query(ChatTurn).count()
    return {
        "users":          db.query(User).count(),
        "active_users":   db.query(User).filter(User.is_active == True).count(),
        "documents":      db.query(Document).count(),
        "chunks":         db.query(DocumentChunk).count(),
        "chat_sessions":  db.query(ChatSession).count(),
        "chat_turns":     total_chat_turns,
        "scrape_sources": db.query(ScrapeSource).count(),
    }


# ─── Documents ───────────────────────────────────────────────────────────────

@router.get("/documents")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    q = db.query(Document)
    if department:
        q = q.filter(Document.department == department.upper())
    total = q.count()
    docs = q.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "documents": [
            {
                "id": d.id, "filename": d.filename, "department": d.department,
                "semester": d.semester, "subject": d.subject,
                "file_type": d.file_type, "is_active": d.is_active,
                "created_at": d.created_at,
            }
            for d in docs
        ],
    }


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, req: Request,
                    db: Session = Depends(get_db), user=Depends(admin_required)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
    db.delete(doc)
    db.commit()

    log_action(db, user.id, "document.delete", f"document:{doc_id}",
               ip=req.client.host)
    logger.info(f"Admin {user.email} deleted document {doc_id}")
    return {"message": "Document deleted successfully"}


# ─── Users ───────────────────────────────────────────────────────────────────

@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    total = q.count()
    users = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "users": [
            {
                "id": u.id, "email": u.email, "full_name": u.full_name,
                "role": u.role, "department": u.department,
                "is_verified": u.is_verified, "is_active": u.is_active,
                "created_at": u.created_at, "last_login": u.last_login,
            }
            for u in users
        ],
    }


@router.delete("/users/{user_id}")
def delete_user(user_id: int, req: Request,
                db: Session = Depends(get_db), user=Depends(admin_required)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    db.delete(target)
    db.commit()
    log_action(db, user.id, "user.delete", f"user:{user_id}", ip=req.client.host)
    return {"message": "User deleted successfully"}


@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, body: UserRoleRequest, req: Request,
                     db: Session = Depends(get_db), user=Depends(admin_required)):
    if body.role not in ("student", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'student' or 'admin'")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    target.role = body.role
    db.commit()
    log_action(db, user.id, "user.role_change", f"user:{user_id}",
               detail=json.dumps({"new_role": body.role}), ip=req.client.host)
    return {"message": f"Role updated to {body.role}", "new_role": body.role}


@router.put("/users/{user_id}/status")
def update_user_status(user_id: int, body: UserStatusRequest, req: Request,
                       db: Session = Depends(get_db), user=Depends(admin_required)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    target.is_active = body.is_active
    db.commit()
    action = "user.activate" if body.is_active else "user.deactivate"
    log_action(db, user.id, action, f"user:{user_id}", ip=req.client.host)
    return {"message": f"User {'activated' if body.is_active else 'deactivated'} successfully"}


# ─── Audit Logs ──────────────────────────────────────────────────────────────

@router.get("/audit-logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    total = db.query(AuditLog).count()
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total, "page": page, "page_size": page_size,
        "logs": [
            {
                "id": l.id, "user_id": l.user_id, "action": l.action,
                "resource": l.resource, "detail": l.detail,
                "ip_address": l.ip_address, "created_at": l.created_at,
            }
            for l in logs
        ],
    }


# ─── Scrape Sources ──────────────────────────────────────────────────────────

@router.post("/sources")
def add_source(request: ScrapeSourceRequest,
               db: Session = Depends(get_db), user=Depends(admin_required)):
    if db.query(ScrapeSource).filter(ScrapeSource.url == request.url).first():
        raise HTTPException(status_code=400, detail="Source URL already exists")
    source = ScrapeSource(name=request.name, url=request.url)
    db.add(source)
    db.commit()
    return {"message": "Source added successfully", "id": source.id}


@router.get("/sources")
def list_sources(db: Session = Depends(get_db), user=Depends(admin_required)):
    return db.query(ScrapeSource).all()


@router.delete("/sources/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db), user=Depends(admin_required)):
    source = db.query(ScrapeSource).filter(ScrapeSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(source)
    db.commit()
    return {"message": "Source deleted successfully"}


# ─── Manual Scrape Trigger ───────────────────────────────────────────────────

@router.post("/scrape")
def trigger_scrape(req: Request, db: Session = Depends(get_db), user=Depends(admin_required)):
    try:
        result = scrape_all_sources()
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        log_action(db, user.id, "scrape.trigger",
                   detail=json.dumps(result), ip=req.client.host)
        logger.info(f"Admin {user.email} triggered scrape: {result}")
        return {
            "message": "Scraping completed successfully",
            "total_chunks_indexed": result.get("total_chunks", 0),
            "per_source": result.get("per_source", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.post("/cache/clear")
def clear_response_cache(user=Depends(admin_required)):
    from app.chat.cache import invalidate_response_cache
    invalidate_response_cache()
    return {"message": "Response cache cleared successfully"}