# Customer Support Agent

An AI-powered customer support automation system that reads inbound emails, classifies intent and priority, generates response drafts using an LLM, supports human review when needed, sends responses, and schedules post-response follow-ups.

The project uses:
- FastAPI for API and web UI endpoints
- LangGraph for workflow orchestration
- SQLite + SQLAlchemy for persistence
- FAISS + embeddings for vector knowledge retrieval
- IMAP/SMTP for inbox polling and email sending
- APScheduler for recurring background jobs

## What This Project Does

The system continuously monitors a support inbox and processes new messages through a multi-step AI workflow:
1. Ingest incoming emails from IMAP.
2. Save each email and customer data into the database.
3. Send an intake acknowledgement once for newly ingested emails.
4. Classify email category and priority.
5. Collect context from customer history + knowledge base.
6. Generate a draft response using configured LLM provider.
7. Route to human review when required.
8. Send final response via SMTP.
9. Schedule follow-up actions based on business rules.

## High-Level Architecture

- API layer: FastAPI app and REST endpoints
- Workflow layer: LangGraph nodes and state transitions
- Service layer: email, LLM, KB, review, scheduler, follow-up worker
- Data layer: SQLAlchemy models, SQLite DB, FAISS vector index
- UI layer: Jinja templates for test page, inbox dashboard, follow-up dashboard

Core backend entry point:
- `server_side/api/main.py`

Workflow definition:
- `server_side/graph/workflow.py`

Workflow state shape:
- `server_side/graph/state.py`

## End-to-End Working Flow

### Startup lifecycle
At startup, the app:
1. Initializes DB tables.
2. Initializes vector KB service and loads `.txt` knowledge files.
3. Optionally checks IMAP/SMTP connectivity.
4. Builds LangGraph workflow and stores it in `app.state.workflow`.
5. Starts scheduler jobs:
	- inbox polling
	- follow-up worker processing
6. Schedules an immediate first inbox poll.
7. Reprocesses emails left in `processing` state from earlier runs.

### Workflow nodes (LangGraph)
Node order and routing:
1. `email_retrieval`
2. `classification`
	- may skip automated senders
	- may route to human review for uncertain/unclassified content
3. `context_analysis`
	- customer history + SQL KB + FAISS fallback
4. `response_generation`
5. `human_review`
6. `review_check`
7. `review_routing`
8. `response_sending`
9. `followup_scheduling`
10. `error_handler`

The graph image is generated to:
- `client_side/static/media/email_workflow.png`

### Review behavior
- If review decision is pending, workflow pauses.
- Once decision is submitted (`approve`/`edit`/`reject`), routing continues.
- For `approve` and `edit`, the API also attempts immediate continuation to sending.

### Follow-up behavior
Follow-ups are created only after successful response (`status=responded`).

Rules:
- Priority `urgent` or `high` -> `reminder` in 24h
- Category `billing` -> `verification` in 48h
- Category `technical_support` -> `reminder` in 12h
- Category `complaint` -> `escalation` in 24h
- Category `api_errors` -> `reminder` in 24h
- Category `password_reset` -> `reminder` in 24h
- Category `other` -> `reminder` in 36h
- Fallback -> `reminder` in 48h

## Project Structure

Top-level:
- `server_side/` backend code
- `client_side/` templates, css/js, workflow image
- `data/vectors/` vector metadata store
- `logs/` application logs
- `test/` pytest tests

Important backend modules:
- `server_side/api/` FastAPI app + routes
- `server_side/nodes/` LangGraph node logic
- `server_side/services/` integrations and domain services
- `server_side/database/` SQLAlchemy models and DB setup
- `server_side/graph/` workflow and state
- `server_side/config/` yaml configuration

## Prerequisites

- Python `>=3.12,<3.13`
- A running Ollama instance if using local models
- Valid IMAP/SMTP credentials for the inbox account

## Setup

### 1) Clone and enter project
```bash
git clone <your-repo-url>
cd Custmor_Support_Agent
```

### 2) Create and activate virtual environment
Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Git Bash:
```bash
python -m venv .venv
source .venv/Scripts/activate
```

### 3) Install dependencies
Using uv (recommended in this repo):
```bash
uv add -r requirements.txt --active
uv pip install -e .
```

