# server_side\services\email.py
"""Email service for IMAP/SMTP operations."""
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

import aiosmtplib
from aiosmtplib.errors import SMTPAuthenticationError
from imap_tools.errors import MailboxLogoutError
from imap_tools.mailbox import MailBox
from imap_tools.query import AND, Header

from server_side.core.logger import logger
from server_side.core.config import settings
from server_side.schemas.email import EmailIn
from server_side.services.base import BaseService

class EmailService(BaseService):
    """Handle email retrieval and sending."""

    def __init__(self):
        """Initialize email service."""
        self.imap_server = settings.IMAP_SERVER
        self.imap_port = settings.IMAP_PORT
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.email_address = settings.EMAIL_ADDRESS
        self.email_password = settings.EMAIL_PASSWORD
        self.from_name = settings.EMAIL_FROM_NAME
        self.mailbox = None

    async def initialize(self) -> None:
        """Initialize email service and test connections."""
        await super().initialize()
        try:
            # Test IMAP connection
            await self._test_imap_connection()
            logger.info("Email service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize email service: {e}")
            raise

    # ensures that IMAP connection is safely closed when the app stops or the service is no longer needed.
    async def cleanup(self) -> None:
        """Cleanup email connections."""
        if self.mailbox:
            try:
                self.mailbox.logout()
            except MailboxLogoutError:
                pass
        await super().cleanup()

    # makes sure always have a live connection when needed.
    async def _get_mailbox(self) -> MailBox:
        """Get IMAP mailbox connection."""
        if not self.mailbox:
            self.mailbox = MailBox(self.imap_server, self.imap_port)
            self.mailbox.login(self.email_address, self.email_password)
        return self.mailbox

    async def _test_imap_connection(self) -> None:
        """Test IMAP connection."""
        try:
            mailbox = MailBox(self.imap_server, self.imap_port)
            mailbox.login(self.email_address, self.email_password)
            mailbox.logout()
            logger.info("IMAP connection test passed")
        except Exception as e:
            logger.error(f"IMAP connection test failed: {e}")
            raise

    async def _test_smtp_connection(self) -> None:
        """Test SMTP connection and authentication."""
        use_tls = self.smtp_port == 465

        try:
            async with aiosmtplib.SMTP(
                hostname=self.smtp_server,
                port=self.smtp_port,
                use_tls=use_tls,
                start_tls=False,
                timeout=30,
            ) as smtp:
                if self.smtp_port == 587:
                    await smtp.starttls()

                await smtp.login(self.email_address, self.email_password)

            logger.info("SMTP connection test passed")

        except SMTPAuthenticationError as e:
            logger.error(
                "SMTP authentication test failed for {}: {}",
                self.email_address,
                e,
            )
            raise

        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            raise
            
    # fetches unread emails, converts into app’s internal data model, and provides a ready-to-use list.
    # bridge between email server and workflow, email_retrieval node in workflow will likely call this method to get emails to process.
    async def fetch_emails(self, limit: int = 10) -> List[EmailIn]:
        """Fetch unread emails from inbox.

        Args:
            limit: Maximum number of emails to fetch

        Returns:
            List of EmailIn objects
        """
        try:
            mailbox = await self._get_mailbox()
            emails = []

            # Calculate date threshold: only fetch unread emails from the last N days
            fetch_days_back = settings.EMAIL_FETCH_DAYS_BACK
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=fetch_days_back)
            
            # Fetch unread emails, newest first
            # Note: Gmail IMAP fetches oldest first by default, so reverse=True gets newest first
            for msg in mailbox.fetch(criteria='UNSEEN', limit=limit, reverse=True, mark_seen=False):
                # Filter by date: skip emails older than cutoff
                if msg.date and msg.date.replace(tzinfo=None) < cutoff_date.replace(tzinfo=None):
                    logger.debug(f"Skipping email from {msg.from_} (date: {msg.date} older than {cutoff_date})")
                    continue
                
                try:
                    # imap-tools message objects may not always expose message_id directly.
                    # Fall back to Message-ID headers, then UID-based synthetic id.
                    message_id = getattr(msg, "message_id", None)
                    if not message_id:
                        headers = getattr(msg, "headers", {}) or {}
                        header_value = (
                            headers.get("Message-ID")
                            or headers.get("Message-Id")
                            or headers.get("message-id")
                        )
                        if isinstance(header_value, (list, tuple)):
                            header_value = header_value[0] if header_value else None
                        message_id = str(header_value).strip() if header_value else None

                    if not message_id:
                        uid = getattr(msg, "uid", None)
                        message_id = f"imap-uid-{uid}" if uid else None

                    email_in = EmailIn(
                        sender=msg.from_,
                        subject=msg.subject or "[No Subject]",
                        body=msg.text or msg.html or "",
                        html_body=msg.html,
                        received_at=msg.date or datetime.now(timezone.utc),
                        message_id=message_id,
                    )
                    emails.append(email_in)
                    logger.debug(f"Fetched email from {email_in.sender}")
                except Exception as e:
                    logger.error(f"Failed to parse email: {e}")
                    continue

            logger.info(
                f"Fetched {len(emails)} unread emails from last {fetch_days_back} days (newest first)"
            )
            return emails

        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            raise

    # sends email with generated response to customer email address
    async def send_email(
        self, to_address: str, subject: str, body: str, html_body: Optional[str] = None
    ) -> bool:
        """Send email via SMTP.

        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body

        Returns:
            True if email sent successfully
        """
        try:
            # Create message
            if html_body:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(html_body, "html"))
            else:
                msg = MIMEText(body)

            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.email_address}>"
            msg["To"] = to_address

            # For Gmail SMTP:
            # - Port 587 uses STARTTLS
            # - Port 465 uses implicit TLS
            use_tls = self.smtp_port == 465

            async with aiosmtplib.SMTP(
                hostname=self.smtp_server,
                port=self.smtp_port,
                use_tls=use_tls,
                start_tls=False,
                timeout=30,
            ) as smtp:
                if self.smtp_port == 587:
                    await smtp.starttls()

                await smtp.login(self.email_address, self.email_password)
                await smtp.send_message(msg)

            logger.info(f"Email sent to {to_address}: {subject}")
            return True

        except SMTPAuthenticationError as e:
            logger.error(
                "SMTP authentication failed for {}. "
                "If using Gmail, use an App Password (not your normal Gmail password), "
                "ensure 2-Step Verification is enabled, and verify EMAIL_ADDRESS/EMAIL_PASSWORD in .env. "
                "Raw error: {}",
                self.email_address,
                e,
            )
            return False

        except Exception as e:
            logger.error(f"Failed to send email to {to_address}: {e}")
            return False

    # update the email’s status to marked as read on the email server, ensuring that it won’t be fetched again in future retrievals.
    async def mark_as_read(self, message_id: str) -> bool:
        """Mark email as read.

        Args:
            message_id: Email message ID

        Returns:
            True if successful
        """
        try:
            if not message_id:
                logger.warning("mark_as_read called with empty message_id")
                return False

            mailbox = await self._get_mailbox()

            criteria = AND(header=Header("Message-ID", message_id))
            matched_uids = [
                msg.uid for msg in mailbox.fetch(criteria=criteria, mark_seen=False) if msg.uid
            ]

            if not matched_uids:
                logger.warning("No IMAP message found for message_id={}", message_id)
                return False

            mailbox.flag(matched_uids, "\\Seen", True)
            logger.info(
                "Marked message_id={} as read (matched_uids={})",
                message_id,
                len(matched_uids),
            )
            return True
        except Exception as e:
            logger.error("Failed to mark message_id={} as read: {}", message_id, e)
            return False

    async def mark_as_read_after_ingestion(self, message_id: str) -> bool:
        """Mark an ingested email as read in Gmail so it is not fetched again."""
        logger.info("Marking email as read in Gmail after ingestion: {}", message_id)
        return await self.mark_as_read(message_id)

    async def health_check(self) -> dict:
        """Check email service health."""
        imap_error = None
        smtp_error = None

        try:
            await self._test_imap_connection()
        except Exception as e:
            imap_error = str(e)

        try:
            await self._test_smtp_connection()
        except Exception as e:
            smtp_error = str(e)

        if not imap_error and not smtp_error:
            return {
                "status": "healthy",
                "service": "email",
                "imap": {"status": "healthy"},
                "smtp": {"status": "healthy"},
            }

        logger.error(
            "Email service health check failed (imap_error={}, smtp_error={})",
            imap_error,
            smtp_error,
        )
        return {
            "status": "unhealthy",
            "service": "email",
            "imap": {"status": "unhealthy" if imap_error else "healthy", "error": imap_error},
            "smtp": {"status": "unhealthy" if smtp_error else "healthy", "error": smtp_error},
        }
