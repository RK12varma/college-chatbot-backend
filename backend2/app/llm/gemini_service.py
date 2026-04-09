"""
gemini_service.py â€” Enhanced LLM Service with Data Science Focus
"""
import re
import time
from groq import Groq
from app.config import settings
from app.logger import logger

client = Groq(api_key=settings.GROQ_API_KEY)

MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
]

# Keep retries short to avoid very slow fallback responses during provider throttling.
LLM_MAX_ATTEMPTS_PER_MODEL = 2
LLM_RATE_LIMIT_BACKOFF_SECONDS = [2, 4]

SYSTEM_PROMPT = """You are CollegeAI â€” an intelligent assistant for the **Department of Data Science** at Saraswati College of Engineering, Kharghar, Navi Mumbai.

## Your Department: Data Science (DS)
You only answer questions related to the Data Science department. If a user asks about other departments (CE, MECH, CIVIL, EXTC, IT), politely redirect them.

## Your Expertise:
- **Data Science Results**: SEM-III to SEM-VIII results for DS students (seat numbers starting with DS)
- **DS Faculty**: Information about Data Science professors and HOD
- **DS Syllabus**: Course structure, subjects, and curriculum
- **DS Question Papers**: Previous year papers for DS courses
- **DS Placements**: Placement statistics for Data Science students
- **DS Projects**: Mini projects, major projects, and internships
- **DS Events**: Department events, workshops, and guest lectures

## Department Faculty Information:
- **HOD**: Dr. [Name] - Head of Data Science Department
- **Core Faculty**: Specializing in Machine Learning, AI, Big Data, Python, Statistics, Deep Learning

## Response Guidelines:
- Always focus on Data Science department only
- If asked about other departments: "I'm specialized in Data Science. Please contact the respective department office for information about [other department]."
- Use DS-specific terminology (Python, Machine Learning, Data Analytics, Big Data, AI)
- Show results only for DS students (seat numbers starting with DS)
- Never hallucinate information not in context

## Formatting:
- Use tables for result data
- Include emojis for visual cues (ðŸ“Š, ðŸ“ˆ, ðŸ for Python, ðŸ¤– for AI/ML)
- Always mention that you're from the Data Science department

Current date: {current_date}
"""


def _is_result_query(question: str) -> bool:
    """Check if query is about results"""
    keywords = ["result", "marks", "sgpi", "pass", "fail", "total marks", "exam result"]
    return any(k in question.lower() for k in keywords)


def _is_syllabus_query(question: str) -> bool:
    """Check if query is about syllabus/subjects."""
    q = question.lower()
    keywords = [
        "syllabus", "curriculum", "subject", "subjects", "course", "courses",
        "teaching scheme", "module", "semester",
    ]
    return any(k in q for k in keywords)


