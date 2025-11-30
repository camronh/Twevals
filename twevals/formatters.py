from typing import Dict, List, Any
from rich.table import Table
from rich.text import Text
import json


def _get_status(result: Dict) -> Text:
    """Determine status Text from result dict."""
    if result.get("error"):
        return Text("ERROR", style="red")
    if result.get("scores"):
        if any(s.get("passed") is True for s in result["scores"]):
            return Text("PASS", style="green")
        if any(s.get("passed") is False for s in result["scores"]):
            return Text("FAIL", style="red")
    return Text("OK", style="yellow")


def format_results_table(results: List[Dict[str, Any]]) -> Table:
    table = Table(title="Evaluation Results", show_header=True, header_style="bold magenta", show_lines=True, expand=True)
    table.add_column("Dataset", style="green", width=20)
    table.add_column("Input", max_width=40)
    table.add_column("Output", max_width=40)
    table.add_column("Status", style="bold", width=10)
    table.add_column("Scores", max_width=30)
    table.add_column("Latency", justify="right", width=12)

    for item in results:
        result = item["result"]

        # Format scores
        scores_text = ""
        for score in result.get("scores") or []:
            key = score.get("key", "")
            if score.get("value") is not None:
                scores_text += f"{key}: {score['value']:.2f}\n"
            elif score.get("passed") is not None:
                scores_text += f"{key}: {'✓' if score['passed'] else '✗'}\n"
            if score.get("notes"):
                notes = score["notes"][:22] + "..." if len(score["notes"]) > 25 else score["notes"]
                scores_text += f"  ({notes})\n"

        latency_text = f"{result['latency']:.3f}s" if result.get("latency") else ""
        input_str = str(result.get("input", ""))[:50]
        output_str = str(result.get("output", ""))[:50]
        if result.get("error") and not output_str:
            output_str = f"Error: {result['error'][:40]}"

        table.add_row(item["dataset"], input_str, output_str, _get_status(result), scores_text.strip(), latency_text)

    return table
