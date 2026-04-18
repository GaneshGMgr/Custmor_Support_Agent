# server_side\api\routes\email_routes.py

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import desc

from server_side.core.logger import logger
from server_side.database.connection import SessionLocal
from server_side.database.models import Email, EmailResponse, FollowUp, HumanReview, ReviewDecision
from server_side.nodes.response_sending import response_sending_node
from server_side.schemas.email import EmailIn
from server_side.services.database import DatabaseService
from server_side.services.review import ReviewService

router = APIRouter(prefix="/api/emails", tags=["Emails"])


class TestEmailRequest(BaseModel):
    """Test email submission."""

    sender: EmailStr
    subject: str
    body: str


class TestEmailResponse(BaseModel):
    """Test email response."""

    email_id: int
    category: Optional[str]
    priority: Optional[str]
    confidence_score: Optional[float]
    generated_response: Optional[str]
    context_summary: Optional[str]
    needs_human_review: bool
    status: str
    execution_time_ms: Optional[int]
    error_message: Optional[str]


class EmailListItem(BaseModel):
    """Email list item for inbox."""

    id: int
    sender: str
    subject: str
    category: Optional[str]
    priority: Optional[str]
    confidence_score: Optional[float]
    status: str
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailDetail(BaseModel):
    """Full email detail with all related data."""

    id: int
    sender: str
    subject: str
    body: str
    category: Optional[str]
    priority: Optional[str]
    confidence_score: Optional[float]
    status: str
    received_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]
    response: Optional[Dict[str, Any]]
    review: Optional[Dict[str, Any]]
    followups: List[Dict[str, Any]] = Field(default_factory=list)
    review_decision: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewDecisionRequest(BaseModel):
    decision: str
    edited_response: Optional[str] = None


