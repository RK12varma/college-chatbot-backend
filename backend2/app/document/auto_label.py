import re


# ─── Department patterns ──────────────────────────────────────────────────────
DEPT_PATTERNS = {
    "DS":    [
        r"data[\s\-_]?science", r"cse[\s\-_]?ds",
        r"cse\-data", r"cse_data",
        r"\bds[\s\-_]",          # DS_ or DS- prefix (e.g. DS_Internship, DS-Toppers)
        r"[\s\-_]ds[\s\-_]",     # _DS_ in middle
        r"[\s\-_]ds\d",          # DS followed by year/number
        r"^ds[\s\-_]",           # starts with DS
    ],
    "CE":    [
        r"computer[\s\-_]?eng(ineering)?",
        r"comp[\s\-_]?eng",
        r"cse(?![\s\-_]ds|[\s\-_]data)",
    ],
    "MECH":  [r"mechanical", r"\bmech\b"],
    "CIVIL": [r"\bcivil\b"],
    "EXTC":  [
        r"\bextc\b", r"electronics[\s\-_]?(and[\s\-_]?telecom)?",
        r"telecommunication",
    ],
    "IT":    [
        r"information[\s\-_]?tech(nology)?",
        r"\bit[\s\-_]?(dept|engineering|department)\b",
    ],
    "MBA":   [r"\bmba\b", r"\bmanagement\b"],
    "MCA":   [r"\bmca\b"],
}


# ─── Content type patterns ────────────────────────────────────────────────────
CONTENT_PATTERNS = {
    "FACULTY":   [
        r"faculty", r"professor", r"staff[\s\-_]?list",
        r"teaching[\s\-_]?staff", r"our[\s\-_]?team", r"hod",
    ],
    "RESULT":    [
        r"result", r"gazette", r"marksheet", r"mark[\s\-_]?list",
        r"c[\s\-_]?scheme[\s\-_]?reg",
        r"scheme.*reg.*\d{4}",
        r"reg.*nov|reg.*may|reg.*apr",
    ],
    "SYLLABUS":  [
        r"syllabus", r"curriculum",
        r"course[\s\-_]?structure", r"course[\s\-_]?outline",
    ],
    "NEWSLETTER": [
        r"news[\s\-_]?letter", r"newsletter", r"magazine",
        r"e[\s\-_]?magazine",
    ],
    "NOTICE":    [
        r"notice", r"circular", r"announcement",
        r"time[\s\-_]?table", r"timetable", r"schedule",
        r"exam[\s\-_]?form", r"hall[\s\-_]?ticket", r"news",
    ],
    "FEE":       [
        r"fee[\s\-_]?(structure|detail)?", r"tuition", r"scholarship",
        r"payment",
    ],
    "NIRF":      [r"nirf", r"naac", r"accreditation", r"\bnba\b", r"ranking"],
    "ADMISSION": [r"admission", r"eligibility", r"apply[\s\-_]?now"],
    "PLACEMENT": [r"placement", r"recruit", r"campus[\s\-_]?drive", r"package"],
    "TOPPER":    [
        r"topper", r"top[\s\-_]?student", r"merit[\s\-_]?list",
        r"rank[\s\-_]?list", r"gold[\s\-_]?medal",
    ],
    "INTERNSHIP": [
        r"internship", r"intern[\s\-_]?report", r"industrial[\s\-_]?training",
        r"project[\s\-_]?report",
    ],
    "COURSE":    [
        r"course[\s\-_]?detail", r"course[\s\-_]?info",
        r"\bb\.?e\.?\b", r"\bb\.?tech\b", r"program[\s\-_]?(detail|overview)",
    ],
    "ABOUT":     [
        r"about[\s\-_]?(us|department|college)?",
        r"overview", r"vision[\s\-_]?mission", r"history",
        r"infrastructure", r"facilities",
    ],
    "LAB":       [r"\blab\b", r"laboratory", r"workshop"],
    "RESEARCH":  [r"research", r"publication", r"journal", r"paper"],
    "ACTIVITY":  [
        r"activity", r"activities", r"event", r"club",
        r"cultural", r"sports", r"fest", r"seminar", r"workshop",
        r"webinar",
    ],
}


