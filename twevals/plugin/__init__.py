"""Twevals Claude Code plugin module.

This module contains the plugin files that can be installed
into a repository or globally for Claude Code.
"""

from pathlib import Path
import shutil

PLUGIN_DIR = Path(__file__).parent


def get_plugin_dir() -> Path:
    """Get the path to the plugin directory."""
    return PLUGIN_DIR


def install_plugin(target_dir: Path) -> None:
    """Install the twevals plugin to the target directory.

    Args:
        target_dir: The directory to install the plugin to.
                   Should be .claude/plugins/twevals/ or similar.
    """
    # Ensure target exists
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy plugin contents
    for item in PLUGIN_DIR.iterdir():
        if item.name == "__init__.py" or item.name == "__pycache__":
            continue

        dest = target_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
