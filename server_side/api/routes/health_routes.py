# server_side\api\routes\health_routes.py

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

from server_side.core.logger import logger
from server_side.core.config import settings
from server_side.services.database import DatabaseService
from server_side.services.email import EmailService

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """Check application and database health."""
    try:
        db_service = DatabaseService()
        email_service = EmailService()

        db_health = await db_service.health_check()
        email_health = await email_service.health_check()
        overall_status = (
            "healthy"
            if db_health.get("status") == "healthy" and email_health.get("status") == "healthy"
            else "unhealthy"
        )

        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": db_health,
            "email": email_health,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }


@router.get("/health/vector-kb", tags=["Health"])
async def vector_kb_debug(request: Request):
    """Debug endpoint for vector KB index and metadata visibility."""
    try:
        vector_store = Path(settings.VECTOR_STORE_PATH)
        index_path = vector_store / "faiss_index.bin"
        metadata_path = vector_store / "documents.json"

        vector_kb = getattr(request.app.state, "vector_kb", None)
        index_ntotal = 0
        index_dimension = 0
        docs = {}

        if vector_kb is not None and getattr(vector_kb, "faiss_index", None) is not None:
            index_ntotal = int(vector_kb.faiss_index.ntotal)
            index_dimension = int(vector_kb.faiss_index.d)
            docs = vector_kb.documents_metadata or {}

        category_counts = {}
        for doc in docs.values():
            cat = doc.get("category") or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        sample_titles = [doc.get("title") for doc in list(docs.values())[:10] if doc.get("title")]

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vector_store_path": str(vector_store.resolve()),
            "files": {
                "faiss_index": {
                    "path": str(index_path.resolve()),
                    "exists": index_path.exists(),
                    "size_bytes": index_path.stat().st_size if index_path.exists() else 0,
                },
                "documents_json": {
                    "path": str(metadata_path.resolve()),
                    "exists": metadata_path.exists(),
                    "size_bytes": metadata_path.stat().st_size if metadata_path.exists() else 0,
                },
            },
            "runtime": {
                "vector_kb_loaded_in_app_state": vector_kb is not None,
                "index_ntotal": index_ntotal,
                "index_dimension": index_dimension,
                "metadata_count": len(docs),
                "category_counts": category_counts,
                "sample_titles": sample_titles,
            },
        }
    except Exception as e:
        logger.error(f"Vector KB debug endpoint failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }
