# Experience Specification: EZVals

**Version:** 0.0.2a15 (Unreleased)
**Generated:** 2025-12-05

This is the canonical source of truth for what EZVals enables users to do and how they do it. If someone deleted all the code but kept these documents, another developer should be able to rebuild the library with identical user-facing behavior.

---

## Related Documents

| Document | Covers |
|----------|--------|
| [EXPERIENCE_SPEC_PYTHON.md](./EXPERIENCE_SPEC_PYTHON.md) | Python API: `@eval`, `EvalContext`, `@parametrize`, schemas |
| [EXPERIENCE_SPEC_CLI.md](./EXPERIENCE_SPEC_CLI.md) | CLI: `ezvals run`, `ezvals serve`, flags, exit codes |
| [EXPERIENCE_SPEC_WEBUI.md](./EXPERIENCE_SPEC_WEBUI.md) | Web UI: table view, detail view, editing, export, REST API |

---

## Principles

### Core Philosophy

EZVals is a **pytest-inspired, code-first evaluation framework** for LLM applications and AI agents.

1. **Write evals like tests** - If you know pytest, you know EZVals. Use `assert`, `@parametrize`, and decorators.

2. **Everything lives locally** - Datasets, code, and results are version-controlled together. No cloud dependencies.

3. **Agent-friendly first** - The CLI is designed for coding agents to run, analyze, and iterate programmatically.

4. **Minimal, not opinionated** - Flexible per-test-case logic, unlike rigid "one function per dataset" frameworks.

5. **Analysis over pass/fail** - Unlike pytest where tests are binary, evals are for analysis. All results matter.

### Design Tradeoffs

| Optimized For | At The Expense Of |
|---------------|-------------------|
| Simplicity and minimal API | Advanced built-in evaluators |
| Local-first, version-controlled | Collaborative cloud features |
| Pytest familiarity | Novel paradigms |
| Agent/CLI-driven workflows | GUI-first workflows |
| Flexibility per test case | Opinionated structure |

---

## Capability Tiers

### Tier 1: Core (Must Never Break)

