# server_side/nodes/followup_scheduling.py

"""Follow-up scheduling node - schedules follow-up actions if needed."""

from datetime import datetime, timedelta, timezone

from server_side.core.logger import logger
from server_side.graph.state import EmailAgentState
from server_side.database.models import FollowUpTypeEnum, EmailStatusEnum
from server_side.services.database import DatabaseService


async def followup_scheduling_node(state: EmailAgentState) -> dict:
    """Schedule follow-up actions based on email category and priority."""

    try:
        email_id = state.get("email_id")
        category = (state.get("category") or "other").lower()
        priority = (state.get("priority") or "medium").lower()
        status = state.get("status", EmailStatusEnum.RESPONDED.value)

        # Step 1: Only run after response is generated
        if status != EmailStatusEnum.RESPONDED.value:
            logger.debug(f"Email {email_id} not responded, skipping follow-up")
            return {"followup_scheduled": False}

        logger.info(f"Scheduling follow-ups for email {email_id}")

        db_service = DatabaseService()
        followup_scheduled = False


        # STEP 2: PRIORITY OVERRIDE RULE (highest priority wins)
        if priority in ["urgent", "high"]:
            scheduled_for = datetime.now(timezone.utc) + timedelta(hours=24)

            await db_service.create_followup(
                email_id=email_id,
                followup_type=FollowUpTypeEnum.REMINDER,
                scheduled_for=scheduled_for,
            )

            logger.info(f"[PRIORITY RULE] 24h follow-up for email {email_id}")
            return {"followup_scheduled": True}


        # STEP 3: CATEGORY-BASED RULES
        category_rules = {
            "billing": (48, FollowUpTypeEnum.VERIFICATION),
            "technical_support": (12, FollowUpTypeEnum.REMINDER),
            "complaint": (24, FollowUpTypeEnum.ESCALATION),
            "api_errors": (24, FollowUpTypeEnum.REMINDER),
            "password_reset": (24, FollowUpTypeEnum.REMINDER),
            "other": (36, FollowUpTypeEnum.REMINDER),
        }

        if category in category_rules:
            hours, followup_type = category_rules[category]

            scheduled_for = datetime.now(timezone.utc) + timedelta(hours=hours)

            await db_service.create_followup(
                email_id=email_id,
                followup_type=followup_type,
                scheduled_for=scheduled_for,
            )

            logger.info(
                f"[CATEGORY RULE] {category} follow-up scheduled for email {email_id}"
            )

            return {"followup_scheduled": True}


        # STEP 4: FALLBACK RULE (safety net)
        scheduled_for = datetime.now(timezone.utc) + timedelta(hours=48)

        await db_service.create_followup(
            email_id=email_id,
            followup_type=FollowUpTypeEnum.REMINDER,
            scheduled_for=scheduled_for,
        )

        logger.info(f"[FALLBACK RULE] Default follow-up for email {email_id}")

        followup_scheduled = True

        logger.info(f"Follow-up scheduling complete for email {email_id}")

        return {"followup_scheduled": followup_scheduled}

    except Exception as e:
        logger.error(f"Error in followup_scheduling: {str(e)}", exc_info=True)
        return {
            "error_message": f"Follow-up scheduling error: {str(e)}",
            "followup_scheduled": False,
        }