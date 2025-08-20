import click
import sys
from typing import Optional
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from evalkit.runner import EvalRunner
from evalkit.formatters import format_results_table


console = Console()


@click.group()
def cli():
    """EvalKit - A lightweight evaluation framework for AI/LLM testing"""
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--dataset', '-d', help='Run evaluations for specific dataset(s), comma-separated')
@click.option('--label', '-l', multiple=True, help='Run evaluations with specific label(s)')
@click.option('--output', '-o', help='Save results to JSON file')
@click.option('--concurrency', '-c', default=0, type=int, help='Number of concurrent evaluations (0 for sequential)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def run(
    path: str,
    dataset: Optional[str],
    label: tuple,
    output: Optional[str],
    concurrency: int,
    verbose: bool
):
    """Run evaluations in specified path"""
    
    # Convert label tuple to list
    labels = list(label) if label else None
    
    # Create runner
    runner = EvalRunner(concurrency=concurrency)
    
    # Run evaluations with progress indicator
    with console.status("[bold green]Running evaluations...", spinner="dots") as status:
        try:
            summary = runner.run(
                path=path,
                dataset=dataset,
                labels=labels,
                output_file=output,
                verbose=verbose
            )
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    
    # Display results
    if summary["total_evaluations"] == 0:
        console.print("[yellow]No evaluations found matching the criteria[/yellow]")
        return
    
    # Print summary
    console.print("\n[bold]Evaluation Summary[/bold]")
    console.print(f"Total Functions: {summary['total_functions']}")
    console.print(f"Total Evaluations: {summary['total_evaluations']}")
    console.print(f"Errors: {summary['total_errors']}")
    
    if summary['total_with_scores'] > 0:
        console.print(f"Passed: {summary['total_passed']}/{summary['total_with_scores']}")
    
    if summary['average_latency'] > 0:
        console.print(f"Average Latency: {summary['average_latency']:.3f}s")
    
    # Show results table
    if verbose and summary['results']:
        console.print("\n[bold]Detailed Results[/bold]")
        table = format_results_table(summary['results'])
        console.print(table)
    
    # Output file notification
    if output:
        console.print(f"\n[green]Results saved to: {output}[/green]")


def main():
    cli()


if __name__ == '__main__':
    main()