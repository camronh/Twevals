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


def main():
    cli()


if __name__ == '__main__':
    main()
