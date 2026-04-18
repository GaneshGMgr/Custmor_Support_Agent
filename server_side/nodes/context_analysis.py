# server_side\nodes\context_analysis.py
"""Context analysis node - gathers customer history and KB documents."""

from server_side.core.logger import logger
from server_side.graph.state import EmailAgentState
from server_side.services.database import DatabaseService
from server_side.services.kb import KnowledgeBaseService


SQL_MIN_RESULTS = 2
SQL_MIN_TOP_RELEVANCE = 0.2


def _normalize_sql_docs(sql_docs: list[dict]) -> list[dict]:
    """Normalize SQL KB docs to common response shape."""
    normalized = []
    for doc in sql_docs:
        relevance = float(doc.get("relevance_score", 0.0) or 0.0)
        normalized.append(
            {
                "id": f"sql-{doc.get('id')}",
                "title": doc.get("title", "Untitled"),
                "content": doc.get("content", ""),
                "category": doc.get("category"),
                "source_url": doc.get("source_url"),
                "similarity_score": relevance,
                "source": "sql",
            }
        )
    return normalized


def _merge_docs_prefer_sql(sql_docs: list[dict], faiss_docs: list[dict], limit: int = 5) -> list[dict]:
    """Merge two KB result sets while preferring SQL entries when duplicated by title."""
    merged: list[dict] = []
    seen_titles: set[str] = set()

    for doc in sql_docs + faiss_docs:
        title_key = str(doc.get("title", "")).strip().lower()
        if title_key and title_key in seen_titles:
            continue

        if title_key:
            seen_titles.add(title_key)
        merged.append(doc)

        if len(merged) >= limit:
            break

    return merged


async def context_analysis_node(state: EmailAgentState) -> dict:
    """Gather customer history and search knowledge base.

    Args:
        state: Current workflow state

    Returns:
        Updated state dict with context
    """
    try:
        email_id = state.get("email_id")
        customer_id = state.get("customer_id")
        subject = state.get("subject", "")
        body = state.get("body", "")
        category = state.get("category", "other")

        logger.info(f"Analyzing context for email {email_id}")

        db_service = DatabaseService()
        kb_service = KnowledgeBaseService()
        from server_side.api.main import app
        vector_kb = app.state.vector_kb

        # Get customer history
        customer_history = []
        if customer_id:
            history_emails = await db_service.get_customer_emails(customer_id, limit=5)
            customer_history = [  # convert to dict with only relevant fields for context
                {
                    "date": email.received_at,
                    "subject": email.subject,
                    "category": email.category,
                    "status": email.status,
                }
                for email in history_emails
            ]
            logger.debug(f"Found {len(customer_history)} previous emails from customer")

        # Retrieval strategy: SQL first, FAISS fallback when SQL is insufficient.
        search_query = f"{subject} {body[:200]}"
        sql_results = await kb_service.search_documents(search_query, category=category, limit=5)
        sql_normalized = _normalize_sql_docs(sql_results)

        sql_top_relevance = max((float(d.get("similarity_score", 0.0) or 0.0) for d in sql_normalized), default=0.0)
        sql_sufficient = len(sql_normalized) >= SQL_MIN_RESULTS and sql_top_relevance >= SQL_MIN_TOP_RELEVANCE

        faiss_results: list[dict] = []
        if sql_sufficient:
            logger.debug(
                f"Using SQL KB only: {len(sql_normalized)} docs, top relevance {sql_top_relevance:.3f}"
            )
            kb_results = sql_normalized
        else:
            faiss_results = await vector_kb.search(search_query, category=category, limit=5, threshold=0.3)
            for doc in faiss_results:
                doc["source"] = "faiss"

            kb_results = _merge_docs_prefer_sql(sql_normalized, faiss_results, limit=5)
            logger.debug(
                "SQL insufficient (count={} top_relevance={:.3f}); fallback FAISS count={}, merged count={}".format(
                    len(sql_normalized), sql_top_relevance, len(faiss_results), len(kb_results)
                )
            )

        # Format context for LLM
        context_summary = await vector_kb.format_context(kb_results)

        return {
            "customer_history": customer_history,
            "kb_results": kb_results,
            "context_summary": context_summary,
        }

    except Exception as e:
        logger.error(f"Error in context_analysis: {str(e)}", exc_info=True)
        return {
            "customer_history": [],
            "kb_results": [],
            "context_summary": "No additional context available.",
        }
