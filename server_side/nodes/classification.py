# server_side\nodes\classification.py
from server_side.core.logger import logger

from server_side.graph.state import EmailAgentState
from server_side.services.llm_model import LLMService
from server_side.services.database import DatabaseService
from server_side.database.models import EmailStatusEnum


LOW_CONFIDENCE_THRESHOLD = 0.5
UNKNOWN_CATEGORIES = {"", "unknown", "unclassified", "uncategorized", "none", "null", "n/a"}
AUTOMATED_SENDER_PATTERNS = (
    "noreply", "no-reply", "mailer-daemon", "notifications-", "do-not-reply",
    "mail-noreply", "classroom.google.com", "linkedin.com"
)
KNOWN_CATEGORIES = {"product_inquiry", "billing", "technical_support", "delivery_issues", "complaint", "feedback", "password_reset", "api_errors"}


def detect_delivery_keywords(subject: str, body: str) -> bool:
    """Detect if email contains delivery-related keywords.
    
    Args:
        subject: Email subject line
        body: Email body text
        
    Returns:
        True if delivery keywords are found, False otherwise
    """
    keywords = [
        "delay", "delivery", "shipping", "package", 
        "tracking", "courier", "dispatch", "order", 
        "arrived", "transit", "shipment"
    ]
    text = (subject + " " + body).lower()
    return any(kw in text for kw in keywords)


def infer_category_by_keywords(subject: str, body: str) -> str | None:
    """Infer a category from deterministic keyword rules when LLM output is weak."""
    text = (subject + " " + body).lower()

    category_keywords = {
        "billing": [
            "charged twice", "duplicate charge", "double charge", "billing", "invoice",
            "refund", "payment", "subscription", "transaction", "extra charge",
        ],
        "password_reset": [
            "forgot password", "reset password", "cannot login", "can't login",
            "account locked", "2fa", "two-factor", "otp",
        ],
        "api_errors": [
            "api", "integration", "webhook", "401", "403", "429", "500", "502", "503",
            "timeout", "bad request", "endpoint",
        ],
        "delivery_issues": [
            "delivery", "shipping", "tracking", "package", "courier", "shipment", "order not arrived",
        ],
        "technical_support": [
            "bug", "error", "not working", "crash", "issue", "technical", "exception",
        ],
        "complaint": [
            "not happy", "frustrating", "disappointed", "unacceptable", "poor service", "complaint",
        ],
        "feedback": [
            "suggestion", "feature request", "feedback", "recommend", "improve",
        ],
        "product_inquiry": [
            "price", "pricing", "plan", "feature", "specification", "how does", "what is",
        ],
    }

    for category_name, keywords in category_keywords.items():
        if any(keyword in text for keyword in keywords):
            return category_name

    return None


async def classification_node(state: EmailAgentState) -> dict[str, object]:
    """Classify email and assess priority.

    Args:
        state: Current workflow state

    Returns:
        Updated state dict with classification results
    """
    try:
        subject = state.get("subject", "")
        body = state.get("body", "")
        sender = str(state.get("sender", "") or "")
        email_id = state.get("email_id")

        if email_id is None:
            raise ValueError("email_id is required for classification")

        logger.info(f"Classifying email {email_id}")

        llm_service = LLMService(provider="ollama")

        # Classify email
        classification_result = await llm_service.classify_email(subject, body)
        raw_category = str(classification_result.get("category", "") or "").strip()
        category = raw_category.lower() if raw_category else "other"
        confidence = float(classification_result.get("confidence_score", 0.0) or 0.0)

        # Assess priority
        priority_result = await llm_service.assess_priority(body)
        priority = priority_result.get("priority", "medium")

        logger.info(f"Email classified as {category} (confidence: {confidence}) - Priority: {priority}")

        # Store classification in database
        db_service = DatabaseService()
        await db_service.update_email_classification(email_id, category, confidence, priority)

        sender_lower = sender.lower()

        # RULE 1: Only skip emails from automated/system senders
        is_automated_sender = any(pattern in sender_lower for pattern in AUTOMATED_SENDER_PATTERNS)
        
        if is_automated_sender:
            skip_reason = f"Skipping automated email from {sender}"
            await db_service.update_email_status(
                email_id,
                EmailStatusEnum.SKIPPED,
                error_msg=skip_reason,
            )
            logger.info("Email {} {}", email_id, skip_reason)
            return {
                "category": category,
                "priority": priority,
                "confidence_score": confidence,
                "skip_email": True,
                "skip_reason": skip_reason,
                "status": EmailStatusEnum.SKIPPED.value,
            }

        # RULE 2: Check for high-confidence known categories or good confidence threshold
        is_known_category = category in KNOWN_CATEGORIES
        is_high_confidence = confidence >= LOW_CONFIDENCE_THRESHOLD
        
        # Route if it's a known category with sufficient confidence
        if is_known_category and is_high_confidence:
            logger.info(f"Email {email_id} classified as {category} with confidence {confidence} - routing through full workflow")
            return {
                "category": category,
                "priority": priority,
                "confidence_score": confidence,
            }
        
        # RULE 3: If category is uncertain, apply deterministic keyword fallback.
        if category == "other" or not is_known_category or not is_high_confidence:
            if detect_delivery_keywords(subject, body):
                logger.info(f"Email {email_id} contains delivery keywords - overriding to delivery_issues")
                # Update database with corrected category
                await db_service.update_email_classification(email_id, "delivery_issues", 0.95, priority)
                return {
                    "category": "delivery_issues",
                    "priority": priority,
                    "confidence_score": 0.95,
                }

            inferred_category = infer_category_by_keywords(subject, body)
            if inferred_category:
                logger.info(
                    f"Email {email_id} matched keyword fallback category {inferred_category} - overriding classification"
                )
                await db_service.update_email_classification(email_id, inferred_category, 0.9, priority)
                return {
                    "category": inferred_category,
                    "priority": priority,
                    "confidence_score": 0.9,
                }
        
        # RULE 4: Truly unclassifiable emails go to human review
        is_unknown_category = category in UNKNOWN_CATEGORIES
        is_unclassified = category == "other" or is_unknown_category or not is_known_category
        
        if is_unclassified:
            review_note = f"Routing unclassified email to human review: {subject}"
            logger.info(review_note)
            await db_service.update_email_status(
                email_id,
                EmailStatusEnum.AWAITING_REVIEW,
                error_msg=review_note,
            )
            return {
                "category": category,
                "priority": priority,
                "confidence_score": confidence,
                "needs_human_review": True,
                "review_reason": review_note,
                "generated_response": "This email has been routed to our support team for review and will be addressed shortly.",
                "status": EmailStatusEnum.AWAITING_REVIEW.value,
            }

        # Known categories continue through full workflow
        return {
            "category": category,
            "priority": priority,
            "confidence_score": confidence,
        }

    except Exception as e:
        logger.error(f"Error in classification: {str(e)}", exc_info=True)
        return {
            "error_message": f"Classification failed: {str(e)}",
            "category": "other",
            "priority": "medium",
            "confidence_score": 0.0,
        }
