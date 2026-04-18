# server_side\nodes\response_sending.py
"""Response sending node - sends final response email."""

from server_side.core.logger import logger
from server_side.graph.state import EmailAgentState
from server_side.database.models import EmailStatusEnum
from server_side.services.email import EmailService
from server_side.services.database import DatabaseService


async def response_sending_node(state: EmailAgentState) -> dict:
    """Send response email to customer.

    Args:
        state: Current workflow state

    Returns:
        Updated state dict with sending result
    """
    try:
        email_id = state.get("email_id")
        sender = state.get("sender")
        message_id = state.get("message_id")
        original_subject = str(state.get("subject") or "").strip()
        response_text = state.get("generated_response") or state.get("approved_response")
        state_subject = str(state.get("response_subject") or "").strip()
        if state_subject:
            response_subject = state_subject
        elif original_subject.lower().startswith("re:"):
            response_subject = original_subject
        elif original_subject:
            response_subject = f"Re: {original_subject}"
        else:
            response_subject = "Re: Customer Support"

        if email_id is None:
            logger.error("No email_id provided to response_sending node")
            return {
                "error_message": "Missing email_id in workflow state",
                "status": EmailStatusEnum.FAILED.value,
                "response_sent": False,
            }

        if not sender:
            logger.error("No sender provided for email {}", email_id)
            return {
                "error_message": "Missing sender in workflow state",
                "status": EmailStatusEnum.FAILED.value,
                "response_sent": False,
            }

        if not response_text:
            logger.error(f"No response text to send for email {email_id}")
            return {
                "error_message": "No response text available",
                "status": EmailStatusEnum.FAILED.value,
            }

        logger.info(f"Sending response for email {email_id} to {sender}")

        email_service = EmailService()
        db_service = DatabaseService()

        # Send email
        send_success = await email_service.send_email(
            to_address=sender,
            subject=response_subject,
            body=response_text,
        )

        if not send_success:
            logger.error(f"Failed to send email to {sender}")
            return {
                "error_message": f"Failed to send email to {sender}",
                "status": EmailStatusEnum.FAILED.value,
                "response_sent": False,
            }

        if message_id:
            mark_success = await email_service.mark_as_read(message_id)
            if mark_success:
                logger.info("Marked source message as read for email_id={} message_id={}", email_id, message_id)
            else:
                logger.warning(
                    "Reply sent but failed to mark source message as read for email_id={} message_id={}",
                    email_id,
                    message_id,
                )
        else:
            logger.warning("No message_id available to mark as read for email_id={}", email_id)

        # Create response record in database if email sent successfully
        await db_service.create_response(
            email_id=email_id,
            response_text=response_text,
            model_used=str(state.get("model_used") or "gpt-4-turbo-preview"),
            tokens_used=int(state.get("tokens_used") or 0),
            confidence_score=float(state.get("confidence_score") or 0.85),
            requires_review=state.get("needs_human_review", False),
        )

        # Update email status
        await db_service.update_email_status(email_id, EmailStatusEnum.RESPONDED)

        logger.info(f"Response sent successfully for email {email_id}")

        return {
            "final_response": response_text,
            "status": EmailStatusEnum.RESPONDED.value,
            "response_sent": True,
        }

    except Exception as e:
        logger.error(f"Error in response_sending: {str(e)}", exc_info=True)
        return {
            "error_message": f"Response sending error: {str(e)}",
            "status": EmailStatusEnum.FAILED.value,
            "response_sent": False,
        }
