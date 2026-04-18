# server_side\nodes\human_review.py
"""Human review node - creates pending human review and pauses workflow."""

from server_side.core.logger import logger
from server_side.graph.state import EmailAgentState
from server_side.services.review import ReviewService


async def human_review_node(state: EmailAgentState) -> dict:
    """Create pending review and return awaiting-review state."""
    try:
        email_id = state.get("email_id")
        generated_response = state.get("generated_response")

        if email_id is None:
            return {
                "error_message": "Missing email_id while creating pending review",
                "awaiting_review": False,
            }
        if not generated_response:
            return {
                "error_message": f"Missing generated response for email {email_id}",
                "awaiting_review": False,
            }

        logger.info("Creating pending review for email {}", email_id)
        review_service = ReviewService()
        review = await review_service.save_pending_review(email_id, generated_response)

        logger.info("Review {} pending for email {}", review.id, email_id)

        return {
            "review_id": review.id,
            "awaiting_review": True,
            "status": "awaiting_review",
        }

    except Exception as e:
        logger.error("Error in human_review: {}", str(e), exc_info=True)
        return {
            "error_message": f"Human review processing error: {str(e)}",
            "awaiting_review": False,
        }
