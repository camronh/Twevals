# Twevals Core Module Documentation

This directory contains the core implementation of the Twevals evaluation framework.

## File Structure

### `__init__.py`
Entry point for the twevals package. Exports the main public API:
- `eval` decorator for marking evaluation functions
- `EvalResult` class for structured evaluation results

### `schemas.py`
Pydantic models for data validation and serialization:
- `Score`: Model for individual evaluation scores (supports value-based or pass/fail scoring)
- `EvalResult`: Main result model containing input, output, scores, latency, and metadata

### `decorators.py`
Core decorator implementation:
- `@eval()` decorator: Marks functions as evaluations with optional dataset and label metadata
- `EvalFunction` class: Wrapper that handles both sync and async evaluation functions
- Automatic latency tracking and error handling
- Support for returning single results or lists of results

### `discovery.py`
Function discovery system:
- `EvalDiscovery` class: Recursively scans files/directories for decorated functions
- Dynamic module loading and inspection
- Filtering by dataset names and labels
- Handles import errors gracefully

### `runner.py`
Evaluation execution engine:
- `EvalRunner` class: Orchestrates evaluation execution
- Support for sequential and concurrent execution
- Async/sync function handling
- Result aggregation and summary statistics
- JSON and CSV export functionality

### `cli.py`
Command-line interface:
- Main CLI entry point using Click framework
- `run` command with options for filtering, output (JSON/CSV), and concurrency
- Progress indicators and status reporting
- Integration with Rich for beautiful console output

### `formatters.py`
Output formatting utilities:
- `format_results_table()`: Creates Rich tables for console display
- Handles truncation of long strings
- Color-coded status indicators (PASS/FAIL/ERROR/OK)
- Score formatting with support for different score types
