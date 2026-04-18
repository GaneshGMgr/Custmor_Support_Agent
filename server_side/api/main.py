# server_side/api/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio

from server_side.api.routes import health_routes, email_routes, followup_routes, ui_routes
from server_side.core.config import settings
from server_side.core.logger import logger, setup_logging
from server_side.database.connection import init_db
from server_side.graph.workflow import create_workflow
from server_side.nodes.factory import get_all_nodes
from server_side.services.email import EmailService
from server_side.services.followup_worker import process_due_followups
from server_side.services.ingestion import poll_inbox, reprocess_stuck_emails
from server_side.services.schedule import SchedulerService
import uvicorn

# Setup logging
setup_logging()

# Base directory (important for production-safe paths)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Paths
TEMPLATES_DIR = BASE_DIR / "client_side" / "templates"
STATIC_DIR = BASE_DIR / "client_side" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle"""
    scheduler = None
    try:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized")

        logger.info("Loading vector knowledge base...")
        from server_side.services.vector_kb import VectorKBService
        vector_kb = VectorKBService()
        await vector_kb.initialize()
        loaded = await vector_kb.load_knowledge_base_from_files()
        logger.info(f"Vector KB ready: {loaded} documents loaded")
        app.state.vector_kb = vector_kb

        if settings.EMAIL_ENABLE_HEALTH_CHECK:
            logger.info("Checking email connectivity (IMAP/SMTP)...")
            email_service = EmailService()
            email_health = await email_service.health_check()
            if email_health.get("status") != "healthy":
                message = f"Email service is unhealthy at startup: {email_health}"
                if settings.EMAIL_STRICT_STARTUP_CHECK:
                    raise RuntimeError(message)
                logger.warning(message)
                logger.warning(
                    "Continuing startup because EMAIL_STRICT_STARTUP_CHECK is disabled. "
                    "Email send/receive operations may fail until credentials are fixed."
                )
                logger.info("Email connectivity check completed with issues")
            else:
                logger.info("Email connectivity verified")
        else:
            logger.warning(
                "Skipping startup email connectivity check because "
                "EMAIL_ENABLE_HEALTH_CHECK is disabled."
            )

        logger.info("Building workflow...")
        nodes = get_all_nodes()
        app.state.workflow = create_workflow(nodes)
        logger.info("Workflow initialized")

        logger.info("Starting scheduler...")
        scheduler = SchedulerService()
        await scheduler.start()
        scheduler.add_job(
            poll_inbox,
            interval=settings.EMAIL_CHECK_INTERVAL,
            args=[app],
            job_id="poll-inbox-job",
        )
        scheduler.add_job(
            process_due_followups,
            interval=settings.FOLLOWUP_WORKER_INTERVAL_SECONDS,
            args=[app],
            job_id="followup-worker-job",
        )
        app.state.scheduler = scheduler
        logger.info("Scheduler initialized")

        logger.info("Scheduling initial inbox poll as background task...")
        asyncio.ensure_future(poll_inbox(app))
        logger.info("Initial inbox poll scheduled")

        logger.info("Running one-time reprocess of stuck processing emails...")
        await reprocess_stuck_emails(app)
        logger.info("One-time stuck email reprocess completed")

        yield

    except Exception as e:
        logger.opt(exception=True).error("Startup error")
        logger.error("Startup details: {}", str(e).replace("{", "{{").replace("}", "}}"))
        raise
    finally:
        logger.info("Shutting down application...")
        if scheduler is not None:
            try:
                await scheduler.stop()
            except Exception as e:
                logger.error("Failed to stop scheduler cleanly: {}", str(e))


def create_app() -> FastAPI:
    """Create and configure FastAPI app"""

    app = FastAPI(
        title="Customer Support Email Agent",
        description="LangGraph-based intelligent customer support system",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Static files (CSS, JS, images)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Templates
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    def _url_for(endpoint_name: str, **path_params):
        # Support Flask-style filename= for static templates.
        if "filename" in path_params and "path" not in path_params:
            path_params["path"] = path_params.pop("filename")
        return app.url_path_for(endpoint_name, **path_params)

    env.globals["url_for"] = _url_for
    app.state.templates = env

    # Routers
    app.include_router(health_routes.router)
    app.include_router(email_routes.router)
    app.include_router(followup_routes.router)
    app.include_router(followup_routes.dev_router)
    app.include_router(ui_routes.router)

    # Root redirect
    @app.get("/", response_class=RedirectResponse)
    async def root():
        return RedirectResponse(url="/ui/test")

    return app


# Create app instance
app = create_app()


# -----------------------------
# CLI entry point for customerSupportBot
# -----------------------------
def main():
    """Run the FastAPI app using Uvicorn"""
    uvicorn.run(
        "server_side.api.main:app",  # points to the app instance above
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )


# customerSupportBot: start the Customer Support Agent server with a single command — no need to type the full "uvicorn server_side.api.main:app --reload" command; just run customerSupportBot.