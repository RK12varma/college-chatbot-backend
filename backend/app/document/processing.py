import re
import os
import subprocess
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from docx import Document as DocxDocument
import xml.etree.ElementTree as ET
from sentence_transformers import SentenceTransformer
import numpy as np

from app.document.faiss_manager import get_index, save_index
from app.database import SessionLocal
from app.models.chunk import DocumentChunk


# =====================================================
# CONFIGURE EXTERNAL TOOLS (UPDATE PATHS IF NEEDED)
# =====================================================

POPPLER_PATH = r"C:\poppler-25.12.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
GHOSTSCRIPT_CMD = "gswin64c"  # make sure this works in CMD

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# =====================================================
# LOAD EMBEDDING MODEL
# =====================================================

model = SentenceTransformer("all-MiniLM-L6-v2")


# =====================================================
# EXTRACT TEXT (PDF + OCR + Ghostscript)
# =====================================================

def extract_text(file_path, file_type):

    if file_type != "pdf":
        return extract_non_pdf(file_path, file_type)

    text = ""

    try:
        # -------------------------------------------------
        # 1️⃣ Try normal PDF text extraction
        # -------------------------------------------------
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        # -------------------------------------------------
        # 2️⃣ Weak detection → OCR using Poppler + Tesseract
        # -------------------------------------------------
        if len(text.strip()) < 200:
            print("⚠ Weak extraction detected → Running OCR")

            images = convert_from_path(
                file_path,
                dpi=300,
                poppler_path=POPPLER_PATH
            )

            ocr_text = ""
            for img in images:
                ocr_text += pytesseract.image_to_string(
                    img,
                    lang="eng"
                )

            text = ocr_text

        # -------------------------------------------------
        # 3️⃣ Still weak → Ghostscript rendering fallback
        # -------------------------------------------------
        if len(text.strip()) < 100:
            print("⚠ OCR weak → Running Ghostscript fallback")

            output_image = "temp_render.png"

            gs_command = [
                GHOSTSCRIPT_CMD,
                "-dNOPAUSE",
                "-dBATCH",
                "-sDEVICE=png16m",
                "-r300",
                f"-sOutputFile={output_image}",
                file_path
            ]

            subprocess.run(gs_command, check=True)

            text = pytesseract.image_to_string(output_image)

            if os.path.exists(output_image):
                os.remove(output_image)

        return text

    except Exception as e:
        print("PDF extraction error:", e)
        return ""


# =====================================================
# NON-PDF EXTRACTION
# =====================================================