# ─── Semester detection ───────────────────────────────────────────────────────
SEM_PATTERN = re.compile(
    r"sem(?:ester)?[\s\-_]*(viii|vii|vi(?!i)|v(?!i)|iv|iii|ii(?!i)|i(?!i|v)|[1-8])",
    re.IGNORECASE
)

ROMAN_TO_NUM = {
    "i": "I", "ii": "II", "iii": "III", "iv": "IV",
    "v": "V", "vi": "VI", "vii": "VII", "viii": "VIII",
    "1": "I", "2": "II", "3": "III", "4": "IV",
    "5": "V", "6": "VI", "7": "VII", "8": "VIII",
}

# ─── Display names ────────────────────────────────────────────────────────────
DEPT_DISPLAY = {
    "DS":    "Data Science",
    "CE":    "Computer Engineering",
    "MECH":  "Mechanical Engineering",
    "CIVIL": "Civil Engineering",
    "EXTC":  "EXTC",
    "IT":    "Information Technology",
    "MBA":   "MBA",
    "MCA":   "MCA",
    "GEN":   "College",
}

TYPE_DISPLAY = {
    "FACULTY":    "Faculty",
    "RESULT":     "Result",
    "SYLLABUS":   "Syllabus",
    "NOTICE":     "Notice",
    "FEE":        "Fee Structure",
    "NIRF":       "NIRF / Accreditation",
    "ADMISSION":  "Admission",
    "PLACEMENT":  "Placements",
    "TOPPER":     "Toppers List",
    "INTERNSHIP": "Internship",
    "NEWSLETTER": "Newsletter",
    "COURSE":     "Course Details",
    "ABOUT":      "About",
    "LAB":        "Laboratories",
    "RESEARCH":   "Research",
    "ACTIVITY":   "Activities & Events",
    "GENERAL":    "Information",
}


def _detect_dept(text: str) -> str:
    for dept, patterns in DEPT_PATTERNS.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            return dept
    return "GEN"


def _detect_content_type(text: str) -> str:
    for ctype, patterns in CONTENT_PATTERNS.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            return ctype
    return "GENERAL"


def _detect_semester(text: str) -> str | None:
    m = SEM_PATTERN.search(text)
    if m:
        raw = m.group(1).lower()
        return "SEM-" + ROMAN_TO_NUM.get(raw, raw.upper())
    return None


def auto_label(filename: str, source_url: str = "") -> dict:
    """
    Automatically detect source_label, dept_tag, content_type and semester
    for any document filename or URL.

    Examples:
        auto_label("DS-Toppers-List22-23.pdf")
        → {"source_label": "Data Science - Toppers List", "dept_tag": "DS", ...}

        auto_label("DS_Internship_5.pdf")
        → {"source_label": "Data Science - Internship", "dept_tag": "DS", ...}

        auto_label("News-Letter-For-CSE-DS.pdf")
        → {"source_label": "Data Science - Newsletter", "dept_tag": "DS", ...}
    """
    combined = (filename + " " + (source_url or "")).strip()

    dept         = _detect_dept(combined)
    content_type = _detect_content_type(combined)
    semester     = _detect_semester(combined)

    dept_name = DEPT_DISPLAY.get(dept, dept)
    type_name = TYPE_DISPLAY.get(content_type, content_type.title())

    if semester and content_type == "RESULT":
        label = f"{dept_name} - Result {semester}"
    else:
        label = f"{dept_name} - {type_name}"

    return {
        "source_label": label,
        "dept_tag":     dept,
        "content_type": content_type,
        "semester":     semester,
    }