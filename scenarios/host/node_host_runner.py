#!/usr/bin/env python3
"""Bounded native-user runner for the Node DSH host tests.

Run through the research bridge's python/script operation. Node inherits this
process's stdout/stderr, so the outer layer does not create a second pipe. The
child is bounded by a wall-clock timeout and, on expiry, its own process tree is
terminated with taskkill /T. This does not turn a failed host test into a pass.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def fail(message: str) -> int:
    print("NODE_HOST_RUNNER_FAILED: " + message, flush=True)
    return 1


def main() -> int:
    output = Path(os.environ.get("RB_OUTPUT_DIR", ".")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config_path = os.environ.get("RB_INPUT_DATA", "")
    if not config_path or not Path(config_path).is_file():
        return fail("RB_INPUT_DATA does not name the runner config JSON")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    node = Path(config["node"])
    plugin_root = Path(config["plugin_root"])
    test_file = config.get("test", "tests/dsh-host.test.mjs")
    timeout = float(config.get("timeout_s", 300))
    if not node.is_file():
        return fail(f"node executable missing: {node}")
    if not (plugin_root / test_file).is_file():
        return fail(f"host test missing: {plugin_root / test_file}")

    environment = dict(os.environ)
    environment.update({key: str(value) for key, value in config.get("env", {}).items()})
    environment.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    command = [str(node), test_file]
    started = time.monotonic()
    timed_out = False
    process = subprocess.Popen(
        command, cwd=str(plugin_root), env=environment,
        stdin=subprocess.DEVNULL, stdout=None, stderr=None, shell=False,
    )
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            code = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait(timeout=15)
    duration = round(time.monotonic() - started, 3)
    report = {
        "schema_version": "research.node-host-runner.v1",
        "command": command,
        "cwd": str(plugin_root),
        "exit_code": code,
        "timed_out": timed_out,
        "duration_s": duration,
        "timeout_s": timeout,
        "stdout_mode": "inherited",
        "host_workspace": environment.get("DSH_TEST_WORKSPACE"),
    }
    (output / "node-host-runner.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"NODE_HOST_RUNNER exit={code} timed_out={timed_out} duration_s={duration}", flush=True)
    if timed_out:
        return 1
    if code != 0:
        return int(code) if 0 < int(code) < 256 else 1
    print("NODE_HOST_TEST_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
