import hashlib
import re
from datetime import datetime
from sqlalchemy.orm import Session

from app.document.processing import process_website   # ← BFS scraper
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.database import SessionLocal
from app.models.scrape_source import ScrapeSource
from app.models.user import User


# =====================================================
# HELPERS
# =====================================================

def _build_source_label(source_name: str, source_url: str) -> str:
    """
    Convert a raw source name like "College - Notices" into a clean,
    human-readable label like "College — Notices".
    Falls back to extracting a readable name from the URL if source_name is blank.
    """
    name = (source_name or "").strip()
    if not name:
        # Derive from URL: strip scheme, www, trailing slash, take last path segment
        name = re.sub(r"https?://(www\.)?", "", source_url).rstrip("/")
        parts = [p for p in name.split("/") if p]
        name = parts[-1].replace("-", " ").replace("_", " ").title() if parts else source_url

    # Normalise separators: " - " → " — "  (em-dash looks better in UI chips)
    name = re.sub(r"\s*-\s*", " — ", name)
    return name[:120]


def _detect_dept_tag(source_name: str, source_url: str) -> str:
    """
    Detect department tag from name/URL.
    Returns short tag like "DS", "CE", "MECH", "CIVIL" or "" if unknown.
    """
    combined = (source_name + " " + source_url).lower()
    if "data-science" in combined or "data science" in combined or "/ds" in combined:
        return "DS"
    if "computer-engineering" in combined or "computer engineering" in combined or "/ce" in combined:
        return "CE"
    if "mechanical" in combined or "/mech" in combined:
        return "MECH"
    if "civil" in combined:
        return "CIVIL"
    if "electronics" in combined or "/extc" in combined:
        return "EXTC"
    return ""


# =====================================================
# SCRAPE A SINGLE SOURCE URL
# =====================================================

def scrape_source(source_url: str, source_name: str, user_id: int):
    """
    Fully crawl one source URL using BFS.
    Extracts text from HTML pages, PDFs, DOCX, images (OCR), etc.
    Saves everything to DB + FAISS under one Document record.
    """
    db = SessionLocal()

    # Pre-compute clean label & dept tag BEFORE opening the DB session
    clean_label = _build_source_label(source_name, source_url)
    dept_tag    = _detect_dept_tag(source_name, source_url)

    try:
        url_hash = hashlib.sha256(source_url.encode()).hexdigest()

        # Check if this source was already scraped
        existing = db.query(Document).filter(
            Document.file_hash == url_hash
        ).first()

        if existing:
            print(f"[SCRAPER] Already scraped, re-scraping: {source_url}")
            # Delete old chunks before re-scraping
            db.query(DocumentChunk).filter(
                DocumentChunk.document_id == existing.id
            ).delete()
            db.commit()
            doc_id = existing.id

            # ✅ Always refresh label/tag in case the source name changed
            existing.last_checked = datetime.utcnow()
            existing.source_label = clean_label
            existing.dept_tag     = dept_tag
            db.commit()
        else:
            # Create a new document record for this source
            new_doc = Document(
                filename     = source_name or source_url,
                file_path    = source_url,
                file_type    = "web",
                file_hash    = url_hash,
                source_url   = source_url,
                department   = "SCRAPED",
                semester     = 0,
                subject      = "SCRAPED",
                uploaded_by  = user_id,
                last_checked = datetime.utcnow(),
                is_active    = True,
                # ✅ Set human-readable label and dept tag
                source_label = clean_label,
                dept_tag     = dept_tag,
            )
            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)
            doc_id = new_doc.id

    except Exception as e:
        print(f"[SCRAPER] DB error setting up source {source_url}: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

    # Run the full BFS scraper — crawls all pages, PDFs, images, etc.
    print(f"[SCRAPER] Starting full BFS crawl: {source_url}")
    summary = process_website(
        start_url=source_url,
        document_id_map={"default": doc_id}
    )

    total = sum(v for k, v in summary.items() if k != "errors")
    print(f"[SCRAPER] Source done: {source_url} → {total} chunks indexed")
    print(f"[SCRAPER] Breakdown: {summary}")
    return total


# =====================================================
# SCRAPE ALL SAVED SOURCES
# =====================================================

def scrape_all_sources():
    """
    Loop through all ScrapeSource records and fully crawl each one.
    Called by the /admin/scrape endpoint.
    """
    db = SessionLocal()

    try:
        admin_user = db.query(User).filter(User.role == "admin").first()
        if not admin_user:
            print("[SCRAPER] No admin user found.")
            return {"error": "No admin user found"}

        sources = db.query(ScrapeSource).all()

        if not sources:
            print("[SCRAPER] No sources configured.")
            return {"error": "No sources configured"}

        print(f"[SCRAPER] Found {len(sources)} source(s) to scrape")

    except Exception as e:
        print(f"[SCRAPER] Fatal DB error: {e}")
        return {"error": str(e)}
    finally:
        db.close()

    # Scrape each source sequentially
    results = {}
    for source in sources:
        print(f"\n[SCRAPER] ══════════════════════════════")
        print(f"[SCRAPER] Scraping source: {source.name} → {source.url}")
        print(f"[SCRAPER] ══════════════════════════════")
        chunks = scrape_source(source.url, source.name, admin_user.id)
        results[source.name] = chunks

    total_chunks = sum(results.values())
    print(f"\n[SCRAPER] All sources done. Total chunks indexed: {total_chunks}")
    print(f"[SCRAPER] Per-source: {results}")

    return {
        "total_chunks": total_chunks,
        "per_source": results
    }