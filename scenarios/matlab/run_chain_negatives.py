#!/usr/bin/env python3
"""Outer python/script job for the native negative-control suite.

The inner negative_controls module performs real MATLAB launches and writes its
own report. The outer wrapper only supplies paths and a completion marker; it is
not itself native MATLAB evidence.
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
    print("RB_CHAIN_NEGATIVES_FAILED: missing config", flush=True)
    raise SystemExit(1)
config = json.loads(CONFIG.read_text(encoding="utf-8"))
plugin = Path(config["plugin_root"]).resolve()
sys.path.insert(0, str(plugin / "scenarios" / "chain_dynamics"))
sys.path.insert(0, str(plugin))
import negative_controls  # noqa: E402

root = OUT / "negatives"
sys.argv = [
    "negative_controls.py",
    "--root", str(root),
    "--expectations-root", str(config["expectations_root"]),
    "--matlab", str(config["matlab"]),
]
try:
    code = negative_controls.main()
except SystemExit as error:
    code = int(error.code or 0)
summary = {
    "schema_version": "research.chain.outer-negatives.v1",
    "root": str(root),
    "inner_exit_code": code,
    "negative_report": str(root / "negative-report.json"),
}
(OUT / "outer-negatives.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("RB_CHAIN_NEGATIVES_OUTER " + json.dumps(summary), flush=True)
if code != 0:
    raise SystemExit(code)
print("RB_CHAIN_NEGATIVES_COMPLETE", flush=True)
raise SystemExit(0)
