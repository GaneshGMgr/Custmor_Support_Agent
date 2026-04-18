# server_side/services/kb.py

from typing import List, Optional

from sqlalchemy.orm import Session

from server_side.core.logger import logger
from server_side.database.connection import SessionLocal
from server_side.database.models import KnowledgeBaseEntry
from server_side.services.base import BaseService


class KnowledgeBaseService(BaseService):
    """Service for knowledge base operations."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize KB service.

        Args:
            db: Optional SQLAlchemy session
        """
        self.db = db

    def _get_session(self) -> Session:
        """Get database session."""
        return self.db or SessionLocal()

    async def search_documents(
        self, query: str, category: Optional[str] = None, limit: int = 5
    ) -> List[dict]:
        """Search knowledge base for relevant documents.

        Args:
            query: Search query
            category: Optional category filter
            limit: Max documents to return

        Returns:
            List of document dicts with title, content, relevance
        """
        try:
            db = self._get_session()

            # Simple keyword search - can be upgraded to full-text or vector search
            search_terms = query.lower().split()

            results = []
            entries = db.query(KnowledgeBaseEntry)

            if category:
                entries = entries.filter(KnowledgeBaseEntry.category == category)

            entries = entries.all()

            # Simple relevance scoring based on keyword matches
            for entry in entries:
                content_lower = (entry.content + " " + entry.title).lower() # combine title and content and lowercase for search 
                matches = sum(1 for term in search_terms if term in content_lower) # how many words from query exist in content/title and count 1 for each match

                if matches > 0:
                    relevance_score = matches / len(search_terms) if search_terms else 0
                    results.append({
                        "id": entry.id,
                        "title": entry.title,
                        "content": entry.content[:500],  # Truncate for summary
                        "category": entry.category,
                        "source_url": entry.source_url,
                        "relevance_score": relevance_score,
                    })

            # Sort by relevance and limit
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            results = results[:limit]

            logger.info(f"Found {len(results)} KB documents for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return []

    async def add_document(
        self, title: str, content: str, category: Optional[str] = None, source_url: Optional[str] = None
    ) -> KnowledgeBaseEntry:
        """Add document to knowledge base.

        Args:
            title: Document title
            content: Document content
            category: Optional category
            source_url: Optional source URL

        Returns:
            Created KnowledgeBaseEntry
        """
        try:
            db = self._get_session()
            entry = KnowledgeBaseEntry(
                title=title, content=content, category=category, source_url=source_url
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            logger.info(f"Added KB document: {title}")
            return entry

        except Exception as e:
            logger.error(f"Failed to add KB document: {e}")
            raise

    async def get_document(self, doc_id: int) -> Optional[dict]:
        """Get document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document dict or None
        """
        try:
            db = self._get_session()
            entry = db.query(KnowledgeBaseEntry).filter(KnowledgeBaseEntry.id == doc_id).first()

            if not entry:
                logger.warning(f"KB document {doc_id} not found")
                return None

            return {
                "id": entry.id,
                "title": entry.title,
                "content": entry.content,
                "category": entry.category,
                "source_url": entry.source_url,
            }

        except Exception as e:
            logger.error(f"Failed to get KB document: {e}")
            return None

    async def get_by_category(self, category: str, limit: int = 10) -> List[dict]:
        """Get documents by category.

        Args:
            category: Category name
            limit: Max documents

        Returns:
            List of document dicts
        """
        try:
            db = self._get_session()
            entries = (
                db.query(KnowledgeBaseEntry)
                .filter(KnowledgeBaseEntry.category == category)
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": e.id,
                    "title": e.title,
                    "content": e.content[:500],
                    "category": e.category,
                }
                for e in entries
            ]

        except Exception as e:
            logger.error(f"Failed to get documents by category: {e}")
            return []

    async def format_context(self, documents: List[dict]) -> str:
        """Format documents into context string for LLM.

        Args:
            documents: List of document dicts

        Returns:
            Formatted context string
        """
        if not documents:
            return "No relevant documentation found."

        context_parts = ["Relevant documentation:"]
        for doc in documents:
            context_parts.append(f"\n- **{doc['title']}**")
            context_parts.append(f"  {doc['content']}")

        return "\n".join(context_parts)

    async def health_check(self) -> dict:
        """Check KB service health."""
        try:
            db = self._get_session()
            count = db.query(KnowledgeBaseEntry).count()
            return {
                "status": "healthy",
                "service": "knowledge_base",
                "documents_count": count,
            }
        except Exception as e:
            logger.error(f"KB service health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "knowledge_base",
                "error": str(e),
            }
