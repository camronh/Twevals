import click
import sys
import inspect
import os
import json
import traceback
import time
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict
from threading import Thread

from rich.console import Console

from twevals.formatters import format_results_table, format_eval_list_table
from twevals.decorators import EvalFunction
from twevals.discovery import EvalDiscovery
from twevals.runner import EvalRunner


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
        self.current_file = None

    def _get_file_display(self, func: EvalFunction) -> str:
        """Get the display name for the file containing the function"""
        try:
            file_path = inspect.getfile(func.func)
            try:
                return str(Path(file_path).relative_to(os.getcwd()))
            except ValueError:
                return Path(file_path).name
        except (TypeError, OSError):
            return func.dataset

    def _switch_file_if_needed(self, func: EvalFunction):
        """Print newline and new file header if file changed."""
        file_display = self._get_file_display(func)
        if file_display != self.current_file:
            if self.current_file is not None:
                console.print("")
            console.print(f"{file_display} ", end="")
            self.current_file = file_display

    def on_start(self, func: EvalFunction):
        """Called when an evaluation starts"""
        self._switch_file_if_needed(func)

    def on_complete(self, func: EvalFunction, result_dict: Dict):
        """Called when an evaluation completes"""
        self._switch_file_if_needed(func)
        result = result_dict["result"]

        # Determine status character and color
        if result.get("error"):
            char, color = "E", "red"
            self.failures.append({"func": func, "result_dict": result_dict, "type": "error"})
        elif result.get("scores"):
            passed = any(s.get("passed") is True for s in result["scores"])
            failed = any(s.get("passed") is False for s in result["scores"])
            if passed:
                char, color = ".", "green"
            elif failed:
                char, color = "F", "red"
                self.failures.append({"func": func, "result_dict": result_dict, "type": "failure"})
            else:
                char, color = ".", "green"
        else:
            char, color = ".", "green"

        console.print(f"[{color}]{char}[/{color}]", end="")

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
                # Show traceback if available
                if result.get("run_data") and result["run_data"].get("traceback"):
                    console.print(f"   [dim]Traceback:[/dim]")
                    console.print(f"   [dim]{result['run_data']['traceback']}[/dim]")
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
    """Twevals - A lightweight evaluation framework for AI/LLM testing

    Start the UI: twevals serve evals.py
    Run headless: twevals run evals.py

    Path can include function name filter: file.py::function_name
    """
    pass


@cli.command('serve')
@click.argument('path', type=str)
@click.option('--dataset', '-d', help='Filter by dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Filter by label(s)')
@click.option('--limit', type=int, help='Limit the number of evaluations')
@click.option('--dev', is_flag=True, help='Enable hot-reload for development')
@click.option('--results-dir', default='.twevals/runs', help='Directory for JSON results storage')
@click.option('--host', default='127.0.0.1', help='Host interface for the web server')
@click.option('--port', default=8000, type=int, help='Port for the web server')
@click.option('--quiet', '-q', is_flag=True, help='Reduce logging; hide access logs')
@click.option('--list', 'list_mode', is_flag=True, help='List all evaluations without running them')
def serve_cmd(
    path: str,
    dataset: Optional[str],
    label: tuple,
    limit: Optional[int],
    dev: bool,
    results_dir: str,
    host: str,
    port: int,
    quiet: bool,
    list_mode: bool,
):
    """Start the web UI to browse and run evaluations."""
    from pathlib import Path as PathLib

    # Parse path to extract file path and optional function name
    function_name = None
    if '::' in path:
        file_path, function_name = path.rsplit('::', 1)
        path = file_path

    # Validate path exists
    path_obj = PathLib(path)
    if not path_obj.exists():
        console.print(f"[red]Error: Path {path} does not exist[/red]")
        sys.exit(1)

    labels = list(label) if label else None

    # Handle list mode
    if list_mode:
        _list_evals(path, dataset, labels, function_name, limit)
        return

    # Default behavior: serve UI (don't auto-run)
    _serve(
        path=path,
        dataset=dataset,
        labels=labels,
        function_name=function_name,
        limit=limit,
        dev=dev,
        results_dir=results_dir,
        host=host,
        port=port,
        quiet=quiet,
    )


