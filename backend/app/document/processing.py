import re
import os
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
# CONFIGURE EXTERNAL TOOLS
# =====================================================

POPPLER_PATH = r"C:\poppler-25.12.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# =====================================================
# LOAD MODEL
# =====================================================

model = SentenceTransformer("all-MiniLM-L6-v2")


# =====================================================
# CREATE EMBEDDINGS
# =====================================================

def create_embeddings(texts):

    if not texts:
        return []

    embeddings = model.encode(texts)
    embeddings = np.array(embeddings).astype("float32")

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    return embeddings


# =====================================================
# EXTRACT TEXT
# =====================================================

def extract_text(file_path, file_type):

    if file_type != "pdf":
        return extract_non_pdf(file_path, file_type)

    text = ""

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        # OCR fallback
        if len(text.strip()) < 200:
            images = convert_from_path(file_path, dpi=300, poppler_path=POPPLER_PATH)
            ocr_text = ""
            for img in images:
                ocr_text += pytesseract.image_to_string(img, lang="eng")
            text = ocr_text

        return text

    except Exception as e:
        print("PDF extraction error:", e)
        return ""


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

    if re.search(r"DS\s*\d{4}", text):
        return "RESULT"

    return "GENERAL"


# =====================================================
# RESULT DOCUMENT EXTRACTION
# =====================================================

def chunk_result_document(text: str):

    students = []

    # Detect semester dynamically
    sem_match = re.search(r"Semester\s+([IVX]+)", text, re.IGNORECASE)

    if sem_match:
        semester_value = f"SEM-{sem_match.group(1).upper()}"
    else:
        semester_value = "UNKNOWN"

    # Split blocks by seat number
    blocks = re.split(r'\n(?=DS\s*\d{4})', text)

    print("Total blocks detected:", len(blocks))

    for block in blocks:

        seat_match = re.search(r'(DS\s*\d{4})', block)
        total_match = re.search(r'\s(\d{3})\s*\n\s*Grade', block)
        name_match = re.search(r'\n([A-Z][A-Z\s]+?)\s*--\s*([PF]{1,2})', block)

        if not seat_match:
            continue

        seat_no = seat_match.group(1).replace(" ", "")
        total_marks = total_match.group(1) if total_match else "0"

        if not name_match:
            continue

        student_name = name_match.group(1).strip()
        result_code = name_match.group(2)

        if result_code == "P":
            overall_status = "PASS"
        elif result_code == "F":
            overall_status = "FAIL"
        elif result_code == "PF":
            overall_status = "PASS WITH FAIL"
        else:
            overall_status = "UNKNOWN"

        structured_text = f"""
Student Seat No: {seat_no}
Student Name: {student_name}
Semester: {semester_value}
Total Marks: {total_marks}
Overall Result: {overall_status}
"""

        students.append({
            "text": structured_text.strip(),
            "subject_json": None
        })

    print("Detected semester:", semester_value)
    print("Total students extracted:", len(students))

    return students


# =====================================================
# GENERAL DOCUMENT CHUNKING
# =====================================================

def chunk_general_document(text: str):

    chunk_size = 800
    overlap = 100

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:

        end = start + chunk_size
        chunk = text[start:end]

        chunks.append({
            "text": chunk.strip(),
            "subject_json": None
        })

        start += chunk_size - overlap

    print("General document chunks created:", len(chunks))

    return chunks


# =====================================================
# CHUNK ROUTER
# =====================================================

def chunk_text(text):

    doc_type = detect_document_type(text)

    if doc_type == "RESULT":
        return chunk_result_document(text)

    return chunk_general_document(text)


# =====================================================
# SAFE FAISS SAVE WITH IDS
# =====================================================

def save_to_faiss(embeddings, chunk_ids):

    index = get_index()

    if embeddings is None or len(embeddings) == 0:
        print("No embeddings generated. Skipping FAISS.")
        return

    embeddings = np.array(embeddings).astype("float32")

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    if embeddings.shape[1] != index.d:
        print("Embedding dimension mismatch. Skipping FAISS.")
        return

    ids = np.array(chunk_ids, dtype=np.int64)

    index.add_with_ids(embeddings, ids)

    save_index()

    print("FAISS updated successfully with IDs.")


# =====================================================
# PROCESS DOCUMENT
# =====================================================

def process_document(file_path, file_type, document_id):

    db = SessionLocal()

    try:
        text = extract_text(file_path, file_type)

        if not text or len(text.strip()) < 50:
            return {"status": "error", "message": "Insufficient text"}

        doc_type = detect_document_type(text)
        print("Detected document type:", doc_type)

        chunks = chunk_text(text)

        if not chunks:
            return {"status": "error", "message": "No chunks generated"}

        chunk_texts = [c["text"] for c in chunks]

        embeddings = create_embeddings(chunk_texts)

        chunk_ids = []

        for i, chunk_obj in enumerate(chunks):

            db_chunk = DocumentChunk(
                document_id=document_id,
                chunk_text=chunk_obj["text"],
                chunk_index=i,
                subject_data=chunk_obj["subject_json"]
            )

            db.add(db_chunk)
            db.flush()
            chunk_ids.append(db_chunk.id)

        db.commit()

        save_to_faiss(embeddings, chunk_ids)

        return {
            "status": "success",
            "chunks_processed": len(chunks)
        }

    except Exception as e:
        db.rollback()
        print("Processing error:", e)
        return {"status": "error", "message": str(e)}

    finally:
        db.close()