def _extract_subjects_from_context(context: str, question: str = "") -> list[dict]:
    """
    Extract subject code/name pairs from syllabus text blocks.
    Handles both clean rows and OCR-flattened rows.
    """
    subjects = []
    seen = set()
    requested_sem = _extract_semester_from_query(question) if question else None
    current_sem = None
    # Support both compact codes (CSC701) and spaced codes (CSDO 701X).
    code_re = re.compile(r"\b([A-Z]{2,8}\s*\d{3}[A-Z]?)\b")

    def _clean_name(raw_name: str) -> str:
        name = " ".join((raw_name or "").replace("â€”", "-").replace("–", "-").split())
        if not name:
            return ""
        name = name.replace("#", "")
        name = re.sub(r"^[^A-Za-z0-9]+", "", name)
        name = re.split(
            r"\b(Teaching Scheme|Credits?|Theory|Pract|Practical|Tut|Total|Assessment|ESE|IA|TW|PR|OR)\b",
            name,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" -:|,")
        name = re.split(r"\s{2,}\d{1,3}(?:\s+\d{1,3}){1,}", name, maxsplit=1)[0].strip()

        # Remove numeric grading tails like: "Deep Learning 3 -- 3 -- 3"
        tokens = name.split()
        if tokens:
            cut_idx = None
            for i, tok in enumerate(tokens):
                if re.match(r"^(?:\d+(?:\.\d+)?|--+|[-/]+)$", tok):
                    tail = tokens[i:]
                    numeric_like = sum(
                        1 for t in tail
                        if re.match(r"^(?:\d+(?:\.\d+)?|--+|[-/]+|[A-Z]{1,2}\+?)$", t)
                    )
                    if tail and (numeric_like / len(tail)) >= 0.6:
                        cut_idx = i
                        break
            if cut_idx is not None:
                tokens = tokens[:cut_idx]
            name = " ".join(tokens).strip(" -:|,")

        # Drop obviously invalid extracted names.
        if not name or len(name) < 3:
            return ""
        if re.fullmatch(r"[\d\W_]+", name):
            return ""
        # If there are standalone long digit tokens left, treat as noisy row.
        if any(re.fullmatch(r"\d{2,}", t) for t in name.split()):
            return ""
        return name

    for raw in context.splitlines():
        line = " ".join((raw or "").split())
        if len(line) < 6:
            continue

        # Track semester sections while scanning syllabus text.
        line_sem = _extract_semester_from_query(line)
        if line_sem:
            current_sem = line_sem

        # If a semester is requested and we are currently inside another semester
        # section, skip extraction for this line.
        if requested_sem and current_sem and current_sem != requested_sem:
            continue

        matches = list(code_re.finditer(line))
        if not matches:
            continue

        for i, m in enumerate(matches):
            code = re.sub(r"\s+", "", m.group(1).upper().strip())
            end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
            seg = line[m.end():end].strip(" -:|,")
            if not seg:
                continue
            name = _clean_name(seg)
            if not name:
                continue
            if any(x in name.lower() for x in ["student name", "seat no", "overall result"]):
                continue

            key = f"{code}|{name.lower()}"
            if key in seen:
                continue
            seen.add(key)
            subjects.append({"code": code, "name": name})

    # Fallback refinement for noisy documents where semester headings are weak.
    # Restrict this to explicit VII/VIII queries only.
    if requested_sem and subjects:
        expected_hundreds = {"SEM-VII": "7", "SEM-VIII": "8"}
        exp = expected_hundreds.get(requested_sem)
        if exp:
            filtered = []
            for s in subjects:
                m = re.search(r"(\d{3})", s.get("code", ""))
                if m and m.group(1).startswith(exp):
                    filtered.append(s)
            if filtered:
                subjects = filtered

    return subjects


def _extract_syllabus_semesters_from_context(context: str) -> list[str]:
    sems = set()
    sem_map = {
        "1": "SEM-I", "I": "SEM-I",
        "2": "SEM-II", "II": "SEM-II",
        "3": "SEM-III", "III": "SEM-III",
        "4": "SEM-IV", "IV": "SEM-IV",
        "5": "SEM-V", "V": "SEM-V",
        "6": "SEM-VI", "VI": "SEM-VI",
        "7": "SEM-VII", "VII": "SEM-VII",
        "8": "SEM-VIII", "VIII": "SEM-VIII",
    }
    order = ["SEM-I", "SEM-II", "SEM-III", "SEM-IV", "SEM-V", "SEM-VI", "SEM-VII", "SEM-VIII"]

    for m in re.finditer(r"\bSEM(?:ESTER)?\s*[-:]?\s*(I{1,3}V?|IV|V?I{0,3}|[1-8])\b", context, re.I):
        token = m.group(1).upper()
        sem = sem_map.get(token)
        if sem:
            sems.add(sem)
    return sorted(sems, key=lambda s: order.index(s) if s in order else 99)

