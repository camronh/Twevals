---
name: /analyze-results
description: Analyze twevals evaluation results from the latest or specified run
---
# Analyze Evaluation Results

Read and analyze twevals evaluation results, providing insights and recommendations.

## Instructions

1. Find the results file:
   - Check `.twevals/runs/` for the latest results
   - Or use the path provided by the user
   - Look for `latest.json` as a shortcut to the most recent run

2. Read and parse the JSON results file

3. Provide comprehensive analysis:

   **Summary Statistics:**
   - Total evaluations run
   - Pass rate (total_passed / total_with_scores)
   - Error count
   - Average latency

   **Failure Analysis:**
   - List each failing test with:
     - Function name and dataset
     - Input that caused the failure
     - Expected vs actual output
     - Score notes explaining why it failed

   **Error Analysis:**
   - List any runtime errors with stack traces
   - Identify common error patterns

   **Recommendations:**
   - Suggest fixes for failing tests
   - Identify potential issues in the evaluation logic
   - Note any performance concerns (slow tests, timeouts)

4. If there are trace URLs in `run_data`, mention them for debugging

## Output Format

Present results in a clear, structured format:
- Use tables for comparing pass/fail across datasets
- Use code blocks for showing problematic inputs/outputs
- Prioritize actionable insights over raw data
