# server_side\nodes\email_retrieval.py
"""Email retrieval node - loads email from database."""

from datetime import datetime, timezone

from server_side.core.logger import logger
from server_side.database.models import EmailStatusEnum
from server_side.graph.state import EmailAgentState
from server_side.services.database import DatabaseService


async def email_retrieval_node(state: EmailAgentState) -> dict:
    """Retrieve and load email details.

    Args:
        state: Current workflow state

    Returns:
        Updated state dict
    """
    try:
        email_id = state.get("email_id")
        logger.info(f"Retrieving email {email_id}")

        # Get email from database
        db_service = DatabaseService()
        email = await db_service.get_email_with_history(email_id)

        if not email:
            logger.error(f"Email {email_id} not found")
            return {
                "error_message": f"Email {email_id} not found",
                "status": EmailStatusEnum.FAILED.value,
            }

        # Update email status to processing
        await db_service.update_email_status(email_id, EmailStatusEnum.PROCESSING)

        logger.info(f"Email retrieved: {email.subject}")

        return {
            "email_id": email_id,
            "sender": email.sender,
            "subject": email.subject,
            "body": email.body,
            "html_body": email.html_body,
            "received_at": email.received_at,
            "customer_id": email.customer_id,
            "processing_started_at": datetime.now(timezone.utc),
        }

    except Exception as e:
        logger.error(f"Error in email_retrieval: {str(e)}", exc_info=True)
        return {
            "error_message": f"Email retrieval failed: {str(e)}",
            "status": EmailStatusEnum.FAILED.value,
        }
