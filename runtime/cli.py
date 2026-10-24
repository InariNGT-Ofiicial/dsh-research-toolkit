#!/usr/bin/env python3
"""JSON-only public interface used by the DSH plugin and other agents."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_bridge import __version__
from research_bridge.catalog import CATALOG, discover, load_config
from research_bridge.core import compile_job, execute_job, read_job

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["catalog", "discover", "compile", "run", "verify"])
    p.add_argument("path", nargs="?")
    p.add_argument("--workspace", default="research-workspace")
    p.add_argument("--config")
    p.add_argument("--max-timeout", type=float, default=300)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        cfg = load_config(a.config)
        if a.command == "catalog":
            root = Path(__file__).resolve().parents[1]
            out = dict(status="passed", version=__version__, engines=CATALOG,
                       extension_guidance=dict(skill="research-bridge-lab",
                           guide=str(root / "docs/bridge-research-guide.md"),
                           templates=str(root / "docs/extensions"),
                           scope="Candidate research is separate from supported native adapters; a generated wrapper is not target-application verification."))
        elif a.command == "discover":
            out = dict(status="passed", engines=discover(cfg), note="Discovery is not an acceptance test.")
        elif a.command == "compile":
            if not a.path:
                p.error("compile requires a job JSON file")
            out = compile_job(read_job(a.path), Path(a.workspace), cfg)
        elif a.command == "run":
            if not a.path:
                p.error("run requires a job JSON file")
            out = execute_job(a.path, a.workspace, cfg, a.max_timeout)
        else:
            from research_bridge.verify import verify_directory
            out = verify_directory(a.path or a.workspace)
        print(json.dumps(out, ensure_ascii=False, allow_nan=False))
        return 2 if out["status"] == "blocked" else (0 if out["status"] in ("passed", "compiled") else 1)
    except Exception as e:
        print(json.dumps(dict(status="failed", error=type(e).__name__, reason=str(e)), ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
