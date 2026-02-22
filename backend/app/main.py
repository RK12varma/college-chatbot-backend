from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.database import Base, engine
from app.auth.routes import router as auth_router
from app.document.routes import router as document_router
from app.chat.routes import router as chat_router
from app.auth.dependencies import admin_required, student_required
from app.admin.routes import router as admin_router
from app.models import scrape_source
from app.services.scheduler import start_scheduler


# Create tables
Base.metadata.create_all(bind=engine)

# Create app ONCE
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(document_router, prefix="/document", tags=["Document"])
app.include_router(chat_router, prefix="/chat", tags=["Chat"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])


# Root
@app.get("/")
def root():
    return {"message": "AI Academic Backend Running"}


# Test routes
@app.get("/admin-only")
def admin_test(user=Depends(admin_required)):
    return {"message": f"Welcome Admin {user.email}"}


@app.get("/student-only")
def student_test(user=Depends(student_required)):
    return {"message": f"Welcome Student {user.email}"}


@app.on_event("startup")
def startup_event():
    start_scheduler()


# ==========================
# React Static Serving
# ==========================

# Serve React static assets
app.mount("/static", StaticFiles(directory="frontend/dist/assets"), name="static")


# Catch-all route (MUST be last)
@app.get("/{full_path:path}")
async def serve_react(full_path: str):
    file_path = f"frontend/dist/{full_path}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return FileResponse("frontend/dist/index.html")