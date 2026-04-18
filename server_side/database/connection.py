# server_side\database\db.py

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from server_side.core.config import settings

# Create engine with appropriate configuration
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite configuration for development
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL configuration for production
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before use
        echo=settings.DEBUG,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _migrate_emails_table()
    _migrate_followups_table()


def _migrate_emails_table() -> None:
    """Best-effort schema upgrades for emails acknowledgment fields."""
    required_columns = {
        "ack_sent_at": "DATETIME",
    }

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        if "emails" not in existing_tables:
            return

        existing_cols = {col["name"] for col in inspector.get_columns("emails")}
        with engine.begin() as conn:
            for col_name, col_def in required_columns.items():
                if col_name in existing_cols:
                    continue
                conn.execute(text(f"ALTER TABLE emails ADD COLUMN {col_name} {col_def}"))

    except Exception:
        # Keep startup resilient even if migration fails; API logs will expose issues.
        pass


def _migrate_followups_table() -> None:
    """Best-effort schema upgrades for followups reliability fields."""
    required_columns = {
        "processing_since": "DATETIME",
        "retry_count": "INTEGER DEFAULT 0 NOT NULL",
        "max_retries": "INTEGER DEFAULT 3 NOT NULL",
        "next_retry_at": "DATETIME",
        "execution_key": "VARCHAR(255)",
        "simulate_failure": "BOOLEAN DEFAULT 0 NOT NULL",
        "last_error": "TEXT",
    }

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        if "followups" not in existing_tables:
            return

        existing_cols = {col["name"] for col in inspector.get_columns("followups")}
        with engine.begin() as conn:
            for col_name, col_def in required_columns.items():
                if col_name in existing_cols:
                    continue
                conn.execute(text(f"ALTER TABLE followups ADD COLUMN {col_name} {col_def}"))

            # Add index for execution guard lookups if missing.
            indexes = {idx["name"] for idx in inspector.get_indexes("followups")}
            if "idx_followups_execution_key" not in indexes:
                conn.execute(text("CREATE INDEX idx_followups_execution_key ON followups (execution_key)"))

    except Exception:
        # Keep startup resilient even if migration fails; worker logs will expose issues.
        pass


def drop_db():
    """Drop all tables (for testing)."""
    Base.metadata.drop_all(bind=engine)