"""Inbox ingestion service used by scheduler-driven polling."""

import asyncio
from typing import Any

from server_side.core.config import settings
from server_side.core.logger import logger
from server_side.database.connection import SessionLocal
from server_side.database.models import Email, EmailStatusEnum
from server_side.schemas.email import EmailIn
from server_side.services.acknowledgement import send_intake_acknowledgement_once
from server_side.services.database import DatabaseService
from server_side.services.email import EmailService


async def _run_workflow_with_timeout(workflow: Any, initial_state: dict[str, Any], email_id: int) -> None:
	"""Run workflow with a warning log for long-running local LLM calls."""
	timeout_seconds = settings.WORKFLOW_TIMEOUT_SECONDS
	warning_after_seconds = max(1, min(60, timeout_seconds - 1))

	workflow_task = asyncio.create_task(workflow.ainvoke(initial_state))
	done, _ = await asyncio.wait({workflow_task}, timeout=warning_after_seconds)

	if workflow_task in done:
		await workflow_task
		return

	logger.warning(
		"Workflow still running for email_id={} — using local LLM, this may take a while",
		email_id,
	)

	remaining_timeout = timeout_seconds - warning_after_seconds
	if remaining_timeout <= 0:
		workflow_task.cancel()
		raise asyncio.TimeoutError()

	await asyncio.wait_for(workflow_task, timeout=remaining_timeout)


async def _mark_ingested_email_as_read(email_service: EmailService, message_id: str | None) -> None:
	"""Mark an ingested email as read so it is not fetched again."""
	if not message_id:
		return

	mark_success = await email_service.mark_as_read_after_ingestion(message_id)
	if not mark_success:
		logger.warning("Failed to mark ingested email as read for message_id={}", message_id)


async def reprocess_stuck_emails(app: Any) -> None:
	"""One-time utility to reprocess emails left in processing state."""
	workflow = getattr(app.state, "workflow", None)
	if workflow is None:
		logger.error("Cannot reprocess stuck emails: workflow is not initialized")
		return

	db_session = SessionLocal()
	db_service = DatabaseService(db=db_session)

	try:
		stuck_emails = (
			db_session.query(Email)
			.filter(Email.status == EmailStatusEnum.PROCESSING)
			.order_by(Email.id.asc())
			.all()
		)

		logger.info("Found {} stuck processing email(s) to reprocess", len(stuck_emails))

		for email in stuck_emails:
			logger.info(
				"Reprocessing stuck email id={} subject='{}'",
				email.id,
				email.subject,
			)
			initial_state = {
				"email_id": email.id,
				"sender": email.sender,
				"subject": email.subject,
				"body": email.body,
				"html_body": email.html_body,
				"received_at": email.received_at,
				"message_id": email.message_id,
				"customer_id": email.customer_id,
			}

			try:
				await _run_workflow_with_timeout(workflow, initial_state, email.id)
				logger.info("Reprocess completed for email_id={}", email.id)
			except asyncio.TimeoutError:
				error_text = f"Reprocess timed out after {settings.WORKFLOW_TIMEOUT_SECONDS} seconds"
				logger.error(
					"Reprocess timed out for email_id={}: {}",
					email.id,
					error_text,
				)
				await db_service.update_email_status(
					email.id,
					EmailStatusEnum.FAILED,
					error_msg=error_text,
				)
			except Exception as reprocess_err:
				error_text = f"Reprocess failed: {str(reprocess_err)}"
				logger.error(
					"Reprocess crashed for email_id={}: {}",
					email.id,
					error_text,
					exc_info=True,
				)
				await db_service.update_email_status(
					email.id,
					EmailStatusEnum.FAILED,
					error_msg=error_text,
				)

	except Exception as e:
		logger.error("Failed during reprocess_stuck_emails run: {}", str(e), exc_info=True)
	finally:
		try:
			db_session.close()
		except Exception:
			pass


