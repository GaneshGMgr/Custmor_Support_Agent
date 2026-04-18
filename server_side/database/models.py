# server_side\database\db_models.py

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Boolean, Index
from sqlalchemy.orm import relationship

from server_side.database.connection import Base


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime for SQLAlchemy defaults."""
    return datetime.now(timezone.utc)


class EmailPriorityEnum(str, PyEnum):
    """Email priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class EmailStatusEnum(str, PyEnum):
    """Email processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    SKIPPED = "skipped"
    RESPONDED = "responded"
    ARCHIVED = "archived"
    FAILED = "failed"


class ReviewDecisionEnum(str, PyEnum):
    """Human review decision values."""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class ReviewReasonEnum(str, PyEnum):
    """Reasons for human review."""

    LOW_CONFIDENCE = "low_confidence"
    ESCALATED_COMPLAINT = "escalated_complaint"
    CRITICAL_KEYWORDS = "critical_keywords"
    UNCERTAIN_CATEGORY = "uncertain_category"
    CUSTOM = "custom"


class ReviewStatusEnum(str, PyEnum):
    """Human review task status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class FollowUpTypeEnum(str, PyEnum):
    """Types of follow-up actions."""

    REMINDER = "reminder"
    VERIFICATION = "verification"
    ESCALATION = "escalation"
    TIMEOUT = "timeout"


class Customer(Base):
    """Customer entity."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    emails = relationship("Email", back_populates="customer")

    def __repr__(self):
        return f"<Customer(id={self.id}, email={self.email})>"


class Email(Base):
    """Incoming customer email."""

    __tablename__ = "emails"
    __table_args__ = (
        Index("idx_customer_id", "customer_id"),
        Index("idx_status", "status"),
        Index("idx_priority", "priority"),
        Index("idx_category", "category"),
    )

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    sender = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    html_body = Column(Text, nullable=True)
    message_id = Column(String(255), nullable=True, unique=True)

    # Classification
    category = Column(String(100), nullable=True)
    priority = Column(Enum(EmailPriorityEnum), default=EmailPriorityEnum.MEDIUM)
    confidence_score = Column(Float, nullable=True)

    # Status tracking
    status = Column(
        Enum(EmailStatusEnum), default=EmailStatusEnum.PENDING, nullable=False
    )
    error_message = Column(Text, nullable=True)

    # Timestamps
    received_at = Column(DateTime, nullable=False)
    ack_sent_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    customer = relationship("Customer", back_populates="emails")
    responses = relationship("EmailResponse", back_populates="email", cascade="all, delete-orphan")
    review = relationship("HumanReview", back_populates="email", uselist=False, cascade="all, delete-orphan")
    review_decision = relationship(
        "ReviewDecision",
        back_populates="email",
        uselist=False,
        cascade="all, delete-orphan",
    )
    followups = relationship("FollowUp", back_populates="email", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Email(id={self.id}, sender={self.sender}, status={self.status})>"


class EmailResponse(Base):
    """AI-generated response to customer email."""

    __tablename__ = "email_responses"

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    response_text = Column(Text, nullable=False)
    response_subject = Column(String(500), nullable=True)

    # Model information
    model_used = Column(String(100), nullable=False)
    tokens_used = Column(Integer, nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Review status
    requires_review = Column(Boolean, default=False)
    is_final = Column(Boolean, default=False)

    # Timestamps
    generated_at = Column(DateTime, default=utc_now)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    email = relationship("Email", back_populates="responses")

    def __repr__(self):
        return f"<EmailResponse(id={self.id}, email_id={self.email_id}, is_final={self.is_final})>"


class HumanReview(Base):
    """Human review task for complex/urgent emails."""

    __tablename__ = "human_reviews"
    __table_args__ = (Index("idx_review_status", "status"),)

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, unique=True)
    reason = Column(Enum(ReviewReasonEnum), nullable=False)
    notes = Column(Text, nullable=True)

    # Assignment
    assigned_to = Column(String(255), nullable=True)
    status = Column(Enum(ReviewStatusEnum), default=ReviewStatusEnum.PENDING)

    # Review result
    approved_response = Column(Text, nullable=True)
    reviewer_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    email = relationship("Email", back_populates="review")

    def __repr__(self):
        return f"<HumanReview(id={self.id}, email_id={self.email_id}, status={self.status})>"


class ReviewDecision(Base):
    """Final human decision for reviewed email response."""

    __tablename__ = "review_decisions"
    __table_args__ = (
        Index("idx_review_decision_email", "email_id"),
        Index("idx_review_decision_type", "decision"),
    )

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, unique=True)
    decision = Column(Enum(ReviewDecisionEnum), nullable=False)
    edited_response = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, default=utc_now, nullable=False)
    reviewer_note = Column(Text, nullable=True)

    email = relationship("Email", back_populates="review_decision")

    def __repr__(self):
        return f"<ReviewDecision(id={self.id}, email_id={self.email_id}, decision={self.decision})>"


class FollowUp(Base):
    """Scheduled follow-up task."""

    __tablename__ = "followups"
    __table_args__ = (
        Index("idx_email_id", "email_id"),
        Index("idx_scheduled_for", "scheduled_for"),
    )

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    followup_type = Column(Enum(FollowUpTypeEnum), nullable=False)

    # Scheduling
    scheduled_for = Column(DateTime, nullable=False)
    processing_since = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)

    # Execution result
    status = Column(String(50), default="pending")
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime, nullable=True)
    execution_key = Column(String(255), nullable=True, index=True)
    simulate_failure = Column(Boolean, default=False, nullable=False)
    last_error = Column(Text, nullable=True)
    result = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    email = relationship("Email", back_populates="followups")

    def __repr__(self):
        return f"<FollowUp(id={self.id}, email_id={self.email_id}, type={self.followup_type})>"


class KnowledgeBaseEntry(Base):
    """Knowledge base document reference."""

    __tablename__ = "kb_entries"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)

    # Source information
    source_url = Column(String(500), nullable=True)
    source_type = Column(String(50), nullable=True)

    # Embeddings (if using vector search)
    embedding = Column(String(10000), nullable=True)  # Serialized vector

    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<KnowledgeBaseEntry(id={self.id}, title={self.title})>"
