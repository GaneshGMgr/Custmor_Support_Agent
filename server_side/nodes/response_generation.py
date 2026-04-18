# server_side\nodes\response_generation.py
"""Response generation node - creates AI response to customer email."""

from server_side.core.logger import logger
from server_side.graph.state import EmailAgentState
from server_side.services.llm_model import LLMService


async def response_generation_node(state: EmailAgentState) -> dict:
    """Generate response to customer email.

    Args:
        state: Current workflow state

    Returns:
        Updated state dict with generated response
    """
    try:
        email_id = state.get("email_id")
        subject = state.get("subject", "")
        body = state.get("body", "")
        category = state.get("category", "other")
        priority = state.get("priority", "medium")
        context_summary = state.get("context_summary", "")
        response_attempt = state.get("response_attempt") or 0

        logger.info(f"Generating response for email {email_id} (attempt {response_attempt + 1})")

        # llm_service = LLMService(provider="openai")
        llm_service = LLMService(provider="ollama")

        # Generate response
        response_result = await llm_service.generate_response(
            subject=subject,
            body=body,
            category=category,
            priority=priority,
            context=context_summary,
        )

        response_text = response_result.get("response_text")
        tokens_used = response_result.get("tokens_used", 0)
        model_used = response_result.get("model_used", "gpt-4-turbo-preview")
        error = response_result.get("error")

        if error:
            logger.error(f"Response generation error: {error}")

            if response_attempt < 2:
                # Retry
                logger.info(f"Retrying response generation...")
                return {
                    "response_attempt": response_attempt + 1,
                    "generated_response": None,
                }
            else:
                # Max retries exceeded
                return {
                    "error_message": f"Response generation failed after {response_attempt + 1} attempts: {error}",
                    "generated_response": None,
                    "needs_human_review": True,
                    "review_reason": "Response generation failed",
                }

        # Validate response length
        if not response_text or len(response_text) < 50:
            logger.warning("Generated response too short")
            if response_attempt < 2:
                return {"response_attempt": response_attempt + 1, "generated_response": None}
            return {
                "error_message": "Generated response too short",
                "needs_human_review": True,
                "review_reason": "Invalid response generation",
            }

        logger.info(f"Response generated successfully ({tokens_used} tokens)")

        return {
            "generated_response": response_text,
            "response_subject": f"Re: {subject}",
            "tokens_used": tokens_used,
            "model_used": model_used,   
            "response_attempt": response_attempt + 1,
        }

    except Exception as e:
        logger.error(f"Error in response_generation: {str(e)}", exc_info=True)
        response_attempt = state.get("response_attempt") or 0

        if response_attempt < 2:
            return {"response_attempt": response_attempt + 1}

        return {
            "error_message": f"Response generation error: {str(e)}",
            "generated_response": None,
        }
