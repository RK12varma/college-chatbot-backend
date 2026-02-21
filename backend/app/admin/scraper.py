import os
import requests
import hashlib
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from sqlalchemy.orm import Session

from app.document.processing import (
    extract_text,
    chunk_text,
    create_embeddings,
    save_to_faiss,
)
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.database import SessionLocal
from app.models.scrape_source import ScrapeSource
from app.models.user import User


UPLOAD_DIR = "data"
os.makedirs(UPLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# =====================================================
# EXTRACT PDF LINKS FROM WEBSITE
# =====================================================

def extract_pdf_links(url: str):
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    links = []

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if ".pdf" in href.lower():
            if href.startswith("http"):
                links.append(href)
            else:
                links.append(urljoin(url, href))

    return links


# =====================================================
# PROCESS PDF FILES
# =====================================================

def process_pdfs(pdf_links, db: Session, user_id: int):
    processed_count = 0

    for pdf_url in pdf_links:
        try:
            print(f"Downloading: {pdf_url}")

            file_response = requests.get(
                pdf_url,
                headers=HEADERS,
            )

            if file_response.status_code != 200:
                print("Failed download:", pdf_url)
                continue

            file_bytes = file_response.content

            # SHA256 duplicate detection
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            existing = db.query(Document).filter(
                Document.file_hash == file_hash
            ).first()

            if existing:
                print("Duplicate found, skipping:", pdf_url)
                continue

            filename = pdf_url.split("/")[-1]
            file_path = os.path.join(UPLOAD_DIR, filename)

            with open(file_path, "wb") as f:
                f.write(file_bytes)

            new_doc = Document(
                filename=filename,
                file_path=file_path,
                file_type="pdf",
                file_hash=file_hash,
                department="SCRAPED",
                semester=0,
                subject="SCRAPED",
                uploaded_by=user_id,
            )

            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)

            text = extract_text(file_path, "pdf")

            if not text or not text.strip():
                print("No text extracted:", filename)
                continue

            chunks = chunk_text(text)
            vector_ids = []

            for chunk in chunks:
                db_chunk = DocumentChunk(
                    document_id=new_doc.id,
                    chunk_text=chunk,
                )
                db.add(db_chunk)
                db.flush()
                vector_ids.append(db_chunk.id)

            db.commit()

            embeddings = create_embeddings(chunks)
            save_to_faiss(embeddings, vector_ids)

            processed_count += 1
            print("Processed:", filename)

        except Exception as e:
            print(f"Error processing {pdf_url}: {str(e)}")
            db.rollback()

    return processed_count


# =====================================================
# SCHEDULED SCRAPE (SELF-MANAGED DB SESSION)
# =====================================================

def scrape_all_sources():
    db = SessionLocal()

    try:
        # Get admin/system user
        admin_user = db.query(User).filter(
            User.role == "admin"
        ).first()

        if not admin_user:
            print("No admin user found. Skipping scheduled scrape.")
            return

        sources = db.query(ScrapeSource).all()

        total_found = 0
        total_processed = 0

        for source in sources:
            print(f"Scheduled scraping: {source.url}")

            pdf_links = extract_pdf_links(source.url)
            total_found += len(pdf_links)

            processed = process_pdfs(
                pdf_links,
                db,
                admin_user.id
            )
            total_processed += processed

        print(
            f"Scheduled scrape done. "
            f"Found: {total_found}, "
            f"Processed: {total_processed}"
        )

    except Exception as e:
        print("Scheduler scrape error:", str(e))
        db.rollback()

    finally:
        db.close()