@router.post("/test", response_model=TestEmailResponse)
async def test_email(request_body: TestEmailRequest, request: Request):
    """Test email submission: creates email and runs workflow.

    Args:
        request_body: sender, subject, body
        request: FastAPI request object

    Returns:
        TestEmailResponse with classification, response, and status
    """
    try:
        logger.info(f"Test email from {request_body.sender}")

        # Create customer and email in database
        db_service = DatabaseService()
        customer = await db_service.get_or_create_customer(
            email=request_body.sender, name=request_body.sender.split("@")[0]
        )

        email_schema = EmailIn(
            sender=request_body.sender,
            subject=request_body.subject,
            body=request_body.body,
            html_body=None,
            received_at=datetime.now(timezone.utc),
            message_id=f"test-{datetime.now(timezone.utc).timestamp()}",
        )
        email_db = await db_service.create_email(email_schema, customer.id)
        logger.info(f"Created email record: {email_db.id}")

        # Run workflow
        workflow = request.app.state.workflow
        logger.info(f"Running workflow for email {email_db.id}")
        final_state = await workflow.ainvoke({"email_id": email_db.id})

        # Extract response data
        return TestEmailResponse(
            email_id=email_db.id,
            category=final_state.get("category"),
            priority=final_state.get("priority"),
            confidence_score=final_state.get("confidence_score"),
            generated_response=final_state.get("generated_response"),
            context_summary=final_state.get("context_summary"),
            needs_human_review=final_state.get("needs_human_review", False),
            status=final_state.get("status", "unknown"),
            execution_time_ms=final_state.get("execution_time_ms"),
            error_message=final_state.get("error_message"),
        )

    except Exception as e:
        logger.error(f"Test email failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=dict)
async def list_emails(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
):
    """List all emails with pagination.

    Args:
        page: page number (1-indexed)
        per_page: emails per page
        status: filter by status (optional)

    Returns:
        {emails: [...], total: N, page: N, pages: N}
    """
    try:
        session = SessionLocal()
        try:
            query = session.query(Email).order_by(desc(Email.received_at))

            # Filter by status if provided
            if status:
                query = query.filter(Email.status == status)

            # Count total
            total = query.count()

            # Pagination
            offset = (page - 1) * per_page
            emails: List[Any] = query.offset(offset).limit(per_page).all()

            # Convert to list items
            email_items = [
                EmailListItem(
                    id=e.id,
                    sender=e.sender,
                    subject=e.subject,
                    category=e.category,
                    priority=e.priority,
                    confidence_score=e.confidence_score,
                    status=e.status,
                    received_at=e.received_at,
                )
                for e in emails
            ]
        finally:
            session.close()

        pages = (total + per_page - 1) // per_page
        return {
            "emails": [item.model_dump() for item in email_items],
            "total": total,
            "page": page,
            "pages": pages,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"List emails failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{email_id}", response_model=EmailDetail)
async def get_email_detail(email_id: int):
    """Get full email detail with all related data.

    Args:
        email_id: email ID

    Returns:
        EmailDetail with email, response, review, and followups
    """
    try:
        session = SessionLocal()

        # Get email
        email = session.query(Email).filter(Email.id == email_id).first()
        if not email:
            session.close()
            raise HTTPException(status_code=404, detail="Email not found")

        # Get response if exists
        response = None
        response_record = (
            session.query(EmailResponse).filter(EmailResponse.email_id == email_id).first()
        )
        if response_record:
            response = {
                "id": response_record.id,
                "response_text": response_record.response_text,
                "response_subject": response_record.response_subject,
                "model_used": response_record.model_used,
                "tokens_used": response_record.tokens_used,
                "confidence_score": response_record.confidence_score,
                "generated_at": response_record.generated_at.isoformat()
                if response_record.generated_at is not None
                else None,
                "sent_at": response_record.sent_at.isoformat()
                if response_record.sent_at is not None
                else None,
            }

        # Get review if exists
        review = None
        review_record = (
            session.query(HumanReview).filter(HumanReview.email_id == email_id).first()
        )
        if review_record:
            review = {
                "id": review_record.id,
                "reason": review_record.reason,
                "status": review_record.status,
                "notes": review_record.notes,
                "approved_response": review_record.approved_response,
                "reviewer_notes": review_record.reviewer_notes,
                "assigned_to": review_record.assigned_to,
                "created_at": review_record.created_at.isoformat()
                if review_record.created_at is not None
                else None,
            }

        # Get followups
        followups = session.query(FollowUp).filter(FollowUp.email_id == email_id).all()
        followups_list = [
            {
                "id": f.id,
                "followup_type": f.followup_type,
                "scheduled_for": f.scheduled_for.isoformat()
                if f.scheduled_for is not None
                else None,
                "executed_at": f.executed_at.isoformat() if f.executed_at is not None else None,
                "status": f.status,
                "result": f.result,
            }
            for f in followups
        ]

        decision_record = session.query(ReviewDecision).filter(ReviewDecision.email_id == email_id).first()
        review_decision = None
        if decision_record:
            review_decision = {
                "id": decision_record.id,
                "decision": decision_record.decision.value if hasattr(decision_record.decision, "value") else str(decision_record.decision),
                "edited_response": decision_record.edited_response,
                "reviewed_at": decision_record.reviewed_at.isoformat() if decision_record.reviewed_at else None,
                "reviewer_note": decision_record.reviewer_note,
            }

        session.close()

        return EmailDetail(
            id=email.id,
            sender=email.sender,
            subject=email.subject,
            body=email.body,
            category=email.category,
            priority=email.priority,
            confidence_score=email.confidence_score,
            status=email.status,
            received_at=email.received_at,
            processed_at=email.processed_at,
            error_message=email.error_message,
            response=response,
            review=review,
            followups=followups_list,
            review_decision=review_decision,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get email detail failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{email_id}/review", response_model=dict)
async def submit_review_decision(email_id: int, request_body: ReviewDecisionRequest):
    """Save human review decision for an email."""
    try:
        decision = request_body.decision.lower().strip()
        if decision not in {"approve", "edit", "reject"}:
            raise HTTPException(status_code=400, detail="decision must be approve, edit, or reject")

        if decision == "edit" and not (request_body.edited_response or "").strip():
            raise HTTPException(status_code=400, detail="edited_response is required when decision=edit")

        review_service = ReviewService()
        saved = await review_service.save_decision(
            email_id=email_id,
            decision=decision,
            edited_response=request_body.edited_response,
        )

        continued = False
        continuation_status = "not_required"

        # For approve/edit, immediately continue to response sending so inbox status
        # can progress to responded without waiting for another poll cycle.
        if decision in {"approve", "edit"}:
            session = SessionLocal()
            try:
                email = session.query(Email).filter(Email.id == email_id).first()
                review_record = session.query(HumanReview).filter(HumanReview.email_id == email_id).first()
            finally:
                session.close()

            if not email:
                continuation_status = "email_not_found"
                logger.warning("Review saved but email {} was not found for continuation", email_id)
            else:
                response_text = (request_body.edited_response or "").strip()
                if not response_text and review_record and review_record.approved_response:
                    response_text = review_record.approved_response

                if not response_text:
                    continuation_status = "missing_response_text"
                    logger.warning(
                        "Review saved for email {} but no response text available for continuation",
                        email_id,
                    )
                else:
                    original_subject = str(email.subject or "").strip()
                    if original_subject.lower().startswith("re:"):
                        response_subject = original_subject
                    elif original_subject:
                        response_subject = f"Re: {original_subject}"
                    else:
                        response_subject = "Re: Customer Support"

                    send_result = await response_sending_node(
                        {
                            "email_id": email.id,
                            "sender": email.sender,
                            "message_id": email.message_id,
                            "subject": email.subject,
                            "response_subject": response_subject,
                            "generated_response": response_text,
                            "model_used": "human-review-approved",
                            "needs_human_review": False,
                        }
                    )
                    if send_result.get("response_sent"):
                        continued = True
                        continuation_status = "responded"
                        logger.info("Auto-continued approved/edit review for email {}", email_id)
                    else:
                        continuation_status = "send_failed"
                        logger.warning(
                            "Review saved for email {} but continuation send failed: {}",
                            email_id,
                            send_result.get("error_message"),
                        )

        return {
            "success": True,
            "email_id": email_id,
            "decision": saved.decision.value if hasattr(saved.decision, "value") else str(saved.decision),
            "continued": continued,
            "continuation_status": continuation_status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit review decision for email {}: {}", email_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