@cli.command('run')
@click.argument('path', type=str)
@click.option('--dataset', '-d', help='Filter by dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Filter by label(s)')
@click.option('--limit', type=int, help='Limit the number of evaluations')
@click.option('--output', '-o', type=click.Path(dir_okay=False), help='Path to JSON file for results')
@click.option('--csv', '-s', type=click.Path(dir_okay=False), help='Path to CSV file for results')
@click.option('--concurrency', '-c', default=0, type=int, help='Number of concurrent evaluations (0 for sequential)')
@click.option('--timeout', type=float, help='Global timeout in seconds')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
@click.option('--json', 'json_mode', is_flag=True, help='Output results as compact JSON to stdout')
def run_cmd(
    path: str,
    dataset: Optional[str],
    label: tuple,
    limit: Optional[int],
    output: Optional[str],
    csv: Optional[str],
    concurrency: int,
    timeout: Optional[float],
    verbose: bool,
    json_mode: bool,
):
    """Run evaluations in headless mode (for CI/CD)."""
    from pathlib import Path as PathLib

    # Parse path to extract file path and optional function name
    function_name = None
    if '::' in path:
        file_path, function_name = path.rsplit('::', 1)
        path = file_path

    # Validate path exists
    path_obj = PathLib(path)
    if not path_obj.exists():
        if json_mode:
            click.echo(json.dumps({"error": f"Path {path} does not exist"}))
        else:
            console.print(f"[red]Error: Path {path} does not exist[/red]")
        sys.exit(1)

    labels = list(label) if label else None

    # Run evaluations
    runner = EvalRunner(concurrency=concurrency, verbose=verbose, timeout=timeout)
    reporter = ProgressReporter() if not json_mode else None

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
            on_complete=reporter.on_complete if reporter else None,
            limit=limit
        )
    except Exception as e:
        if json_mode:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error during runner.run(): {e}[/red]")
            console.print("[red]Full traceback:[/red]")
            console.print(traceback.format_exc())
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

    if summary['results']:
        table = format_results_table(summary['results'])
        console.print(table)

    # Print summary
    console.print("\n[bold]Evaluation Summary[/bold]")
    console.print(f"Total Functions: {summary['total_functions']}")
    console.print(f"Total Evaluations: {summary['total_evaluations']}")
    console.print(f"Errors: {summary['total_errors']}")

    if summary['total_with_scores'] > 0:
        console.print(f"Passed: {summary['total_passed']}/{summary['total_with_scores']}")

    if summary['average_latency'] > 0:
        console.print(f"Average Latency: {summary['average_latency']:.3f}s")

    if output:
        console.print(f"\n[green]Results saved to: {output}[/green]")
    if csv:
        console.print(f"[green]Results saved to: {csv}[/green]")


def _list_evals(path: str, dataset: Optional[str], labels: Optional[List[str]], function_name: Optional[str], limit: Optional[int]):
    """List evaluations without running them."""
    eval_functions = EvalDiscovery().discover(
        path=path,
        dataset=dataset,
        labels=labels,
        function_name=function_name
    )

    if limit is not None:
        eval_functions = eval_functions[:limit]

    if not eval_functions:
        console.print("[yellow]No evaluations found matching the criteria[/yellow]")
        return

    eval_info_list = [{
        "function": func.__name__,
        "dataset": func.dataset,
        "labels": func.labels,
        "input": func.context_kwargs.get('input'),
        "reference": func.context_kwargs.get('reference'),
        "metadata": func.context_kwargs.get('metadata'),
        "evaluators": [e.__name__ for e in func.evaluators],
        "target": func.target.__name__ if func.target else None,
        "has_context": func.context_param is not None,
    } for func in eval_functions]

    console.print(format_eval_list_table(eval_info_list))
    console.print(f"\\n[bold]Total evaluations:[/bold] {len(eval_info_list)}")
    console.print(f"[bold]Unique datasets:[/bold] {len(set(i['dataset'] for i in eval_info_list))}")