Or pip:
```bash
pip install -r requirements.txt
pip install -e .
```

### 4) Create environment file
Copy `.env.example` to `.env` and set values.

Minimum required values:
```env
OPENAI_API_KEY=...
EMAIL_ADDRESS=...
EMAIL_PASSWORD=...
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
DEBUG=True
DATABASE_URL=sqlite:///./customer_support.db
VECTOR_STORE_PATH=./data/vectors
```

Note:
- Current workflow code uses Ollama in classification/response generation and vector embedding in vector KB service.
- Ensure Ollama endpoint and models in YAML config are available when running locally.

### 5) Run server
CLI entrypoint:
```bash
customerSupportBot
```

Alternative:
```bash
uvicorn server_side.api.main:app --host 0.0.0.0 --port 8000 --reload
```

## UI Pages

After server start:
- Test page: `http://localhost:8000/ui/test`
- Inbox dashboard: `http://localhost:8000/ui/inbox`
- Follow-up dashboard: `http://localhost:8000/ui/followups`

## API Overview

### Health
- `GET /health` overall health (database + email)
- `GET /health/vector-kb` vector index and metadata diagnostics

### Email processing
- `POST /api/emails/test` create test email and run workflow
- `GET /api/emails` list emails with pagination/filter
- `GET /api/emails/{email_id}` full details including response/review/follow-ups
- `POST /api/emails/{email_id}/review` submit human review decision

### Follow-up monitoring
- `GET /api/followups` list follow-ups
- `GET /api/followups/stats` aggregate stats
- `GET /api/followups/health` worker heartbeat health
- `GET /api/followups/{followup_id}` follow-up detail

### Dev follow-up endpoints (debug mode)
- `POST /api/dev/followup/create-test`
- `POST /api/dev/followup/run`
- `POST /api/dev/followup/heartbeat/ping`

## Database Entities

Main tables:
- `customers`
- `emails`
- `email_responses`
- `human_reviews`
- `review_decisions`
- `followups`
- `kb_entries`

Key email statuses:
- `pending`
- `processing`
- `awaiting_review`
- `skipped`
- `responded`
- `archived`
- `failed`

## Knowledge Base and Retrieval

The project uses a hybrid retrieval approach:
1. SQL keyword search first (`KnowledgeBaseService`).
2. If SQL relevance is weak/insufficient, fallback to FAISS semantic search (`VectorKBService`).
3. Merge and format context for response generation.

Knowledge source files:
- `server_side/data/knowledge_base/*.txt`

Vector artifacts:
- index: `data/vectors/faiss_index.bin`
- metadata: `data/vectors/documents.json`

## Running Tests

```bash
pytest -q
```

Current tests include API flow, graph behavior, nodes, and embedding-related checks under `test/`.

## Operational Notes

- Inbox polling and follow-up worker run on scheduler intervals from environment settings.
- Workflow invocation has a timeout (`WORKFLOW_TIMEOUT_SECONDS`).
- Failed processing can be retried/reprocessed depending on settings.
- New ingestion sends acknowledgement once per email row (`ack_sent_at` guard).

## Gmail SMTP 535 Fix

If SMTP send fails with:
`535 5.7.8 Username and Password not accepted`

Use this checklist:
1. Enable 2-Step Verification on the Gmail account.
2. Create a Gmail App Password.
3. Use the 16-character app password as `EMAIL_PASSWORD`.
4. Confirm:

```env
EMAIL_ADDRESS=your_gmail@gmail.com
EMAIL_PASSWORD=your_16_char_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
EMAIL_STRICT_STARTUP_CHECK=true
```

5. Restart the server.

Notes:
- Do not use your normal Gmail account password for SMTP.
- App passwords require 2-Step Verification.
- For local debugging only, `EMAIL_STRICT_STARTUP_CHECK=false` allows startup even if email auth is broken.

## Suggested Next Improvements

- Add architecture diagram + sequence diagram to README.
- Add `.env` field documentation table with defaults and meanings.
- Add migration strategy (Alembic) and seed-data scripts to onboarding section.
- Add API examples (curl/Postman) for review and follow-up routes.


