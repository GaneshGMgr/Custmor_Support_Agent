# server_side\nodes\review_check.py
"""Review check node - polls for human decision."""

from server_side.core.logger import logger
from server_side.graph.state import EmailAgentState
from server_side.services.review import ReviewService


async def review_check_node(state: EmailAgentState) -> dict:
    """Poll persisted review decision and update state."""
    try:
        email_id = state.get("email_id")
        if email_id is None:
            return {
                "error_message": "Missing email_id while checking review decision",
                "awaiting_review": False,
            }

        logger.info("Polling review decision for email {}", email_id)
        review_service = ReviewService()
        decision = await review_service.get_decision(email_id)

        if decision is None:
            logger.info("No review decision yet for email {}", email_id)
            return {
                "awaiting_review": True,
            }

        logger.info("Review decision '{}' available for email {}", decision.decision.value, email_id)

        return {
            "review_decision": decision.decision.value,
            "edited_response": decision.edited_response,
            "awaiting_review": False,
        }

    except Exception as e:
        logger.error("Error in review_check: {}", str(e), exc_info=True)
        return {
            "error_message": f"Review check error: {str(e)}",
            "awaiting_review": True,
        }
