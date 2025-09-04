from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


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

    def generate_run_id(self) -> str:
        # ISO-like timestamp, UTC, with seconds precision: YYYY-MM-DDTHH-MM-SSZ
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

    def run_path(self, run_id: str) -> Path:
        return self.base_dir / f"{run_id}.json"

    def latest_path(self) -> Path:
        return self.base_dir / "latest.json"

    def save_run(self, summary: Dict[str, Any], run_id: Optional[str] = None) -> str:
        rid = run_id or self.generate_run_id()
        path = self.run_path(rid)
        _atomic_write_json(path, summary)
        # Maintain a portable copy as latest.json
        shutil.copyfile(path, self.latest_path())
        return rid

    def load_run(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        path = self.latest_path() if run_id in (None, "latest") else self.run_path(run_id)
        with open(path, "r") as f:
            return json.load(f)

    def list_runs(self) -> list[str]:
        # Return run_ids sorted descending (newest first)
        items = []
        for p in self.base_dir.glob("*.json"):
            if p.name == "latest.json":
                continue
            items.append(p.stem)
        return sorted(items, reverse=True)

    def _get_lock(self, run_id: str) -> Lock:
        if run_id not in self._locks:
            self._locks[run_id] = Lock()
        return self._locks[run_id]

    def update_result(self, run_id: str, index: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update allowed fields for a specific result entry and persist.

        Allowed fields:
        - dataset
        - labels
        - result.scores
        - result.metadata
        - result.error
        - result.reference
        - result.annotation (full replace)
        """
        lock = self._get_lock(run_id)
        with lock:
            summary = self.load_run(run_id)
            results = summary.get("results", [])
            if index < 0 or index >= len(results):
                raise IndexError("result index out of range")

            entry = results[index]
            # Top-level fields
            if "dataset" in updates:
                entry["dataset"] = updates["dataset"]
            if "labels" in updates:
                entry["labels"] = updates["labels"]

            # Nested result fields
            result_updates = updates.get("result") or {}
            if result_updates:
                result_entry = entry.setdefault("result", {})
                for key in ("scores", "metadata", "error", "reference", "annotation"):
                    if key in result_updates:
                        result_entry[key] = result_updates[key]

            # Persist atomically
            _atomic_write_json(self.run_path(run_id), summary)
            # Keep latest.json copy in sync
            shutil.copyfile(self.run_path(run_id), self.latest_path())
            return entry

