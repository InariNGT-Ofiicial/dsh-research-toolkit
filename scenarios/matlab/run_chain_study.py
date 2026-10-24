#!/usr/bin/env python3
"""Outer python/script job that drives the 0.3.0 chain study on the normal host.

The outer process is a Python job launched by the already installed research_run
operation; the inner 0.3.0 CLI/compiler executes MATLAB natively and keeps its
canonical result. The outer wrapper is not counted as MATLAB native evidence by
itself: MATLAB identity, MAT files, CSVs and the SciPy comparisons are inspected
separately.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

OUT = Path(os.environ.get("RB_OUTPUT_DIR", ".")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = Path(os.environ.get("RB_INPUT_DATA", ""))
if not CONFIG.is_file():
    print("RB_CHAIN_STUDY_FAILED: missing config", flush=True)
    raise SystemExit(1)
config = json.loads(CONFIG.read_text(encoding="utf-8"))
plugin_root = Path(config["plugin_root"]).resolve()
chain = plugin_root / "scenarios" / "chain_dynamics"
sys.path.insert(0, str(chain))
sys.path.insert(0, str(plugin_root))
import run_study  # noqa: E402

run_root = OUT / "study"
sys.argv = [
    "run_study.py",
    "--matlab", str(config["matlab"]),
    "--run-root", str(run_root),
    "--expectations-root", str(config["expectations_root"]),
    "--only", str(config.get("only", "")),
    "--max-timeout", str(config.get("max_timeout", 550)),
]
try:
    code = run_study.main()
except SystemExit as error:
    code = int(error.code or 0)
summary = {
    "schema_version": "research.chain.outer-study.v1",
    "only": config.get("only", ""),
    "run_root": str(run_root),
    "inner_exit_code": code,
    "study_report": str(run_root / "study-report.json"),
}
(OUT / "outer-study.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("RB_CHAIN_STUDY_OUTER " + json.dumps(summary), flush=True)
if code != 0:
    raise SystemExit(code)
print("RB_CHAIN_STUDY_COMPLETE", flush=True)
raise SystemExit(0)
