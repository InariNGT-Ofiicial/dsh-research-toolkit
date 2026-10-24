"""Compiler skeleton matching this bundle's explicit adapter dispatch.

Copy into an isolated prototype first. It is documentation, not a loadable
runtime extension. No target-specific command-line flags are assumed here.
"""
from pathlib import Path

ENGINE = "candidate-target"  # Choose a catalog id after official-interface research.
OPERATION = "candidate-operation"
SUPPORTED_ENGINES = {ENGINE}
# A code-review/development checkpoint, never an argument supplied by a job.
NATIVE_IMPLEMENTATION_REVIEWED = False


def _inside(path, workspace):
    path, root = Path(path).resolve(), Path(workspace).resolve()
    if path != root and root not in path.parents:
        raise ValueError("candidate output/cwd escapes workspace")
    return path


def _prepare_native(job, workspace, executable):
    """Implement and return the real target plan, without executing it.

    Generate target-language source inside workspace. Use only officially
    verified fixed argv/API calls; never copy a free-form command from the job.
    Return source_path, command (or commands), cwd, timeout_s,
    expected_artifacts and required_markers. The target itself must produce
    declared native outputs. Do not use a different program as a silent fallback.
    """
    raise NotImplementedError("official target compiler and native evidence are not implemented")


def compile_job(job, workspace, executables):
    """Return the compiled-plan shape consumed by research_bridge.core.

    core.compile_job performs catalog/operation validation and later supplies
    schema_version, job_id, mode and workspace. To integrate, explicitly add
    this module to that dispatch; declaring SUPPORTED_ENGINES does not register it.
    """
    if job.get("engine") != ENGINE or job.get("operation") != OPERATION:
        raise ValueError("candidate adapter does not implement the requested engine/operation")
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / "candidate-source.txt"
    with source.open("x", encoding="utf-8") as stream:
        stream.write("BLOCKED: target-specific source has not been implemented.\n"
                     "Consult version-matched official documentation and the bridge candidate manifest.\n")
    plan = {"engine": ENGINE, "operation": OPERATION, "status": "compiled",
            "source_path": str(source), "command": [], "cwd": str(root),
            "timeout_s": job.get("timeout_s", 120), "expected_artifacts": [],
            "required_markers": [], "ready": False,
            "reason": "candidate template has not implemented a verified target interface"}
    executable = executables.get(ENGINE)
    if not executable or not Path(executable).is_file():
        plan["reason"] = "native executable is missing or unverified"
        return plan
    if not NATIVE_IMPLEMENTATION_REVIEWED:
        return plan
    try:
        native = _prepare_native(job, root, str(Path(executable).resolve()))
    except NotImplementedError as error:
        plan["reason"] = str(error)
        return plan
    if not isinstance(native, dict):
        raise ValueError("native compiler must return a plan object")
    if "command" in native and "commands" in native:
        raise ValueError("declare command or commands, not both")
    commands = native.get("commands") if "commands" in native else [native.get("command")]
    if not isinstance(commands, list) or not commands:
        raise ValueError("native command plan is empty")
    for command in commands:
        if not isinstance(command, list) or not command or any(not isinstance(v, str) or not v for v in command):
            raise ValueError("native argv must be a nonempty array of strings")
    if not native.get("expected_artifacts"):
        raise ValueError("native plan must declare fresh verifiable outputs")
    native["cwd"] = str(_inside(native.get("cwd", root), root))
    native["source_path"] = str(_inside(native["source_path"], root))
    if not Path(native["source_path"]).is_file():
        raise ValueError("generated native source is missing")
    native["expected_artifacts"] = [str(_inside(p, root)) for p in native["expected_artifacts"]]
    timeout = native.get("timeout_s", job.get("timeout_s", 120))
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 1800:
        raise ValueError("timeout_s must be between 0 and 1800")
    plan.update(native)
    # Caller-supplied plan metadata cannot relabel the target or bypass readiness.
    plan.update(engine=ENGINE, operation=OPERATION, status="compiled", ready=True,
                timeout_s=timeout)
    plan.pop("reason", None)
    return plan
