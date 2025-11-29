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


@click.command()
@click.argument('path', type=str)
# Run options
@click.option('--dataset', '-d', help='Run evaluations for specific dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Run evaluations with specific label(s)')
@click.option('--output', '-o', type=click.Path(dir_okay=False), help='Path to JSON file for results')
@click.option('--csv', '-s', type=click.Path(dir_okay=False), help='Path to CSV file for results (include filename)')
@click.option('--concurrency', '-c', default=0, type=int, help='Number of concurrent evaluations (0 for sequential)')
@click.option('--timeout', type=float, help='Global timeout in seconds (overrides individual test timeouts)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
@click.option('--json', 'json_mode', is_flag=True, help='Output results as compact JSON to stdout')
@click.option('--list', 'list_mode', is_flag=True, help='List all evaluations without running them')
@click.option('--limit', type=int, help='Limit the number of evaluations to run')
# Session options
@click.option('--session', help='Session name to group runs together')
@click.option('--run-name', help='Name for this run (used as file prefix)')
# Serve options
@click.option('--serve', is_flag=True, help='Serve a web UI to browse results')
@click.option('--dev', is_flag=True, help='Enable hot-reload for development (watches repo for changes)')
@click.option('--results-dir', default='.twevals/runs', help='Directory for JSON results storage')
@click.option('--host', default='127.0.0.1', help='Host interface for the web server')
@click.option('--port', default=8000, type=int, help='Port for the web server')
@click.option('--quiet', '-q', is_flag=True, help='Reduce logging; hide access logs')
def cli(
    path: str,
    dataset: Optional[str],
    label: tuple,
    output: Optional[str],
    csv: Optional[str],
    concurrency: int,
    timeout: Optional[float],
    verbose: bool,
    json_mode: bool,
    list_mode: bool,
    limit: Optional[int],
    session: Optional[str],
    run_name: Optional[str],
    serve: bool,
    dev: bool,
    results_dir: str,
    host: str,
    port: int,
    quiet: bool,
):
    """Twevals - A lightweight evaluation framework for AI/LLM testing

    Run evaluations: twevals evals.py

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

    # Handle serve mode
    if serve:
        _serve(
            path=path,
            dataset=dataset,
            labels=labels,
            concurrency=concurrency,
            dev=dev,
            function_name=function_name,
            limit=limit,
            results_dir=results_dir,
            host=host,
            port=port,
            verbose=verbose,
            quiet=quiet,
            session_name=session,
            run_name=run_name,
        )
        return

    # Handle list mode
    if list_mode:
        import csv as csv_module

        eval_functions = EvalDiscovery().discover(
            path=path,
            dataset=dataset,
            labels=labels,
            function_name=function_name
        )

        if limit is not None:
            eval_functions = eval_functions[:limit]

        if not eval_functions:
            if json_mode:
                click.echo(json.dumps({"evaluations": [], "total": 0}))
            else:
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

        if json_mode:
            click.echo(json.dumps({
                "evaluations": _remove_none(eval_info_list),
                "total": len(eval_info_list)
            }, separators=(',', ':'), default=str))
            return

        if csv:
            with open(csv, 'w', newline='') as csvfile:
                writer = csv_module.DictWriter(csvfile, fieldnames=[
                    'function', 'dataset', 'labels', 'input', 'reference',
                    'metadata', 'evaluators', 'target', 'has_context'
                ])
                writer.writeheader()
                for info in eval_info_list:
                    writer.writerow({
                        'function': info['function'],
                        'dataset': info['dataset'],
                        'labels': ','.join(info['labels']),
                        'input': json.dumps(info['input']) if info['input'] is not None else '',
                        'reference': json.dumps(info['reference']) if info['reference'] is not None else '',
                        'metadata': json.dumps(info['metadata']) if info['metadata'] else '',
                        'evaluators': ','.join(info['evaluators']),
                        'target': info['target'] or '',
                        'has_context': 'yes' if info['has_context'] else 'no',
                    })
            console.print(f"[green]Evaluations list saved to: {csv}[/green]")
            return

        console.print(format_eval_list_table(eval_info_list))
        console.print(f"\\n[bold]Total evaluations:[/bold] {len(eval_info_list)}")
        console.print(f"[bold]Unique datasets:[/bold] {len(set(i['dataset'] for i in eval_info_list))}")
        return

    # Run evaluations (default behavior)
    runner = EvalRunner(concurrency=concurrency, verbose=verbose, timeout=timeout)

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


def _serve(
    path: str,
    dataset: Optional[str],
    labels: Optional[List[str]],
    concurrency: int,
    dev: bool,
    function_name: Optional[str],
    limit: Optional[int],
    results_dir: str,
    host: str,
    port: int,
    verbose: bool,
    quiet: bool,
    session_name: Optional[str] = None,
    run_name: Optional[str] = None,
):
    """Serve a web UI to browse results."""
    try:
        from twevals.server import create_app
        import uvicorn
    except Exception:
        console.print("[red]Missing server dependencies. Install with:[/red] \n  uv add fastapi uvicorn jinja2")
        raise

    from twevals.storage import ResultsStore
    from twevals.runner import EvalRunner

    # Discover functions
    discovery = EvalDiscovery()
    functions = discovery.discover(path=path, dataset=dataset, labels=labels, function_name=function_name)
    if limit is not None:
        functions = functions[:limit]

    # Create initial run with pending results
    store = ResultsStore(results_dir)
    run_id = store.generate_run_id()
    runner = EvalRunner(concurrency=concurrency or 0, verbose=verbose)

    initial_results = [{
        "function": f.func.__name__,
        "dataset": f.dataset,
        "labels": f.labels,
        "result": {
            "input": f.context_kwargs.get("input"),
            "reference": f.context_kwargs.get("reference"),
            "metadata": f.context_kwargs.get("metadata"),
            "output": None, "error": None, "scores": None, "latency": None,
            "run_data": None, "annotation": None, "annotations": None, "status": "pending",
        },
    } for f in functions]

    rerun_config = {
        "path": path, "dataset": dataset, "labels": labels,
        "function_name": function_name, "limit": limit,
        "concurrency": concurrency, "verbose": verbose,
    }
    summary = runner._calculate_summary(initial_results)
    summary["results"] = initial_results
    summary["rerun_config"] = rerun_config
    store.save_run(summary, run_id=run_id, session_name=session_name, run_name=run_name)

    # Create app - it will start running evaluations if functions provided
    app = create_app(
        results_dir=results_dir,
        active_run_id=run_id,
        path=path,
        dataset=dataset,
        labels=labels,
        concurrency=concurrency,
        verbose=verbose,
        function_name=function_name,
        limit=limit,
        session_name=session_name,
        run_name=run_name,
        initial_functions=functions if functions else None,
    )

    if not functions:
        console.print("[yellow]No evaluations found; serving UI with an empty run.[/yellow]")

    url = f"http://{host}:{port}"
    console.print(f"\n[bold green]Twevals UI[/bold green] serving at: [bold blue]{url}[/bold blue]")
    if functions:
        console.print("[cyan]Evaluations are running in the background; rows will update live as they finish.[/cyan]")
    console.print("Press Esc to stop (or Ctrl+C)\n")

    Thread(target=lambda: (time.sleep(0.5), webbrowser.open(url)), daemon=True).start()

    log_level = "warning" if quiet and not verbose else ("info" if not verbose else "debug")
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
        _os.environ["TWEVALS_CONCURRENCY"] = str(concurrency)
        _os.environ["TWEVALS_VERBOSE"] = "1" if verbose else "0"
        if function_name:
            _os.environ["TWEVALS_FUNCTION_NAME"] = str(function_name)
        if limit is not None:
            _os.environ["TWEVALS_LIMIT"] = str(limit)
        if session_name:
            _os.environ["TWEVALS_SESSION_NAME"] = str(session_name)
        if run_name:
            _os.environ["TWEVALS_RUN_NAME"] = str(run_name)

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
                    # Disable ICANON (line buffering) and ECHO, but keep OPOST (output processing)
                    # This ensures that \n from background threads is still translated to \r\n
                    mode[3] = mode[3] & ~(termios.ICANON | termios.ECHO)
                    termios.tcsetattr(fd, termios.TCSADRAIN, mode)
                    
                    while server_thread.is_alive():
                        # Check for input with timeout
                        if select.select([sys.stdin], [], [], 0.5)[0]:
                            ch = sys.stdin.read(1)
                            if not ch:  # EOF
                                return False
                            if ch == '\x1b' or ch == '\x03':
                                return True
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except (ImportError, AttributeError, OSError):
                # Fallback for Windows or non-POSIX
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
