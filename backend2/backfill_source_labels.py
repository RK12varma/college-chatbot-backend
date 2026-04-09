"""
backfill_source_labels.py

One-time script to fix source_label for all existing scraped documents
that currently have NULL source_label in the DB.

Run once from your backend2 directory:
    cd backend2 && python backfill_source_labels.py
"""
import sys, re
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.document import Document
from app.models.scrape_source import ScrapeSource
from app.models.chunk import DocumentChunk
from app.models.user import User





def _build_source_label(source_name: str, source_url: str) -> str:
    """
    Convert a raw source name like "College - Notices" into a clean label
    like "College — Notices".
    """
    name = (source_name or "").strip()
    if not name:
        name = re.sub(r"https?://(www\.)?", "", source_url).rstrip("/")
        parts = [p for p in name.split("/") if p]
        name = parts[-1].replace("-", " ").replace("_", " ").title() if parts else source_url

    # " - " → " — " (em-dash looks better in UI chips)
    name = re.sub(r"\s*-\s*", " — ", name)
    return name[:120]


def _detect_dept_tag(source_name: str, source_url: str) -> str:
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


def main():
    db = SessionLocal()

    # Build a URL → source_name map from scrape_sources table
    sources = db.query(ScrapeSource).all()
    url_to_name = {s.url: s.name for s in sources}
    print(f"Found {len(sources)} scrape source(s) in DB")

    # Fix all web documents that have NULL or empty source_label
    docs = db.query(Document).filter(
        Document.file_type == "web"
    ).all()

    fixed = 0
    for doc in docs:
        # Determine the name: prefer scrape_sources table, else use doc.filename
        source_url  = doc.source_url or doc.file_path or ""
        source_name = url_to_name.get(source_url, "") or doc.filename or ""

        clean_label = _build_source_label(source_name, source_url)
        dept_tag    = _detect_dept_tag(source_name, source_url)

        if doc.source_label != clean_label or doc.dept_tag != dept_tag:
            print(f"  Fixing doc #{doc.id}: '{doc.source_label}' → '{clean_label}'  [{dept_tag}]")
            doc.source_label = clean_label
            doc.dept_tag     = dept_tag
            fixed += 1

    db.commit()
    db.close()

    print(f"\n✅ Done — updated {fixed} document(s)")


if __name__ == "__main__":
    main()