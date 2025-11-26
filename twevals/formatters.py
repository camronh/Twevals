from typing import Dict, List, Any
from rich.table import Table
from rich.text import Text
import json


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
        
        # Format status
        if result.get("error"):
            status = Text("ERROR", style="red")
        elif result.get("scores"):
            # Check if any score has passed=True
            passed = any(
                score.get("passed") is True 
                for score in result["scores"]
            )
            if passed:
                status = Text("PASS", style="green")
            else:
                # Check if there are explicit failures
                failed = any(
                    score.get("passed") is False 
                    for score in result["scores"]
                )
                if failed:
                    status = Text("FAIL", style="red")
                else:
                    status = Text("OK", style="yellow")
        else:
            status = Text("OK", style="yellow")
        
        # Format scores
        scores_text = ""
        if result.get("scores"):
            for score in result["scores"]:
                key = score.get("key", "")
                if score.get("value") is not None:
                    scores_text += f"{key}: {score['value']:.2f}\n"
                elif score.get("passed") is not None:
                    passed_str = "✓" if score["passed"] else "✗"
                    scores_text += f"{key}: {passed_str}\n"
                
                # Add notes if present
                if score.get("notes"):
                    notes = score["notes"]
                    # Truncate long notes
                    if len(notes) > 25:
                        notes = notes[:22] + "..."
                    scores_text += f"  ({notes})\n"
        
        # Format latency
        latency_text = ""
        if result.get("latency"):
            latency_text = f"{result['latency']:.3f}s"
        
        # Truncate long strings
        input_str = str(result.get("input", ""))[:50]
        output_str = str(result.get("output", ""))[:50]

        # Only show error in output column if output is empty
        if result.get("error") and not output_str:
            output_str = f"Error: {result['error'][:40]}"
        
        table.add_row(
            item["dataset"],
            input_str,
            output_str,
            status,
            scores_text.strip(),
            latency_text
        )

    return table


def format_eval_list_table(eval_info_list: List[Dict[str, Any]]) -> Table:
    def fmt(val, max_len):
        if val is None:
            return ""
        try:
            s = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
        except (TypeError, ValueError):
            # Fall back to str() for non-JSON-serializable objects
            s = str(val)
        return s if len(s) <= max_len else s[:max_len-3] + "..."

    table = Table(
        title="Evaluation Functions",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        expand=True
    )

    table.add_column("Function", style="cyan", width=30)
    table.add_column("Dataset", style="green", width=20)
    table.add_column("Labels", max_width=15)
    table.add_column("Input", max_width=30)
    table.add_column("Reference", max_width=20)
    table.add_column("Metadata", max_width=20)

    for info in eval_info_list:
        table.add_row(
            info['function'],
            info['dataset'],
            ", ".join(info['labels']),
            fmt(info.get('input'), 60),
            fmt(info.get('reference'), 40),
            fmt(info.get('metadata'), 40)
        )

    return table
