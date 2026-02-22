import os
import requests
import hashlib
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from sqlalchemy.orm import Session

from app.document.processing import process_document
from app.models.document import Document
from app.database import SessionLocal
from app.models.scrape_source import ScrapeSource
from app.models.user import User


UPLOAD_DIR = "data"
os.makedirs(UPLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MAX_WORKERS = 5
MAX_FILE_SIZE_MB = 20


# =====================================================
# EXTRACT PDF LINKS
# =====================================================

def extract_pdf_links(url: str):

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"[SCRAPER] Failed to fetch {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" in href.lower():
            full_url = href if href.startswith("http") else urljoin(url, href)
            links.append(full_url)

    return list(set(links))


# =====================================================
# DOWNLOAD + PROCESS SINGLE FILE
# =====================================================

def handle_single_pdf(pdf_url, user_id):

    db = SessionLocal()

    try:
        print(f"[SCRAPER] Checking: {pdf_url}")

        response = requests.get(pdf_url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            print("[SCRAPER] Failed download:", pdf_url)
            return False

        file_bytes = response.content
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        existing = db.query(Document).filter(
            Document.source_url == pdf_url
        ).first()

        # -------------------------------------------------
        # CHANGE DETECTION
        # -------------------------------------------------
        if existing:

            existing.last_checked = datetime.utcnow()

            if existing.file_hash == file_hash:
                print("[SCRAPER] No change:", pdf_url)
                db.commit()
                return False

            # File updated → reprocess
            print("[SCRAPER] File updated. Reprocessing:", pdf_url)

            existing.file_hash = file_hash
            db.commit()

            process_document(existing.file_path, "pdf", existing.id)
            return True

        # -------------------------------------------------
        # NEW FILE
        # -------------------------------------------------

        filename = pdf_url.split("/")[-1]
        file_path = os.path.join(UPLOAD_DIR, filename)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        new_doc = Document(
            filename=filename,
            file_path=file_path,
            file_type="pdf",
            file_hash=file_hash,
            source_url=pdf_url,
            department="SCRAPED",
            semester=0,
            subject="SCRAPED",
            uploaded_by=user_id,
            last_checked=datetime.utcnow(),
            is_active=True,
        )

        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        process_document(file_path, "pdf", new_doc.id)

        print("[SCRAPER] New file processed:", pdf_url)
        return True

    except Exception as e:
        print("[SCRAPER] Error:", e)
        db.rollback()
        return False

    finally:
        db.close()


# =====================================================
# MAIN SCRAPER
# =====================================================

def scrape_all_sources():

    db = SessionLocal()

    try:
        admin_user = db.query(User).filter(
            User.role == "admin"
        ).first()

        if not admin_user:
            print("[SCRAPER] No admin user found.")
            return

        sources = db.query(ScrapeSource).all()

        all_links = []

        for source in sources:
            print("[SCRAPER] Scraping:", source.url)
            links = extract_pdf_links(source.url)
            all_links.extend(links)

        all_links = list(set(all_links))

        print(f"[SCRAPER] Total PDFs found: {len(all_links)}")

        processed_count = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(handle_single_pdf, link, admin_user.id)
                for link in all_links
            ]

            for future in as_completed(futures):
                if future.result():
                    processed_count += 1

        print(f"[SCRAPER] Total processed: {processed_count}")

        # -------------------------------------------------
        # DOCUMENT AGING SYSTEM
        # -------------------------------------------------
        now = datetime.utcnow()
        for doc in db.query(Document).filter(
            Document.department == "SCRAPED"
        ).all():

            if (now - doc.last_checked).days > 30:
                doc.is_active = False

        db.commit()

    except Exception as e:
        print("[SCRAPER] Fatal error:", e)
        db.rollback()

    finally:
        db.close()