| Capability | What It Enables | Spec |
|------------|-----------------|------|
| `@eval` decorator | Mark functions as evaluations | [Python](./EXPERIENCE_SPEC_PYTHON.md#the-eval-decorator) |
| `EvalContext` injection | Build results declaratively | [Python](./EXPERIENCE_SPEC_PYTHON.md#evalcontext) |
| Assertion-based scoring | Pytest-like pass/fail | [Python](./EXPERIENCE_SPEC_PYTHON.md#assertion-based-scoring) |
| `ezvals run` command | Headless execution | [CLI](./EXPERIENCE_SPEC_CLI.md#ezvals-run) |
| Results saved to JSON | Persistence and analysis | [CLI](./EXPERIENCE_SPEC_CLI.md#output-options) |
| `ezvals serve` command | Web UI for review | [CLI](./EXPERIENCE_SPEC_CLI.md#ezvals-serve) |

### Tier 2: Important (Has Workarounds)

| Capability | What It Enables | Spec |
|------------|-----------------|------|
| `@parametrize` | Multiple test cases from one function | [Python](./EXPERIENCE_SPEC_PYTHON.md#parametrize-decorator) |
| `store()` | Set all context fields with explicit params | [Python](./EXPERIENCE_SPEC_PYTHON.md#the-store-method) |
| File-level defaults | Shared config across evals | [Python](./EXPERIENCE_SPEC_PYTHON.md#file-level-defaults) |
| Evaluators | Reusable post-processing | [Python](./EXPERIENCE_SPEC_PYTHON.md#evaluators) |
| Target hooks | Separated agent invocation | [Python](./EXPERIENCE_SPEC_PYTHON.md#target-hooks) |
| Filtering (`--dataset`, `--label`) | Selective runs | [CLI](./EXPERIENCE_SPEC_CLI.md#filtering-options) |
| Run/Stop in UI | Interactive execution | [WebUI](./EXPERIENCE_SPEC_WEBUI.md#running-evaluations) |

### Tier 3: Conveniences

| Capability | What It Enables | Spec |
|------------|-----------------|------|
| `--visual` output | Rich terminal display | [CLI](./EXPERIENCE_SPEC_CLI.md#output-options) |
| `--verbose` | Debug output | [CLI](./EXPERIENCE_SPEC_CLI.md#output-options) |
| `ezvals.json` config | Persistent defaults | [CLI](./EXPERIENCE_SPEC_CLI.md#configuration-file-ezvalsjson) |
| UI inline editing | Result annotation | [WebUI](./EXPERIENCE_SPEC_WEBUI.md#inline-editing) |
| CSV export | Spreadsheet analysis | [WebUI](./EXPERIENCE_SPEC_WEBUI.md#export) |
| Sessions/runs | Grouping for comparison | [CLI](./EXPERIENCE_SPEC_CLI.md#session-options) |

---

## Data Flow

```
┌─────────────────┐
│   @eval func    │
│   + params      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  EvalContext    │ ◄── ctx.store(input=, output=, scores=)
│  (mutable)      │
└────────┬────────┘
         │ .build()
         ▼
┌─────────────────┐
│  EvalResult     │ ◄── Immutable result
│  (immutable)    │
└────────┬────────┘
         │ evaluators run
         ▼
┌─────────────────┐
│  Final Result   │ ◄── Additional scores merged
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  JSON Storage   │ ◄── .ezvals/runs/{name}_{timestamp}.json
└─────────────────┘
```

---

## Invariants (Cross-Cutting)

### Scoring

1. Every score must have at least `value` or `passed`
2. Default score key is "correctness" unless overridden
3. Failed assertions become **scores** (passed=False), not errors
4. No explicit scoring = auto-pass score added

### Data Preservation

1. Input and output are always preserved, even on errors
2. Partial data survives exceptions
3. Error field captures messages without replacing other fields

### Execution

1. Target runs before eval body (if specified)
2. Evaluators run after eval completes
3. Async functions are properly awaited
4. Timeout terminates with error, not failed score

### CLI Exit Codes

1. Exit 0 = evaluations completed (regardless of pass/fail)
2. Exit non-zero = execution error only
3. Check JSON output for actual pass/fail status

---

## Discrepancies: Documentation vs Reality

### Untested (Implemented but No Test Coverage)

| Feature | Risk Level |
|---------|------------|
| `--no-save` flag | High |
| `--limit` flag | High |
| `--session` flag | Medium |
| `--run-name` flag | Medium |
| Auto-generated friendly names | Medium |
| Global `--timeout` CLI flag | Medium |

---

## Common User Confusion States

These are mistakes new users commonly make.

### Silent Failures (No Error, Wrong Behavior)

| What User Does | What Happens | Fix |
|----------------|--------------|-----|
| `@eval` without `ctx: EvalContext` parameter | Works, but assertions don't create scores | Add `ctx: EvalContext` parameter |
| `@parametrize` above `@eval` | Discovery fails silently | Put `@eval` above `@parametrize` |

### Clear Errors

| What User Does | Error Message |
|----------------|---------------|
| Target without context param | `ValueError: Target functions require... context parameter` |
| Custom param not in signature | `TypeError: got unexpected keyword argument 'prompt'` |
| `store(scores=...)` without key and no default | `ValueError: Must specify score key or set default_score_key` |
| Score missing value and passed | `ValidationError: Either 'value' or 'passed' must be provided` |
| Wrong return type | `ValueError: Evaluation function must return EvalResult, List[EvalResult], EvalContext, or None` |
| Path doesn't exist | `Error: Path nonexistent.py does not exist` (exit 1) |
| Invalid path type | `ValueError: Path some_file.txt is neither a Python file nor a directory` |
| Concurrency = 0 | `ValueError: concurrency must be at least 1, got 0` |
| Parametrize count mismatch | `ValueError: Expected 3 values, got 2` |

---

## Test Coverage Recommendations

### High Priority

```gherkin
# Add CLI tests
Scenario: --no-save outputs JSON to stdout
  When `ezvals run evals/ --no-save`
  Then JSON printed to stdout, no file created

Scenario: --limit restricts evaluation count
  Given 10 @eval functions
  When `ezvals run evals/ --limit 3`
  Then only 3 run
```

### Medium Priority

```gherkin
Scenario: --session and --run-name in output JSON
Scenario: Auto-generated friendly run names
Scenario: Global --timeout overrides decorator timeout
Scenario: Three-state filtering (include/exclude/any)
Scenario: Filter persistence across navigation
```

---

## Undocumented Capabilities

1. **Context Manager:** `with EvalContext() as ctx:`
2. **store() with spread:** `ctx.store(**agent_result, scores=True)` for clean agent integration
3. **Forward ref annotations:** `ctx: "EvalContext"` works
4. **call_async():** `await func.call_async()` for async functions
5. **Result status field:** "not_started", "pending", "running", "completed", "error", "cancelled"
6. **Annotations field:** Editable in UI, persists to JSON