async def poll_inbox(app: Any) -> None:
	"""Poll mailbox, persist new emails, and invoke workflow processing.

	This function is designed to be called by the scheduler and must never
	raise unhandled exceptions that could break repeated polling.
	"""
	logger.info("Inbox polling cycle started")

	db_session = SessionLocal()
	db_service = DatabaseService(db=db_session)
	email_service = EmailService()

	try:
		fetched_emails = await email_service.fetch_emails()
		logger.info("Fetched {} email(s) from inbox", len(fetched_emails))

		for idx, email_in in enumerate(fetched_emails, start=1):
			try:
				logger.info("Processing fetched email {}/{}", idx, len(fetched_emails))
				saved_email = None

				if email_in.message_id:
					existing = await db_service.get_email_by_message_id(email_in.message_id)
					if existing:
						should_retry_failed = (
							settings.EMAIL_RETRY_FAILED
							and existing.status == EmailStatusEnum.FAILED
						)

						await _mark_ingested_email_as_read(email_service, email_in.message_id)

						if not should_retry_failed:
							logger.info(
								"Skipping duplicate email with message_id={} (email_id={}, status={})",
								email_in.message_id,
								existing.id,
								existing.status,
							)
							continue

						logger.info(
							"Retrying previously failed duplicate email with message_id={} (email_id={})",
							email_in.message_id,
							existing.id,
						)
						saved_email = existing

				if saved_email is None:
					customer_name = email_in.sender.split("@")[0] if email_in.sender else None
					customer = await db_service.get_or_create_customer(
						email=email_in.sender,
						name=customer_name,
					)

					saved_email = await db_service.create_email(
						email_in=EmailIn(
							sender=email_in.sender,
							subject=email_in.subject,
							body=email_in.body,
							html_body=email_in.html_body,
							received_at=email_in.received_at,
							message_id=email_in.message_id,
						),
						customer_id=customer.id if customer else None,
					)

					logger.info(
						"Saved inbound email id={} message_id={}",
						saved_email.id,
						saved_email.message_id,
					)

					# ACK runs only at intake-time for newly created inbound emails.
					await send_intake_acknowledgement_once(db_session, saved_email.id)

					await _mark_ingested_email_as_read(email_service, saved_email.message_id)

				workflow = getattr(app.state, "workflow", None)
				if workflow is None:
					logger.error("Workflow is not initialized on app.state; skipping processing")
					continue

				initial_state = {
					"email_id": saved_email.id,
					"sender": saved_email.sender,
					"subject": saved_email.subject,
					"body": saved_email.body,
					"html_body": saved_email.html_body,
					"received_at": saved_email.received_at,
					"message_id": saved_email.message_id,
					"customer_id": saved_email.customer_id,
				}
				try:
					await _run_workflow_with_timeout(workflow, initial_state, saved_email.id)
					logger.info("Workflow completed for email_id={}", saved_email.id)
				except asyncio.TimeoutError:
					error_text = f"Workflow timed out after {settings.WORKFLOW_TIMEOUT_SECONDS} seconds"
					logger.error(
						"Workflow timed out for email_id={}: {}",
						saved_email.id,
						error_text,
					)
					await db_service.update_email_status(
						saved_email.id,
						EmailStatusEnum.FAILED,
						error_msg=error_text,
					)
				except Exception as workflow_err:
					error_text = f"Workflow crashed: {str(workflow_err)}"
					logger.error(
						"Workflow crashed for email_id={}: {}",
						saved_email.id,
						error_text,
						exc_info=True,
					)
					await db_service.update_email_status(
						saved_email.id,
						EmailStatusEnum.FAILED,
						error_msg=error_text,
					)
					continue

			except Exception as email_err:
				logger.error("Failed to process one fetched email: {}", str(email_err))

	except Exception as poll_err:
		logger.error("Inbox polling cycle failed: {}", str(poll_err))
	finally:
		try:
			await email_service.cleanup()
		except Exception as cleanup_err:
			logger.warning("Email service cleanup failed after poll cycle: {}", str(cleanup_err))
		try:
			db_session.close()
		except Exception:
			pass
		logger.info("Inbox polling cycle finished")
