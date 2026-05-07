"""Main entry point for the AuditChain FastAPI application.

Provides the API server configuration, CORS middleware, and initial endpoints.
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from auditchain.api.limiter import limiter

from auditchain.core.config import get_settings
from auditchain.core.logging import configure_logging, get_logger
from auditchain.data.database import get_session
from auditchain.api.routers import audits, auth, companies, ingestion, admin

# Initialize logging and settings
configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title="AuditChain API",
    description="Multi-agent SEC fraud detection system",
    version="1.0.0"
)

# Rate Limiting Configuration
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
cors_origins = [
    "http://localhost:3000",
    "https://audit-bigfour.duckdns.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
# NOTE: ingestion router must be registered before companies router because
# companies has a catch-all /{cik} path that would intercept /check, /add, /ingestions.
app.include_router(auth.router)
app.include_router(ingestion.router)
app.include_router(companies.router)
app.include_router(audits.router)
app.include_router(admin.router)

@app.on_event("startup")
async def startup_event():
    """Actions to run on API startup."""
    logger.info("api_started", timestamp=datetime.utcnow().isoformat())

@app.get("/")
async def root():
    """Root endpoint returning basic API status."""
    return {
        "name": "AuditChain API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/info")
async def get_info():
    """Returns general statistics and system information."""
    try:
        with get_session() as session:
            # Count companies
            company_count = session.execute(text("SELECT COUNT(*) FROM companies")).scalar()
            # Count audit runs
            audit_count = session.execute(text("SELECT COUNT(*) FROM audit_runs")).scalar()
            
        return {
            "statistics": {
                "total_companies": company_count,
                "total_audits": audit_count
            },
            "available_models": {
                "fast_model": settings.llm_fast_model,
                "smart_model": settings.llm_smart_model
            },
            "environment": "development"
        }
    except Exception as e:
        logger.error("api_info_failed", error=str(e))
        return {"error": "Could not retrieve system info", "detail": str(e)}
