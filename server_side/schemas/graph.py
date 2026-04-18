# server_side/schemas/graph.py

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from server_side.schemas.email import EmailPriority, EmailStatus


class GraphState(BaseModel):
    """State object for LangGraph workflow."""

    model_config = ConfigDict(from_attributes=True)

    # Email metadata
    email_id: Optional[int] = None
    sender: str
    subject: str
    body: str
    html_body: Optional[str] = None
    received_at: datetime

    # Processing results
    priority: Optional[EmailPriority] = None
    status: EmailStatus = EmailStatus.PENDING
    classification: Optional[str] = None
    context_analysis: Optional[Dict[str, Any]] = None

    # LLM response
    generated_response: Optional[str] = None
    llm_model: Optional[str] = None
    confidence_score: Optional[float] = None

    # Metadata
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class NodeOutput(BaseModel):
    """Output from a graph node."""

    model_config = ConfigDict(from_attributes=True)

    node_name: str
    success: bool
    output: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float
