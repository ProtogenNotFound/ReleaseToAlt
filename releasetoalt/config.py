import json
from pathlib import Path
from typing import Dict, Any, List, Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "releasetoalt"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"

def get_default_config() -> List[Dict[str, Any]]:
    return []

def load_config(path: Path = DEFAULT_CONFIG_PATH) -> List[Dict[str, Any]]:
    """Load configuration from file as a list of repo configs."""
    if not path.exists():
        return get_default_config()
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Migrate legacy dict format to list format
            if isinstance(data, dict):
                migrated_list = []
                global_cfg = data.get("global", {})
                repos = data.get("repos", {})
                
                for repo_name, repo_cfg in repos.items():
                    merged = {
                        "repo_name": repo_name,
                        **global_cfg,
                        **repo_cfg
                    }
                    migrated_list.append(merged)
                
                if not migrated_list and global_cfg:
                    migrated_list.append(global_cfg)
                    
                return migrated_list
                
            elif isinstance(data, list):
                return data
            else:
                return get_default_config()
    except Exception as e:
        print(f"Error loading config at {path}: {e}")
        return get_default_config()

def save_config(config: List[Dict[str, Any]], path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save configuration array to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def get_repo_config(config_list: List[Dict[str, Any]], repo_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve config for a specific repository from the list."""
    for cfg in config_list:
        if cfg.get("repo_name") == repo_name:
            return cfg
    return None

def get_global_defaults(config_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract global auth defaults from the latest item in the list."""
    defaults = {
        "main_account": None,
        "alt_account": None,
        "new_name": None,
        "new_email": None
    }
    for cfg in reversed(config_list):
        for k in defaults:
            if cfg.get(k) is not None and defaults[k] is None:
                defaults[k] = cfg[k]
    return defaults

def update_repo_config(config_list: List[Dict[str, Any]], repo_name: str, new_cfg: Dict[str, Any]) -> None:
    """Update config for a specific repository in the list."""
    new_cfg["repo_name"] = repo_name
    for i, cfg in enumerate(config_list):
        if cfg.get("repo_name") == repo_name:
            config_list[i] = new_cfg
            return
    config_list.append(new_cfg)
