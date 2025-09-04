import click
import sys
from typing import Optional

from rich.console import Console

from twevals.runner import EvalRunner
from twevals.formatters import format_results_table


console = Console()


@click.group()
def cli():
    """Twevals - A lightweight evaluation framework for AI/LLM testing"""
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--dataset', '-d', help='Run evaluations for specific dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Run evaluations with specific label(s)')
@click.option('--output', '-o', type=click.Path(dir_okay=False), help='Path to JSON file for results')
@click.option('--csv', '-s', type=click.Path(dir_okay=False), help='Path to CSV file for results (include filename)')
@click.option('--concurrency', '-c', default=0, type=int, help='Number of concurrent evaluations (0 for sequential)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def run(
    path: str,
    dataset: Optional[str],
    label: tuple,
    output: Optional[str],
    csv: Optional[str],
    concurrency: int,
    verbose: bool
):
    """Run evaluations in specified path"""
    
    # Convert label tuple to list
    labels = list(label) if label else None
    
    # Create runner
    runner = EvalRunner(concurrency=concurrency, verbose=verbose)
    
    # Run evaluations with progress indicator
    with console.status("[bold green]Running evaluations...", spinner="dots") as status:
        try:
            summary = runner.run(
                path=path,
                dataset=dataset,
                labels=labels,
                output_file=output,
                csv_file=csv,
                verbose=verbose
            )
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    
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
        console.print("[red]Missing server dependencies. Install with:[/red] \n  poetry add fastapi uvicorn jinja2")
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
