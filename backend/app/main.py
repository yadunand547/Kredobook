"""
KredoBook - FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.auth import router as auth_router
from app.routes.borrowers import router as borrowers_router
from app.routes.health import router as health_router
from app.routes.loans import admin_router as loans_admin_router
from app.routes.loans import borrower_router as loans_borrower_router
from app.routes.payments import router as payments_router
from app.routes.reminders import router as reminders_router
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler on startup, stop it cleanly on shutdown."""
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="KredoBook API",
    description="KredoBook - Smart & Secure Loan Lifecycle Management Platform API.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration - allows the React dev server to communicate
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(borrowers_router)
app.include_router(loans_admin_router)
app.include_router(loans_borrower_router)
app.include_router(payments_router)
app.include_router(reminders_router)
