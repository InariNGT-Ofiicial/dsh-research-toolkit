# DSH Research Toolkit

This native DSH plugin discovers local research software, compiles explicit jobs into each application's native language, runs available engines, and preserves evidence for acceptance. Supported operations and local execution status are listed by `research_catalog`, `research_discover`, and the accompanying acceptance report.

Compilation, actual application execution, and file interchange have different evidence boundaries. An unavailable commercial engine can have a usable native compiler while its execution remains blocked. Writing a REFI-QDA, RIS, BibTeX or table file does not establish that its target GUI application opened or processed it.

## Install

The offline DSH bundle is `dsh-research-toolkit-0.3.0.tgz`, produced by npm rather than a renamed ZIP. It contains the Cordis entry, bundle manifest/patch, Python bridge, scenarios, and embedded research skills. It does not contain research applications or commercial licenses.

Use the DSH plugin manager to select the reviewed local tarball, or use the Desktop-installed command for the reserved `desktop` profile:

```powershell
dsh plugin --profile desktop add "C:\path\to\dsh-research-toolkit-0.3.0.tgz"
```

DSH's native add operation selects new bundles for activation. `scripts/install.ps1` therefore requires an explicit profile and only displays the command; it does not execute it or modify the running profile:

```powershell
pwsh -File scripts/install.ps1 -Profile desktop -PackagePath "C:\path\to\dsh-research-toolkit-0.3.0.tgz"
```

The npm-only `dsh` launcher can reject the reserved Desktop profile; use the command supplied by the Desktop installation. Reload or restart where configuration HMR is unavailable. Runtime acceptance does not itself change the active application's configuration.

## Configure and call

Configuration fields are `pythonPath`, `workspaceRoot`, and `maxTimeoutSeconds`. An empty interpreter chooses `DSH_RESEARCH_PYTHON` or `python`; an empty workspace root chooses `<DSH launch directory>/research-workspace`. Point the interpreter at the installed bridge environment when its jobs require additional Python packages. All runtime code is located relative to the installed bundle.

The agent receives five tools:

| Tool | Input | Result |
|---|---|---|
| `research_catalog` | `{}` | Supported engines and operations |
| `research_discover` | `{}` | Local executable discovery |
| `research_compile` | `{jobPath, workspace?}` | Native scripts and plan in a fresh directory |
| `research_run` | `{jobPath, workspace?}` | Real engine execution and recorded artifacts |
| `research_acceptance_report` | `{acceptanceDir}` | Saved process and artifact verification |

Every tool returns `{ok,status,exitCode,command,data,diagnostics,durationMs}`. The canonical CLI result is in `data`; exit 0 means success/compiled, 2 means blocked, and 1 means failed. `workspace` selects a base directory within the configured root; repeated compile/run calls preserve earlier results in fresh child directories. Source job files may be elsewhere on the local filesystem.

The embedded skill is registered with the native DSH skill service when present. No copy into a shared global skills directory is required. See [DSH integration and verification](docs/dsh-plugin.md) for complete configuration examples, native host test commands, installation semantics, and the tested runtime boundary.

## Reproduce the package

```powershell
python scripts/package_plugin.py --output "C:\ResearchWork\package"
```

The script runs `npm pack` with lifecycle scripts disabled and offline mode, checks the actual tarball's manifest and file boundary, and saves a SHA-256 package report. It refuses to replace an existing tarball unless `--overwrite` is explicitly supplied.

Scientific scenarios and application-specific acceptance details are in the accompanying acceptance report. The native DSH host test uses actual Cordis, ToolRuntime, SkillRegistry, and app-boot package code from the installed host; it does not claim a recorded Desktop UI conversation.

## Validated scope on this machine (2026-10-24)

Version 0.3.0 adds `matlab/chain_dynamics`: a complete base-MATLAB program for a
fixed-fixed mass-spring-damper chain (generalized modes and mass orthogonality,
Rayleigh-damped modes, multi-frequency `ode45` transient, energy balance with
dissipation, dynamic residual, CSV/JSON/v7 MAT/PNG outputs). The SciPy oracle
and comparator in `scenarios/chain_dynamics` freeze expectations and tolerances
before execution and reject NaN/Inf, truncated shapes and stale hashes. On this
machine, three jobs (N=12/48/96) each ran twice in fresh directories on MATLAB
R2026a `26.1.0.3203278`; all six runs passed the frozen oracle, reruns were
identical within `1e-10`, and the job JSON hashes were unchanged. Six compile
rejections, simulated missing runtime, native error, missing artifact, timeout
and recovery passed. Installing this bundle and accepting it in an actual model
session remain separate steps; the catalog entry alone is not a passed run.

The catalog has 29 named entries: 17 tested native/local-API routes, 8 explicitly
limited interchange routes, and 4 commercial native routes blocked by missing
applications. Office validation includes real Word/PDF, Excel recalculation of
the 576-row study workbook, and PowerPoint/PDF. Each application is validated
only for the listed operations, not its full menu or all research methods.

R, Python, jmv, SPSS, Octave and Julia match an independent QR oracle on the same
synthetic 144-subject, four-visit study (535 complete rows, 41 missing outcomes).
The R random-intercept model, 12 Holm comparisons and 200 subject bootstrap
replicates have independent numerical checks. Zotero uses an isolated synthetic
library with 12 papers; no user's normal library is written. ImageJ measures six
known-size targets and rejects small noise; graph/figure and multilingual report
outputs have structural and content oracles.

Stata, SAS and Origin stay blocked pending installation/licensing. MATLAB is
installed at `E:/MATLAB` (R2026a, `26.1.0.3203278`); the native `chain_dynamics`
operation is accepted for the three declared jobs on this release. Installing
the 0.3.0 bundle and the subsequent actual-model tool session are still pending.
JabRef, EndNote, NVivo, MAXQDA, ATLAS.ti, Prism, JASP and RStudio entries are file
interchange only; their GUI/live sessions are not proven by those files. JASP and
JabRef were not installed as duplicate GUI alternatives to the validated stack.
The coverage matrix is not an exhaustive list of every discipline's software.

See [job contracts and boundaries](docs/jobs.md), [native DSH packaging](docs/dsh-plugin.md)
and the delivered acceptance report. `requirements-acceptance.txt` declares the
optional scientific/test environment; bridge runtime itself uses the standard
library. The source workspace is not an OS sandbox for arbitrary user scripts.

```powershell
python -B -m unittest discover -s tests -p "test_*.py" -v
python -B scenarios/run_acceptance.py C:\ResearchWork\acceptance --zotero-fixture --spss-timeout 90
```

Run real applications with normal user permissions. A restrictive executor may
block SPSS subprocesses, Jupyter's connection-file ACLs or Office COM; that is
distinct from a failed software license or a passed analysis. Tests use the
bundled standard XSD and local optional test dependencies.

## Bridge research for unfamiliar software

Load the bundled `research-bridge-lab` skill when the catalog does not cover a local research application. The [bridge research guide](docs/bridge-research-guide.md) provides isolated candidate development, evidence templates and promotion criteria. Candidates are not silently registered as supported engines. `research_catalog` exposes the installed guide and template paths.
