"""Run the AuditChain FastAPI server.

Usage:
    python -m scripts.run_api
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "auditchain.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
