# server_side\core\config.py
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables (.env)"""

    # API / Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    ENV: str = "development"

    # OpenAI / LLM API keys
    OPENAI_API_KEY: str
    OLLAMA_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # LangChain
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "customer-support-email-agent"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OLLAMA_EMBEDDING_MODEL: str = "embeddinggemma:300m"

    # Email
    IMAP_SERVER: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    EMAIL_ADDRESS: str
    EMAIL_PASSWORD: str
    EMAIL_FROM_NAME: str = "Customer Support"
    EMAIL_ENABLE_HEALTH_CHECK: bool = True
    EMAIL_STRICT_STARTUP_CHECK: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./customer_support.db"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # Email processing
    EMAIL_CHECK_INTERVAL: int = 30
    MAX_EMAILS_PER_BATCH: int = 10
    EMAIL_RESPONSE_TIMEOUT: int = 300 # If an email reply is not ready in 5 minutes, stop waiting and mark it as failed or retry
    WORKFLOW_TIMEOUT_SECONDS: int = 300 # The entire customer support pipeline must finish within 30 seconds, or we cancel it.
    EMAIL_RETRY_FAILED: bool = False
    EMAIL_FETCH_DAYS_BACK: int = 1 # Only check emails that arrived in the last 24 hours.
    FOLLOWUP_WORKER_INTERVAL_SECONDS: int = 120
    FOLLOWUP_STALE_TIMEOUT_SECONDS: int = 900
    FOLLOWUP_MAX_RETRIES: int = 3
    FOLLOWUP_RETRY_BASE_SECONDS: int = 60
    FOLLOWUP_ALERT_WEBHOOK_URL: Optional[str] = None
    FOLLOWUP_FAILURE_RATE_ALERT_THRESHOLD: float = 0.25
    FOLLOWUP_RETRY_QUEUE_ALERT_THRESHOLD: int = 20
    FOLLOWUP_ALERT_COOLDOWN_SECONDS: int = 300

    # LLM request timeouts
    OLLAMA_TIMEOUT_SECONDS: int = 120

    # Vector store
    VECTOR_STORE_PATH: str = "./data/vectors"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

# Global instance
settings = Settings()  # type: ignore[call-arg]

os.environ["LANGCHAIN_TRACING_V2"] = "false"
settings.LANGCHAIN_TRACING_V2 = False