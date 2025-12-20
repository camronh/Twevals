"""Shared export utilities for PDF, Markdown, and CSV generation."""

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


def _ascii_bar(pct: int, width: int = 10) -> str:
    """Generate ASCII bar for percentage."""
    filled = pct * width // 100
    return "█" * filled + "░" * (width - filled)


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

    # Stats summary
    lines.append("## Summary")
    lines.append(f"- **Tests:** {stats.get('filtered', stats['total'])}/{stats['total']}")
    lines.append(f"- **Errors:** {stats['errors']}")
    if stats["avg_latency"] > 0:
        lines.append(f"- **Avg Latency:** {stats['avg_latency']:.2f}s")
    lines.append("")

    # Score bars
    if stats["chips"]:
        lines.append("## Scores")
        for chip in stats["chips"]:
            pct = _chip_to_pct(chip)
            bar = _ascii_bar(pct)
            if chip["type"] == "ratio":
                detail = f"{chip['passed']}/{chip['total']}"
            else:
                detail = f"avg: {chip['avg']:.2f}"
            lines.append(f"- **{chip['key']}:** {bar} {pct}% ({detail})")
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
                scores = res.get("scores", [])
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


def _truncate(s: str, max_len: int) -> str:
    """Truncate string to max length with ellipsis."""
    s = str(s)
    if len(s) > max_len:
        return s[:max_len - 3] + "..."
    return s


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


def render_html_for_pdf(
    data: Dict[str, Any],
    columns: Optional[List[str]] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> str:
    """Render run data as HTML suitable for PDF conversion.

    Args:
        data: Run data dict with results, run_name, session_name
        columns: List of columns to include (None = all)
        stats: Pre-computed stats (if None, computed from data)
    """
    if stats is None:
        stats = compute_stats(data)

    run_name = data.get("run_name", "Untitled Run")
    session_name = data.get("session_name", "")

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

    # Build SVG bar chart
    chart_svg = _build_svg_chart(stats["chips"])

    # Build table HTML
    results = data.get("results", [])
    table_rows = []
    for r in results:
        res = r.get("result", {})
        cells = []
        for c in cols:
            if c == "function":
                val = _escape_html(r.get("function", ""))
            elif c == "dataset":
                val = _escape_html(r.get("dataset", ""))
            elif c == "input":
                val = _escape_html(_truncate(json.dumps(res.get("input", ""), default=str), 80))
            elif c == "output":
                val = _escape_html(_truncate(json.dumps(res.get("output", ""), default=str), 80))
            elif c == "reference":
                val = _escape_html(_truncate(json.dumps(res.get("reference", ""), default=str), 80))
            elif c == "scores":
                scores = res.get("scores", [])
                badges = []
                for s in scores:
                    key = s.get("key", "?")
                    if s.get("passed") is True:
                        badges.append(f'<span class="badge pass">{_escape_html(key)}</span>')
                    elif s.get("passed") is False:
                        badges.append(f'<span class="badge fail">{_escape_html(key)}</span>')
                    elif s.get("value") is not None:
                        badges.append(f'<span class="badge">{_escape_html(key)}: {s["value"]}</span>')
                val = " ".join(badges)
            elif c == "error":
                err = res.get("error") or ""
                val = f'<span class="error">{_escape_html(_truncate(err, 50))}</span>' if err else ""
            elif c == "latency":
                lat = res.get("latency")
                val = f"{lat:.2f}s" if lat else ""
            else:
                val = ""
            cells.append(f"<td>{val}</td>")
        table_rows.append("<tr>" + "".join(cells) + "</tr>")

    # Column headers
    th_cells = "".join(f"<th>{col_headers.get(c, c.title())}</th>" for c in cols)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{_escape_html(run_name)}</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 11px;
    color: #1a1a1a;
    margin: 20px;
    line-height: 1.4;
}}
h1 {{
    font-size: 18px;
    margin: 0 0 4px 0;
}}
.session {{
    color: #666;
    font-size: 12px;
    margin-bottom: 16px;
}}
.stats {{
    display: flex;
    gap: 24px;
    margin-bottom: 16px;
    font-size: 12px;
}}
.stat {{
    display: flex;
    flex-direction: column;
}}
.stat-value {{
    font-size: 20px;
    font-weight: 600;
}}
.stat-label {{
    color: #666;
    font-size: 10px;
    text-transform: uppercase;
}}
.chart {{
    margin: 16px 0;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
}}
th {{
    background: #f5f5f5;
    padding: 6px 8px;
    text-align: left;
    border-bottom: 1px solid #ddd;
    font-weight: 600;
}}
td {{
    padding: 6px 8px;
    border-bottom: 1px solid #eee;
    vertical-align: top;
    word-break: break-word;
    max-width: 200px;
}}
tr:nth-child(even) {{
    background: #fafafa;
}}
.badge {{
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 9px;
    background: #e0e0e0;
    margin: 1px;
}}
.badge.pass {{
    background: #d4edda;
    color: #155724;
}}
.badge.fail {{
    background: #f8d7da;
    color: #721c24;
}}
.error {{
    color: #dc3545;
}}
</style>
</head>
<body>
<h1>{_escape_html(run_name)}</h1>
<div class="session">{_escape_html(session_name)}</div>