def _build_syllabus_subject_answer(subjects: list[dict], question: str) -> str | None:
    """Build subject-only syllabus answer from extracted items."""
    if not subjects:
        return None
    # For syllabus answers, always return only course names (no subject codes).
    unique_names = []
    seen = set()
    for s in subjects:
        name = (s.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_names.append(name)

    rows = []
    for i, name in enumerate(unique_names[:25], 1):
        rows.append(f"{i}. {name}")

    return "\U0001F4DA **Data Science Syllabus Subjects**\n\n" + "\n".join(rows)


def _extract_student(context: str) -> list[dict]:
    """Extract student data from context chunks"""
    students = []
    seen_keys = set()
    
    for block in re.split(r"(?=Student Seat No:)", context):
        if "Student Seat No:" not in block:
            continue
        
        def get(field):
            m = re.search(rf"{field}:\s*(.+)", block)
            return m.group(1).strip() if m else ""
        
        s = {
            "seat": get("Student Seat No"),
            "name": get("Student Name"),
            "search_names": get("Name Search"),
            "sem": get("Semester"),
            "sgpi": get("SGPI"),
            "marks": get("Total Marks"),
            "result": get("Overall Result"),
        }
        
        # Only include DS students (seat numbers start with DS)
        if s["name"] and s["result"] and s["seat"] and s["seat"].startswith("DS"):
            s["sgpi"] = s["sgpi"] if s["sgpi"] and s["sgpi"] != "--" else "N/A"
            # Deduplicate repeated rows coming from overlapping chunks/documents.
            dedupe_key = (
                s["seat"].strip().upper(),
                (s["sem"] or "").strip().upper(),
                (s["marks"] or "").strip(),
                (s["result"] or "").strip().upper(),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            students.append(s)
    
    return students


def _matches_name(student_name: str, search_names: str, query: str) -> bool:
    """Enhanced name matching using Name Search field"""
    q_lower = query.lower()
    
    stopwords = {"result", "marks", "sem", "semester", "show", "get", "what", 
                 "the", "his", "her", "their", "my", "give", "tell", "find",
                 "for", "of", "in", "on", "at", "by", "to", "from",
                 "data", "science", "department", "student", "students", "ds"}
    
    query_words = [w for w in q_lower.split() if w not in stopwords and len(w) >= 3]
    
    if not query_words:
        return True
    
    haystack = f"{student_name} {search_names}".lower().strip()
    if not haystack:
        return False

    # Exact multi-word phrase match first (e.g., "rahul varma")
    if len(query_words) >= 2:
        full_query = " ".join(query_words)
        if full_query in haystack:
            return True

    # For multi-word names, require all tokens to appear somewhere in the name fields.
    # This avoids broad matches like "rahul" matching many students.
    matched_count = sum(1 for w in query_words if w in haystack)
    if len(query_words) >= 2:
        return matched_count == len(query_words)

    # Single-token fallback
    return matched_count >= 1


def _result_icon(result: str) -> str:
    """Get result icon"""
    r = result.upper()
    if "WITH FAIL" in r:
        return "\u26A0\uFE0F PASS WITH FAIL"
    if r == "PASS":
        return "\u2705 PASS"
    if r == "FAIL":
        return "\u274C FAIL"
    return result


def _extract_semester_from_query(question: str) -> str | None:
    """Parse semester reference from query (roman or numeric) into SEM-* form."""
    q = (question or "").lower()
    m = re.search(
        r"\b(?:sem(?:ester)?\s*[-:]?\s*(viii|vii|vi|v|iv|iii|ii|i|[1-8])|([1-8])(?:st|nd|rd|th)?\s*sem(?:ester)?)\b",
        q,
        re.I,
    )
    if not m:
        return None
    token = (m.group(1) or m.group(2) or "").lower()
    sem_map = {
        "1": "SEM-I", "i": "SEM-I",
        "2": "SEM-II", "ii": "SEM-II",
        "3": "SEM-III", "iii": "SEM-III",
        "4": "SEM-IV", "iv": "SEM-IV",
        "5": "SEM-V", "v": "SEM-V",
        "6": "SEM-VI", "vi": "SEM-VI",
        "7": "SEM-VII", "vii": "SEM-VII",
        "8": "SEM-VIII", "viii": "SEM-VIII",
    }
    return sem_map.get(token)


def _build_result_table(students: list[dict], question: str) -> str | None:
    """Build formatted result table with DS focus"""
    if not students:
        return None
    
    q_lower = question.lower()
    
    requested_sem = _extract_semester_from_query(question)

    # Match students by name
    matched = []
    for s in students:
        if _matches_name(s["name"], s.get("search_names", ""), question):
            matched.append(s)
    
    # Match by seat number
    if not matched:
        seat_match = re.search(r"DS\d{4}", q_lower.upper())
        if seat_match:
            seat = seat_match.group(0)
            for s in students:
                if s["seat"] == seat:
                    matched = [s]
                    break
    
    if not matched:
        logger.info(f"[ResultParser] No matches for '{question}'")
        return None

    # Final safety dedupe at render stage.
    deduped = []
    seen = set()
    for s in matched:
        k = (
            (s.get("seat") or "").strip().upper(),
            (s.get("sem") or "").strip().upper(),
            (s.get("marks") or "").strip(),
            (s.get("result") or "").strip().upper(),
        )
        if k in seen:
            continue
        seen.add(k)
        deduped.append(s)
    matched = deduped

    # If user asked for a specific semester, enforce it.
    if requested_sem:
        sem_filtered = [s for s in matched if (s.get("sem") or "").upper() == requested_sem]
        if sem_filtered:
            matched = sem_filtered

    # Single student result
    if len(matched) == 1:
        s = matched[0]
        return (
            f"\U0001F4CA **Student Result (Data Science)**\n\n"
            f"| Field | Details |\n"
            f"|---|---|\n"
            f"| **Name** | {s['name']} |\n"
            f"| **Seat No** | {s['seat']} |\n"
            f"| **Semester** | {s['sem']} |\n"
            f"| **Total Marks** | {s['marks']} / 750 |\n"
            f"| **SGPI** | {s['sgpi']} |\n"
            f"| **Result** | {_result_icon(s['result'])} |"
        )
    
    # Multiple students (for department queries)
    semester = matched[0]["sem"] if matched else "DS"
    
    rows = "\n".join(
        f"| {s['seat']} | {s['name']} | {s['sem']} "
        f"| {s['marks']} / 750 | {s['sgpi']} | {_result_icon(s['result'])} |"
        for s in matched[:20]
    )
    
    return (
        f"\U0001F4CA **Data Science Student Results ({semester})**\n\n"
        f"| Seat No | Name | Semester | Total Marks | SGPI | Result |\n"
        f"|---|---|---|---|---|---|\n"
        f"{rows}"
    )


def _call_llm(prompt: str) -> str:
    """Call Groq LLM with retry logic"""
    for model in MODELS:
        for attempt in range(LLM_MAX_ATTEMPTS_PER_MODEL):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    temperature=0.3,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "rate" in err or "quota" in err:
                    if attempt < (LLM_MAX_ATTEMPTS_PER_MODEL - 1):
                        wait = (
                            LLM_RATE_LIMIT_BACKOFF_SECONDS[attempt]
                            if attempt < len(LLM_RATE_LIMIT_BACKOFF_SECONDS)
                            else LLM_RATE_LIMIT_BACKOFF_SECONDS[-1]
                        )
                        logger.warning(f"Rate limit on {model}. Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    logger.warning(f"{model} exhausted. Trying next model...")
                    break
                logger.error(f"Groq error on {model}: {e}")
                return "âš ï¸ AI service error. Please try again."
    return "âš ï¸ AI service is temporarily busy. Please try again in a moment."


def generate_answer(question: str, context: str) -> str:
    """Generate answer using LLM with DS focus"""
    from datetime import datetime
    
    # For result queries â€” build table directly
    if _is_result_query(question):
        students = _extract_student(context)
        
        if students:
            logger.info(f"[ResultParser] Found {len(students)} DS students in context")
            result = _build_result_table(students, question)
            if result:
                return result
        
        return "I couldn't find that student's result in the Data Science department records. Please check the name spelling or seat number (should start with DS)."

    # For syllabus queries â€” extract subject list directly from context (no hallucination).
    if _is_syllabus_query(question):
        subjects = _extract_subjects_from_context(context, question=question)
        if subjects:
            ans = _build_syllabus_subject_answer(subjects, question)
            if ans:
                return ans
        requested_sem = _extract_semester_from_query(question)
        available_sems = _extract_syllabus_semesters_from_context(context)
        if requested_sem and available_sems:
            return (
                f"I couldn't find syllabus subjects for **{requested_sem}** in available Data Science syllabus documents. "
                f"Available semesters are: {', '.join(available_sems)}."
            )
        return "I couldn't find syllabus subject names in the available Data Science documents. Please upload/reindex the correct syllabus PDF."

    # For all other queries â€” use LLM
    prompt = f"""{SYSTEM_PROMPT.format(current_date=datetime.now().strftime("%Y-%m-%d"))}

---CONTEXT (Data Science department documents)---
{context}

---STUDENT QUESTION---
{question}

---YOUR ANSWER (focus on Data Science)---"""

    return _call_llm(prompt)


