from __future__ import annotations

import json
import os
import random
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

# Word lists for generating friendly names
_ADJECTIVES = [
    "swift", "bright", "calm", "bold", "keen", "warm", "cool", "quick",
    "sharp", "gentle", "fierce", "quiet", "loud", "soft", "strong",
    "light", "dark", "fresh", "wild", "tame", "brave", "wise", "kind",
    "proud", "humble", "eager", "patient", "lively", "mellow", "vivid",
    "clever", "steady", "nimble", "silent", "golden", "silver", "ancient",
    "cosmic", "mystic", "lucid", "subtle", "radiant", "serene", "noble",
    "polar", "azure", "coral", "jade", "amber", "scarlet", "violet",
    "rustic", "sleek", "brisk", "dusky", "frosty", "hazy", "misty",
]

_NOUNS = [
    "falcon", "river", "mountain", "thunder", "whisper", "shadow", "crystal",
    "phoenix", "dragon", "tiger", "eagle", "wolf", "bear", "hawk", "raven",
    "storm", "frost", "flame", "wave", "stone", "cloud", "star", "moon",
    "forest", "meadow", "canyon", "glacier", "comet", "spark", "breeze",
    "panda", "otter", "heron", "viper", "lynx", "fox", "owl", "crane",
    "orchid", "lotus", "cedar", "maple", "birch", "oak", "pine", "willow",
    "nebula", "quasar", "nova", "aurora", "zenith", "horizon", "prism",
    "summit", "ridge", "valley", "delta", "reef", "grove", "shore",
]


def _generate_friendly_name() -> str:
    """Generate a random adjective-noun name like 'swift-falcon'."""
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"


_SAFE_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_-]")


def _sanitize_name(name: str) -> str:
    """Sanitize a name for safe use in file paths. Only allows alphanumerics, dash, underscore."""
    return _SAFE_NAME_PATTERN.sub("", name)


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent)) as tmp:
        json.dump(data, tmp, indent=2, default=str)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


