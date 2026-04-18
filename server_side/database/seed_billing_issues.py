from server_side.database.connection import SessionLocal
from server_side.database.models import KnowledgeBaseEntry
from datetime import datetime


def insert_entry(db, title, content, category, source_type="seed"):
    entry = KnowledgeBaseEntry(
        title=title,
        content=content,
        category=category,
        source_type=source_type,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(entry)
    return entry


def seed_billing_issues():
    db = SessionLocal()

    try:
        print("Seeding Billing Issues KB entries...")

        # 1
        insert_entry(
            db,
            title="Duplicate Charge Investigation Process",
            content="""
If a customer reports a duplicate charge:
- Check transaction history carefully
- Verify subscription cycle and renewal dates
- Identify pending authorization holds
- Confirm whether both charges are real or pending
- Refund confirmed duplicates immediately
""",
            category="billing_issues"
        )

        # 2
        insert_entry(
            db,
            title="Incorrect Billing Amount Analysis",
            content="""
If the charged amount is unexpected:
- Review invoice breakdown
- Check for taxes, fees, or currency conversion
- Verify shipping or add-on charges
- Compare with order confirmation
""",
            category="billing_issues"
        )

        # 3
        insert_entry(
            db,
            title="Refund Processing Guidelines",
            content="""
Refund processing rules:
- Card payments: 5–10 business days
- Wallet payments: 2–5 business days
- Bank transfers: 5–14 business days
- Always provide refund reference ID
""",
            category="billing_issues"
        )

        # 4
        insert_entry(
            db,
            title="Payment Failure Troubleshooting",
            content="""
If payment fails:
- Verify card details (number, expiry, CVV)
- Ensure sufficient balance
- Check bank restrictions on online payments
- Retry with different payment method
""",
            category="billing_issues"
        )

        # 5
        insert_entry(
            db,
            title="Subscription Billing Cycle Explanation",
            content="""
Subscription billing:
- Charges occur based on selected billing cycle
- Monthly or annual plans auto-renew
- Renewal date shown in account settings
- Cancel before renewal to avoid charges
""",
            category="billing_issues"
        )

        # 6
        insert_entry(
            db,
            title="Invoice Request Handling",
            content="""
For invoice requests:
- Verify order ID and billing email
- Retrieve invoice from billing system
- Include tax breakdown if required
- Send updated invoice within 24 hours
""",
            category="billing_issues"
        )

        # 7
        insert_entry(
            db,
            title="Chargeback Dispute Handling",
            content="""
If a chargeback is raised:
- Collect transaction evidence
- Provide order timeline and proof of delivery
- Coordinate with payment gateway
- Note: account may be restricted during dispute
""",
            category="billing_issues"
        )

        # 8
        insert_entry(
            db,
            title="Currency Conversion Fee Explanation",
            content="""
If currency conversion is involved:
- Bank may apply conversion fees
- Exchange rates vary by provider
- Final charged amount may differ slightly from order total
""",
            category="billing_issues"
        )

        # 9
        insert_entry(
            db,
            title="Failed Refund Investigation",
            content="""
If refund not received:
- Check original transaction reference
- Verify bank processing time
- Confirm refund status in payment gateway
- Escalate if delay exceeds expected window
""",
            category="billing_issues"
        )

        # 10
        insert_entry(
            db,
            title="Billing Support Priority Rules",
            content="""
Billing priority handling:
- Duplicate charges → high priority
- Failed payments → medium priority
- Invoice requests → standard priority
- Disputes → critical escalation
""",
            category="billing_issues"
        )

        db.commit()
        print("Billing Issues seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error while seeding billing issues: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_billing_issues()

# python server_side/database/seed_billing_issues.py