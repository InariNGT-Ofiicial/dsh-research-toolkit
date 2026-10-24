#!/usr/bin/env python3
"""Real negative controls for matlab/chain_dynamics, with recovery.

Compile-time rejections run without MATLAB. Missing-runtime is a *simulated*
missing engine: discovery is pinned with strict_executables so no catalog
fallback or PATH lookup can reach the real installation. Native script failure,
missing artifact and timeout require MATLAB and are marked not executed when it
is absent. Expected-blocked controls that actually ran do not block the suite.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(HERE))

import compare as comparator  # noqa: E402
import oracle  # noqa: E402
from research_bridge.catalog import discover  # noqa: E402
from research_bridge.core import compile_job, execute_job, run_compiled  # noqa: E402

BASE_JOB = HERE / "jobs" / "chain-uniform-n12.json"


def fresh(base: Path, name: str) -> Path:
    path = base / f"{name}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_rejections(base: Path) -> list[dict]:
    base_job = json.loads(BASE_JOB.read_text(encoding="utf-8"))
    cases = [
        ("illegal-zero-mass", "invalid_mass", lambda p: p.update(mass={"kind": "values", "values": [1.0] * 11 + [0.0]}), "greater than 0"),
        ("illegal-negative-stiffness", "invalid_stiffness", lambda p: p.update(stiffness={"kind": "values", "values": [100.0] * 12 + [-1.0]}), "greater than 0"),
        ("dimension-mismatch", "dimension", lambda p: p.update(mass={"kind": "values", "values": [1.0] * 11}), "exactly 12 numbers"),
        ("non-finite-mass", "non_finite", lambda p: p.update(mass={"kind": "values", "values": [float("inf")] + [1.0] * 11}), "finite"),
        ("zero-rayleigh-damping", "invalid_damping", lambda p: p.update(damping={"alpha": 0.0, "beta": 0.0}), "alpha + beta > 0"),
        ("free-form-script-injection", "unsupported_parameter", lambda p: p.update(script="system('calc')"), "unsupported chain_dynamics parameters"),
    ]
    records = []
    for name, category, mutate, needle in cases:
        job = copy.deepcopy(base_job)
        mutate(job["parameters"])
        directory = fresh(base, name)
        (directory / "job.json").write_text(
            json.dumps(job, ensure_ascii=False, indent=2).replace("Infinity", "1e309"), encoding="utf-8")
        try:
            compile_job(job, directory / "workspace", config=None)
            record = {"name": name, "category": category, "status": "failed",
                      "reason": "compile unexpectedly accepted the invalid job", "passed": False}
        except Exception as error:  # noqa: BLE001 - rejection is the expected path
            passed = needle in str(error)
            record = {"name": name, "category": category,
                      "status": "rejected_as_expected" if passed else "failed",
                      "error_type": type(error).__name__, "reason": str(error),
                      "expected_fragment": needle, "job": str(directory / "job.json"), "passed": passed}
        records.append(record)
    return records


def summarize(report: dict) -> dict:
    """Expected-blocked controls that ran and passed are successes, not blocks."""
    compile_ok = bool(report["compile_rejections"]) and all(item["passed"] for item in report["compile_rejections"])
    controls = report.get("runtime_controls", [])
    executed = [item for item in controls if item.get("executed")]
    unexecuted = [item for item in controls if not item.get("executed")]
    executed_ok = bool(executed) and all(item["passed"] for item in executed)
    recovery_ok = bool(report.get("recovery") and report["recovery"].get("passed"))
    if unexecuted:
        names = ", ".join(item["name"] for item in unexecuted)
        return {"status": "blocked", "compile_passed": compile_ok, "executed_controls_passed": executed_ok,
                "recovery_passed": recovery_ok,
                "reason": f"required native control(s) were not executed: {names}"}
    if compile_ok and executed_ok and recovery_ok:
        return {"status": "passed", "compile_passed": True, "executed_controls_passed": True,
                "recovery_passed": True, "reason": "compile rejections, executed runtime controls and recovery passed"}
    return {"status": "failed", "compile_passed": compile_ok, "executed_controls_passed": executed_ok,
            "recovery_passed": recovery_ok, "reason": "one or more controls did not meet the expected outcome"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path.cwd() / "runs" / "negatives"))
    parser.add_argument("--expectations-root", default=str(Path.cwd() / "oracles" / "expectations"))
    parser.add_argument("--matlab")
    args = parser.parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    config = {"executables": {"matlab": args.matlab}, "strict_executables": True} if args.matlab else None
    found = discover(config).get("matlab", {})
    default_found = discover(None).get("matlab", {})
    valid_job = json.loads(BASE_JOB.read_text(encoding="utf-8"))
    simulated = Path.cwd() / "runs" / "negatives-simulated-missing" / "does-not-exist" / "matlab.exe"
    strict_config = {"executables": {"matlab": str(simulated)}, "strict_executables": True}
    strict_discovery = discover(strict_config).get("matlab", {})

    # Freeze the recovery oracle before the first negative; never change a
    # threshold after seeing a native result.
    expectations_root = Path(args.expectations_root)
    expectations_dir = expectations_root / valid_job["id"]
    if not (expectations_dir / "expectations.json").is_file():
        oracle.freeze(BASE_JOB, expectations_dir)
    expectations_sha256 = digest(expectations_dir / "expectations.json")

    report = {
        "schema_version": "research.chain.negatives.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "matlab_installed": bool(found.get("installed")),
        "matlab_executable": found.get("executable"),
        "discovery_isolation": {
            "strict_engine_pin": {"installed": bool(strict_discovery.get("installed")),
                                  "executable": strict_discovery.get("executable")},
            "default_discovery": {"installed": bool(default_found.get("installed")),
                                  "executable": default_found.get("executable")},
            "note": "missing-runtime is simulated by strict_executables with a nonexistent path; the real installation and global configuration are untouched",
        },
        "expectations": {"path": str(expectations_dir / "expectations.json"), "sha256": expectations_sha256,
                         "frozen_before_negatives": True},
        "compile_rejections": compile_rejections(root),
        "runtime_controls": [],
        "recovery": None,
    }

    # Simulated missing runtime: an explicit engine pin with no fallback.
    directory = fresh(root, "missing-runtime")
    pinned = directory / "does-not-exist" / "matlab.exe"
    strict_config = {"executables": {"matlab": str(pinned)}, "strict_executables": True}
    strict_discovery = discover(strict_config).get("matlab", {})
    compiled = compile_job(valid_job, directory / "workspace", config=strict_config)
    result = run_compiled(compiled, max_timeout_s=60)
    passed = (strict_discovery.get("installed") is False and compiled.get("ready") is False
              and result.get("status") == "blocked" and not result.get("processes"))
    report["runtime_controls"].append({
        "name": "missing-runtime", "category": "missing_runtime",
        "simulated_missing_runtime": True,
        "discovery_mode": "strict_executables_no_fallback",
        "pinned_executable": str(pinned),
        "strict_discovery_installed": strict_discovery.get("installed"),
        "default_discovery_installed": default_found.get("installed"),
        "expected_outcome": "blocked",
        "status": result.get("status"), "ready": compiled.get("ready"), "executed": True,
        "reason": result.get("reason") or compiled.get("reason"), "passed": passed,
        "workspace": str(directory),
    })

    if found.get("installed"):
        directory = fresh(root, "native-script-failure")
        compiled = compile_job(valid_job, directory / "workspace", config=config)
        source = Path(compiled["source_path"])
        text = source.read_text(encoding="utf-8")
        source.write_text(text.replace("function rb_chain_dynamics()\n",
                                       "function rb_chain_dynamics()\nerror('RB_SYNTHETIC_NATIVE_FAILURE');\n", 1),
                          encoding="utf-8")
        result = run_compiled(compiled, max_timeout_s=600)
        processes = result.get("processes") or []
        passed = result.get("status") == "failed" and bool(processes) and not processes[0].get("timed_out")
        report["runtime_controls"].append({
            "name": "native-script-failure", "category": "native_failure", "expected_outcome": "failed",
            "status": result.get("status"), "executed": True,
            "exit_code": processes[0].get("exit_code") if processes else None,
            "timed_out": processes[0].get("timed_out") if processes else None,
            "reason": "synthetic error injected into the generated program", "passed": passed,
            "workspace": str(directory),
        })

        directory = fresh(root, "missing-artifact")
        compiled = compile_job(valid_job, directory / "workspace", config=config)
        source = Path(compiled["source_path"])
        text = source.read_text(encoding="utf-8")
        if "'energy.csv'" not in text:
            raise RuntimeError("generated source no longer contains energy.csv")
        source.write_text(text.replace("'energy.csv'", "'energy_skipped.csv'"), encoding="utf-8")
        result = run_compiled(compiled, max_timeout_s=600)
        passed = result.get("status") == "failed" and any("energy.csv" in error for error in result.get("errors", []))
        report["runtime_controls"].append({
            "name": "missing-artifact", "category": "missing_artifact", "expected_outcome": "failed",
            "status": result.get("status"), "executed": True,
            "errors": result.get("errors"), "passed": passed, "workspace": str(directory),
        })

        directory = fresh(root, "timeout")
        timeout_job = copy.deepcopy(valid_job)
        timeout_job["timeout_s"] = 1
        compiled = compile_job(timeout_job, directory / "workspace", config=config)
        result = run_compiled(compiled, max_timeout_s=5)
        processes = result.get("processes") or []
        passed = result.get("status") == "failed" and any(p.get("timed_out") for p in processes)
        report["runtime_controls"].append({
            "name": "timeout", "category": "timeout", "expected_outcome": "failed",
            "status": result.get("status"), "executed": True,
            "timed_out": any(p.get("timed_out") for p in processes),
            "duration_s": processes[0].get("duration_s") if processes else None,
            "passed": passed, "workspace": str(directory),
        })

        recovery = execute_job(BASE_JOB, root / "recovery", config=config, max_timeout_s=600)
        run_dir = Path(recovery["workspace"])
        comparison = comparator.compare(run_dir, expectations_dir, BASE_JOB)
        passed = recovery.get("status") == "passed" and comparison.get("status") == "passed"
        report["recovery"] = {"status": "passed" if passed else "failed", "workspace": str(run_dir),
                              "bridge_status": recovery.get("status"),
                              "comparison_status": comparison.get("status"), "passed": passed}
    else:
        for name, category in (("native-script-failure", "native_failure"),
                               ("missing-artifact", "missing_artifact"),
                               ("timeout", "timeout")):
            report["runtime_controls"].append({
                "name": name, "category": category, "expected_outcome": "failed",
                "status": "not_run", "executed": False,
                "reason": "MATLAB is not installed; this native control was not executed", "passed": False})

    report["expectations_sha256_after"] = digest(expectations_dir / "expectations.json")
    report["expectations_unchanged"] = report["expectations_sha256_after"] == expectations_sha256
    if not report["expectations_unchanged"]:
        report["recovery"] = report.get("recovery") or {"status": "failed", "passed": False,
                                                        "reason": "expectations changed during the run"}
    report.update(summarize(report))
    path = root / "negative-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else (0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
