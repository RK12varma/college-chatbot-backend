"""
app/config.py — Application Configuration (Data Science Department Focus)
"""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ─── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "CollegeAI Backend - Data Science Department"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # ─── Department Configuration (Data Science Focus) ────────────────────────
    DEPARTMENT: str = "DS"  # Data Science department only
    DEPARTMENT_NAME: str = "Data Science"
    DEPARTMENT_FULL_NAME: str = "Department of Data Science"
    FILTER_BY_DEPARTMENT: bool = True  # Only show DS documents
    
    # ─── College Information ──────────────────────────────────────────────────
    COLLEGE_NAME: str = os.getenv("COLLEGE_NAME", "Saraswati College of Engineering")
    COLLEGE_LOCATION: str = os.getenv("COLLEGE_LOCATION", "Kharghar, Navi Mumbai")
    COLLEGE_WEBSITE_URL: str = os.getenv("COLLEGE_WEBSITE_URL", "https://www.scoe.edu.in")
    
    # ─── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # ─── Auth / JWT ───────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change_me_in_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

    # ─── Admin ────────────────────────────────────────────────────────────────
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "")

    # ─── Email ────────────────────────────────────────────────────────────────
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")

    # ─── AI / LLM ─────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # ─── Web Search ───────────────────────────────────────────────────────────
    ENABLE_WEB_SEARCH: bool = os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true"
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
    BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")

    # ─── Upload ───────────────────────────────────────────────────────────────
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "data")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", 50))

    # ─── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    def __init__(self):
        if os.getenv("FRONTEND_URL"):
            self.ALLOWED_ORIGINS.append(os.getenv("FRONTEND_URL"))
        
        # Create upload directory if it doesn't exist
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(os.path.join(self.UPLOAD_DIR, "pdfs"), exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# ─── Legacy aliases ───────────────────────────────────────────────────────────
DATABASE_URL = settings.DATABASE_URL
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES