#!/usr/bin/env python3
"""Bounded native-user runner for the Python unittest suite.

Run through the installed research_run python/script operation so the tests use
normal host permissions. Output is captured for a durable receipt, echoed, and
bounded by a wall-clock timeout; expiry kills the process tree.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    output = Path(os.environ.get("RB_OUTPUT_DIR", ".")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config_path = os.environ.get("RB_INPUT_DATA", "")
    if not config_path or not Path(config_path).is_file():
        print("PYTHON_UNITTEST_FAILED: missing config", flush=True)
        return 1
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    python = Path(config["python"])
    plugin_root = Path(config["plugin_root"])
    timeout = float(config.get("timeout_s", 300))
    if not python.is_file():
        print("PYTHON_UNITTEST_FAILED: python missing", flush=True)
        return 1
    command = [str(python), "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    environment = dict(os.environ)
    environment.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = time.monotonic()
    timed_out = False
    process = subprocess.Popen(command, cwd=str(plugin_root), env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, shell=False)
    try:
        stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
        code = process.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            stdout_bytes, stderr_bytes = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_bytes, stderr_bytes = process.communicate(timeout=15)
        code = process.returncode if process.returncode is not None else -9
    stdout = stdout_bytes.decode("utf-8", "replace")
    stderr = stderr_bytes.decode("utf-8", "replace")
    (output / "python-unittest-output.txt").write_text(
        "--- stdout ---\n" + stdout + "\n--- stderr ---\n" + stderr, encoding="utf-8")
    print(stdout, end="")
    print(stderr, end="", file=sys.stderr)
    match = re.search(r"Ran (\d+) tests?", stderr + "\n" + stdout)
    report = {
        "schema_version": "research.python-unittest-runner.v1",
        "command": command,
        "cwd": str(plugin_root),
        "exit_code": code,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - started, 3),
        "timeout_s": timeout,
        "tests_run": int(match.group(1)) if match else None,
        "ok_line": bool(re.search(r"^OK\b", stderr, re.MULTILINE)),
    }
    (output / "python-unittest-runner.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("PYTHON_UNITTEST_RUNNER " + json.dumps({"exit_code": code, "timed_out": timed_out,
                                                  "tests_run": report["tests_run"]}), flush=True)
    if timed_out or code != 0:
        return 1
    print("PYTHON_UNITTEST_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
