# test/test_graph.py
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone
from uuid import uuid4

from server_side.database.connection import init_db
from server_side.graph.workflow import create_workflow
from server_side.nodes.factory import get_all_nodes
from server_side.schemas.email import EmailIn
from server_side.services.database import DatabaseService


@pytest.mark.asyncio
async def test_compiled_workflow_runs_and_returns_terminal_state(monkeypatch):
	init_db()

	monkeypatch.setattr(
		"server_side.services.llm_model.LLMService.classify_email",
		AsyncMock(return_value={"category": "billing", "confidence_score": 0.95}),
	)
	monkeypatch.setattr(
		"server_side.services.llm_model.LLMService.assess_priority",
		AsyncMock(return_value={"priority": "medium"}),
	)
	monkeypatch.setattr(
		"server_side.services.llm_model.LLMService.generate_response",
		AsyncMock(
			return_value={
				"response_text": "Thank you for contacting support. We have reviewed your billing question and will resolve it shortly.",
				"tokens_used": 42,
				"model_used": "test-model",
			}
		),
	)
	monkeypatch.setattr(
		"server_side.services.email.EmailService.send_email",
		AsyncMock(return_value=True),
	)

	db_service = DatabaseService()
	customer = await db_service.get_or_create_customer("workflow-test1@example.com", "workflow-test")
	email_in = EmailIn(
		sender="workflow-test@example.com",
		subject="Billing question",
		body="I have an issue with my last invoice amount.",
		received_at=datetime.now(timezone.utc),
		message_id=f"test-graph-message-id-{uuid4()}",
	)
	email_row = await db_service.create_email(email_in, customer.id)

	workflow = create_workflow(get_all_nodes(), save_image=False)
	final_state = await workflow.ainvoke({"email_id": email_row.id})

	assert final_state.get("response_sent") is True or final_state.get("awaiting_review") is True
