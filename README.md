# EvalKit

A lightweight, code-first evaluation framework for testing AI agents and LLM applications.

## Installation

```bash
pip install evalkit
```

## Quick Start

```python
from evalkit import eval, EvalResult

@eval(dataset="my_tests")
def test_example():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"key": "accuracy", "value": 0.95}
    )
```

Run evaluations:

```bash
evalkit run tests/
```

## CLI Commands

### Basic Usage

```bash
# Run evaluations in a specific directory
evalkit run path/to/evals/

# Run evaluations in a specific file
evalkit run path/to/eval_file.py

# Get help
evalkit --help
evalkit run --help
```

### Filtering Options

```bash
# Filter by dataset name (comma-separated for multiple)
evalkit run tests/ --dataset my_dataset
evalkit run tests/ --dataset dataset1,dataset2

# Filter by labels (can specify multiple)
evalkit run tests/ --label production
evalkit run tests/ --label test --label staging
```

### Output Options

```bash
# Save results to JSON file
evalkit run tests/ --output results.json

# Run with verbose output (shows print statements from eval functions)
evalkit run tests/ --verbose
```

### Concurrency

```bash
# Run evaluations concurrently (default is sequential)
evalkit run tests/ --concurrency 4
```

### Combined Examples

```bash
# Run production evals with JSON output
evalkit run examples/ --label production --output prod_results.json

# Run specific dataset with verbose logging
evalkit run tests/ --dataset customer_service --verbose

# Run with concurrency and save results
evalkit run evals/ --concurrency 8 --output results.json
```

## Decorator Options

```python
# Basic decorator (dataset inferred from filename)
@eval
def test_simple():
    return EvalResult(input="in", output="out")

# With dataset
@eval(dataset="my_dataset")
def test_with_dataset():
    return EvalResult(input="in", output="out")

# With labels
@eval(labels=["production", "critical"])
def test_with_labels():
    return EvalResult(input="in", output="out")

# With both dataset and labels
@eval(dataset="customer_service", labels=["production"])
def test_full():
    return EvalResult(input="in", output="out")
```

## Output Format

The CLI displays:
- A detailed results table with dataset, input, output, status, scores, and latency
- Summary statistics including total functions, evaluations, errors, and pass rates
- JSON export option for programmatic analysis