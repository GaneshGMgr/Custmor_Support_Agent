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


def seed_password_reset():
    db = SessionLocal()

    try:
        print("Seeding Password Reset KB entries...")

        # 1
        insert_entry(
            db,
            title="Password Reset Email Not Received",
            content="""
If reset email is not received:
- Check spam or junk folder
- Confirm correct registered email
- Wait 5–10 minutes for delivery delay
- Request a new reset link
""",
            category="password_reset"
        )

        # 2
        insert_entry(
            db,
            title="Reset Link Expired Handling",
            content="""
If reset link expired:
- Reset links are time-limited for security
- Request a new password reset email
- Use link immediately after receiving
""",
            category="password_reset"
        )

        # 3
        insert_entry(
            db,
            title="Incorrect Email Login Issue",
            content="""
If email is incorrect:
- Verify correct registered email
- Try alternative emails used during signup
- Contact support if email is unknown
""",
            category="password_reset"
        )

        # 4
        insert_entry(
            db,
            title="Account Locked Recovery Process",
            content="""
If account is locked:
- Wait 10–15 minutes before retry
- Use password reset option
- Contact support if lock persists
""",
            category="password_reset"
        )

        # 5
        insert_entry(
            db,
            title="Two-Factor Authentication Issues",
            content="""
If 2FA is not working:
- Sync device time correctly
- Use latest authentication code
- Contact support if device is lost
""",
            category="password_reset"
        )

        # 6
        insert_entry(
            db,
            title="Password Requirements Policy",
            content="""
Password rules:
- Minimum 8 characters
- Must include letters, numbers, symbols
- Avoid using personal information
- Do not reuse old passwords
""",
            category="password_reset"
        )

        # 7
        insert_entry(
            db,
            title="Unable to Login Troubleshooting",
            content="""
If unable to login:
- Check caps lock
- Clear browser cache
- Try different browser/device
- Reset password if needed
""",
            category="password_reset"
        )

        # 8
        insert_entry(
            db,
            title="Account Recovery Verification",
            content="""
For account recovery:
- Provide registered email
- Verify identity if required
- Support may request additional proof
""",
            category="password_reset"
        )

        # 9
        insert_entry(
            db,
            title="Security Best Practices",
            content="""
Security tips:
- Never share password
- Use strong unique passwords
- Enable 2FA when possible
- Log out from shared devices
""",
            category="password_reset"
        )

        # 10
        insert_entry(
            db,
            title="Login Issue Escalation Flow",
            content="""
If login issues persist:
- Collect error details
- Check authentication logs
- Escalate to security team
- Provide temporary access if needed
""",
            category="password_reset"
        )

        db.commit()
        print("Password Reset seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error while seeding password reset: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_password_reset()


# python server_side/database/seed_password_reset.py