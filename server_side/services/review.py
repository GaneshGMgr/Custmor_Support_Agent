"""Human review service for managing escalation workflows."""

from typing import List, Optional

from sqlalchemy.orm import Session

from server_side.core.logger import logger
from server_side.database.connection import SessionLocal
from server_side.database.models import (
    Email,
    EmailStatusEnum,
    HumanReview,
    ReviewDecision,
    ReviewDecisionEnum,
    ReviewReasonEnum,
    ReviewStatusEnum,
)
from server_side.services.base import BaseService


class ReviewService(BaseService):
    """Service for human review task management."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize review service.

        Args:
            db: Optional SQLAlchemy session
        """
        self.db = db

    def _get_session(self) -> Session:
        """Get database session."""
        return self.db or SessionLocal()

    async def save_pending_review(self, email_id: int, generated_response: str) -> HumanReview:
        """Persist pending human-review state for an email.

        Args:
            email_id: Email id
            generated_response: Model-generated draft response

        Returns:
            HumanReview row
        """
        db = self._get_session()
        review = db.query(HumanReview).filter(HumanReview.email_id == email_id).first()

        if not review:
            review = HumanReview(
                email_id=email_id,
                reason=ReviewReasonEnum.CUSTOM,
                status=ReviewStatusEnum.PENDING,
                notes="Queued by automated workflow for human review",
            )
            db.add(review)

        review.status = ReviewStatusEnum.PENDING
        review.approved_response = generated_response

        email = db.query(Email).filter(Email.id == email_id).first()
        if email:
            email.status = EmailStatusEnum.AWAITING_REVIEW

        db.commit()
        db.refresh(review)
        logger.info("Saved pending review for email {}", email_id)
        return review

    async def get_decision(self, email_id: int) -> Optional[ReviewDecision]:
        """Get persisted human review decision for an email."""
        db = self._get_session()
        decision = db.query(ReviewDecision).filter(ReviewDecision.email_id == email_id).first()
        return decision

    async def save_decision(
        self,
        email_id: int,
        decision: str,
        edited_response: Optional[str] = None,
        reviewer_note: Optional[str] = None,
    ) -> ReviewDecision:
        """Save or update human review decision for an email."""
        db = self._get_session()

        try:
            decision_enum = ReviewDecisionEnum(decision)
        except ValueError as e:
            raise ValueError(f"Unsupported review decision: {decision}") from e

        review_decision = db.query(ReviewDecision).filter(ReviewDecision.email_id == email_id).first()
        if not review_decision:
            review_decision = ReviewDecision(email_id=email_id, decision=decision_enum)
            db.add(review_decision)

        review_decision.decision = decision_enum
        review_decision.edited_response = edited_response
        review_decision.reviewer_note = reviewer_note

        review = db.query(HumanReview).filter(HumanReview.email_id == email_id).first()
        if review:
            if decision_enum == ReviewDecisionEnum.REJECT:
                review.status = ReviewStatusEnum.REJECTED
            else:
                review.status = ReviewStatusEnum.APPROVED
                if edited_response:
                    review.approved_response = edited_response

        email = db.query(Email).filter(Email.id == email_id).first()
        if email:
            if decision_enum == ReviewDecisionEnum.REJECT:
                email.status = EmailStatusEnum.ARCHIVED
            else:
                email.status = EmailStatusEnum.PROCESSING

        db.commit()
        db.refresh(review_decision)
        logger.info("Saved decision '{}' for email {}", decision_enum.value, email_id)
        return review_decision

    async def get_pending_reviews(self, agent_id: Optional[str] = None, limit: int = 10) -> List[HumanReview]:
        """Get pending review tasks.

        Args:
            agent_id: Optional agent ID to filter by
            limit: Max reviews to return

        Returns:
            List of HumanReview objects
        """
        try:
            db = self._get_session()
            query = db.query(HumanReview).filter(HumanReview.status == ReviewStatusEnum.PENDING)

            if agent_id:
                query = query.filter(HumanReview.assigned_to == agent_id)

            reviews = query.limit(limit).all()
            logger.info(f"Retrieved {len(reviews)} pending reviews")
            return reviews

        except Exception as e:
            logger.error(f"Failed to get pending reviews: {e}")
            return []

    async def assign_to_agent(self, review_id: int, agent_id: str) -> Optional[HumanReview]:
        """Assign review task to agent.

        Args:
            review_id: Review task ID
            agent_id: Agent ID

        Returns:
            Updated HumanReview or None
        """
        try:
            db = self._get_session()
            review = db.query(HumanReview).filter(HumanReview.id == review_id).first()

            if not review:
                logger.warning(f"Review {review_id} not found")
                return None

            review.assigned_to = agent_id
            db.commit()
            db.refresh(review)
            logger.info(f"Assigned review {review_id} to agent {agent_id}")
            return review

        except Exception as e:
            logger.error(f"Failed to assign review: {e}")
            return None

    async def health_check(self) -> dict:
        """Check review service health."""
        try:
            db = self._get_session()
            pending_count = db.query(HumanReview).filter(
                HumanReview.status == ReviewStatusEnum.PENDING
            ).count()
            return {
                "status": "healthy",
                "service": "review",
                "pending_reviews": pending_count,
            }
        except Exception as e:
            logger.error(f"Review service health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "review",
                "error": str(e),
            }