<div class="stats">
    <div class="stat">
        <span class="stat-value">{stats.get('filtered', stats['total'])}/{stats['total']}</span>
        <span class="stat-label">Tests</span>
    </div>
    <div class="stat">
        <span class="stat-value">{stats['errors']}</span>
        <span class="stat-label">Errors</span>
    </div>
    <div class="stat">
        <span class="stat-value">{stats['avg_latency']:.2f}s</span>
        <span class="stat-label">Avg Latency</span>
    </div>
</div>

<div class="chart">
{chart_svg}
</div>

<table>
<thead><tr>{th_cells}</tr></thead>
<tbody>
{"".join(table_rows)}
</tbody>
</table>
</body>
</html>"""

    return html


def _escape_html(s: str) -> str:
    """Escape HTML special characters."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _build_svg_chart(chips: List[Dict]) -> str:
    """Build SVG bar chart from score chips."""
    if not chips:
        return ""

    bar_width = 60
    bar_gap = 20
    chart_height = 120
    bar_max_height = 80
    label_height = 30

    total_width = len(chips) * (bar_width + bar_gap)

    bars = []
    for i, chip in enumerate(chips):
        pct = _chip_to_pct(chip)
        bar_height = pct * bar_max_height // 100
        x = i * (bar_width + bar_gap)
        y = bar_max_height - bar_height

        # Color based on percentage
        if pct >= 80:
            color = "#10b981"  # green
        elif pct >= 50:
            color = "#f59e0b"  # amber
        else:
            color = "#ef4444"  # red

        # Bar
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{color}" rx="3"/>')

        # Percentage label on bar
        bars.append(f'<text x="{x + bar_width//2}" y="{y - 5}" text-anchor="middle" font-size="11" font-weight="600">{pct}%</text>')

        # Key label below
        key = chip["key"][:10]  # Truncate long keys
        bars.append(f'<text x="{x + bar_width//2}" y="{bar_max_height + 15}" text-anchor="middle" font-size="10" fill="#666">{_escape_html(key)}</text>')

        # Ratio/avg below key
        if chip["type"] == "ratio":
            detail = f"{chip['passed']}/{chip['total']}"
        else:
            detail = f"{chip['avg']:.2f}"
        bars.append(f'<text x="{x + bar_width//2}" y="{bar_max_height + 27}" text-anchor="middle" font-size="9" fill="#999">{detail}</text>')

    return f'''<svg width="{total_width}" height="{chart_height + label_height}" xmlns="http://www.w3.org/2000/svg">
    {"".join(bars)}
</svg>'''


def export_to_pdf(data: Dict[str, Any], output_path: str, columns: Optional[List[str]] = None, stats: Optional[Dict[str, Any]] = None):
    """Export run data to PDF file.

    Requires weasyprint to be installed, plus system libraries (Pango, Cairo).
    """
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as e:
        raise ImportError(
            f"PDF export requires weasyprint and system libraries (Pango, Cairo, GLib).\n"
            f"Install weasyprint with: pip install ezvals[pdf]\n"
            f"See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation\n"
            f"Original error: {e}"
        )

    html = render_html_for_pdf(data, columns, stats)
    HTML(string=html).write_pdf(output_path)


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
