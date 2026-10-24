#!/usr/bin/env python3
"""Run the three chain_dynamics jobs twice in fresh directories and verify them.

Freezes the SciPy expectations first, executes real MATLAB through the bridge,
then applies the independent comparator to each run and to the run pair. A
missing or unlicensed engine produces an explicit blocked report, never a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(HERE))

import compare as comparator  # noqa: E402
import oracle  # noqa: E402
from research_bridge.catalog import discover  # noqa: E402
from research_bridge.core import execute_job  # noqa: E402

JOBS = ["chain-uniform-n12.json", "chain-graded-n48.json", "chain-highstiff-n96.json"]


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default=str(Path.cwd() / "runs" / "study"))
    parser.add_argument("--expectations-root", default=str(Path.cwd() / "oracles" / "expectations"))
    parser.add_argument("--job-dir", default=str(HERE / "jobs"))
    parser.add_argument("--matlab")
    parser.add_argument("--max-timeout", type=float, default=600)
    parser.add_argument("--refresh-expectations", action="store_true")
    parser.add_argument("--only", default="", help="run a single job fixture stem or job id")
    args = parser.parse_args()

    selected = [name for name in JOBS if not args.only or args.only in (name, Path(name).stem)]
    if not selected:
        raise SystemExit(f"--only did not match any fixture: {args.only}")

    run_root = Path(args.run_root)
    expectations_root = Path(args.expectations_root)
    job_dir = Path(args.job_dir)
    config = {"executables": {"matlab": args.matlab}, "strict_executables": True} if args.matlab else None
    found = discover(config).get("matlab", {})
    report = {
        "schema_version": "research.chain.study.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "matlab",
        "operation": "chain_dynamics",
        "matlab": {"executable": found.get("executable"), "installed": found.get("installed"),
                   "availability": found.get("availability")},
        "jobs": [],
    }
    if not found.get("installed"):
        report.update(status="blocked",
                      reason="MATLAB executable is not installed or configured; no native execution attempted",
                      next_action="Install/activate MATLAB R2026a and rerun this study with --matlab <path> if discovery misses it")
        (run_root).mkdir(parents=True, exist_ok=True)
        path = run_root / "study-report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    all_passed = True
    for name in selected:
        job_path = (job_dir / name).resolve()
        job = json.loads(job_path.read_text(encoding="utf-8-sig"))
        job_id = job.get("id", job_path.stem)
        exp_dir = expectations_root / job_id
        before = digest(job_path)
        if args.refresh_expectations or not (exp_dir / "expectations.json").is_file():
            oracle.freeze(job_path, exp_dir)
        entry = {"job_id": job_id, "job_path": str(job_path), "job_sha256_before": before,
                 "expectations": str(exp_dir), "runs": [], "status": "pending"}
        previous = None
        for index in ("a", "b"):
            result = execute_job(job_path, run_root, config=config, max_timeout_s=args.max_timeout)
            run_dir = Path(result["workspace"])
            comparison_path = run_dir / "comparison.json"
            try:
                comparison = comparator.compare(run_dir, exp_dir, job_path)
                comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2, allow_nan=False),
                                           encoding="utf-8")
            except Exception as error:  # noqa: BLE001 - evidence must record the failure
                comparison = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
            run_record = {
                "label": index,
                "workspace": str(run_dir),
                "bridge_status": result.get("status"),
                "exit_code": (result.get("processes") or [{}])[0].get("exit_code"),
                "timed_out": (result.get("processes") or [{}])[0].get("timed_out"),
                "duration_s": (result.get("processes") or [{}])[0].get("duration_s"),
                "comparison_status": comparison.get("status"),
                "comparison_path": str(comparison_path),
                "failed_checks": [item["name"] for item in comparison.get("checks", []) if not item.get("passed")],
                "artifacts": result.get("artifacts", []),
            }
            entry["runs"].append(run_record)
            if previous is not None:
                try:
                    repetition = comparator.compare_runs(previous, run_dir, exp_dir)
                except Exception as error:  # noqa: BLE001
                    repetition = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
                entry["repetition"] = repetition
                (run_dir / "repetition.json").write_text(json.dumps(repetition, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
            previous = run_dir
            if result.get("status") != "passed" or comparison.get("status") != "passed":
                all_passed = False
        entry["job_sha256_after"] = digest(job_path)
        entry["job_unchanged"] = entry["job_sha256_after"] == before
        if not entry["job_unchanged"]:
            all_passed = False
        entry["status"] = "passed" if all(
            run["bridge_status"] == "passed" and run["comparison_status"] == "passed"
            for run in entry["runs"]) and entry.get("repetition", {}).get("status") == "passed" else "failed"
        if entry["status"] != "passed":
            all_passed = False
        report["jobs"].append(entry)

    identity_path = Path(report["jobs"][0]["runs"][0]["workspace"]) / "identity.json"
    if identity_path.is_file():
        report["matlab_identity"] = json.loads(identity_path.read_text(encoding="utf-8-sig"))
    report["status"] = "passed" if all_passed else "failed"
    (run_root).mkdir(parents=True, exist_ok=True)
    path = run_root / "study-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