def _serve(
    path: str,
    dataset: Optional[str],
    labels: Optional[List[str]],
    function_name: Optional[str],
    limit: Optional[int],
    dev: bool,
    results_dir: str,
    host: str,
    port: int,
    quiet: bool,
):
    """Serve a web UI to browse and run evaluations."""
    try:
        from twevals.server import create_app
        import uvicorn
    except Exception:
        console.print("[red]Missing server dependencies. Install with:[/red] \n  uv add fastapi uvicorn jinja2")
        raise

    from twevals.storage import ResultsStore

    # Discover functions (for display, not running)
    discovery = EvalDiscovery()
    functions = discovery.discover(path=path, dataset=dataset, labels=labels, function_name=function_name)
    if limit is not None:
        functions = functions[:limit]

    # Create store and generate run_id for when user triggers run
    store = ResultsStore(results_dir)
    run_id = store.generate_run_id()

    # Create app - does NOT auto-run, just displays discovered evals
    app = create_app(
        results_dir=results_dir,
        active_run_id=run_id,
        path=path,
        dataset=dataset,
        labels=labels,
        function_name=function_name,
        limit=limit,
        discovered_functions=functions,  # For display only
    )

    if not functions:
        console.print("[yellow]No evaluations found matching the criteria.[/yellow]")

    url = f"http://{host}:{port}"
    console.print(f"\n[bold green]Twevals UI[/bold green] serving at: [bold blue]{url}[/bold blue]")
    console.print(f"[cyan]Found {len(functions)} evaluation(s). Click Run to start.[/cyan]")
    console.print("Press Esc to stop (or Ctrl+C)\n")

    Thread(target=lambda: (time.sleep(0.5), webbrowser.open(url)), daemon=True).start()

    log_level = "warning" if quiet else "info"
    access_log = not quiet

    if dev:
        from pathlib import Path as _Path
        import os as _os, json as _json

        repo_root = _Path('.').resolve()
        _os.environ["TWEVALS_RESULTS_DIR"] = str(results_dir)
        _os.environ["TWEVALS_ACTIVE_RUN_ID"] = str(run_id)
        _os.environ["TWEVALS_PATH"] = str(path)
        if dataset:
            _os.environ["TWEVALS_DATASET"] = str(dataset)
        if labels is not None:
            _os.environ["TWEVALS_LABELS"] = _json.dumps(labels)
        if function_name:
            _os.environ["TWEVALS_FUNCTION_NAME"] = str(function_name)
        if limit is not None:
            _os.environ["TWEVALS_LIMIT"] = str(limit)

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
        config = uvicorn.Config(app, host=host, port=port, log_level=log_level, access_log=access_log)
        server = uvicorn.Server(config)

        server_thread = Thread(target=server.run)
        server_thread.start()

        def wait_for_stop_signal():
            """Wait for Esc or Ctrl+C while preserving log output formatting."""
            try:
                if not sys.stdin.isatty():
                    server_thread.join()
                    return False

                import termios
                import select
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    mode = termios.tcgetattr(fd)
                    mode[3] = mode[3] & ~(termios.ICANON | termios.ECHO)
                    termios.tcsetattr(fd, termios.TCSADRAIN, mode)

                    while server_thread.is_alive():
                        if select.select([sys.stdin], [], [], 0.5)[0]:
                            ch = sys.stdin.read(1)
                            if not ch:
                                return False
                            if ch == '\x1b' or ch == '\x03':
                                return True
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except (ImportError, AttributeError, OSError):
                try:
                    while server_thread.is_alive():
                        ch = click.getchar()
                        if ch == '\x1b' or ch == '\x03':
                            return True
                except (EOFError, KeyboardInterrupt):
                    return True
            return False

        try:
            if wait_for_stop_signal():
                console.print("\nStopping server...")
                server.should_exit = True
        except (KeyboardInterrupt, SystemExit):
            console.print("\nStopping server...")
            server.should_exit = True

        server_thread.join()


def main():
    cli()


if __name__ == '__main__':
    main()
