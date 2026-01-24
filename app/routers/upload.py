from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil

router = APIRouter(prefix="/upload", tags=["File Upload"])

BASE_UPLOAD_DIR = "uploads"

@router.post("/syllabus")
async def upload_syllabus_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    save_path = os.path.join(BASE_UPLOAD_DIR, "syllabus", file.filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Syllabus PDF uploaded successfully",
        "file_path": save_path
    }
