from pathlib import Path


# Project folder structure
list_of_files = [
    # Root files
    ".env",
    ".env.example",
    ".gitignore",
    ".python-version",
    "customer_support.db",
    "fix_prompts.py",
    "folderScanner.py",
    "folderStructure.py",
    "init_setup.sh",
    "pyproject.toml",
    "README.md",
    "requirements.txt",
    "setup.py",
    "temp_test.txt",
    "uv.lock",

    # Git keep
    ".github/workflows/.gitkeep",

    # Pytest cache
    ".pytest_cache/.gitignore",
    ".pytest_cache/CACHEDIR.TAG",
    ".pytest_cache/README.md",
    ".pytest_cache/v/cache/lastfailed",
    ".pytest_cache/v/cache/nodeids",
    ".pytest_cache/v/cache/stepwise",

    # Client-side
    "client_side/static/css/style.css",
    "client_side/static/js/script.js",
    "client_side/static/media/email_workflow.png",
    "client_side/templates/base.html",
    "client_side/templates/inbox.html",
    "client_side/templates/index.html",
    "client_side/templates/test_email.html",

    # Egg info (root)
    "custmor_support_agent.egg-info/dependency_links.txt",
    "custmor_support_agent.egg-info/entry_points.txt",
    "custmor_support_agent.egg-info/PKG-INFO",
    "custmor_support_agent.egg-info/requires.txt",
    "custmor_support_agent.egg-info/SOURCES.txt",
    "custmor_support_agent.egg-info/top_level.txt",

    # Logs
    "logs/app.log",

    # Server-side API
    "server_side/__init__.py",
    "server_side/api/__init__.py",
    "server_side/api/main.py",
    "server_side/api/routes/__init__.py",
    "server_side/api/routes/email_routes.py",
    "server_side/api/routes/health_routes.py",
    "server_side/api/routes/ui_routes.py",

    # Config & Core
    "server_side/config/configuration.yaml",
    "server_side/core/__init__.py",
    "server_side/core/config.py",
    "server_side/core/constants.py",
    "server_side/core/custom_exception.py",
    "server_side/core/logger.py",
    "server_side/core/yaml_config.py",

    # Server-side egg info
    "server_side/custmor_support_agent.egg-info/dependency_links.txt",
    "server_side/custmor_support_agent.egg-info/entry_points.txt",
    "server_side/custmor_support_agent.egg-info/PKG-INFO",
    "server_side/custmor_support_agent.egg-info/requires.txt",
    "server_side/custmor_support_agent.egg-info/SOURCES.txt",
    "server_side/custmor_support_agent.egg-info/top_level.txt",

    # Data - Files
    "server_side/data/files/corrective_rag_CRAG.pdf",
    "server_side/data/files/Self_RAG.pdf",

    # Data - Knowledge Base
    "server_side/data/knowledge_base/api_errors.txt",
    "server_side/data/knowledge_base/billing_issues.txt",
    "server_side/data/knowledge_base/delivery_issues.txt",
    "server_side/data/knowledge_base/password_reset.txt",

    # Database
    "server_side/database/connection.py",
    "server_side/database/customer_support.db",
    "server_side/database/models.py",

    # Graph
    "server_side/graph/__init__.py",
    "server_side/graph/state.py",
    "server_side/graph/workflow.py",

    # Nodes
    "server_side/nodes/__init__.py",
    "server_side/nodes/classification.py",
    "server_side/nodes/context_analysis.py",
    "server_side/nodes/email_retrieval.py",
    "server_side/nodes/error_handler.py",
    "server_side/nodes/factory.py",
    "server_side/nodes/followup_scheduling.py",
    "server_side/nodes/human_review.py",
    "server_side/nodes/response_generation.py",
    "server_side/nodes/response_sending.py",
    "server_side/nodes/review_check.py",
    "server_side/nodes/review_routing.py",

    # Prompts
    "server_side/prompts/__init__.py",
    "server_side/prompts/prompt_templets.py",

    # Schemas
    "server_side/schemas/__init__.py",
    "server_side/schemas/email.py",
    "server_side/schemas/graph.py",

    # Services
    "server_side/services/__init__.py",
    "server_side/services/base.py",
    "server_side/services/database.py",
    "server_side/services/email.py",
    "server_side/services/ingestion.py",
    "server_side/services/kb.py",
    "server_side/services/llm_model.py",
    "server_side/services/review.py",
    "server_side/services/schedule.py",
    "server_side/services/vector_kb.py",

    # Tests
    "test/test_api.py",
    "test/test_embedding.py",
    "test/test_graph.py",
    "test/test_nodes.py",
]

# Create directories and files
for filepath in list_of_files:
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)  # Create directories

    if not filepath.exists():
        filepath.touch()  # Create the file
        print(f"Created: {filepath}")
    else:
        print(f"Already exists: {filepath}")


