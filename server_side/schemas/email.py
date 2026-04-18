# server_side/schemas/email.py 

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class EmailPriority(str, Enum):
    """Email priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class EmailStatus(str, Enum):
    """Email processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    RESPONDED = "responded"
    ARCHIVED = "archived"
    FAILED = "failed"


class EmailIn(BaseModel):
    """Input schema for incoming emails."""

    model_config = ConfigDict(from_attributes=True)

    sender: EmailStr
    subject: str
    body: str
    html_body: Optional[str] = None
    received_at: datetime
    message_id: Optional[str] = None


class EmailOut(BaseModel):
    """Output schema for emails."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: EmailStr
    subject: str
    body: str
    status: EmailStatus
    priority: EmailPriority
    created_at: datetime
    updated_at: datetime


class EmailResponse(BaseModel):
    """Schema for email responses."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    email_id: int
    response_text: str
    model_used: str
    tokens_used: Optional[int] = None
    generated_at: datetime


class ProcessingResult(BaseModel):
    """Schema for email processing results."""

    model_config = ConfigDict(from_attributes=True)

    success: bool
    email_id: int
    status: EmailStatus
    priority: EmailPriority
    response_id: Optional[int] = None
    error_message: Optional[str] = None
    processing_time_ms: float
