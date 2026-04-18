# server_side\core\yaml_config.py
from pathlib import Path
import yaml
from server_side.core.logger import logger as log
from server_side.core.custom_exception import ConfigMissingException, CustomerSupportException

def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def load_yaml_config(config_path: str = None) -> dict:
    """Load structured config from YAML (models, embeddings, etc.)"""
    try:
        path = Path(config_path or _project_root() / "config" / "configuration.yaml")
        if not path.exists():
            log.error("Configuration file not found", path=str(path))
            raise ConfigMissingException(f"Config file not found at: {path}", config_name=str(path))

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        top_keys = list(config.keys()) if isinstance(config, dict) else []
        log.info("YAML configuration loaded successfully", path=str(path), keys=top_keys)
        return config

    except ConfigMissingException:
        raise
    except Exception as e:
        log.error("Error loading YAML configuration", error=str(e))
        raise CustomerSupportException("Failed to load YAML configuration", error_details=e)

# Standalone test
if __name__ == "__main__":
    config = load_yaml_config()
    print(config)