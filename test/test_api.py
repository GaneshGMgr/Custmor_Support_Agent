# test/test_api.py
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from server_side.api.main import app


@pytest.fixture
def async_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_returns_200(monkeypatch, async_client):
    monkeypatch.setattr(
        "server_side.services.database.DatabaseService.health_check",
        AsyncMock(return_value={"status": "healthy", "service": "database"}),
    )
    monkeypatch.setattr(
        "server_side.services.email.EmailService.health_check",
        AsyncMock(return_value={"status": "healthy", "service": "email"}),
    )

    async with async_client as client:
        response = await client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_review_approve_returns_200(monkeypatch, async_client):
    mock_saved = type("MockDecision", (), {"decision": type("D", (), {"value": "approve"})()})
    monkeypatch.setattr(
        "server_side.services.review.ReviewService.save_decision",
        AsyncMock(return_value=mock_saved),
    )

    async with async_client as client:
        response = await client.post("/api/emails/1/review", json={"decision": "approve"})

    assert response.status_code == 200
    assert response.json()["decision"] == "approve"


@pytest.mark.asyncio
async def test_review_edit_returns_200(monkeypatch, async_client):
    mock_saved = type("MockDecision", (), {"decision": type("D", (), {"value": "edit"})()})
    monkeypatch.setattr(
        "server_side.services.review.ReviewService.save_decision",
        AsyncMock(return_value=mock_saved),
    )

    async with async_client as client:
        response = await client.post(
            "/api/emails/1/review",
            json={"decision": "edit", "edited_response": "Updated final response"},
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "edit"


@pytest.mark.asyncio
async def test_review_invalid_decision_returns_422(async_client):
    async with async_client as client:
        response = await client.post("/api/emails/1/review", json={"decision": 123})

    assert response.status_code == 422