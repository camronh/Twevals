---
name: /run-evals
description: Run twevals evaluations and analyze the results
---
# Run Evaluations

Run the twevals evaluation suite and provide analysis of the results.

## Instructions

1. First, identify the eval files to run:
   - Look for files matching `*eval*.py`, `*test*.py`, or check if user specified a path
   - If no evals found, ask the user where their eval files are located

2. Run the evaluations using the CLI:
   ```bash
   twevals run <path> --visual
   ```

3. After running, read and analyze the results:
   - Check the output for pass/fail summary
   - Read the saved JSON file from `.twevals/runs/` for detailed results
   - Identify any failures or errors

4. Provide a summary including:
   - Overall pass rate
   - Any failing tests with their error messages
   - Suggestions for fixing failures if applicable

## Options

If the user provides arguments after `/run-evals`, use them:
- A path: `twevals run <path> --visual`
- `--dataset <name>`: Filter by dataset
- `--label <name>`: Filter by label
- `--concurrency <n>`: Run in parallel
