"""
result_extractor.py - Shared extraction logic for DS result documents.
Used by both processing.py and insert_results.py to keep parsing consistent.
"""
import io
import json
import re
from typing import Optional

import pdfplumber

from app.logger import logger


STATUS_MAP = {
    "PASS": "PASS",
    "P": "PASS",
    "FAIL": "FAIL",
    "F": "FAIL",
    "PF": "PASS WITH FAIL",
    "PASSWITHFAIL": "PASS WITH FAIL",
}

GRADE_TOKENS = {
    "AB", "ESE", "IA", "FA", "TOT", "PR", "OR", "TW", "GP", "MAXM", "MINM",
    "MARKSO", "GRADE", "RESULT", "SGPI", "GPA", "C", "P", "F", "PF",
}

SKIP_NAME_TOKENS = {
    "RESULT", "SGPI", "GPA", "NAME", "SEM", "TOTAL", "MARKS", "GRADE",
    "PASS", "FAIL", "PREPARED", "CHECKED", "CONTROLLER", "PRINCIPAL", "PAGE",
}


def detect_semester_from_text(text: str) -> str:
    for pat in [
        r"Semester\s+([IVX]+)",
        r"SEM[\s\-]*([IVX]+|\d+)",
        r"\(Semester\s+([IVX]+)\)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return "SEM-" + m.group(1).upper()
    return "UNKNOWN"


def clean_student_name(raw: str) -> str:
    if not raw:
        return ""

    raw = re.sub(
        r"\b(A|B|C|D|F|O|P|A\+|B\+|C\+|AB|ESE|IA|FA|TOT|GP|GPA)\b",
        "",
        raw,
        flags=re.I,
    )
    # Remove tokens that are clearly not part of a human name (digits, seat-like tokens).
    raw = " ".join(tok for tok in raw.split() if not re.search(r"\d", tok))
    name = " ".join(raw.split())
    if name.isupper():
        name = name.title()
    parts = name.split()
    if len(parts) > 4:
        name = " ".join(parts[:4])
    return name.strip()


def _is_valid_student_name(name: str) -> bool:
    if not name:
        return False
    if re.search(r"\d", name):
        return False
    parts = [p for p in name.split() if p.isalpha()]
    return len(parts) >= 2


def build_name_search_text(name: str) -> str:
    parts = name.split()
    variants = [name]
    if len(parts) >= 2:
        variants.append(parts[1] + " " + parts[0])
        variants.append(parts[1])
        if len(parts) >= 3:
            variants.append(parts[1] + " " + parts[0] + " " + " ".join(parts[2:]))
    return " | ".join(variants)


def make_result_chunk_text(student: dict) -> str:
    name = student["name"]
    search_names = build_name_search_text(name)
    return (
        f"Student Seat No: {student['seat_no']}\n"
        f"Student Name: {name}\n"
        f"Name Search: {search_names}\n"
        f"Semester: {student['semester']}\n"
        f"SGPI: {student.get('sgpi', '--')}\n"
        f"Total Marks: {student['marks']}\n"
        f"Overall Result: {student['result']}"
    )


def students_to_result_chunks(students: list[dict]) -> list[dict]:
    chunks = []
    for s in students:
        chunks.append(
            {
                "text": make_result_chunk_text(s),
                "subject_json": json.dumps(s),
                "semester": s.get("semester"),
                "content_type": "RESULT",
                "department": "DS",
            }
        )
    return chunks


def _normalise_result(raw: str) -> str:
    key = (raw or "").upper().replace(".", "").replace(" ", "")
    return STATUS_MAP.get(key, "UNKNOWN")


def _extract_sgpi_from_text(text: str) -> str:
    """Extract SGPI/GPA float from noisy row/block text."""
    if not text:
        return "--"

    label_match = (
        re.search(r"\bSGPI\s*[:\-]?\s*(\d+(?:\.\d+)?)\b", text, re.I)
        or re.search(r"\bGPA\s*[:\-]?\s*(\d+(?:\.\d+)?)\b", text, re.I)
    )
    if label_match:
        val = label_match.group(1)
        try:
            f = float(val)
            if 0 <= f <= 10:
                return f"{f:.2f}".rstrip("0").rstrip(".")
        except ValueError:
            pass

    # Handles OCR formats like "6 . 89" or "7,23".
    spaced = re.findall(r"\b(\d{1,2})\s*[.,]\s*(\d{1,2})\b", text)
    for a, b in reversed(spaced):
        try:
            f = float(f"{a}.{b}")
            if 0 <= f <= 10:
                return f"{f:.2f}".rstrip("0").rstrip(".")
        except ValueError:
            continue

    floats = [f for f in re.findall(r"\b(\d+\.\d{1,2})\b", text) if 0 <= float(f) <= 10]
    if floats:
        val = float(floats[-1])
        return f"{val:.2f}".rstrip("0").rstrip(".")

    return "--"


def _extract_sgpi_by_seat_from_full_text(full_text: str) -> dict[str, str]:
    """
    Build seat->SGPI map from full extracted PDF text.
    Useful for layouts where SGPI appears on a separate Grade line.
    """
    seat_to_sgpi: dict[str, str] = {}
    if not full_text:
        return seat_to_sgpi

    for m in re.finditer(r"(DS\s*\d{4})([\s\S]{0,650}?)(?=DS\s*\d{4}|\Z)", full_text, re.I):
        seat = m.group(1).replace(" ", "").upper()
        block = m.group(0)

        sgpi = _extract_sgpi_from_text(block)
        if sgpi != "--":
            seat_to_sgpi[seat] = sgpi
            continue

        # Typical pattern in your PDF: "... 6.22 P" on grade line.
        tail = re.search(r"\b(\d\.\d{1,2})\s+(?:PASS|FAIL|PF|P|F)\b", block, re.I)
        if tail:
            seat_to_sgpi[seat] = tail.group(1)

    return seat_to_sgpi


def parse_result_fixed_coords(pdf_data: bytes, semester: str) -> list[dict]:
    students = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            for page in pdf.pages:
                words = page.extract_words(keep_blank_chars=False)
                if not words:
                    continue

                seat_positions = {}
                for w in words:
                    txt = (w.get("text") or "").strip().upper()
                    if re.match(r"^DS\d{4}$", txt):
                        seat_positions[txt] = w["top"]
                if not seat_positions:
                    continue

                for seat, seat_y in sorted(seat_positions.items(), key=lambda x: x[1]):
                    # Collect a narrow row window around seat position so we can
                    # recover total marks and SGPI even when PDF text order is noisy.
                    row_words = [
                        w for w in words
                        if abs((w.get("top") or 0) - seat_y) <= 8
                    ]
                    row_words.sort(key=lambda t: (t.get("x0") or 0))
                    row_text = " ".join((w.get("text") or "").strip() for w in row_words)

                    name_words = []
                    result_val = None
                    for w in words:
                        dy = w["top"] - seat_y
                        if -5 <= dy <= 85:
                            x = w["x0"]
                            txt_raw = (w.get("text") or "").strip()
                            txt = txt_raw.upper()

                            if x < 200 and len(txt) >= 2 and txt not in GRADE_TOKENS and re.match(r"^[A-Z]+$", txt):
                                name_words.append((w["top"], x, txt))
                            if x > 900 and txt in ("P", "F", "PF", "PASS", "FAIL"):
                                if result_val is None:
                                    result_val = txt

                    name_words.sort(key=lambda t: (t[0], t[1]))
                    name_parts = [t[2] for t in name_words if t[2] not in SKIP_NAME_TOKENS]
                    clean_name = " ".join(name_parts[:3]).strip()

                    # Numeric recovery from row text.
                    total_marks = "0"
                    total_slash = re.search(r"\b(\d{2,3})\s*/\s*750\b", row_text, re.I)
                    if total_slash:
                        total_marks = total_slash.group(1)
                    else:
                        ints = [int(n) for n in re.findall(r"\b(\d{2,3})\b", row_text)]
                        totals = [n for n in ints if 100 <= n <= 749]
                        if totals:
                            total_marks = str(totals[-1])

                    sgpi = _extract_sgpi_from_text(row_text)

                    if result_val is None:
                        result_m = re.search(r"\b(PASS|FAIL|PF|P|F)\b", row_text, re.I)
                        if result_m:
                            result_val = result_m.group(1).upper()

                    if clean_name and len(clean_name) >= 4 and result_val:
                        students.append(
                            {
                                "seat_no": seat,
                                "name": clean_name,
                                "semester": semester,
                                "marks": total_marks,
                                "sgpi": sgpi,
                                "result": _normalise_result(result_val),
                            }
                        )

        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf2:
            full_text = "\n".join(p.extract_text() or "" for p in pdf2.pages)

        seat_to_total = {}
        for seat_raw, nums_str in re.findall(r"(DS\s*\d{4})\s+MarksO\s+([\d\sAB]+)", full_text, re.I):
            seat = seat_raw.replace(" ", "").upper()
            nums = re.findall(r"\d+", nums_str)
            totals = [n for n in nums if len(n) == 3 and 100 <= int(n) <= 750]
            if totals:
                seat_to_total[seat] = totals[-1]
        seat_to_sgpi = _extract_sgpi_by_seat_from_full_text(full_text)

        for s in students:
            if s.get("marks") in ("", "0", None):
                s["marks"] = seat_to_total.get(s["seat_no"], "0")
            if s.get("sgpi") in ("", "--", None):
                s["sgpi"] = seat_to_sgpi.get(s["seat_no"], "--")

        logger.info(f"[ResultExtractor] Fixed parser extracted {len(students)} students")
        return students
    except Exception as e:
        logger.error(f"[ResultExtractor] Fixed parser error: {e}")
        return []


def parse_result_from_tables(pdf_data: bytes, semester: str, min_students: int = 5) -> list[dict]:
    students = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            all_rows = []
            header = None
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    for i, row in enumerate(table):
                        row_text = " ".join(str(cell or "").strip() for cell in row)
                        if re.search(r"(Seat\s+No|PRN|Roll\s+No|Name\s+of\s+Student)", row_text, re.I):
                            header = row
                            all_rows.extend(table[i + 1 :])
                            break
                    else:
                        header = table[0]
                        all_rows.extend(table[1:])

            if all_rows:
                for row in all_rows:
                    row_str = " ".join(str(cell or "").strip() for cell in row)
                    seat_m = re.search(r"(DS\d{4})", row_str, re.I)
                    if not seat_m:
                        continue
                    seat_no = seat_m.group(1).upper()

                    name_idx = None
                    if header:
                        for idx, cell in enumerate(header):
                            if cell and re.search(r"Name", str(cell), re.I):
                                name_idx = idx
                                break

                    if name_idx is not None and name_idx < len(row):
                        raw_name = str(row[name_idx] or "").strip()
                    else:
                        raw_name_match = re.search(
                            r"DS\d{4}\s+([A-Z][A-Z\s]+?)(?=\s+(?:[A-Z]{1,2}\+?|\d|PASS|FAIL|$))",
                            row_str,
                            re.I,
                        )
                        if raw_name_match:
                            raw_name = raw_name_match.group(1).strip()
                        else:
                            raw_name = str(row[1] or "").strip() if len(row) > 1 else ""

                    name = clean_student_name(raw_name)
                    if not _is_valid_student_name(name):
                        raw_name_match = re.search(
                            r"DS\d{4}\s+([A-Z][A-Z\s]{3,}?)\s+(?:[A-Z]{1,2}\+?|\d|PASS|FAIL|PF|P|F)\b",
                            row_str,
                            re.I,
                        )
                        if raw_name_match:
                            name = clean_student_name(raw_name_match.group(1))
                        if not _is_valid_student_name(name):
                            continue

                    result_raw = ""
                    for cell in row:
                        cell_upper = str(cell or "").strip().upper()
                        if cell_upper in ("P", "F", "PF", "PASS", "FAIL"):
                            result_raw = cell_upper
                            break
                    if not result_raw:
                        result_match = re.search(r"\b(PASS|FAIL|PF|P|F)\b", row_str, re.I)
                        result_raw = result_match.group(1).upper() if result_match else "UNKNOWN"

                    total_marks = "0"
                    total_slash = re.search(r"\b(\d{2,3})\s*/\s*750\b", row_str, re.I)
                    if total_slash:
                        total_marks = total_slash.group(1)
                    else:
                        totals = [int(n) for n in re.findall(r"\b(\d{2,3})\b", row_str)]
                        # Prefer obtained totals over fixed denominator like 750.
                        obtained = [n for n in totals if 100 <= n <= 749]
                        if obtained:
                            total_marks = str(obtained[-1])
                        elif totals:
                            total_marks = str(totals[-1])

                    sgpi = _extract_sgpi_from_text(row_str)

                    students.append(
                        {
                            "seat_no": seat_no,
                            "name": name,
                            "semester": semester,
                            "marks": total_marks,
                            "sgpi": sgpi,
                            "result": _normalise_result(result_raw),
                        }
                    )

        if students:
            try:
                with pdfplumber.open(io.BytesIO(pdf_data)) as pdf2:
                    full_text = "\n".join(p.extract_text() or "" for p in pdf2.pages)
                seat_to_sgpi = _extract_sgpi_by_seat_from_full_text(full_text)
                for s in students:
                    if s.get("sgpi") in ("", "--", None):
                        s["sgpi"] = seat_to_sgpi.get(s["seat_no"], "--")
            except Exception:
                pass

        if len(students) >= min_students:
            logger.info(f"[ResultExtractor] Table parser extracted {len(students)} students")
            return students
    except Exception as e:
        logger.error(f"[ResultExtractor] Table parser error: {e}")

    return parse_result_fixed_coords(pdf_data, semester)


def parse_result_from_text_blocks(text: str, semester: str) -> list[dict]:
    students = []
    for block in re.split(r"(?=DS\s*\d{4})", text):
        block = block.strip()
        if not block:
            continue

        seat_m = re.search(r"(DS\s*\d{4})", block, re.I)
        if not seat_m:
            continue
        seat_no = seat_m.group(1).replace(" ", "").upper()

        total_m = (
            re.search(r"\b(\d{2,3})\s*/\s*750\b", block, re.I)
            or re.search(r"Total\s*Marks?\s*[:\-]?\s*(\d{2,3})\b", block, re.I)
            or re.search(r"(\d{3})\s*\n\s*Grade", block, re.I)
            or re.search(r"Total[:\s]+(\d{3})", block, re.I)
            or re.search(r"(\d{3})(?=\s*$)", block, re.MULTILINE)
        )
        total_marks = total_m.group(1) if total_m else "0"
        sgpi = _extract_sgpi_from_text(block)

        name_m = (
            re.search(r"([A-Z][A-Z\s]{3,}?)\s*-{1,2}\s*(PASS|FAIL|PF|P|F)\b", block, re.I)
            or re.search(r"\n([A-Z][A-Z\s]{3,}?)\n\s*(PASS|FAIL|PF|P|F)\b", block, re.I)
        )
        result_only = re.search(r"Result\s*[:\-]\s*(PASS|FAIL|PASS WITH FAIL|PF|P|F)\b", block, re.I)

        if name_m:
            student_name = clean_student_name(name_m.group(1))
            result_raw = name_m.group(2).upper()
        else:
            nl = re.search(r"DS\s*\d{4}\s*\n([A-Z][A-Z\s]{3,})", block, re.I)
            student_name = clean_student_name(nl.group(1)) if nl else ""
            result_raw = result_only.group(1).upper() if result_only else "UNKNOWN"

        if not _is_valid_student_name(student_name):
            continue

        students.append(
            {
                "seat_no": seat_no,
                "name": student_name,
                "semester": semester,
                "marks": total_marks,
                "sgpi": sgpi,
                "result": _normalise_result(result_raw),
            }
        )
    return students


def parse_result_document(
    text: str,
    pdf_data: Optional[bytes] = None,
    semester: Optional[str] = None,
    min_students: int = 5,
) -> list[dict]:
    sem = semester or detect_semester_from_text(text)

    if pdf_data:
        # KT/ATKT result files can legitimately have a small number of students.
        # Accept any non-empty structured parse instead of forcing a high threshold.
        students = parse_result_from_tables(pdf_data, sem, min_students=1)
        if students:
            return students

    students = parse_result_from_text_blocks(text, sem)
    return students
