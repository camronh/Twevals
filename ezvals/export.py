"""Shared export utilities for Markdown and CSV generation."""

import csv
import io
import json
from typing import Any, Dict, List, Optional


def compute_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute stats and score chips from run data."""
    results = data.get("results", [])

    # Build per-score-key chips
    score_map: Dict[str, Dict] = {}
    total_errors = 0
    latency_sum = 0.0
    latency_count = 0

    for r in results:
        res = (r or {}).get("result") or {}
        if res.get("error"):
            total_errors += 1
        lat = res.get("latency")
        if lat is not None:
            try:
                latency_sum += float(lat)
                latency_count += 1
            except (TypeError, ValueError):
                pass

        for s in res.get("scores") or []:
            key = s.get("key") if isinstance(s, dict) else getattr(s, "key", None)
            if not key:
                continue
            d = score_map.setdefault(key, {"passed": 0, "failed": 0, "bool": 0, "sum": 0.0, "count": 0})
            passed = s.get("passed") if isinstance(s, dict) else getattr(s, "passed", None)
            if passed is True:
                d["passed"] += 1
                d["bool"] += 1
            elif passed is False:
                d["failed"] += 1
                d["bool"] += 1
            value = s.get("value") if isinstance(s, dict) else getattr(s, "value", None)
            if value is not None:
                try:
                    d["sum"] += float(value)
                    d["count"] += 1
                except (TypeError, ValueError):
                    pass

    chips = []
    for k, d in score_map.items():
        if d["bool"] > 0:
            total = d["passed"] + d["failed"]
            chips.append({"key": k, "type": "ratio", "passed": d["passed"], "total": total})
        elif d["count"] > 0:
            avg = d["sum"] / d["count"]
            chips.append({"key": k, "type": "avg", "avg": avg, "count": d["count"]})

    return {
        "total": len(results),
        "errors": total_errors,
        "avg_latency": latency_sum / latency_count if latency_count > 0 else 0,
        "chips": chips,
    }


def _chip_to_pct(chip: Dict) -> int:
    """Convert a score chip to percentage (0-100)."""
    if chip["type"] == "ratio":
        return round(chip["passed"] / chip["total"] * 100) if chip["total"] > 0 else 0
    else:
        # For avg, assume 0-1 scale, cap at 100
        return min(100, round(chip["avg"] * 100))


def _ascii_bar(pct: int, width: int = 20) -> str:
    """Generate ASCII bar for percentage with color emoji."""
    filled = pct * width // 100
    bar = "█" * filled + "░" * (width - filled)
    # Color indicator based on percentage
    if pct >= 80:
        indicator = "🟢"
    elif pct >= 50:
        indicator = "🟡"
    else:
        indicator = "🔴"
    return f"{bar} {indicator}"


def _truncate(s: str, max_len: int) -> str:
    """Truncate string to max length with ellipsis."""
    s = str(s)
    if len(s) > max_len:
        return s[:max_len - 3] + "..."
    return s


def render_markdown(
    data: Dict[str, Any],
    columns: Optional[List[str]] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> str:
    """Render run data as Markdown with ASCII bar chart.

    Args:
        data: Run data dict with results, run_name, session_name
        columns: List of columns to include (None = all)
        stats: Pre-computed stats (if None, computed from data)
    """
    if stats is None:
        stats = compute_stats(data)

    lines = []

    # Header
    run_name = data.get("run_name", "Untitled Run")
    session_name = data.get("session_name")
    lines.append(f"# {run_name}")
    if session_name:
        lines.append(f"**Session:** {session_name}")
    lines.append("")

    # Stats summary - compact inline format
    filtered = stats.get('filtered', stats['total'])
    total = stats['total']
    errors = stats['errors']
    latency = stats['avg_latency']

    summary_parts = [f"**{filtered}/{total}** tests"]
    if errors > 0:
        summary_parts.append(f"**{errors}** errors")
    if latency > 0:
        summary_parts.append(f"**{latency:.2f}s** avg latency")
    lines.append(" · ".join(summary_parts))
    lines.append("")

    # Score bars as table
    if stats["chips"]:
        lines.append("## Scores")
        lines.append("")
        lines.append("| Metric | Progress | Score |")
        lines.append("|--------|----------|-------|")
        for chip in stats["chips"]:
            pct = _chip_to_pct(chip)
            bar = _ascii_bar(pct)
            if chip["type"] == "ratio":
                score = f"{pct}% ({chip['passed']}/{chip['total']})"
            else:
                score = f"{pct}% (avg: {chip['avg']:.2f})"
            lines.append(f"| **{chip['key']}** | {bar} | {score} |")
        lines.append("")

    # Results table
    lines.append("## Results")
    results = data.get("results", [])
    if not results:
        lines.append("*No results*")
        return "\n".join(lines)

    # Default columns
    all_cols = ["function", "dataset", "input", "output", "reference", "scores", "error", "latency"]
    cols = columns if columns else all_cols

    col_headers = {
        "function": "Eval",
        "dataset": "Dataset",
        "input": "Input",
        "output": "Output",
        "reference": "Reference",
        "scores": "Scores",
        "error": "Error",
        "latency": "Latency",
    }

    # Table header
    header = " | ".join(col_headers.get(c, c.title()) for c in cols)
    lines.append(f"| {header} |")
    lines.append("|" + "|".join("---" for _ in cols) + "|")

    # Table rows
    for r in results:
        res = r.get("result", {})
        row_vals = []
        for c in cols:
            if c == "function":
                val = r.get("function", "")
            elif c == "dataset":
                val = r.get("dataset", "")
            elif c == "input":
                val = _truncate(json.dumps(res.get("input", ""), default=str), 50)
            elif c == "output":
                val = _truncate(json.dumps(res.get("output", ""), default=str), 50)
            elif c == "reference":
                val = _truncate(json.dumps(res.get("reference", ""), default=str), 50)
            elif c == "scores":
                scores = res.get("scores") or []
                parts = []
                for s in scores:
                    key = s.get("key", "?")
                    if s.get("passed") is True:
                        parts.append(f"✓{key}")
                    elif s.get("passed") is False:
                        parts.append(f"✗{key}")
                    elif s.get("value") is not None:
                        parts.append(f"{key}:{s['value']}")
                val = " ".join(parts)
            elif c == "error":
                val = _truncate(res.get("error") or "", 30)
            elif c == "latency":
                lat = res.get("latency")
                val = f"{lat:.2f}s" if lat else ""
            else:
                val = ""
            # Escape pipes for markdown
            row_vals.append(val.replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(row_vals) + " |")

    return "\n".join(lines)


def render_csv(
    data: Dict[str, Any],
    columns: Optional[List[str]] = None,
) -> str:
    """Render run data as CSV.

    Args:
        data: Run data dict with results
        columns: List of columns to include (None = all)
    """
    all_cols = ["function", "dataset", "labels", "input", "output", "reference",
                "scores", "error", "latency", "metadata", "trace_data", "annotations"]
    cols = columns if columns else all_cols

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=cols)
    writer.writeheader()

    for r in data.get("results", []):
        result = r.get("result", {})
        row = {}
        for c in cols:
            if c == "function":
                row[c] = r.get("function")
            elif c == "dataset":
                row[c] = r.get("dataset")
            elif c == "labels":
                row[c] = ";".join(r.get("labels") or [])
            elif c == "input":
                row[c] = json.dumps(result.get("input"), default=str)
            elif c == "output":
                row[c] = json.dumps(result.get("output"), default=str)
            elif c == "reference":
                row[c] = json.dumps(result.get("reference"), default=str)
            elif c == "scores":
                row[c] = json.dumps(result.get("scores"), default=str)
            elif c == "error":
                row[c] = result.get("error")
            elif c == "latency":
                row[c] = result.get("latency")
            elif c == "metadata":
                row[c] = json.dumps(result.get("metadata"), default=str)
            elif c == "trace_data":
                row[c] = json.dumps(result.get("trace_data"), default=str)
            elif c == "annotations":
                row[c] = json.dumps(result.get("annotations"), default=str)
        writer.writerow(row)

    return output.getvalue()


def export_to_markdown(data: Dict[str, Any], output_path: str, columns: Optional[List[str]] = None, stats: Optional[Dict[str, Any]] = None):
    """Export run data to Markdown file."""
    md = render_markdown(data, columns, stats)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)


def export_to_csv(data: Dict[str, Any], output_path: str, columns: Optional[List[str]] = None):
    """Export run data to CSV file."""
    csv_content = render_csv(data, columns)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(csv_content)
