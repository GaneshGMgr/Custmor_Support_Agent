#!/usr/bin/env python
"""Fix the prompts file by reconstructing it correctly."""

prompts_content = '''"""
LLM Prompt Templates

This module contains prompt templates for different tasks in the email processing workflow.
"""

# System prompts
SYSTEM_PROMPT_CUSTOMER_SUPPORT = """You are an expert customer support representative with extensive knowledge of customer service best practices.
You respond to customer emails with professionalism, empathy, and clarity.
Your responses should be concise, helpful, and address the customer's concerns thoroughly.
Always maintain a courteous and respectful tone, even with complaints."""

# Email classification
EMAIL_CLASSIFICATION_PROMPT = """Analyze the following customer support email and classify it into ONE of these categories:
- product_inquiry: Questions about product features or specifications
- billing: Issues related to billing or payment
- technical_support: Technical problems or bugs
- delivery_issues: Shipping, delivery delays, damaged packages, tracking problems
- complaint: Complaints or negative feedback
- feedback: General feedback or suggestions
- password_reset: Account access, password reset, login issues
- api_errors: API errors, integration issues, technical API problems
- other: Anything else

Email Subject: {subject}
Email Body:
{email_body}

Return valid JSON only in this exact schema:
{"category":"<one_of_allowed_categories>","confidence_score":<float_0_to_1>}

Rules:
- category must be one of: product_inquiry, billing, technical_support, delivery_issues, complaint, feedback, password_reset, api_errors, other
- confidence_score must be a number between 0.0 and 1.0
- No markdown, no explanations, no extra keys"""

# Email Priority assessment
EMAIL_PRIORITY_PROMPT = """Assess the urgency and priority of this customer support email based on:
1. Use of urgent/critical keywords (fire, down, broken, help, urgent, asap)
2. Impact on business (revenue loss, system down, multiple users affected)
3. Customer tone (frustrated, angry, threatening)
4. Number of exclamation marks and capitalization

Priority levels: low, medium, high, urgent

Email:
{email_body}

Respond with ONLY the priority level (low/medium/high/urgent), nothing else."""

# Context assessment
CONTEXT_ASSESSMENT_PROMPT = """Based on the customer's current email and their history, assess if this requires human review.
Consider:
1. Ambiguity in the email
2. Potential for escalation
3. Complexity of the issue
4. Customer sentiment

Current Email:
{current_email}

Customer History:
{customer_history}

Respond with only "yes" or "no". Answer "yes" if human review is strongly recommended."""

# Response generation
RESPONSE_GENERATION_PROMPT = """You are a helpful customer support agent. Generate a professional response to this customer email.

IMPORTANT INSTRUCTIONS:
1. Address the specific concern in the email
2. Use the provided knowledge base information when relevant
3. Be empathetic and professional
4. Provide clear action items or next steps
5. Keep response concise (100-300 words)
6. Sign off professionally using exactly {support_team_name}
7. Do not use placeholders like [Your Name] or [Company Name]

Email Category: {classification}
Priority Level: {priority}
Support Team Name: {support_team_name}

Customer Email:
Subject: {subject}
Body:
{email_body}

{context}

Generate only the response body text, no subject line."""

# Follow-up recommendation
FOLLOWUP_PROMPT = """Based on this customer email and the response, should we schedule a follow-up?
Consider:
1. If the issue is likely to require verification
2. If the customer needs time to implement a solution
3. If this is a critical issue needing status updates

Email Category: {classification}
Issue: {email_body}

Respond with JSON: {{"schedule_followup": true/false, "days": number_if_true, "reason": "brief reason"}}"""
'''

with open('server_side/prompts/prompt_templets.py', 'w', encoding='utf-8') as f:
    f.write(prompts_content)

print("✓ Prompts file fixed successfully")
