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