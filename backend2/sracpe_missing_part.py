"""
backend/scrape_missing_data.py

Scrapes all missing college data:
- Fee structure
- Exam timetable  
- Placement statistics
- SEM-III, IV, VI, VIII result PDFs (from college results page)

Run: cd backend && python scrape_missing_data.py
"""
import sys, os, requests, re
sys.path.insert(0, ".")

from bs4 import BeautifulSoup
from app.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.scrape_source import ScrapeSource
from app.models.chat_history import ChatSession, ChatTurn
from app.models.audit_log import AuditLog
from app.document.auto_label import auto_label
from app.document.processing import process_website
import hashlib

BASE = "https://engineering.saraswatikharghar.edu.in"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ── URLs to scrape ─────────────────────────────────────────────────────────
SCRAPE_TARGETS = [
    # Fee structure
    {
        "url":   f"{BASE}/fee-structure/",
        "label": "College - Fee Structure",
        "dept":  "GEN",
    },
    # Placement
    {
        "url":   f"{BASE}/placement/",
        "label": "College - Placements",
        "dept":  "GEN",
    },
    # Exam timetable
    {
        "url":   f"{BASE}/timetable/",
        "label": "College - Timetable",
        "dept":  "GEN",
    },
    # DS Results page (has links to all semester PDFs)
    {
        "url":   f"{BASE}/results-cse-data-science/",
        "label": "Data Science - Results",
        "dept":  "DS",
    },
    # CE Results page
    {
        "url":   f"{BASE}/results-computer-engineering/",
        "label": "Computer Engineering - Results",
        "dept":  "CE",
    },
    # Notices
    {
        "url":   f"{BASE}/notices/",
        "label": "College - Notices",
        "dept":  "GEN",
    },
    # About
    {
        "url":   f"{BASE}/about-saraswati/",
        "label": "College - About",
        "dept":  "GEN",
    },
]


def url_exists(db, url: str) -> bool:
    url = url.split("#")[0].rstrip("/")
    return db.query(Document).filter(Document.filename == url).first() is not None


def scrape_url(db, url: str, label: str, dept: str, user_id: int = 1):
    url = url.split("#")[0].rstrip("/")
    if not url.startswith("http"):
        print(f"  ⚠️  Skipping invalid URL: {url}")
        return False

    # Check if already scraped
    existing = db.query(Document).filter(Document.filename == url).first()
    if existing:
        # Delete old chunks and re-scrape
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == existing.id
        ).delete()
        db.commit()
        existing.source_label = label
        existing.dept_tag     = dept
        db.commit()
        new_doc = existing
        print(f"  🔄 Re-scraping: {url}")
    else:
        new_doc = Document(
            filename     = url,
            file_path    = url,
            file_type    = "web",
            file_hash    = hashlib.sha256(url.encode()).hexdigest(),
            department   = dept,
            semester     = 0,
            subject      = "GENERAL",
            uploaded_by  = user_id,
            source_url   = url,
            source_label = label,
            dept_tag     = dept,
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        print(f"  🌐 Scraping: {url}")

    try:
        summary = process_website(
            start_url       = url,
            document_id_map = {"default": new_doc.id}
        )
        total = sum(v for k, v in summary.items() if k != "errors")
        if total == 0:
            # Delete document if nothing scraped
            if not existing:
                db.delete(new_doc)
                db.commit()
            print(f"  ⚠️  No content extracted from {url}")
            return False
        print(f"  ✅ {total} chunks | label='{label}'")
        return True
    except Exception as e:
        print(f"  ❌ Error scraping {url}: {e}")
        return False


def main():
    db    = SessionLocal()
    ok    = 0
    fail  = 0

    print("=" * 60)
    print("Scraping missing college data...")
    print("=" * 60)

    for target in SCRAPE_TARGETS:
        print(f"\n📌 {target['label']}")
        success = scrape_url(
            db,
            target["url"],
            target["label"],
            target["dept"],
        )
        if success:
            ok += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print(f"✅ Success: {ok} | ❌ Failed: {fail}")
    print(f"Total documents: {db.query(Document).count()}")
    print(f"Total chunks:    {db.query(DocumentChunk).count()}")
    db.close()

    print("\nRebuilding FAISS index...")
    os.system("python rebuild_faiss.py")
    print("Done! Restart uvicorn to apply changes.")


if __name__ == "__main__":
    main()