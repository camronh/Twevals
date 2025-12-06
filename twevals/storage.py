from __future__ import annotations

import json
import os
import random
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
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
    # Write to a temp file in the same directory then atomically replace
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent)) as tmp:
        json.dump(data, tmp, indent=2, default=str)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


@dataclass
class ResultsStore:
    base_dir: Path

    def __init__(self, base_dir: str | Path = ".twevals/runs") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, Lock] = {}
        # Cache mapping run_id -> filename for fast lookups
        self._run_id_to_file: dict[str, str] = {}

    def generate_run_id(self) -> str:
        # ISO-like timestamp, UTC, with seconds precision: YYYY-MM-DDTHH-MM-SSZ
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

    def _filename(self, run_id: str, run_name: Optional[str] = None) -> str:
        """Generate filename: {run_name}_{run_id}.json or {run_id}.json"""
        if run_name:
            safe_name = _sanitize_name(run_name)
            return f"{safe_name}_{run_id}.json" if safe_name else f"{run_id}.json"
        return f"{run_id}.json"

    def run_path(self, run_id: str, run_name: Optional[str] = None) -> Path:
        return self.base_dir / self._filename(run_id, run_name)

    def _find_run_file(self, run_id: str) -> Path:
        """Find the file for a run_id, handling both prefixed and non-prefixed names."""
        # Check cache first
        if run_id in self._run_id_to_file:
            return self.base_dir / self._run_id_to_file[run_id]
        # Search for file ending with _{run_id}.json or exactly {run_id}.json
        for p in self.base_dir.glob("*.json"):
            if p.name == "latest.json":
                continue
            if p.name == f"{run_id}.json" or p.name.endswith(f"_{run_id}.json"):
                self._run_id_to_file[run_id] = p.name
                return p
        # Fallback to simple path
        return self.base_dir / f"{run_id}.json"

    def latest_path(self) -> Path:
        return self.base_dir / "latest.json"

    def save_run(
        self,
        summary: Dict[str, Any],
        run_id: Optional[str] = None,
        session_name: Optional[str] = None,
        run_name: Optional[str] = None,
    ) -> str:
        rid = run_id or self.generate_run_id()
        # If run_id exists on disk and no names provided, reuse existing names/file
        existing_file = self._find_run_file(rid)
        if existing_file.exists() and (session_name is None or run_name is None):
            with open(existing_file, "r") as f:
                existing = json.load(f)
            sess = session_name or existing.get("session_name") or _generate_friendly_name()
            rname = run_name or existing.get("run_name") or _generate_friendly_name()
            path = existing_file  # Reuse existing file path
        else:
            # Generate friendly names if not provided (new run)
            sess = session_name or _generate_friendly_name()
            rname = run_name or _generate_friendly_name()
            path = self.run_path(rid, rname)
        # Add session/run metadata to summary
        summary = {
            "session_name": sess,
            "run_name": rname,
            "run_id": rid,
            **summary,
        }
        _atomic_write_json(path, summary)
        # Cache the mapping
        self._run_id_to_file[rid] = path.name
        # Maintain a portable copy as latest.json
        shutil.copyfile(path, self.latest_path())
        return rid

    def load_run(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        if run_id in (None, "latest"):
            path = self.latest_path()
        else:
            path = self._find_run_file(run_id)
        with open(path, "r") as f:
            return json.load(f)

    def _extract_run_id(self, filename: str) -> str:
        """Extract run_id from filename like 'name_2024-01-01T00-00-00Z.json' or '2024-01-01T00-00-00Z.json'"""
        stem = filename.removesuffix(".json")
        # Check if it has a prefix (contains underscore before the timestamp pattern)
        if "_" in stem:
            # The run_id is after the last underscore that precedes the timestamp
            parts = stem.rsplit("_", 1)
            if len(parts) == 2:
                return parts[1]
        return stem

    def list_runs(self) -> list[str]:
        """Return run_ids sorted descending (newest first)."""
        items = []
        for p in self.base_dir.glob("*.json"):
            if p.name == "latest.json":
                continue
            run_id = self._extract_run_id(p.name)
            items.append(run_id)
            # Update cache
            self._run_id_to_file[run_id] = p.name
        return sorted(items, reverse=True)

    def list_runs_for_session(self, session_name: str) -> list[str]:
        """Return run_ids for a specific session, sorted descending (newest first)."""
        items = []
        for p in self.base_dir.glob("*.json"):
            if p.name == "latest.json":
                continue
            with open(p, "r") as f:
                data = json.load(f)
            if data.get("session_name") == session_name:
                run_id = data.get("run_id") or self._extract_run_id(p.name)
                items.append(run_id)
        return sorted(items, reverse=True)

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
            # Keep latest.json copy in sync
            shutil.copyfile(run_file, self.latest_path())
            return entry

