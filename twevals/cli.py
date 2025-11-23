import click
import sys
import inspect
import os
import json
from pathlib import Path
from typing import Optional, List, Dict

from rich.console import Console

from twevals.runner import EvalRunner
from twevals.formatters import format_results_table
from twevals.decorators import EvalFunction


console = Console()


def _remove_none(obj):
    """Recursively remove None values from dictionaries"""
    if isinstance(obj, dict):
        return {k: _remove_none(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_remove_none(v) for v in obj]
    return obj


class ProgressReporter:
    """Pytest-style progress reporter for evaluation runs"""
    
    def __init__(self):
        self.failures: List[Dict] = []
        self.current_line = ""
        self.current_file = None
    
    def _get_file_display(self, func: EvalFunction) -> str:
        """Get the display name for the file containing the function"""
        try:
            # Try to get the file path directly from the function
            file_path = inspect.getfile(func.func)
            # Try to make it relative to CWD
            try:
                return str(Path(file_path).relative_to(os.getcwd()))
            except ValueError:
                return Path(file_path).name
        except (TypeError, OSError):
            # Fallback: try to get from module
            module = inspect.getmodule(func.func)
            if module and hasattr(module, '__file__') and module.__file__:
                try:
                    return str(Path(module.__file__).relative_to(os.getcwd()))
                except ValueError:
                    return Path(module.__file__).name
            # Final fallback: use dataset name
            return func.dataset
    
    def on_start(self, func: EvalFunction):
        """Called when an evaluation starts"""
        # In sequential mode, we could print the header here.
        # But to be safe with how runner calls things, we'll handle it in on_complete
        # or check if we need to initialize the first file line.
        file_display = self._get_file_display(func)
        if file_display != self.current_file:
            if self.current_file is not None:
                console.print("") # Newline for previous file
            console.print(f"{file_display} ", end="")
            self.current_file = file_display
            self.current_line = ""
    
    def on_complete(self, func: EvalFunction, result_dict: Dict):
        """Called when an evaluation completes"""
        # Ensure we're on the right file line (in case on_start didn't catch it or out of order - though runner is ordered)
        file_display = self._get_file_display(func)
        if file_display != self.current_file:
            if self.current_file is not None:
                console.print("")
            console.print(f"{file_display} ", end="")
            self.current_file = file_display
            self.current_line = ""

        result = result_dict["result"]
        
        # Determine status character and color
        if result.get("error"):
            char = "E"
            color = "red"
            self.failures.append({
                "func": func,
                "result_dict": result_dict,
                "type": "error"
            })
        elif result.get("scores"):
            # Check if any score has passed=True
            passed = any(
                score.get("passed") is True 
                for score in result["scores"]
            )
            if passed:
                char = "."
                color = "green"
            else:
                # Check if there are explicit failures
                failed = any(
                    score.get("passed") is False 
                    for score in result["scores"]
                )
                if failed:
                    char = "F"
                    color = "red"
                    self.failures.append({
                        "func": func,
                        "result_dict": result_dict,
                        "type": "failure"
                    })
                else:
                    char = "."
                    color = "green"
        else:
            char = "."
            color = "green"
        
        # Print character inline with color (no newline)
        console.print(f"[{color}]{char}[/{color}]", end="")
        self.current_line += char
    
    def print_failures(self):
        """Print detailed failure information"""
        if self.current_file is not None:
            console.print("") # Final newline
            
        if not self.failures:
            return
        
        # console.print("\n")  # No extra newline needed as we added one above
        
        for i, failure in enumerate(self.failures, 1):
            func = failure["func"]
            result_dict = failure["result_dict"]
            result = result_dict["result"]
            failure_type = failure["type"]
            
            # Format like pytest: dataset::function_name
            dataset = result_dict.get("dataset", "unknown")
            func_name = func.func.__name__
            
            console.print(f"\n[red]{i}. {dataset}::{func_name}[/red]")
            
            if failure_type == "error":
                error_msg = result.get("error", "Unknown error")
                console.print(f"   [red]ERROR:[/red] {error_msg}")
            elif failure_type == "failure":
                # Show failing scores
                if result.get("scores"):
                    for score in result["scores"]:
                        if score.get("passed") is False:
                            key = score.get("key", "unknown")
                            notes = score.get("notes", "")
                            if notes:
                                console.print(f"   [red]FAIL:[/red] {key} - {notes}")
                            else:
                                console.print(f"   [red]FAIL:[/red] {key}")
            
            # Show input/output if available
            if result.get("input"):
                console.print(f"   [dim]Input:[/dim] {result['input']}")
            if result.get("output"):
                console.print(f"   [dim]Output:[/dim] {result['output']}")


@click.group()
def cli():
    """Twevals - A lightweight evaluation framework for AI/LLM testing"""
    pass


@cli.command()
@click.argument('path', type=str)
@click.option('--dataset', '-d', help='Run evaluations for specific dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Run evaluations with specific label(s)')
@click.option('--output', '-o', type=click.Path(dir_okay=False), help='Path to JSON file for results')
@click.option('--csv', '-s', type=click.Path(dir_okay=False), help='Path to CSV file for results (include filename)')
@click.option('--concurrency', '-c', default=0, type=int, help='Number of concurrent evaluations (0 for sequential)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
@click.option('--json', 'json_mode', is_flag=True, help='Output results as compact JSON to stdout')
def run(
    path: str,
    dataset: Optional[str],
    label: tuple,
    output: Optional[str],
    csv: Optional[str],
    concurrency: int,
    verbose: bool,
    json_mode: bool
):
    """Run evaluations in specified path
    
    Path can include function name filter: file.py::function_name
    """
    from pathlib import Path as PathLib
    
    # Parse path to extract file path and optional function name
    function_name = None
    if '::' in path:
        file_path, function_name = path.rsplit('::', 1)
        path = file_path
    
    # Validate that the file path portion exists
    path_obj = PathLib(path)
    if not path_obj.exists():
        if json_mode:
            click.echo(json.dumps({"error": f"Path {path} does not exist"}))
        else:
            console.print(f"[red]Error: Path {path} does not exist[/red]")
        sys.exit(1)
    
    # Convert label tuple to list
    labels = list(label) if label else None
    
    # Create runner
    runner = EvalRunner(concurrency=concurrency, verbose=verbose)
    
    # Create progress reporter
    reporter = ProgressReporter() if not json_mode else None
    
    # Run evaluations with progress reporting
    if not json_mode:
        console.print("[bold green]Running evaluations...[/bold green]")
    
    try:
        summary = runner.run(
            path=path,
            dataset=dataset,
            labels=labels,
            function_name=function_name,
            output_file=output,
            csv_file=csv,
            verbose=verbose,
            on_start=reporter.on_start if reporter else None,
            on_complete=reporter.on_complete if reporter else None
        )
    except Exception as e:
        if json_mode:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    
    # Handle JSON output
    if json_mode:
        summary_clean = _remove_none(summary)
        click.echo(json.dumps(summary_clean, separators=(',', ':'), default=str))
        return

    # Print failure details if any
    reporter.print_failures()
    
    # Display results
    if summary["total_evaluations"] == 0:
        console.print("[yellow]No evaluations found matching the criteria[/yellow]")
        return
    
    # Show results table (always, not just with verbose)
    if summary['results']:
        table = format_results_table(summary['results'])
        console.print(table)
    
    # Print summary below table
    console.print("\n[bold]Evaluation Summary[/bold]")
    console.print(f"Total Functions: {summary['total_functions']}")
    console.print(f"Total Evaluations: {summary['total_evaluations']}")
    console.print(f"Errors: {summary['total_errors']}")
    
    if summary['total_with_scores'] > 0:
        console.print(f"Passed: {summary['total_passed']}/{summary['total_with_scores']}")
    
    if summary['average_latency'] > 0:
        console.print(f"Average Latency: {summary['average_latency']:.3f}s")
    
    # Output file notification
    if output:
        console.print(f"\n[green]Results saved to: {output}[/green]")
    if csv:
        console.print(f"[green]Results saved to: {csv}[/green]")


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--dataset', '-d', help='Run evaluations for specific dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Run evaluations with specific label(s)')
@click.option('--concurrency', '-c', default=0, type=int, help='Number of concurrent evaluations (0 for sequential)')
@click.option('--dev', is_flag=True, help='Enable hot-reload for development (watches repo for changes)')
@click.option('--results-dir', default='.twevals/runs', help='Directory for JSON results storage')
@click.option('--host', default='127.0.0.1', help='Host interface for the web server')
@click.option('--port', default=8000, type=int, help='Port for the web server')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed server logs')
@click.option('--quiet', '-q', is_flag=True, help='Reduce logging; hide access logs')
def serve(
    path: str,
    dataset: str | None,
    label: tuple,
    concurrency: int,
    dev: bool,
    results_dir: str,
    host: str,
    port: int,
    verbose: bool,
    quiet: bool,
):
    """Serve a web UI to browse results."""

    labels = list(label) if label else None

    try:
        from twevals.server import create_app
        import uvicorn
    except Exception as e:
        console.print("[red]Missing server dependencies. Install with:[/red] \n  uv add fastapi uvicorn jinja2")
        raise

    # Always create a fresh run on startup
    from twevals.storage import ResultsStore

    store = ResultsStore(results_dir)
    run_id = store.generate_run_id()
    run_path = store.run_path(run_id)

    # Create runner and execute evaluations, writing to JSON
    runner = EvalRunner(concurrency=concurrency, verbose=verbose)
    with console.status("[bold green]Running evaluations...", spinner="dots") as status:
        try:
            summary = runner.run(
                path=path,
                dataset=dataset,
                labels=labels,
                output_file=str(run_path),
                verbose=verbose,
            )
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    # Update latest.json portable copy
    store.save_run(summary, run_id)

    app = create_app(
        results_dir=results_dir,
        active_run_id=run_id,
        path=path,
        dataset=dataset,
        labels=labels,
        concurrency=concurrency,
        verbose=verbose,
    )
    # Friendly startup message
    url = f"http://{host}:{port}"
    console.print(f"\n[bold green]Twevals UI[/bold green] serving at: [bold blue]{url}[/bold blue]")
    console.print("Press Ctrl+C to stop\n")

    # Control logging verbosity
    log_level = "warning" if quiet and not verbose else ("info" if not verbose else "debug")
    access_log = False if quiet else True

    if dev:
        # Enable hot reload watching the repo (code + templates).
        # Uvicorn requires an import string/factory for reload to work.
        # We use twevals.server:load_app_from_env and pass config via env.
        from pathlib import Path as _Path
        import os as _os, json as _json

        repo_root = _Path('.').resolve()

        # Pass config to the child reloader process
        _os.environ["TWEVALS_RESULTS_DIR"] = str(results_dir)
        _os.environ["TWEVALS_ACTIVE_RUN_ID"] = str(run_id)
        _os.environ["TWEVALS_PATH"] = str(path)
        if dataset:
            _os.environ["TWEVALS_DATASET"] = str(dataset)
        if labels is not None:
            _os.environ["TWEVALS_LABELS"] = _json.dumps(labels)
        _os.environ["TWEVALS_CONCURRENCY"] = str(concurrency)
        _os.environ["TWEVALS_VERBOSE"] = "1" if verbose else "0"

        uvicorn.run(
            "twevals.server:load_app_from_env",
            host=host,
            port=port,
            log_level=log_level,
            access_log=access_log,
            reload=True,
            factory=True,
            reload_dirs=[str(repo_root)],
            reload_includes=["*.py", "*.pyi", "*.html", "*.jinja", "*.ini", "*.toml", "*.yaml", "*.yml", "*.json"],
        )
    else:
        uvicorn.run(app, host=host, port=port, log_level=log_level, access_log=access_log)


def main():
    cli()


if __name__ == '__main__':
    main()
