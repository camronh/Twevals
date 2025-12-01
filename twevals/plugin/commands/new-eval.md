---
name: /new-eval
description: Create a new twevals evaluation function with guided setup
---
# Create New Evaluation

Help the user create a new twevals evaluation function.

## Instructions

1. **Gather Requirements** - Ask about:
   - What system/agent is being tested?
   - What behavior should be evaluated?
   - What inputs will be used?
   - What does success look like? (expected outputs, criteria)

2. **Determine Eval Type** - Based on requirements, choose:
   - **Simple assertion**: For exact match or boolean checks
   - **Parametrized**: For testing multiple input/output pairs
   - **LLM-judged**: For subjective quality assessment
   - **Multi-score**: For evaluating multiple criteria

3. **Create the Eval Function** - Generate code following this pattern:

```python
from twevals import eval, EvalContext

@eval(
    input="<the input to test>",
    reference="<expected output if applicable>",
    dataset="<logical grouping>",
    labels=["<optional>", "<tags>"],
)
async def test_<descriptive_name>(ctx: EvalContext):
    # Call the system under test
    ctx.output = await system_under_test(ctx.input)

    # Score the result
    ctx.add_score(
        <condition>,
        "<explanation of what was checked>",
        key="<metric_name>"
    )
```

4. **Add to Existing File or Create New** - Ask user preference:
   - Add to existing eval file
   - Create new file (suggest `evals/<dataset>_evals.py`)

5. **Suggest Follow-ups**:
   - Additional test cases via `@parametrize`
   - Edge cases to consider
   - How to run: `twevals run <file>::<function>`

## Templates

### Simple Eval
```python
@eval(input="test input", dataset="my_tests")
def test_basic(ctx: EvalContext):
    ctx.output = my_function(ctx.input)
    ctx.add_score(ctx.output is not None, "Returns a response")
```

### Parametrized Eval
```python
@eval(dataset="my_tests")
@parametrize("input,reference", [
    ("input1", "expected1"),
    ("input2", "expected2"),
])
def test_multiple(ctx: EvalContext):
    ctx.output = my_function(ctx.input)
    ctx.add_score(ctx.output == ctx.reference)
```

### Multi-Score Eval
```python
@eval(input="complex input", dataset="quality")
async def test_quality(ctx: EvalContext):
    ctx.output = await my_agent(ctx.input)

    ctx.add_score(len(ctx.output) > 100, "Sufficient length", key="length")
    ctx.add_score("keyword" in ctx.output, "Contains keyword", key="relevance")
    ctx.add_score(0.85, "Quality score", key="quality")
```
