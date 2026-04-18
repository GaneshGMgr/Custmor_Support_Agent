"""Acknowledgment email sending for newly ingested emails."""

from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy.orm import Session

from server_side.core.logger import logger
from server_side.database.models import Email
from server_side.services.email import EmailService


ACK_SUBJECT = "We received your support request"
ACK_BODY = (
    "Hello,\n\n"
    "We've received your request and our support team is reviewing it. "
    "We will get back to you shortly.\n\n"
    "Best regards,\n"
    "Customer Support"
)


async def send_intake_acknowledgement_once(db: Session, email_id: int) -> bool:
    """Send an intake acknowledgment email once per email record.

    Returns:
        True when ACK is already sent or sent successfully, False otherwise.
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if email is None:
        logger.warning("ACK skipped: email_id={} not found", email_id)
        return False

    email_row = cast(Any, email)

    if email_row.ack_sent_at is not None:
        logger.info("ACK already sent for email_id={} at {}", email_id, email_row.ack_sent_at)
        return True

    email_service = EmailService()
    sent = await email_service.send_email(
        to_address=str(email_row.sender),
        subject=ACK_SUBJECT,
        body=ACK_BODY,
    )
    if not sent:
        logger.warning("ACK send failed for email_id={}", email_id)
        return False

    email_row.ack_sent_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("ACK sent for email_id={} to {}", email_id, email_row.sender)
    return True
