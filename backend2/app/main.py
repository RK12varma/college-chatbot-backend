import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database import Base, engine
from app.logger import logger

# ─── Routers ─────────────────────────────────────────────────────────────────
from app.auth.routes     import router as auth_router
from app.document.routes import router as document_router
from app.chat.routes     import router as chat_router
from app.admin.routes    import router as admin_router
from app.services.scheduler import start_scheduler
from app.document.qp_routes import router as qp_router

# ─── Import all models so Alembic/SQLAlchemy sees them ───────────────────────
from app.models import user, document, chunk, scrape_source  # noqa
from app.models import chat_history, audit_log               # noqa


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} started "
                f"[{settings.ENVIRONMENT}]")
    yield
    # Shutdown
    logger.info("Server shutting down.")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered college information assistant backend",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Logging Middleware ───────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 1)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} [{duration}ms]")
    return response


# ─── Global Exception Handlers ───────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": e["loc"][-1], "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(auth_router,     prefix="/auth",     tags=["Auth"])
app.include_router(document_router, prefix="/document", tags=["Document"])
app.include_router(chat_router,     prefix="/chat",     tags=["Chat"])
app.include_router(admin_router,    prefix="/admin",    tags=["Admin"])
app.include_router(qp_router, prefix="/qp", tags=["Question Papers"])

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["System"])
def root():
    return {"message": f"{settings.APP_NAME} is running"}
