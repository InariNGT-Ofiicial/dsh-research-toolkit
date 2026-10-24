# Job contract

The machine-readable contract is `job.schema.json`. Relative input paths resolve
against the job JSON directory. Example numeric model:

```json
{
  "schema_version": "research.job.v1",
  "id": "intervention-model",
  "engine": "r",
  "operation": "analysis",
  "inputs": {"data": "data/study.csv"},
  "parameters": {"method":"linear_regression", "outcome":"score",
                 "predictors":["time","treatment","time_treatment"]},
  "timeout_s": 120
}
```

`analysis` generates numeric OLS with intercept and audited complete cases. It
does not infer categorical encoding, imputation or causal identification. Use
the scripted mixed-model scenario for repeated measures. Julia/Octave's compact
analysis CSV reader rejects quoted/irregular CSV; custom scripts can use their
full CSV packages. Missing engines still compile but remain `ready:false`.

For `script`, declare `inputs.script`, optional `inputs.data`, and
`parameters.expected_artifacts` (relative filenames) plus `required_markers`.
Statistical scripts receive `RB_INPUT_DATA` and `RB_OUTPUT_DIR`. SPSS uses its
own bundled Python, real Start/Submit sentinel, per-installation bounded mutex
and precise native OMS numbers. A startup timeout is not proof of no license.

For documents/figures, use `inputs.source` and `parameters.format`: Pandoc and
LibreOffice `convert`, Quarto/LaTeX/Graphviz `render`, Inkscape `export`.
Office `convert` accepts `application:word|excel|powerpoint` and exports PDF;
`recalculate` requires `application:excel`. Source opens read-only and its
automation instance is closed. Word and Excel macros are disabled.

Additional document dependencies go in `inputs`. Quarto, LaTeX and Notebook
preserve paths relative to the source parent. External resources default to
their basename; `parameters.resource_map`, e.g. `{"data":"data/study.csv"}`,
overrides placement within the job workspace. Metadata collisions and escapes
are rejected. Jupyter copies the notebook before `execute`; select a kernel
bound to the intended interpreter (this machine: `dsh-research`).

ImageJ `macro` reads `.ijm`; `{{OUTPUT_DIR}}` and `{{INPUT_DATA}}` are replaced.
`parameters.output` defaults to `measurements.csv`. ImageJ1 `-batch` suppresses
the main window but uses desktop AWT components; a display-free Linux server
requires an appropriate ImageJ2/Fiji runtime instead.

### MATLAB chain dynamics

`engine: matlab`, `operation: chain_dynamics` generates a complete, base-MATLAB
program for a fixed-fixed mass-spring-damper chain. The job carries parameter
data only; free-form MATLAB code is not accepted. Parameters: `case`
(`uniform`, `graded`, `high_stiffness`), `n` (3..256), `mass` and `stiffness`
as `{kind:"uniform", value:x}` or `{kind:"values", values:[...]}` with lengths
`n` and `n+1`, Rayleigh damping `{alpha, beta}` (C = alpha*M + beta*K),
`forcing` with 1..8 components `{nodes, amplitudes, frequencies_hz, phases}`,
`t_end`, `n_samples` (>=1001), `solver` `{rel_tol, abs_tol, max_step}`, and
`plot`.

The generated program builds M/K/C, solves the generalized eigenproblem with
`eig(K, M)`, checks mass orthonormality and the eigen residual (and the uniform
chain closed form), computes damped modes from the first-order state matrix,
integrates multi-frequency forcing with `ode45`/`odeset`, and writes
`modal.csv`, `damped_modes.csv`, `time_history.csv`, `energy.csv`,
`results.json`, `identity.json` (release, `version('-release')`, `matlabroot`,
batch flag), `chain_results.mat` (v7) and `chain_summary.png`. Energy balance
includes the damping dissipation integral; the dynamic residual uses
second-order central and one-sided difference stencils. Scientific acceptance
requires the separate SciPy oracle (`scenarios/chain_dynamics`), which freezes
expected values and tolerances before execution. MATLAB is a commercial engine:
missing installation compiles to `ready:false`. `version('-release')` returns
`2026a` without the `R` prefix, and `save(...,'-v7')` keeps the
`MATLAB 5.0 MAT-file` header; acceptance checks those exact native conventions
and then loads the MAT file to verify its variables.

JabRef/EndNote `bibliography` takes a JSON record array with `id`, `title`,
`author` (CSL family/given or literal), `year`, container-title, DOI. It emits
BibTeX/RIS. NVivo/MAXQDA/ATLAS.ti `codebook` exports `{codes:[...]}` to REFI-QDA
`.qdc`; `import_codebook` parses `.qdc` back to JSON. Hierarchy, GUIDs,
descriptions, colors, isCodable and sets/member GUIDs are supported; coded
passages and full `.qdpx` projects are outside this scope. Prism/JASP `table`
is CSV interchange; RStudio `project` emits `.Rproj`, not a live IDE session.
These routes always retain `application_verified:false`.

Zotero read-only `search|item|children` takes query/limit/key in `parameters`.
Its desktop must run with local communication enabled. Connections stay on
127.0.0.1:23119, bypass environment proxies and never request write permission.
`scenarios/zotero_fixture.py` tests a real desktop with a separate synthetic
library, then stops it. Git `snapshot` creates a separate repository; its
workspace must be outside the source to prevent recursive copying.

The runner verifies exit status, time limit, markers, fresh files, native
signatures/containers, structured content and SHA-256. Windows children enter
a kill-on-close Job Object before running. Saved evidence supports relative
artifact paths and failed scientific oracles override byte-integrity success.

The workspace is an organizational boundary, not an OS sandbox for arbitrary
native user scripts: they run with DSH's granted permissions. The native DSH
policy guard controls tool execution. Runtime code needs only the standard
library; `requirements-acceptance.txt` is the optional test/scientific stack.
Research applications and licenses are external dependencies.
