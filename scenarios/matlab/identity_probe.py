#!/usr/bin/env python3
"""Bounded MATLAB identity probe.

Runs only release/version/matlabroot/batchStartupOptionUsed, plus the executable
hash and the installation VersionInfo.xml. It never reads a license file,
account, entitlement or credential. Intended to be launched by the already
installed research_run python/script operation from the normal DSH host user.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

STATEMENT = ("fprintf('RB_IDENTITY release=%s version=%s matlabroot=%s batch=%d\\n', "
             "version('-release'), version, matlabroot, batchStartupOptionUsed);")


def main() -> int:
    output = Path(os.environ.get("RB_OUTPUT_DIR", ".")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config_path = os.environ.get("RB_INPUT_DATA", "")
    if not config_path or not Path(config_path).is_file():
        print("RB_IDENTITY_FAILED: missing runner config", flush=True)
        return 1
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    executable = Path(config["matlab"]).resolve()
    cwd = Path(config["cwd"]).resolve()
    cwd.mkdir(parents=True, exist_ok=True)
    timeout = float(config.get("timeout_s", 300))
    if not executable.is_file():
        print(f"RB_IDENTITY_FAILED: executable missing: {executable}", flush=True)
        return 1
    version_info = executable.parent.parent / "VersionInfo.xml"
    report = {
        "schema_version": "research.matlab.identity.v1",
        "executable": str(executable),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "executable_bytes": executable.stat().st_size,
        "version_info_path": str(version_info),
        "version_info_sha256": hashlib.sha256(version_info.read_bytes()).hexdigest() if version_info.is_file() else None,
        "version_info": version_info.read_text(encoding="utf-8-sig") if version_info.is_file() else None,
        "command": [str(executable), "-batch", STATEMENT],
        "timeout_s": timeout,
    }
    started = time.monotonic()
    try:
        completed = subprocess.run([str(executable), "-batch", STATEMENT], cwd=str(cwd),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=timeout, shell=False)
        report["exit_code"] = completed.returncode
        report["timed_out"] = False
        stdout = completed.stdout.decode("utf-8", "replace")
        stderr = completed.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as error:
        report["exit_code"] = None
        report["timed_out"] = True
        stdout = (error.stdout or b"").decode("utf-8", "replace")
        stderr = (error.stderr or b"").decode("utf-8", "replace")
    report["duration_s"] = round(time.monotonic() - started, 3)
    report["stdout"] = stdout
    report["stderr"] = stderr
    match = re.search(r"RB_IDENTITY release=(\S+) version=(.*?) matlabroot=(.*?) batch=(\d+)", stdout)
    if match:
        report["identity"] = {
            "release": match.group(1),
            "version": match.group(2).strip(),
            "matlabroot": match.group(3).strip(),
            "batch_startup": match.group(4) == "1",
        }
    else:
        report["identity"] = None
    report["status"] = "passed" if report["identity"] and report["exit_code"] == 0 else "failed"
    (output / "identity-probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
                                                encoding="utf-8")
    print("RB_MATLAB_IDENTITY_PROBE " + json.dumps(report["identity"], ensure_ascii=False), flush=True)
    if report["status"] != "passed":
        print("RB_IDENTITY_FAILED", flush=True)
        return 1
    print("RB_IDENTITY_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
