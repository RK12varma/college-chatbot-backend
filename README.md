# CollegeAI Chatbot

CollegeAI is a full-stack college assistant focused on the Data Science department. This repository contains the React frontend and the FastAPI backend used for authentication, chat, document search, question-paper access, and admin operations.

## Repository Overview

This workspace currently contains:

- `frontend/` - React + Vite frontend
- `backend2/` - FastAPI backend
- `.env.example` - Example environment configuration

## Architecture

```text
frontend (React + Vite)
        |
        | HTTP API
        v
backend2 (FastAPI)
        |
        | Database, document indexing, OCR, scraping, LLM integration
        v
PostgreSQL / vector search / external services
```

## Main Features

- Student and admin authentication with JWT
- OTP verification and password reset flows
- Department-focused AI chatbot interface
- Persistent chat sessions
- PDF and document search support
- Admin dashboard for:
  - Document upload and indexing
  - URL scraping
  - User management
  - Audit logs
  - System statistics
- Optional web search support through backend providers

## Tech Stack

### Frontend

- React 19
- Vite 5
- React Router
- Axios
- Tailwind CSS

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL-compatible database
- FAISS for semantic search
- OCR and scraping utilities
- LLM integration through configured providers

## Project Structure

```text
sem6/
|-- frontend/        React frontend application
|-- backend2/        FastAPI backend application
|-- .env.example     Shared example environment file
|-- .gitignore
`-- README.md
```

## Quick Start

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd sem6
```

### 2. Configure environment variables

Use the root example file as a reference:

```bash
cp .env.example backend2/.env
```

On Windows PowerShell, you can use:

```powershell
Copy-Item .env.example backend2/.env
```

Then update the values in `backend2/.env` for your machine, especially:

- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_SECRET_KEY`
- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `GROQ_API_KEY` or other LLM-related keys
- `SERPAPI_KEY` and `BRAVE_API_KEY` if web search is enabled

### 3. Start the backend

```bash
cd backend2
python -m venv venv
```

Activate the environment:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the backend server:

```bash
uvicorn app.main:app --reload
```

The backend usually runs at:

```text
http://127.0.0.1:8000
```

### 4. Start the frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend usually runs at:

```text
http://localhost:5173
```

## Important Setup Note

The root `.env.example` includes a `VITE_API_URL` variable, but the current frontend code still uses a hardcoded API base URL in `frontend/src/services/api.js`.

Right now, the frontend expects the backend at:

```text
http://127.0.0.1:8000
```

If your backend is running elsewhere, update `frontend/src/services/api.js` before starting the frontend.

## Running Each Part Separately

### Frontend only

See `frontend/README.md` for frontend routes, scripts, and UI details.

### Backend only

See `backend2/README.md` for backend endpoints, services, and deployment notes.

## Typical Local Development Flow

1. Configure `backend2/.env`.
2. Start the backend with `uvicorn app.main:app --reload` from `backend2`.
3. Start the frontend with `npm run dev` from `frontend`.
4. Open `http://localhost:5173`.
5. Register a user or log in.
6. Use an admin account to access `/admin`.

## Useful Paths

- Frontend entry: `frontend/src/main.jsx`
- Frontend routes: `frontend/src/App.jsx`
- Frontend API client: `frontend/src/services/api.js`
- Backend entry: `backend2/app/main.py`
- Backend config: `backend2/app/config.py`

## Common Requirements

- Node.js 18+
- npm
- Python 3.10+
- A configured database
- API keys and email settings required by the backend

## Documentation Notes

This root README is meant to help new contributors understand the full project quickly. More detailed instructions live in the service-specific READMEs:

- `frontend/README.md`
- `backend2/README.md`

## Future Improvements

- Move the frontend API URL fully to `VITE_API_URL`
- Add database setup and migration instructions
- Add screenshots for the chat and admin flows
- Add test and deployment instructions at the root level
