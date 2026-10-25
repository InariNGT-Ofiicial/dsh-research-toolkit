# DSH bundle integration

This package is a native DSH Cordis bundle, delivered as the npm tarball `dsh-research-toolkit-0.4.0.tgz`. Its `package.json` declares `dsh.manifestVersion: 1` and `dsh.bundle.patch: ./cordis.patch.yml`; the patch inserts the research-toolkit plugin. No installer lifecycle scripts or npm runtime dependencies are needed.

The compatibility declaration preserves DSH `>=0.2.1-rc.2 <0.3.0` from the 0.3.1 compatibility maintenance release. rc.2 and rc.3 passed the native host regression; the current installed host is rc.3. Later versions within the declaration are not automatically covered by these test results.

## Install the reviewed package

Use the DSH plugin manager to install the local `.tgz` by its absolute path. With the Desktop-installed `dsh` command available, the equivalent command is:

```powershell
dsh plugin --profile desktop add "C:\path\to\dsh-research-toolkit-0.4.0.tgz"
```

Use the command distributed by the Desktop installation for its reserved `desktop` profile. A separately installed npm `dsh` launcher can reject that profile. Where configuration HMR is unavailable, reload or restart DSH after installation. Successful npm installation alone does not establish that a plugin started.

For a development profile, use `dsh plugin --profile <profile> add <absolute-source-directory>`. A local link reflects source edits after reload. The delivered `.tgz` contains the Python bridge and skill alongside the JavaScript entry; it is not a generic ZIP renamed to a DSH extension.

The host-only acceptance commands below do not edit an active Desktop profile. A live Agent acceptance run is separate: retain its actual model/tool events and restore any task-local configuration override after it finishes.

## Configure

The bundle defaults are:

```yaml
pythonPath: ''
workspaceRoot: ''
maxTimeoutSeconds: 600
```

`pythonPath` selects the Python interpreter. An empty value uses `DSH_RESEARCH_PYTHON` when set, otherwise `python` on `PATH`. `workspaceRoot` is the base for compiled and executed jobs; an empty value uses `<DSH launch working directory>/research-workspace`. `maxTimeoutSeconds` bounds the bridge call and is forwarded as the native-run time cap.

To override the whole plugin row through the profile's user patch, retain all wanted fields:

```yaml
- id: research-toolkit
  name: dsh-research-toolkit
  config:
    pythonPath: 'C:/path/to/python.exe'
    workspaceRoot: 'C:/ResearchWork'
    maxTimeoutSeconds: 600
```

DSH patch replacement uses a complete `config` row rather than deep-merging fields. The runtime is located relative to the installed bundle, without a machine-specific path in the JavaScript entry. Software executable discovery is handled by the Python catalog and its local configuration.

## Model-facing tools

| Tool | Parameters | Effect |
|---|---|---|
| `research_catalog` | `{}` | Read supported engines and operations |
| `research_integrations` | `{}` | Inspect companion tools visible to the current calling agent; does not execute or bypass their policies |
| `research_discover` | `{}` | Read local executable discovery |
| `research_compile` | `{jobPath, workspace?}` | Write native source and compiled plan |
| `research_run` | `{jobPath, workspace?}` | Execute a real native job in a fresh run directory |
| `research_acceptance_report` | `{acceptanceDir}` | Verify saved run evidence |

`workspace` is an optional base directory within `workspaceRoot`, including filesystem-link checks. Compile and run each use a fresh child directory, so repeated requests preserve earlier source and evidence. The source job file and report directory may be absolute paths. Every call returns `{ok,status,exitCode,command,data,diagnostics,durationMs}`. `data` is the complete canonical CLI JSON result. The outer `ok` is true only for exit 0; exit 2 is a blocked dependency and exit 1 is failure. DSH transport success does not mean the scientific job passed: callers must inspect `ok` and `data.status`.

The plugin registers its embedded `research-toolkit` and `research-bridge-lab` skills with `ctx.skills` when that service is present, including each source path and the native `{kind: "directory", path: ...}` resource base. The official model-facing `skill` tool can validate and render both; no files are copied into the user's shared skills directory. The lab skill routes unsupported-software research and complex stress tests to the [Chinese extension guide](bridge-research-guide.md) and [candidate templates](extensions/README.md). Catalog exposes those installed paths through `extension_guidance`. These resources do not load unknown adapters or turn blocked candidates into native capabilities.

Native DSH allow/deny/ask policy applies before the bridge executes. Catalog, discovery, and report reads declare concurrent safety; compile and run remain exclusive. Child processes use argument arrays and no command shell. Cancellation and time bounds stop the process tree started by the bridge. Unloading the plugin also cancels active calls and waits for their child-process cleanup.

## Reproduce native host acceptance

The host test imports the actual `ToolRuntime`, `SkillRegistry`, and Cordis `Context` from an installed DSH module tree. When an Electron ASAR is supplied, the test extracts public runtime package code into a task-local cache and records the loaded versions plus the tools-entry SHA-256. It does not load a live profile, credentials, sessions, network connections, or a model API. The system-prompt service is a small test fixture; this test does not claim a complete Desktop UI conversation.

```powershell
$env:DSH_HOST_ASAR = 'C:\path\to\DSH\resources\app.asar'
$env:DSH_HOST_CACHE = 'C:\ResearchWork\host-runtime'
$env:DSH_TEST_WORKSPACE = 'C:\ResearchWork\host-tests'
$env:DSH_TEST_PYTHON = 'C:\path\to\python.exe'
node --test tests/dsh-host.test.mjs tests/skill-tool-native.test.mjs
```

Alternatively, set `DSH_HOST_MODULE_ROOT` to a directory containing the original DSH `node_modules`. The test performs real catalog/discovery/compile/run/report calls through the native execution pipeline, verifies OLS estimates and missing-row handling, checks blocked interpreters and native guards, and verifies plugin disposal. It saves `dsh-native-host-report.json` inside the reported test directory.

The skill regression additionally loads the official `@deepseek-ai/dsh-tool-skill` module and calls `ToolRuntime.execute` to verify its output schema and rendered directory hint. A negative control submits the former string resource base and confirms that the official validation rejects it. Unrelated agents and working-directory services are minimal fixtures; the skill tool, registry, runtime, schema and renderer use unmodified host code. Its separate evidence is `skill-native-host-report.json`.

## Pack

```powershell
npm pack --dry-run --json
npm pack --ignore-scripts --pack-destination <reviewed-output-directory>
```

Inspect the tarball's `package/package.json`, bundle patch, JavaScript entry, Python modules, scenarios and skill. Generated run directories, `__pycache__`, `.pyc`, installed applications and proprietary engines are outside the package allowlist. Preserve the separate software acceptance report so source-only and blocked adapters remain visible at delivery.
