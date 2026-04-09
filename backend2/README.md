# CollegeAI Backend (Data Science Department)

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/your-repo/ci.yml?branch=main)
![License](https://img.shields.io/github/license/your-repo/license)

## 📖 Overview

**CollegeAI** is an AI‑powered backend for a college information chatbot, tailored for the **Data Science** department. It provides:
- Secure authentication with JWT (access & refresh tokens).
- Document ingestion, OCR, and semantic search powered by FAISS.
- Automated scraping of departmental resources.
- Rich API for chat sessions, document management, and admin operations.
- Robust logging, health checks, and extensible architecture.

The project follows modern FastAPI best‑practices, uses Pydantic settings, and is container‑ready.

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Backend[FastAPI Backend]
        direction TB
        Config[Config & Settings]
        DB[Database (SQLAlchemy)]
        Auth[Auth Router]
        Document[Document Router]
        Chat[Chat Router]
        Admin[Admin Router]
        Scheduler[Scheduler Service]
        OCR[OCR & PDF Processing]
        FAISS[FAISS Vector Store]
    end
    subgraph Frontend[Frontend (React/Vite)]
        UI[User Interface]
    end
    Config --> DB
    Auth --> DB
    Document --> DB
    Chat --> DB
    Admin --> DB
    OCR --> FAISS
    FAISS --> DB
    UI --> Backend
```

---

## ✨ Features

- **Centralised configuration** via `app/config.py` (`Settings` class).
- **Structured logging** (`app/logger.py`).
- **JWT authentication** with refresh tokens.
- **Document pipeline**:
  - OCR (Tesseract + EasyOCR fallback).
  - Chunking with overlap for semantic search.
  - FAISS index management (`faiss_manager.py`).
- **Auto‑labeling** of documents (`auto_label.py`).
- **Scheduler** for periodic scraping (`services/scheduler.py`).
- **Health check** endpoint.
- **Extensive API docs** at `/docs` (development) or `/redoc`.

---

## 📦 Installation

### Prerequisites

- Python **3.10+**
- **Poetry** or **pip** for dependency management
- **Tesseract OCR** (optional, for better OCR accuracy)
- **Poppler** (for PDF image conversion)
- PostgreSQL (or any SQLAlchemy‑compatible DB)

### Steps

```bash
# Clone the repository
git clone https://github.com/your-username/collegeai-backend.git
cd collegeai-backend/backend2

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example env and edit values
cp .env.example .env
# Edit .env with your DB URL, secret keys, etc.
```

### Optional OCR dependencies

```bash
# Tesseract (Windows example)
choco install tesseract
# Poppler (Windows example)
choco install poppler
```

---

## ⚙️ Environment Variables (`.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | `development` or `production` | `development` |
| `DATABASE_URL` | SQLAlchemy DB connection string | `postgresql://user:pass@localhost/dbname` |
| `SECRET_KEY` | JWT secret for access tokens | `supersecret` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `UPLOAD_DIR` | Directory for uploaded files | `data` |
| `MAX_UPLOAD_SIZE_MB` | Max upload size | `50` |
| `GROQ_API_KEY` | API key for LLM service | `xxxx` |
| `SMTP_HOST`, `SMTP_PORT`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD` | Email configuration for OTPs | – |
| `ENABLE_WEB_SEARCH` | Enable external web search (true/false) | `true` |
| `SERPAPI_KEY`, `BRAVE_API_KEY` | Keys for web‑search providers | – |

---

## ▶️ Running the Application

```bash
# Start the FastAPI server (auto‑reload in dev)
uvicorn app.main:app --reload
```

- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

---

## 📚 API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | — | Register a new user |
| `POST` | `/auth/verify-otp` | — | Verify email OTP |
| `POST` | `/auth/login` | — | Login and receive tokens |
| `POST` | `/auth/refresh` | — | Refresh access token |
| `POST` | `/auth/forgot-password` | — | Send reset OTP |
| `POST` | `/auth/reset-password` | — | Reset password with OTP |
| `POST` | `/auth/resend-otp` | — | Resend verification OTP |
| `POST` | `/chat/ask` | JWT | Ask a question |
| `GET` | `/chat/sessions` | JWT | List user chat sessions |
| `GET` | `/chat/sessions/{id}` | JWT | Get session history |
| `DELETE` | `/chat/sessions/{id}` | JWT | Delete a session |
| `GET` | `/document/list` | JWT | Browse documents |
| `POST` | `/document/upload` | Admin | Upload a file |
| `POST` | `/document/scrape` | Admin | Scrape a URL |
| `GET` | `/admin/stats` | Admin | Dashboard statistics |
| `GET` | `/admin/users` | Admin | List users (paginated) |
| `PUT` | `/admin/users/{id}/role` | Admin | Change user role |
| `PUT` | `/admin/users/{id}/status` | Admin | Activate/deactivate user |
| `DELETE` | `/admin/users/{id}` | Admin | Delete user |
| `GET` | `/admin/documents` | Admin | List all documents |
| `DELETE` | `/admin/documents/{id}` | Admin | Delete document |
| `GET` | `/admin/audit-logs` | Admin | View audit trail |
| `GET` | `/admin/sources` | Admin | List scrape sources |
| `POST` | `/admin/sources` | Admin | Add scrape source |
| `DELETE` | `/admin/sources/{id}` | Admin | Remove scrape source |
| `POST` | `/admin/scrape` | Admin | Trigger manual scrape |
| `GET` | `/health` | — | Health check |

---

## 📂 Code Overview

- `app/main.py` – FastAPI entry point, middleware, and router registration.
- `app/config.py` – Pydantic‑based settings loaded from `.env`.
- `app/logger.py` – Structured JSON logger.
- `app/auth/` – Authentication routes and JWT utilities.
- `app/document/` – Document upload, scraping, auto‑labeling (`auto_label.py`), processing (`processing.py`), and FAISS search.
- `app/chat/` – Chat session management.
- `app/admin/` – Admin dashboards and audit logs.
- `app/services/scheduler.py` – APScheduler for periodic scraping.
- `app/llm/` – LLM integration (Groq / Gemini).
- `app/models/` – SQLAlchemy ORM models (users, documents, chunks, etc.).
- `app/utils/` – Helper utilities (email, etc.).

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/awesome-feature`).
3. Write tests and ensure they pass (`pytest`).
4. Submit a Pull Request.

Please follow the existing code style (black, isort, flake8) and update documentation as needed.

---

## 📄 License

This project is licensed under the **MIT License** – see the `LICENSE` file for details.

---

*Happy coding!*
