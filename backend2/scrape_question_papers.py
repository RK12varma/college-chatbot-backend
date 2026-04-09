"""
backend/scrape_question_papers.py

Scrapes the question papers page and populates the question_papers table.
Run: cd backend && python scrape_question_papers.py

Handles the Saraswati College QP page format:
- Table with columns: SEM III | SEM IV | SEM V | SEM VI | SEM VII | SEM VIII
- Each cell has links like "May-2025", "Dec-2024" etc
"""
import sys, re, requests
sys.path.insert(0, ".")

from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import SessionLocal

# Import all models so SQLAlchemy resolves relationships
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.scrape_source import ScrapeSource
from app.models.chat_history import ChatSession, ChatTurn
from app.models.audit_log import AuditLog
from app.models.question_paper import QuestionPaper

# ── Config ────────────────────────────────────────────────────────────────────
QP_URLS = [
    {
        "url":        "https://engineering.saraswatikharghar.edu.in/qp-ds",
        "department": "DS",
        "label":      "Data Science",
    },
    # Add more departments here:
    # {
    #     "url":        "https://engineering.saraswatikharghar.edu.in/qp-ce",
    #     "department": "CE",
    #     "label":      "Computer Engineering",
    # },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Semester column header → standard name
SEM_MAP = {
    "SEM III": "SEM-III", "SEM IV":  "SEM-IV",  "SEM V":   "SEM-V",
    "SEM VI":  "SEM-VI",  "SEM VII": "SEM-VII",  "SEM VIII":"SEM-VIII",
    "SEM 3":   "SEM-III", "SEM 4":   "SEM-IV",   "SEM 5":   "SEM-V",
    "SEM 6":   "SEM-VI",  "SEM 7":   "SEM-VII",  "SEM 8":   "SEM-VIII",
}

# Month label → standard name
MONTH_MAP = {
    "jan": "January",  "feb": "February", "mar": "March",
    "apr": "April",    "may": "May",       "jun": "June",
    "jul": "July",     "aug": "August",    "sep": "September",
    "oct": "October",  "nov": "November",  "dec": "December",
}


def parse_exam_label(text: str):
    """
    Parse "May-2025", "Dec-2024", "May 2023" etc.
    Returns (month, year, label) or None.
    """
    text = text.strip()
    m = re.search(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-]+(\d{4})",
        text, re.IGNORECASE
    )
    if not m:
        return None
    month_abbr = m.group(1).lower()
    year       = int(m.group(2))
    month      = MONTH_MAP.get(month_abbr, month_abbr.title())
    label      = f"{month[:3].title()}-{year}"
    return month, year, label


def scrape_qp_page(url: str, department: str) -> list[dict]:
    """Scrape a question papers page and return list of paper dicts."""
    print(f"Scraping: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to fetch {url}: {e}")
        return []

    soup    = BeautifulSoup(resp.text, "html.parser")
    papers  = []
    tables  = soup.find_all("table")

    if not tables:
        print(f"  ⚠️  No tables found on page")
        return []

    for table in tables:
        # Get header row to map columns to semesters
        headers    = []
        header_row = table.find("tr")
        if not header_row:
            continue

        for th in header_row.find_all(["th", "td"]):
            text = th.get_text(strip=True).upper()
            headers.append(SEM_MAP.get(text, text))

        if not any(h.startswith("SEM-") for h in headers):
            continue  # not a QP table

        print(f"  Found QP table with semesters: {[h for h in headers if h.startswith('SEM-')]}")

        # Parse data rows
        for row in table.find_all("tr")[1:]:  # skip header
            cells = row.find_all(["td", "th"])
            for col_idx, cell in enumerate(cells):
                if col_idx >= len(headers):
                    break
                semester = headers[col_idx]
                if not semester.startswith("SEM-"):
                    continue

                # Find all links in this cell
                for link in cell.find_all("a", href=True):
                    href     = link["href"].strip()
                    link_txt = link.get_text(strip=True)

                    # Must be a PDF link
                    if not (href.lower().endswith(".pdf") or
                            "wp-content" in href.lower()):
                        continue

                    # Build absolute URL
                    if href.startswith("http"):
                        pdf_url = href
                    else:
                        from urllib.parse import urljoin
                        pdf_url = urljoin(url, href)

                    # Parse exam label from link text or filename
                    label_src  = link_txt or href.split("/")[-1]
                    parsed     = parse_exam_label(label_src)
                    if not parsed:
                        # Try from filename
                        parsed = parse_exam_label(href.split("/")[-1])
                    if not parsed:
                        print(f"    ⚠️  Could not parse date from: {label_src}")
                        continue

                    month, year, exam_label = parsed
                    filename = href.split("/")[-1]

                    papers.append({
                        "department": department,
                        "semester":   semester,
                        "exam_month": month,
                        "exam_year":  year,
                        "exam_label": exam_label,
                        "url":        pdf_url,
                        "filename":   filename,
                        "source_page":url,
                    })
                    print(f"    ✅ {semester} | {exam_label} | {filename[:50]}")

    return papers


def main():
    db = SessionLocal()

    total_added   = 0
    total_updated = 0

    for config in QP_URLS:
        papers = scrape_qp_page(config["url"], config["department"])
        print(f"\nFound {len(papers)} papers for {config['label']}")

        for p in papers:
            now = datetime.utcnow()

            stmt = pg_insert(QuestionPaper).values(
                department  = p["department"],
                semester    = p["semester"],
                exam_month  = p["exam_month"],
                exam_year   = p["exam_year"],
                exam_label  = p["exam_label"],
                url         = p["url"],
                filename    = p["filename"],
                source_page = p["source_page"],
                created_at  = now,
                updated_at  = now,
            ).on_conflict_do_update(
                # Must match your unique constraint columns exactly
                index_elements=["department", "semester", "exam_label"],
                set_={
                    "url":        p["url"],
                    "filename":   p["filename"],
                    "source_page":p["source_page"],
                    "updated_at": now,
                }
            )

            result = db.execute(stmt)

            # inserted_primary_key is set on INSERT, None on UPDATE
            if result.inserted_primary_key and result.inserted_primary_key[0]:
                total_added += 1
            else:
                total_updated += 1

        db.commit()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"✅ Added:   {total_added} papers")
    print(f"🔄 Updated: {total_updated} papers")

    total = db.query(QuestionPaper).count()
    print(f"📚 Total in DB: {total} papers")

    print(f"\nBreakdown by semester:")
    rows = (
        db.query(QuestionPaper.semester, func.count(QuestionPaper.id))
        .group_by(QuestionPaper.semester)
        .order_by(QuestionPaper.semester)
        .all()
    )
    for sem, count in rows:
        print(f"  {sem}: {count} papers")

    db.close()


if __name__ == "__main__":
    main()