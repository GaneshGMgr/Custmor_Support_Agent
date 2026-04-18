# server_side\nodes\review_routing.py
"""Review routing node - routes based on human review decision."""

from server_side.core.logger import logger
from server_side.graph.state import EmailAgentState
from server_side.database.models import EmailStatusEnum


async def review_routing_node(state: EmailAgentState) -> dict:
    """Route workflow according to review_decision."""
    try:
        email_id = state.get("email_id")
        decision = (state.get("review_decision") or "").lower()

        if decision == "approve":
            logger.info("Review approved for email {}", email_id)
            return {
                "route_after_review": "response_sending",
            }

        if decision == "edit":
            edited_response = state.get("edited_response")
            logger.info("Review edited for email {}", email_id)
            return {
                "generated_response": edited_response or state.get("generated_response"),
                "route_after_review": "response_sending",
            }

        if decision == "reject":
            logger.warning("Review rejected for email {}", email_id)
            return {
                "route_after_review": "end",
                "status": EmailStatusEnum.SKIPPED.value,
                "response_sent": False,
            }

        logger.info("No actionable review decision for email {} yet", email_id)
        return {
            "route_after_review": "end",
            "awaiting_review": True,
        }

    except Exception as e:
        logger.error("Error in review_routing: {}", str(e), exc_info=True)
        return {
            "error_message": f"Review routing failed: {str(e)}",
            "route_after_review": "end",
        }
