"""Twevals Claude Skill module.

This module contains the SKILL.md file that can be installed
into a repository or globally for Claude Code.
"""

from pathlib import Path

SKILL_DIR = Path(__file__).parent
SKILL_FILE = SKILL_DIR / "SKILL.md"


def get_skill_content() -> str:
    """Get the content of the twevals SKILL.md file."""
    return SKILL_FILE.read_text()


def get_skill_path() -> Path:
    """Get the path to the SKILL.md file."""
    return SKILL_FILE
