# test/test_nodes.py
import pytest
from unittest.mock import AsyncMock

from server_side.nodes.classification import classification_node
from server_side.nodes.human_review import human_review_node
from server_side.nodes.response_generation import response_generation_node
from server_side.nodes.review_routing import review_routing_node


@pytest.fixture
def base_state():
	return {
		"email_id": 100,
		"sender": "customer@example.com",
		"subject": "Need billing help",
		"body": "My billing invoice looks incorrect and I need support.",
		"category": "billing",
		"priority": "medium",
		"confidence_score": 0.9,
		"generated_response": "Draft response text for human review.",
	}


@pytest.mark.asyncio
async def test_classification_node_billing(monkeypatch, base_state):
	monkeypatch.setattr(
		"server_side.services.llm_model.LLMService.classify_email",
		AsyncMock(return_value={"category": "billing", "confidence_score": 0.98}),
	)
	monkeypatch.setattr(
		"server_side.services.llm_model.LLMService.assess_priority",
		AsyncMock(return_value={"priority": "medium"}),
	)
	monkeypatch.setattr(
		"server_side.services.database.DatabaseService.update_email_classification",
		AsyncMock(return_value=None),
	)

	out = await classification_node(base_state)
	assert out["category"] == "billing"


@pytest.mark.asyncio
async def test_response_generation_node_non_empty(monkeypatch, base_state):
	monkeypatch.setattr(
		"server_side.services.llm_model.LLMService.generate_response",
		AsyncMock(
			return_value={
				"response_text": "Hello, thanks for your billing email. We are looking into this now and will update you shortly.",
				"tokens_used": 77,
				"model_used": "test-model",
			}
		),
	)

	out = await response_generation_node(base_state)
	assert isinstance(out.get("generated_response"), str)
	assert out.get("generated_response")


@pytest.mark.asyncio
async def test_human_review_sets_awaiting_review(monkeypatch, base_state):
	mock_review = type("MockReview", (), {"id": 501})
	monkeypatch.setattr(
		"server_side.services.review.ReviewService.save_pending_review",
		AsyncMock(return_value=mock_review),
	)

	out = await human_review_node(base_state)
	assert out.get("awaiting_review") is True


@pytest.mark.asyncio
async def test_review_routing_approve(monkeypatch, base_state):
	state = {**base_state, "review_decision": "approve"}
	out = await review_routing_node(state)
	assert out.get("route_after_review") == "response_sending"