@dataclass
class ResultsStore:
    base_dir: Path

    def __init__(self, base_dir: str | Path = ".ezvals/sessions") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, Lock] = {}
        # Cache mapping run_id -> (session_name, filename) for fast lookups
        self._run_id_cache: dict[str, tuple[str, str]] = {}

    def generate_run_id(self) -> str:
        """Generate a run ID using Unix timestamp."""
        return str(int(time.time()))

    def _session_dir(self, session_name: str) -> Path:
        """Get path to session directory."""
        safe_name = _sanitize_name(session_name) or "default"
        return self.base_dir / safe_name

    def _find_run_file(self, run_id: str, session_name: Optional[str] = None) -> Path:
        """Find the file for a run_id, optionally scoped to a session."""
        # Check cache first, but verify file still exists (handles renames from other instances)
        if run_id in self._run_id_cache:
            cached_session, cached_filename = self._run_id_cache[run_id]
            cached_path = self.base_dir / cached_session / cached_filename
            if cached_path.exists():
                return cached_path
            # Cache is stale, clear it and search
            del self._run_id_cache[run_id]

        # If session specified, search only that directory
        if session_name:
            session_dir = self._session_dir(session_name)
            if session_dir.exists():
                for p in session_dir.glob(f"*_{run_id}.json"):
                    self._run_id_cache[run_id] = (session_dir.name, p.name)
                    return p

        # Search all sessions
        for session_dir in self.base_dir.iterdir():
            if not session_dir.is_dir():
                continue
            for p in session_dir.glob(f"*_{run_id}.json"):
                self._run_id_cache[run_id] = (session_dir.name, p.name)
                return p

        raise FileNotFoundError(f"Run {run_id} not found")

    def save_run(
        self,
        summary: Dict[str, Any],
        run_id: Optional[str] = None,
        session_name: Optional[str] = None,
        run_name: Optional[str] = None,
        overwrite: bool = True,
    ) -> str:
        """Save a run to the session directory.

        Args:
            summary: The run data to save
            run_id: Optional run ID (defaults to generated timestamp)
            session_name: Session name (defaults to "default")
            run_name: Run name (defaults to auto-generated friendly name)
            overwrite: If True, replaces existing file with same run_name in session
        """
        rid = run_id or self.generate_run_id()
        sess = _sanitize_name(session_name) if session_name else "default"

        # If run_id exists and no run_name provided, preserve existing run_name
        existing_path = None
        if run_id and not run_name:
            try:
                existing_path = self._find_run_file(run_id, sess)
                # Extract run_name from existing filename
                existing_filename = existing_path.name
                if "_" in existing_filename:
                    run_name = existing_filename.rsplit("_", 1)[0]
            except FileNotFoundError:
                pass

        rname = _sanitize_name(run_name) if run_name else _generate_friendly_name()

        session_dir = self._session_dir(sess)
        session_dir.mkdir(parents=True, exist_ok=True)

        # If updating existing file, delete it first
        if existing_path and existing_path.exists():
            existing_path.unlink()

        # Overwrite: delete existing file(s) with same run_name in this session (different run_ids)
        if overwrite:
            for p in session_dir.glob(f"{rname}_*.json"):
                if p.name != f"{rname}_{rid}.json":  # Don't delete the file we're about to write
                    p.unlink()
                    old_run_id = self._extract_run_id(p.name)
                    self._run_id_cache.pop(old_run_id, None)

        path = session_dir / f"{rname}_{rid}.json"

        # Add session/run metadata to summary
        summary = {
            "session_name": sess,
            "run_name": rname,
            "run_id": rid,
            **summary,
        }
        _atomic_write_json(path, summary)

        # Cache the mapping
        self._run_id_cache[rid] = (sess, path.name)

        return rid

    def load_run(self, run_id: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """Load a run by ID."""
        path = self._find_run_file(run_id, session_name)
        with open(path, "r") as f:
            return json.load(f)

    def _extract_run_id(self, filename: str) -> str:
        """Extract run_id from filename like 'name_1705312200.json'"""
        stem = filename.removesuffix(".json")
        if "_" in stem:
            parts = stem.rsplit("_", 1)
            if len(parts) == 2:
                return parts[1]
        return stem

    def _extract_run_name(self, filename: str) -> str:
        """Extract run_name from filename like 'name_1705312200.json'"""
        stem = filename.removesuffix(".json")
        if "_" in stem:
            parts = stem.rsplit("_", 1)
            if len(parts) == 2:
                return parts[0]
        return stem

    def list_sessions(self) -> list[str]:
        """Return all session names (directories with JSON files)."""
        sessions = []
        for d in self.base_dir.iterdir():
            if d.is_dir() and any(d.glob("*.json")):
                sessions.append(d.name)
        return sorted(sessions)

    def list_runs(self) -> list[str]:
        """Return all run_ids across all sessions, sorted descending (newest first)."""
        items = []
        for session_dir in self.base_dir.iterdir():
            if not session_dir.is_dir():
                continue
            for p in session_dir.glob("*.json"):
                run_id = self._extract_run_id(p.name)
                items.append(run_id)
                self._run_id_cache[run_id] = (session_dir.name, p.name)
        return sorted(items, key=lambda x: int(x) if x.isdigit() else 0, reverse=True)

    def list_runs_for_session(self, session_name: str) -> list[str]:
        """Return run_ids for a specific session, sorted descending (newest first)."""
        session_dir = self._session_dir(session_name)
        if not session_dir.exists():
            return []

        items = []
        for p in session_dir.glob("*.json"):
            run_id = self._extract_run_id(p.name)
            items.append(run_id)
            self._run_id_cache[run_id] = (session_dir.name, p.name)
        return sorted(items, key=lambda x: int(x) if x.isdigit() else 0, reverse=True)

    def rename_run(self, run_id: str, new_name: str, session_name: Optional[str] = None) -> str:
        """Rename a run - updates filename and JSON metadata."""
        old_path = self._find_run_file(run_id, session_name)
        data = json.loads(old_path.read_text())

        new_name_safe = _sanitize_name(new_name)
        data["run_name"] = new_name_safe

        new_path = old_path.parent / f"{new_name_safe}_{run_id}.json"
        _atomic_write_json(new_path, data)
        old_path.unlink()

        # Update cache
        self._run_id_cache[run_id] = (old_path.parent.name, new_path.name)

        return new_name_safe

    def delete_run(self, run_id: str, session_name: Optional[str] = None) -> bool:
        """Delete a run file."""
        try:
            path = self._find_run_file(run_id, session_name)
            path.unlink()
            self._run_id_cache.pop(run_id, None)
            return True
        except FileNotFoundError:
            return False

    def delete_session(self, session_name: str) -> bool:
        """Delete an entire session and all its runs."""
        session_dir = self._session_dir(session_name)
        if session_dir.exists():
            # Clean cache for all runs in this session
            for p in session_dir.glob("*.json"):
                run_id = self._extract_run_id(p.name)
                self._run_id_cache.pop(run_id, None)
            shutil.rmtree(session_dir)
            return True
        return False

    def _get_lock(self, run_id: str) -> Lock:
        if run_id not in self._locks:
            self._locks[run_id] = Lock()
        return self._locks[run_id]

    def update_result(self, run_id: str, index: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update allowed fields for a specific result entry and persist.

        Allowed fields (annotations + scores only):
        - result.scores
        - result.annotation
        - result.annotations
        """
        lock = self._get_lock(run_id)
        with lock:
            summary = self.load_run(run_id)
            results = summary.get("results", [])
            if index < 0 or index >= len(results):
                raise IndexError("result index out of range")

            entry = results[index]
            result_updates = updates.get("result")
            if result_updates:
                result_entry = entry.setdefault("result", {})
                for key in ("scores", "annotation", "annotations"):
                    if key in result_updates:
                        result_entry[key] = result_updates[key]

            # Persist atomically
            run_file = self._find_run_file(run_id)
            _atomic_write_json(run_file, summary)
            return entry
