# server_side/core/services/llm_model.py

import json
import re
from typing import Optional, Dict, Any

# LLM SDKs
from openai import AsyncOpenAI
from groq import AsyncGroq
from ollama import AsyncClient as AsyncOllamaClient

from server_side.core.logger import logger
from server_side.core.yaml_config import load_yaml_config
from server_side.core.config import settings
from server_side.prompts.prompt_templets import (
    SYSTEM_PROMPT_CUSTOMER_SUPPORT,
    EMAIL_CLASSIFICATION_PROMPT,
    EMAIL_PRIORITY_PROMPT,
    RESPONSE_GENERATION_PROMPT,
)
from server_side.services.base import BaseService


class LLMService(BaseService):
    def __init__(self, provider: str = "openai"):
        """
        Initialize the LLM service for OpenAI, Ollama, or Groq.

        Args:
            provider: 'openai', 'ollama', or 'groq'
        """
        self.yaml_conf = load_yaml_config()
        self.provider = provider.lower()
        self.provider_conf = self.yaml_conf['llm'][self.provider]
        self.model = self.provider_conf['model_name']
        self.temperature = self.provider_conf.get("temperature", 0.7)
        self.max_tokens = self.provider_conf.get("max_output_tokens", 1000)
        self.total_tokens_used = 0

        # Initialize provider client
        if self.provider == "ollama":
            self.client = AsyncOllamaClient(
                host=self.provider_conf.get("base_url", "http://localhost:11434"),
                timeout=settings.OLLAMA_TIMEOUT_SECONDS,
            )
            self.api_key = None  # Local Ollama usually doesn't require API key

        elif self.provider == "groq":
            self.api_key = settings.GROQ_API_KEY
            self.client = AsyncGroq(api_key=self.api_key)

        else:  # default OpenAI
            self.api_key = settings.OPENAI_API_KEY
            self.client = AsyncOpenAI(api_key=self.api_key)

    async def _call_model(self, messages: list, max_tokens: Optional[int] = None) -> str:
        """Internal helper to call the LLM based on provider"""
        max_tokens = max_tokens or self.max_tokens

        try:
            if self.provider == "ollama":
                response = await self.client.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": self.temperature,
                        "num_predict": max_tokens,
                    },
                )
                text = response["message"]["content"].strip()

            elif self.provider == "groq":
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                text = response.choices[0].message.content.strip()
                if response.usage:
                    self.total_tokens_used += response.usage.total_tokens

            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                text = response.choices[0].message.content.strip()
                self.total_tokens_used += response.usage.total_tokens

            return text

        except Exception as e:
            logger.error(f"LLM call failed ({self.provider}): {e}")
            raise

    async def classify_email(self, subject: str, body: str) -> Dict[str, Any]:
        try:
            prompt = EMAIL_CLASSIFICATION_PROMPT.format(subject=subject, email_body=body)
            messages = [
                {"role": "system", "content": "You are an email classification expert."},
                {"role": "user", "content": prompt},
            ]
            tokens_before = self.total_tokens_used
            raw_response = await self._call_model(messages, max_tokens=120)
            category, confidence = self._parse_classification_response(raw_response)
            tokens_used = max(0, self.total_tokens_used - tokens_before)
            logger.debug(f"Email classified as: {category}")
            return {
                "category": category,
                "confidence_score": confidence,
                "tokens_used": tokens_used,
            }
        except Exception as e:
            return {"category": "other", "confidence_score": 0.0, "tokens_used": 0, "error": str(e)}

    def _parse_classification_response(self, raw_response: str) -> tuple[str, float]:
        """Parse classification output and normalize confidence score."""
        allowed_categories = {
            "product_inquiry",
            "billing",
            "technical_support",
            "delivery_issues",
            "complaint",
            "feedback",
            "password_reset",
            "api_errors",
            "other",
        }

        alias_map = {
            "billing_issues": "billing",
            "billing issue": "billing",
            "billing issues": "billing",
            "delivery": "delivery_issues",
            "delivery_issue": "delivery_issues",
            "delivery issue": "delivery_issues",
            "delivery issues": "delivery_issues",
            "password": "password_reset",
            "password_issue": "password_reset",
            "password reset": "password_reset",
            "api_error": "api_errors",
            "api_issue": "api_errors",
            "api errors": "api_errors",
            "tech_support": "technical_support",
            "technical": "technical_support",
            "technical support": "technical_support",
        }

        parsed: Dict[str, Any] = {}
        response_text = (raw_response or "").strip()

        # Try strict JSON first.
        try:
            parsed = json.loads(response_text)
        except Exception:
            # Fallback: extract first JSON object from free-form output.
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:
                    parsed = {}

        category_raw = str(
            parsed.get("category")
            or parsed.get("label")
            or parsed.get("intent")
            or ""
        ).lower().strip()

        if not category_raw:
            # Fallback for non-JSON/free-form responses from local models.
            known_tokens = sorted(allowed_categories.union(set(alias_map.keys())), key=len, reverse=True)
            category_match = re.search(r"\b(" + "|".join(map(re.escape, known_tokens)) + r")\b", response_text.lower())
            if category_match:
                category_raw = category_match.group(1)

        category = alias_map.get(category_raw, category_raw)
        if category not in allowed_categories:
            category = "other"

        confidence = parsed.get("confidence_score", None)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None

        # If model did not provide valid confidence, use a simple deterministic fallback.
        if confidence is None or not (0.0 <= confidence <= 1.0):
            confidence = 0.75 if category != "other" else 0.45

        return category, round(confidence, 3)

    async def assess_priority(self, body: str) -> Dict[str, Any]:
        try:
            prompt = EMAIL_PRIORITY_PROMPT.format(email_body=body)
            messages = [
                {"role": "system", "content": "You are an email priority assessment expert."},
                {"role": "user", "content": prompt},
            ]
            priority = (await self._call_model(messages, max_tokens=50)).lower()
            logger.debug(f"Email priority assessed as: {priority}")
            return {"priority": priority, "tokens_used": getattr(self.client, 'usage', 0)}
        except Exception as e:
            return {"priority": "medium", "tokens_used": 0, "error": str(e)}

    async def generate_response(
        self, subject: str, body: str, category: str, priority: str, context: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            context_str = f"\nContext from knowledge base:\n{context}" if context else ""
            support_team_name = settings.EMAIL_FROM_NAME
            prompt = RESPONSE_GENERATION_PROMPT.format(
                subject=subject,
                email_body=body,
                classification=category,
                priority=priority,
                context=context_str,
                support_team_name=support_team_name,
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_CUSTOMER_SUPPORT},
                {"role": "user", "content": prompt},
            ]
            response_text = await self._call_model(messages, max_tokens=1000)
            if response_text:
                response_text = response_text.replace("[Your Name]", support_team_name)
                response_text = response_text.replace("[Company Name]", support_team_name)
            logger.debug("Response generated")
            return {
                "response_text": response_text,
                "model_used": self.model,
                "tokens_used": getattr(self.client, 'usage', 0),
                "confidence_score": 0.85,
            }
        except Exception as e:
            return {"response_text": None, "model_used": self.model, "tokens_used": 0, "error": str(e)}

    async def health_check(self) -> dict:
        try:
            test_message = [{"role": "user", "content": "Test"}]
            await self._call_model(test_message, max_tokens=10)
            return {
                "status": "healthy",
                "service": "llm",
                "model": self.model,
                "total_tokens_used": self.total_tokens_used,
            }
        except Exception as e:
            logger.error(f"LLM service health check failed: {e}")
            return {"status": "unhealthy", "service": "llm", "error": str(e)}