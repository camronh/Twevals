"""Config file management for ezvals."""

import json
from pathlib import Path

CONFIG_FILENAME = "ezvals.json"

DEFAULT_CONFIG = {
    "concurrency": 1,
    "results_dir": ".ezvals/sessions",
    "overwrite": True,
}


def get_config_path() -> Path:
    """Returns path to config file in current working directory."""
    return Path.cwd() / CONFIG_FILENAME


def load_config() -> dict:
    """Load config from file. Creates default config if not found."""
    path = get_config_path()
    if not path.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(path) as f:
        return json.load(f)


def save_config(config: dict) -> None:
    """Save config to file."""
    path = get_config_path()
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
