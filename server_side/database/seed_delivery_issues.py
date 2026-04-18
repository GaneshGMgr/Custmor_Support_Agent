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


def seed_delivery_issues():
    db = SessionLocal()

    try:
        print("Seeding Delivery Issues KB entries...")

        # 1
        insert_entry(
            db,
            title="Delayed Shipment Handling",
            content="""
If delivery is delayed:
- Check order processing status (1–3 business days)
- Verify shipping carrier tracking updates
- Consider peak season delays (5–7 extra days)
- Escalate if delay exceeds estimated window
""",
            category="delivery_issues"
        )

        # 2
        insert_entry(
            db,
            title="Order Not Shipped Yet Investigation",
            content="""
If order is not shipped:
- Confirm payment was successfully processed
- Check inventory availability
- Verify processing time (usually 2–3 business days)
- Escalate if no movement after expected time
""",
            category="delivery_issues"
        )

        # 3
        insert_entry(
            db,
            title="Wrong Item Delivery Resolution",
            content="""
If wrong item is received:
- Compare SKU with order details
- Request customer photos for verification
- Arrange replacement shipment immediately
- Provide prepaid return label
""",
            category="delivery_issues"
        )

        # 4
        insert_entry(
            db,
            title="Missing Package Investigation",
            content="""
If package is marked delivered but missing:
- Check with neighbors or reception
- Verify delivery timestamp and location
- Initiate carrier investigation
- Issue refund or replacement after confirmation
""",
            category="delivery_issues"
        )

        # 5
        insert_entry(
            db,
            title="Tracking Not Updating Issue",
            content="""
If tracking is not updating:
- Wait up to 24 hours after shipment
- Check carrier website directly
- Escalate if no update after 48 hours
""",
            category="delivery_issues"
        )

        # 6
        insert_entry(
            db,
            title="Damaged Package Handling",
            content="""
If package arrives damaged:
- Request photos of packaging and product
- Ensure customer keeps original packaging
- File carrier damage claim
- Offer replacement or refund
""",
            category="delivery_issues"
        )

        # 7
        insert_entry(
            db,
            title="International Shipping Delay Explanation",
            content="""
For international orders:
- Delivery may take 10–30 business days
- Customs clearance may cause delays
- Tracking updates may be inconsistent
- Escalate if beyond estimated delivery window
""",
            category="delivery_issues"
        )

        # 8
        insert_entry(
            db,
            title="Shipping Carrier Escalation Process",
            content="""
If carrier issue persists:
- Open formal carrier investigation
- Provide tracking number and order ID
- Monitor case until resolution
- Update customer at each milestone
""",
            category="delivery_issues"
        )

        # 9
        insert_entry(
            db,
            title="Lost Package Resolution Policy",
            content="""
If package is lost:
- Confirm last tracking scan location
- Initiate investigation with carrier
- Declare loss after carrier confirmation
- Issue replacement or refund
""",
            category="delivery_issues"
        )

        # 10
        insert_entry(
            db,
            title="Shipping Time Expectations Guide",
            content="""
Standard shipping times:
- Standard: 3–5 business days
- Expedited: 1–2 business days
- International: 10–30 business days
- Processing time not included in delivery time
""",
            category="delivery_issues"
        )

        db.commit()
        print("Delivery Issues seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error while seeding delivery issues: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_delivery_issues()


# python server_side/database/seed_delivery_issues.py