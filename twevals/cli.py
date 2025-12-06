import click
import sys
import inspect
import os
import traceback
import time
import webbrowser
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict
from threading import Thread

from rich.console import Console

from twevals.formatters import format_results_table
from twevals.decorators import EvalFunction
from twevals.discovery import EvalDiscovery
from twevals.runner import EvalRunner
from twevals.config import load_config


console = Console()


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
@click.option('--results-dir', default=None, help='Directory for JSON results storage')
@click.option('--port', default=None, type=int, help='Port for the web server')
@click.option('--session', default=None, help='Name for this evaluation session')
@click.option('--run', 'auto_run', is_flag=True, help='Automatically run all evals on startup')
def serve_cmd(
    path: str,
    dataset: Optional[str],
    label: tuple,
    results_dir: Optional[str],
    port: Optional[int],
    session: Optional[str],
    auto_run: bool,
):
    """Start the web UI to browse and run evaluations."""
    from pathlib import Path as PathLib

    # Load config and merge with CLI args
    config = load_config()
    results_dir = results_dir if results_dir is not None else config.get("results_dir", ".twevals/runs")
    port = port if port is not None else config.get("port", 8000)

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

    _serve(
        path=path,
        dataset=dataset,
        labels=labels,
        function_name=function_name,
        results_dir=results_dir,
        port=port,
        session_name=session,
        auto_run=auto_run,
    )


@cli.command('run')
@click.argument('path', type=str)
@click.option('--dataset', '-d', help='Filter by dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Filter by label(s)')
@click.option('--limit', type=int, help='Limit the number of evaluations')
@click.option('--output', '-o', type=click.Path(dir_okay=False), help='Override path for results JSON file')
@click.option('--concurrency', '-c', default=None, type=int, help='Number of concurrent evaluations (0 for sequential)')
@click.option('--timeout', type=float, help='Global timeout in seconds')
@click.option('--verbose', '-v', is_flag=True, help='Show stdout from eval functions')
@click.option('--visual', is_flag=True, help='Show rich progress dots, table, and summary')
@click.option('--session', default=None, help='Name for this evaluation session')
@click.option('--run-name', default=None, help='Name for this specific run')
@click.option('--no-save', is_flag=True, help='Skip saving results to file')
def run_cmd(
    path: str,
    dataset: Optional[str],
    label: tuple,
    limit: Optional[int],
    output: Optional[str],
    concurrency: Optional[int],
    timeout: Optional[float],
    verbose: bool,
    visual: bool,
    session: Optional[str],
    run_name: Optional[str],
    no_save: bool,
):
    """Run evaluations headless. Optimized for LLM agents by default."""
    from pathlib import Path as PathLib
    from twevals.storage import ResultsStore

    # Load config and merge with CLI args
    config = load_config()
    concurrency = concurrency if concurrency is not None else config.get("concurrency", 1)
    timeout = timeout if timeout is not None else config.get("timeout")

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

    # Set up runner and reporter based on mode
    runner = EvalRunner(concurrency=concurrency, verbose=verbose, timeout=timeout)
    reporter = ProgressReporter() if visual else None

    def on_complete_callback(func, result_dict):
        if verbose:
            result = result_dict["result"]
            if result.get("error"):
                console.print(f"\n[red]ERROR in {func.func.__name__}:[/red]\n{result['error']}")
        if reporter:
            reporter.on_complete(func, result_dict)

    if visual:
        console.print("[bold green]Running evaluations...[/bold green]")
    else:
        console.print(f"Running {path}...")

    try:
        summary = runner.run(
            path=path,
            dataset=dataset,
            labels=labels,
            function_name=function_name,
            on_start=reporter.on_start if reporter else None,
            on_complete=on_complete_callback if verbose or reporter else None,
            limit=limit
        )
        summary["path"] = path
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if visual:
            console.print(traceback.format_exc())
        sys.exit(1)

    # Save results to file (unless --no-save)
    saved_path = None
    if not no_save:
        if output:
            # --output overrides default results_dir
            runner._save_results(summary, output)
            saved_path = output
        else:
            # Save to config results_dir (default .twevals/runs)
            results_dir = config.get("results_dir", ".twevals/runs")
            store = ResultsStore(results_dir)
            run_id = store.save_run(summary, session_name=session, run_name=run_name)
            saved_path = str(store._find_run_file(run_id))

    if visual:
        # Rich output mode: progress dots, failures, table, summary
        reporter.print_failures()

        if summary["total_evaluations"] == 0:
            console.print("[yellow]No evaluations found matching the criteria[/yellow]")
            return

        if summary['results']:
            table = format_results_table(summary['results'])
            console.print(table)

        console.print("\n[bold]Evaluation Summary[/bold]")
        console.print(f"Total Functions: {summary['total_functions']}")
        console.print(f"Total Evaluations: {summary['total_evaluations']}")
        console.print(f"Errors: {summary['total_errors']}")

        if summary['total_with_scores'] > 0:
            console.print(f"Passed: {summary['total_passed']}/{summary['total_with_scores']}")

        if summary['average_latency'] > 0:
            console.print(f"Average Latency: {summary['average_latency']:.3f}s")

    if no_save:
        print(json.dumps(summary, default=str))

    # Print where results were saved (if saved)
    if saved_path:
        console.print(f"Results saved to {saved_path}")


def _serve(
    path: str,
    dataset: Optional[str],
    labels: Optional[List[str]],
    function_name: Optional[str],
    results_dir: str,
    port: int,
    session_name: Optional[str] = None,
    auto_run: bool = False,
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
        discovered_functions=functions,
        session_name=session_name,
    )

    if not functions:
        console.print("[yellow]No evaluations found matching the criteria.[/yellow]")

    url = f"http://127.0.0.1:{port}"
    console.print(f"\n[bold green]Twevals UI[/bold green] serving at: [bold blue]{url}[/bold blue]")
    if auto_run:
        console.print(f"[cyan]Auto-running {len(functions)} evaluation(s)...[/cyan]")
    else:
        console.print(f"[cyan]Found {len(functions)} evaluation(s). Click Run to start.[/cyan]")
    console.print("Press Esc to stop (or Ctrl+C)\n")

    Thread(target=lambda: (time.sleep(0.5), webbrowser.open(url)), daemon=True).start()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    server_thread = Thread(target=server.run)
    server_thread.start()

    # Auto-run evals if --run flag was passed
    if auto_run:
        def do_auto_run():
            time.sleep(0.5)  # Wait for server to be ready
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/runs/rerun",
                    data=b'{}',
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req, timeout=5)
            except urllib.error.URLError:
                pass  # Server not ready, user can click Run manually
        Thread(target=do_auto_run, daemon=True).start()

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
