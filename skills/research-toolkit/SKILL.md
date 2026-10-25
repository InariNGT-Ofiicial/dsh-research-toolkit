---
name: research-toolkit
description: "Compile and run reproducible jobs in installed research software, inspect native artifacts, and report verified or blocked capabilities."
---

# Local research toolkit

Use `research_catalog` to learn the supported job schema and native operations, then `research_discover` to establish the current local environment. Keep the user's requested research method and target software explicit in a job JSON file.

For first-time setup, also call `research_integrations`. Summarize local software,
available operations, missing dependencies and registered companion tools in a
short briefing, then ask which software the user wants to bridge. Discovery does
not authorize an unrelated benchmark. When the user has already selected a scope,
continue within that authorization instead of asking again.

`research_integrations` returns the actual tool names and schemas visible to the
calling agent. Prefer registered `mcp__matlab__*` tools for interactive MATLAB,
Code Analyzer and MATLAB unit tests, and `zotero_*` tools for collections, richer
literature searches, notes and PDF fulltext. Call each external tool by its own
name through DSH so its policy, approval and output schema remain in effect.
Use `research_compile` / `research_run` for reproducible native job files and
artifact acceptance. Companion registration is not application verification;
report disconnected servers, missing toolboxes and license failures explicitly.
Only claim Simulink support when the relevant model tools are registered and
the requested licensed operation has actually passed. Zotero note writes require
a user-requested write; a software briefing does not authorize library edits.
See [companion integrations](../../docs/integrations.md) for pinned sources,
installation, conflicts and the acceptance boundary.

`research_compile` turns a job file into native source and a plan inside the configured workspace. Compilation can succeed while an engine is unavailable: inspect `data.ready` and the missing requirements. A compiled script is not evidence that a program ran.

`research_run` executes that job in the real software and retains its scripts, logs and artifacts. Inspect both the outer `ok`/`exitCode` and the canonical `data` result. Exit 0 means the CLI succeeded, exit 2 means a blocked dependency, and exit 1 means failure. Do not relabel a blocked adapter, dry run, source-only job, or substituted program as passed in the named software.

Validate scientific outputs against the job's expected numeric values, structure or file properties. Use `research_acceptance_report` on the saved run directory to read the actual evidence. When several programs implement the same analysis, compare their estimates using declared tolerances and compatible preprocessing. A program's availability check alone does not establish scientific equivalence.

Use a new workspace subdirectory for each experiment. `workspace` is confined to the configured `workspaceRoot`; `jobPath` names the source JSON. Reuse another program only when the user accepts that substitution and record which engine actually ran. Commercial software stays blocked until a valid local license and engine can be demonstrated.

The tools execute Python without a command shell. Configure an interpreter that has the bridge's Python dependencies via `pythonPath` (or `DSH_RESEARCH_PYTHON`). The bundle resolves its own runtime relative to its installed package and defaults `workspaceRoot` to `<DSH launch directory>/research-workspace`.

A minimal job uses `schema_version:research.job.v1`, `id`, `engine`, `operation`,
`inputs`, `parameters`, and optional `timeout_s` (1..1800). For numeric OLS use
`operation:analysis`, `inputs.data`, and parameters `method:linear_regression`,
`outcome`, `predictors`. For native scripts use `inputs.script`, declare
`expected_artifacts` and `required_markers`, and write outputs via
`RB_OUTPUT_DIR`; input CSV is `RB_INPUT_DATA`. Detailed contracts and other
operations are in [jobs.md](../../docs/jobs.md).

Document/Notebook dependencies declared in inputs retain their paths relative
to the source parent; use resource_map for external files. A fresh job workspace
does not sandbox arbitrary native scripts. Keep the DSH policy guard and the
user's authorized scope in control.

For an unsupported application or operation, or for complex adapter stress tests,
load the bundled `research-bridge-lab` skill. It routes to the
[extension guide](../../docs/bridge-research-guide.md) and isolated prototype
templates; it does not make unknown engines executable.
