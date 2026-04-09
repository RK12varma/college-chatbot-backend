# backend/app/document/qp_routes.py
import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth.dependencies import get_current_user, admin_required
from app.models.question_paper import QuestionPaper

router = APIRouter()


@router.get("/list")
def list_question_papers(
    department: str = Query("DS"),
    semester:   str = Query(None),
    year:       int = Query(None),
    db: Session = Depends(get_db),
):
    """List question papers with optional filters."""
    q = db.query(QuestionPaper).filter(
        QuestionPaper.department == department.upper()
    )
    if semester:
        q = q.filter(QuestionPaper.semester == semester.upper())
    if year:
        q = q.filter(QuestionPaper.exam_year == year)

    papers = q.order_by(
        QuestionPaper.semester,
        QuestionPaper.exam_year.desc(),
        QuestionPaper.exam_month
    ).all()

    # Group by semester
    grouped = {}
    for p in papers:
        sem = p.semester
        if sem not in grouped:
            grouped[sem] = []
        grouped[sem].append({
            "id":         p.id,
            "exam_label": p.exam_label,
            "exam_year":  p.exam_year,
            "exam_month": p.exam_month,
            "url":        p.url,
            "filename":   p.filename,
        })

    return {
        "department": department.upper(),
        "total":      len(papers),
        "semesters":  grouped,
    }


@router.get("/search")
def search_question_papers(
    q:          str = Query(..., description="Search query e.g. 'sem 5 may 2024'"),
    department: str = Query("DS"),
    db: Session = Depends(get_db),
):
    """Search question papers by semester, year, or month."""
    query = db.query(QuestionPaper).filter(
        QuestionPaper.department == department.upper()
    )

    # Extract semester
    sem_match = re.search(
        r"sem[\s\-]*(iii|iv|viii|vii|vi|v|3|4|5|6|7|8)",
        q, re.IGNORECASE
    )
    if sem_match:
        raw = sem_match.group(1).upper()
        sem_map = {
            "3":"SEM-III","4":"SEM-IV","5":"SEM-V","6":"SEM-VI",
            "7":"SEM-VII","8":"SEM-VIII",
            "III":"SEM-III","IV":"SEM-IV","V":"SEM-V","VI":"SEM-VI",
            "VII":"SEM-VII","VIII":"SEM-VIII",
        }
        sem = sem_map.get(raw)
        if sem:
            query = query.filter(QuestionPaper.semester == sem)

    # Extract year
    year_match = re.search(r"\b(20\d{2})\b", q)
    if year_match:
        query = query.filter(QuestionPaper.exam_year == int(year_match.group(1)))

    # Extract month
    month_map = {
        "jan":"January","feb":"February","mar":"March","apr":"April",
        "may":"May","jun":"June","jul":"July","aug":"August",
        "sep":"September","oct":"October","nov":"November","dec":"December",
    }
    for abbr, full in month_map.items():
        if abbr in q.lower() or full.lower() in q.lower():
            query = query.filter(QuestionPaper.exam_month == full)
            break

    papers = query.order_by(
        QuestionPaper.exam_year.desc(),
        QuestionPaper.semester
    ).limit(10).all()

    return {
        "query":   q,
        "results": [
            {
                "id":         p.id,
                "department": p.department,
                "semester":   p.semester,
                "exam_label": p.exam_label,
                "url":        p.url,
                "filename":   p.filename,
            }
            for p in papers
        ],
    }


@router.post("/refresh")
def refresh_question_papers(
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    """Re-scrape question papers from college website."""
    import subprocess
    import sys
    try:
        result = subprocess.run(
            [sys.executable, "scrape_question_papers.py"],
            capture_output=True, text=True, timeout=120
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "output": result.stdout[-2000:],
            "errors": result.stderr[-500:] if result.stderr else None,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}