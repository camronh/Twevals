# Bug Diagnoses (Do Not Fix Here)

This doc explains likely root causes + the minimal “shape” of fixes for the reported issues, with pointers to where in the codebase they originate.

---

## 1) Target is not hot reloading

### Symptom
After running evals from the UI, changing the implementation of the **target** (e.g. switching models), then clicking **Rerun** does not reflect the change unless the server is restarted.

### What’s happening
The UI rerun endpoint (`ezvals/server/__init__.py`, `POST /api/runs/rerun`) calls `EvalDiscovery().discover(...)` each time, so the *eval file* is re-executed on rerun.

However, `EvalDiscovery._discover_in_file()` executes the eval file via `importlib.util.spec_from_file_location(...).loader.exec_module(module)` (`ezvals/discovery.py`). That re-executes the eval file in a fresh module object, **but it does not clear Python’s import cache** (`sys.modules`) for modules imported by the eval file.

So if your eval file does something like:

```py
from my_target_module import target

@eval(target=target)
def some_eval(ctx: EvalContext): ...
```

and you edit `my_target_module.py`, then rerun:
- the eval file is re-executed
- but `import my_target_module` returns the already-imported module from `sys.modules`
- which means `target` is still the old function object (or at least old module code)

That is why a process restart “fixes” it: restarting clears `sys.modules`.

### Solution shape (pick one)
1. **“Project module reload” on rerun** (recommended):
   - Before rediscovering, remove entries from `sys.modules` for modules whose `__file__` lives under the eval root (or the directory containing the eval file).
   - Call `importlib.invalidate_caches()`.
   - Then execute discovery again.
   - This forces `import my_target_module` to re-import updated code.

2. **Lazy import in user code** (workaround):
   - Import the target inside the function that needs it, or explicitly `importlib.reload(my_target_module)` before using the target.
   - This is less “magical” but pushes responsibility to users.

3. **Rely on an external reloader** (dev-only):
   - Run the server with a file-watcher reloader (e.g. `uvicorn --reload`) so the whole process restarts on code changes.
   - This is heavier than true “runtime reload” and may not be desired for eval runs.

### Extra note (naming collisions)
`spec_from_file_location(file_path.stem, file_path)` uses only the file stem as the module name (`ezvals/discovery.py`). Two different directories with the same filename can collide conceptually (and it makes debugging harder). Even though `exec_module` here doesn’t register in `sys.modules`, a unique module name (e.g. path-hash) is still a good idea if you later add caching/reloading.

---

## 2) LangSmith tagging: run_id / session name not available in `ctx`

### Symptom
You want `run_id`, `session_name`, `run_name`, etc. available inside the `EvalContext` so target/eval code can tag LangSmith traces (or otherwise attach metadata).

### What’s happening
Right now there is no plumbing from the runner/server “run metadata” into the per-eval `EvalContext`:

- `EvalContext` only stores `input`, `reference`, `metadata`, `trace_data`, etc. (`ezvals/context.py`). Any extra `**kwargs` passed to `EvalContext(...)` are accepted but discarded.
- `EvalFunction._create_context()` builds the context from decorator-provided values (`self.context_kwargs`) plus call kwargs (`ezvals/decorators.py`). In practice, the runner calls evals with no kwargs (`func()` / `func.call_async()`), so there’s no runtime metadata injected.
- The server does have `app.state.active_run_id`, `app.state.session_name`, `app.state.run_name` (`ezvals/server/__init__.py`), and the persisted JSON includes these fields (`ezvals/storage.py`), but none of that is currently threaded into the context object passed to targets/evals.

### Solution shape
Decide where “run metadata” should live (fields vs metadata), then inject it at execution time:

1. **Put run metadata in `ctx.metadata`** (minimal API change):
   - Example convention:
     - `ctx.metadata["ezvals"] = {"run_id": ..., "session_name": ..., "run_name": ..., "eval_path": ...}`
   - Requires injecting this dict into the context right before running target/eval.

2. **Add first-class fields on `EvalContext`** (more explicit):
   - Add `run_id`, `session_name`, `run_name`, maybe `eval_path`, `function_name`, `dataset`, `case_index`, etc.
   - Still requires injecting values at runtime.

Injection points (conceptual):
- Server side: when `start_run(...)` kicks off execution (`ezvals/server/__init__.py`), set a per-run context object for the runner thread/tasks.
- Runner side: before calling each `EvalFunction`, attach runtime info (either by mutating `func.context_kwargs["metadata"]`, or by providing a “runtime context override” facility).
- A clean approach is to use a `contextvars.ContextVar` (set in `start_run` / per task) that `EvalFunction._create_context()` reads and merges into the `EvalContext` it constructs.

---

## 3) Can’t rerun after changing run name

### Symptom
Run evals in the UI, rename the run, then rerun either a subset or the full suite. Rerun “breaks” (often manifests as results not updating / inconsistent state).

### What’s happening (root cause)
There’s a mismatch between:
- the run name on disk after rename, and
- the run name the server uses when persisting rerun updates.

Key details:
- Renaming is done via `PATCH /api/runs/{run_id}` which calls `store.rename_run(run_id, ...)` (`ezvals/server/__init__.py` → `ezvals/storage.py`). This renames the JSON file (e.g. `old_<run_id>.json` → `new_<run_id>.json`) and updates the `store` instance’s cache.
- The server keeps `app.state.run_name`, but `update_run(...)` does **not** update `app.state.run_name`.
- When saving during execution, `start_run(...)` creates a **new** `ResultsStore` instance (`run_store = ResultsStore(results_dir)`) and writes using `run_name=app.state.run_name` (`ezvals/server/__init__.py`).

After renaming, `app.state.run_name` is stale (“old”), so `start_run(...)` writes a new file `old_<run_id>.json` while the UI continues reading `new_<run_id>.json` (because `app.state.store` still points at it). Result: the UI doesn’t see updates, and you can end up with **two files with the same `run_id`**.

This can be reproduced purely with `ResultsStore`:
- Save `old_<run_id>.json`
- Rename to `new_<run_id>.json`
- Save again with same `run_id` but “old” `run_name`
- You now have both `new_<run_id>.json` and `old_<run_id>.json`, and different store instances can resolve the same `run_id` to different files depending on their cache.

### Solution shape (minimal options)
1. **Keep `app.state.run_name` in sync**:
   - When `PATCH /api/runs/{run_id}` renames the active run, also set `app.state.run_name = new_name`.

2. **Stop creating a second `ResultsStore` for writing**:
   - Use the same `store` instance for reads/writes inside the server so caches stay consistent.

3. **Preserve existing run_name on rerun**:
   - When writing a run with an existing `run_id`, don’t pass `run_name` so `save_run(...)` can preserve the existing filename’s run_name (`ezvals/storage.py` already has logic for this when `run_name` is omitted).

4. **Hard guard in storage** (defensive):
   - When saving `run_id=X`, delete any `*_<X>.json` siblings in the same session before writing the new file, ensuring there is only one file per `run_id`.