def extract_non_pdf(file_path, file_type):

    if file_type == "docx":
        doc = DocxDocument(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    elif file_type == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    elif file_type == "xml":
        tree = ET.parse(file_path)
        root = tree.getroot()
        return ET.tostring(root, encoding="unicode")

    return ""


# =====================================================
# DOCUMENT TYPE DETECTION
# =====================================================

def detect_document_type(text: str):

    if "MarksO" in text or "-- P" in text or "SGPI" in text:
        return "RESULT"

    if "Syllabus" in text or "Course Objectives" in text:
        return "SYLLABUS"

    if "Event" in text or "Challenge" in text or "Academic Year" in text:
        return "EVENT"

    return "GENERAL"


# =====================================================
# RESULT DOCUMENT CHUNKING
# =====================================================

def chunk_result_document(text):

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    chunks = []

    semester = "Unknown"
    sem_match = re.search(r"Semester\s*[- ]?\s*(\w+)", text, re.IGNORECASE)
    if sem_match:
        semester = sem_match.group(1)

    for i, line in enumerate(lines):

        if "--" in line or re.search(r"\bPass\b|\bFail\b", line, re.IGNORECASE):

            name = line.split("--")[0].strip()

            result = "Pass"
            if "FAIL" in line.upper():
                result = "Fail"

            total_marks = "Unknown"
            sgpi = "Unknown"
            subjects = {}

            sgpi_match = re.search(r"\b\d+\.\d+\b", line)
            if sgpi_match:
                sgpi = sgpi_match.group(0)

            for j in range(i - 1, max(i - 40, 0), -1):
                if "MarksO" in lines[j] or "TOTAL" in lines[j].upper():
                    numbers = re.findall(r"\b\d{2,4}\b", lines[j])
                    if numbers:
                        total_marks = numbers[-1]
                    break

            for j in range(i - 1, max(i - 30, 0), -1):
                subject_match = re.match(r"([A-Z]{2,6}\d{3,4})", lines[j])
                if subject_match:
                    subject_code = subject_match.group(1)
                    numbers = re.findall(r"\b\d{2,3}\b", lines[j])
                    if numbers:
                        subjects[subject_code] = numbers[-1]

            chunk = f"""
Student Name: {name}
Semester: {semester}
Overall Result: {result}
Total Marks Obtained: {total_marks}
SGPI: {sgpi}

Subject Performance:
"""

            for code, marks in subjects.items():
                chunk += f"- {code}: {marks} marks\n"

            chunks.append(chunk.strip())

    return chunks


# =====================================================
# SYLLABUS CHUNKING
# =====================================================

def chunk_syllabus_document(text):

    sections = re.split(r"\n(?=Unit|Module|Chapter|PO|PSO|CO)", text)
    return [s.strip() for s in sections if len(s.strip()) > 80]


# =====================================================
# EVENT CHUNKING
# =====================================================

def chunk_event_document(text):

    sections = re.split(r'\n(?=[A-Z][A-Z\s]{4,})', text)

    chunks = []
    buffer = ""

    for section in sections:
        buffer += section.strip() + "\n"

        if len(buffer) > 400:
            chunks.append(buffer.strip())
            buffer = ""

    if buffer:
        chunks.append(buffer.strip())

    return chunks


# =====================================================
# GENERAL CHUNKING
# =====================================================

def chunk_general_document(text):

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    chunks = []
    buffer = ""

    for line in lines:

        buffer += line + " "

        if len(buffer) > 400:
            chunks.append(buffer.strip())
            buffer = ""

    if buffer:
        chunks.append(buffer.strip())

    return chunks


# =====================================================
# MASTER CHUNK ROUTER
# =====================================================

def chunk_text(text):

    doc_type = detect_document_type(text)
    print("Detected document type:", doc_type)

    if doc_type == "RESULT":
        chunks = chunk_result_document(text)
    elif doc_type == "SYLLABUS":
        chunks = chunk_syllabus_document(text)
    elif doc_type == "EVENT":
        chunks = chunk_event_document(text)
    else:
        chunks = chunk_general_document(text)

    print("Chunks created:", len(chunks))
    return chunks


# =====================================================
# CREATE EMBEDDINGS
# =====================================================

def create_embeddings(text_chunks):

    embeddings = model.encode(
        text_chunks,
        normalize_embeddings=True,
        batch_size=16,
        show_progress_bar=False
    )

    return np.array(embeddings).astype("float32")


# =====================================================
# SAVE TO FAISS
# =====================================================

def save_to_faiss(embeddings, ids):

    index = get_index()
    ids = np.array(ids)

    if embeddings.shape[1] != index.d:
        raise ValueError(
            f"Embedding dimension {embeddings.shape[1]} "
            f"does not match FAISS dimension {index.d}"
        )

    index.add_with_ids(embeddings, ids)
    save_index()


# =====================================================
# FULL PROCESS PIPELINE
# =====================================================

def process_document(file_path, file_type, document_id):

    db = SessionLocal()

    try:
        text = extract_text(file_path, file_type)

        if not text or len(text.strip()) < 50:
            return {
                "status": "error",
                "message": "Insufficient text extracted"
            }

        chunks = chunk_text(text)

        if not chunks:
            return {
                "status": "error",
                "message": "No chunks created"
            }

        chunk_ids = []
        chunk_values = []

        for i, chunk_value in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=document_id,
                chunk_text=chunk_value,
                chunk_index=i
            )

            db.add(db_chunk)
            db.flush()

            chunk_ids.append(db_chunk.id)
            chunk_values.append(chunk_value)

        db.commit()

        embeddings = create_embeddings(chunk_values)
        save_to_faiss(embeddings, chunk_ids)

        return {
            "status": "success",
            "chunks_processed": len(chunks)
        }

    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "message": str(e)
        }

    finally:
        db.close()