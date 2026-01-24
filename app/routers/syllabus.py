from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.academic import Syllabus

router = APIRouter(prefix="/syllabus", tags=["Syllabus"])

@router.post("/add")
def add_syllabus(
    course: str,
    branch: str,
    semester: int,
    year: int,
    file_path: str,
    db: Session = Depends(get_db)
):
    syllabus = Syllabus(
        course=course,
        branch=branch,
        semester=semester,
        year=year,
        file_path=file_path
    )
    db.add(syllabus)
    db.commit()
    db.refresh(syllabus)
    return {"message": "Syllabus added successfully", "id": syllabus.syllabus_id}

@router.get("/all")
def get_all_syllabus(db: Session = Depends(get_db)):
    return db.query(Syllabus).all()
