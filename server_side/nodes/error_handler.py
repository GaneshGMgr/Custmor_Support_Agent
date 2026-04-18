# server_side\nodes\error_handler.py
"""Error handler node - handles and logs processing errors."""

from server_side.core.logger import logger
from server_side.database.connection import SessionLocal
from server_side.database.models import Email
from server_side.graph.state import EmailAgentState
from server_side.database.models import EmailStatusEnum
from server_side.services.database import DatabaseService


async def error_handler_node(state: EmailAgentState) -> dict:
    """Handle errors and update email status.

    Args:
        state: Current workflow state

    Returns:
        Final state dict
    """
    try:
        email_id = state.get("email_id")
        error_message = state.get("error_message", "Unknown error")

        logger.error(f"Error handling email {email_id}: {error_message}")

        # Update email status to failed
        db_service = DatabaseService()
        failed_row = None
        try:
            failed_row = await db_service.update_email_status(
                email_id,
                EmailStatusEnum.FAILED,
                error_msg=error_message,
            )
        except Exception as update_err:
            logger.error(
                "Primary failed-status update failed for email {}: {}",
                email_id,
                str(update_err),
            )

        # Fallback DB write to avoid stuck 'processing' states.
        if failed_row is None and email_id is not None:
            session = SessionLocal()
            try:
                email = session.query(Email).filter(Email.id == email_id).first()
                if email is not None:
                    email.status = EmailStatusEnum.FAILED
                    email.error_message = error_message
                    session.commit()
                    logger.info("Fallback status transition -> failed for email {}", email_id)
                else:
                    logger.error("Fallback failed-status update: email {} not found", email_id)
            except Exception as fallback_err:
                session.rollback()
                logger.critical(
                    "Fallback failed-status update crashed for email {}: {}",
                    email_id,
                    str(fallback_err),
                    exc_info=True,
                )
            finally:
                session.close()
        else:
            logger.info("Status transition -> failed for email {}", email_id)

        # Log error details
        logger.error(f"Email {email_id} processing failed")
        logger.error(f"Error details: {error_message}")

        # Optional: Send notification to admin
        # await notify_admin(f"Email {email_id} failed: {error_message}")

        return {
            "status": EmailStatusEnum.FAILED.value,
            "error_message": error_message,
        }

    except Exception as e:
        logger.critical(f"Error in error_handler: {str(e)}", exc_info=True)
        return {
            "status": EmailStatusEnum.FAILED.value,
            "error_message": f"Critical error in error handler: {str(e)}",
        }
