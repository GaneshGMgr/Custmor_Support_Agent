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


def seed_api_errors():
    db = SessionLocal()

    try:
        print("Seeding API Errors KB entries...")

        # 1
        insert_entry(
            db,
            title="API Authentication Failure Troubleshooting",
            content="""
If API authentication fails:
- Verify API key is active
- Ensure correct Authorization header format (Bearer token)
- Check environment mismatch (test vs production)
- Regenerate API key if expired
""",
            category="api_errors"
        )

        # 2
        insert_entry(
            db,
            title="Invalid API Key Handling",
            content="""
If API key is invalid:
- Confirm key is copied correctly
- Check for extra spaces or missing characters
- Ensure key has not been revoked
- Generate a new key if needed
""",
            category="api_errors"
        )

        # 3
        insert_entry(
            db,
            title="Rate Limit Exceeded Handling",
            content="""
When rate limit is exceeded:
- Reduce request frequency
- Add retry with exponential backoff
- Cache frequent API responses
- Monitor usage quota regularly
""",
            category="api_errors"
        )

        # 4
        insert_entry(
            db,
            title="HTTP 500 Server Error Handling",
            content="""
For server errors (500):
- Retry request after short delay
- Check system status page
- Log request ID for debugging
- Avoid repeated rapid retries
""",
            category="api_errors"
        )

        # 5
        insert_entry(
            db,
            title="Bad Request (400) Fix Guide",
            content="""
If you receive a 400 error:
- Validate request parameters
- Ensure required fields are included
- Check JSON format validity
- Refer to API documentation
""",
            category="api_errors"
        )

        # 6
        insert_entry(
            db,
            title="Unauthorized Access (401) Resolution",
            content="""
If you get 401 Unauthorized:
- Check API key validity
- Ensure correct authentication method
- Verify token expiration
- Confirm correct environment usage
""",
            category="api_errors"
        )

        # 7
        insert_entry(
            db,
            title="Forbidden Access (403) Troubleshooting",
            content="""
For 403 errors:
- Verify account permissions
- Ensure API key has required scopes
- Check endpoint access restrictions
- Contact admin if access is missing
""",
            category="api_errors"
        )

        # 8
        insert_entry(
            db,
            title="Timeout Error Handling Strategy",
            content="""
If request times out:
- Increase timeout settings
- Retry after short delay
- Check network stability
- Break large requests into smaller ones
""",
            category="api_errors"
        )

        # 9
        insert_entry(
            db,
            title="Webhook Delivery Failure Fix",
            content="""
If webhook is not received:
- Ensure endpoint is publicly accessible
- Verify 200 OK response is returned
- Check server logs for errors
- Retry event delivery manually
""",
            category="api_errors"
        )

        # 10
        insert_entry(
            db,
            title="API Integration Debugging Guide",
            content="""
For integration issues:
- Validate base URL and version
- Check required headers
- Test using Postman or curl
- Review API logs for errors
""",
            category="api_errors"
        )

        db.commit()
        print("API Errors seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error while seeding API errors: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_api_errors()


# python server_side/database/seed_api_errors.py