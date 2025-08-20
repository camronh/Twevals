# EvalKit

A lightweight, code-first evaluation framework for testing AI agents and LLM applications.

## Key Features

- 🎯 **Pytest-style decorators** - Familiar `@eval` and `@parametrize` decorators
- 📊 **Beautiful output** - Rich tables with automatic score tracking
- 🔄 **Parametrization** - Run the same test with multiple inputs
- 🏷️ **Flexible organization** - Group by datasets and labels
- 📁 **File-based** - Everything in version control
- ⚡ **Async support** - Works with async functions

## Installation

```bash
pip install evalkit
```

## Quick Start

```python
from evalkit import eval, EvalResult, parametrize

# Simple evaluation
@eval(dataset="my_tests")
def test_simple():
    return EvalResult(
        input="test input",
        output="test output",
        scores={"key": "accuracy", "value": 0.95}
    )

# With parametrization
@eval(dataset="my_tests")
@parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
])
def test_uppercase(input, expected):
    output = input.upper()
    return EvalResult(
        input=input,
        output=output,
        reference=expected,
        scores={"key": "match", "passed": output == expected}
    )
```

Run: `evalkit run tests/`

## CLI Commands

```bash
# Run evaluations
evalkit run path/to/tests/
evalkit run test_file.py

# Filter by dataset or labels
evalkit run tests/ --dataset my_dataset
evalkit run tests/ --label production

# Save results and options
evalkit run tests/ --output results.json
evalkit run tests/ --verbose  # Show print statements
evalkit run tests/ --concurrency 4  # Parallel execution
```

## Decorators

### @eval

```python
@eval  # Dataset inferred from filename
@eval(dataset="my_dataset")
@eval(labels=["production", "critical"])
@eval(dataset="service", labels=["prod"])
```

### @parametrize

```python
# Simple parameters
@parametrize("x,y", [(1, 2), (3, 4)])

# Named test cases
@parametrize("input,expected", 
    [("test1", "out1"), ("test2", "out2")],
    ids=["first", "second"]
)

# Cartesian product
@parametrize("model", ["gpt-3.5", "gpt-4"])
@parametrize("temperature", [0.0, 1.0])
# Creates 4 tests (2 models × 2 temperatures)
```

## EvalResult Schema

```python
EvalResult(
    input=Any,           # Required: test input
    output=Any,          # Required: model output
    reference=Any,       # Optional: expected output
    scores={             # Optional: metrics
        "key": str,
        "value": float,  # Numeric score
        "passed": bool,  # Pass/fail
    },
    error=str,           # Optional: error message
    latency=float,       # Optional: override auto timing
    metadata=dict,       # Optional: extra data
)
```