"""
api/v1/health.py — GET /api/v1/health

Returns service liveness and MongoDB connectivity state.
If MongoDB is unreachable, returns 503 with a clear diagnostic.
"""
from fastapi import APIRouter, Response
from app.core.database import ping_db
from app.core.config import settings

router = APIRouter()


@router.get("/health", tags=["system"])
def health_check(response: Response):
    db_ok = ping_db()
    status = "ok" if db_ok else "degraded"
    if not db_ok:
        response.status_code = 503
    return {
        "status": status,
        "service": settings.app_name,
        "version": settings.app_version,
        "database": {
            "connected": db_ok,
            "uri_host": settings.mongodb_uri.split("@")[-1]
            if "@" in settings.mongodb_uri
            else settings.mongodb_uri,
            "db": settings.mongodb_db,
        },
        "message": (
            "All systems operational."
            if db_ok
            else (
                "MongoDB unreachable. Start MongoDB Community and ensure "
                f"MONGODB_URI={settings.mongodb_uri} is correct. "
                "See infra/mongodb/README.md for setup instructions."
            )
        ),
    }
