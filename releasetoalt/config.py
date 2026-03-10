import json
import os
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "releasetoalt"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"

def get_default_config() -> Dict[str, Any]:
    return {
        "global": {
            "main_account": None,
            "alt_account": None,
            "new_name": None,
            "new_email": None
        },
        "repos": {}
    }

def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load configuration from file."""
    if not path.exists():
        return get_default_config()
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure basic structure
            if "global" not in data:
                data["global"] = {}
            if "repos" not in data:
                data["repos"] = {}
            return data
    except Exception as e:
        print(f"Error loading config at {path}: {e}")
        return get_default_config()

def save_config(config: Dict[str, Any], path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save configuration to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def get_repo_config(config: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
    """Retrieve config for a specific repository."""
    return config.get("repos", {}).get(repo_name, {
        "whitelist": [],
        "blacklist": [],
        "visibility": "private"  # 'public' or 'private'
    })

def update_repo_config(config: Dict[str, Any], repo_name: str, repo_config: Dict[str, Any]) -> None:
    """Update config for a specific repository without saving."""
    if "repos" not in config:
        config["repos"] = {}
    config["repos"][repo_name] = repo_config
