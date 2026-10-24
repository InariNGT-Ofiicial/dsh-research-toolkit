#!/usr/bin/env python3
"""Create the frozen chain_dynamics job fixtures.

The arrays are deterministic formulas so the jobs can be regenerated and
hash-checked. They cover the three requested cases at N=12, 48 and 96.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "jobs"


def mass_graded(n: int, low: float, high: float) -> list[float]:
    return [low + (high - low) * i / (n - 1) for i in range(n)]


def stiffness_graded(n: int, low: float, high: float, alternating: float = 1.0) -> list[float]:
    values = []
    for j in range(n + 1):
        base = low + (high - low) * j / n
        values.append(base * (alternating if j % 2 else 1.0))
    return values


def stiffness_high(n: int, low: float, high: float) -> list[float]:
    return [low + (high - low) * j / n for j in range(n + 1)]


def job(job_id: str, case: str, n: int, mass: dict, stiffness: dict, damping: dict,
        forcing: dict, t_end: float, n_samples: int, solver: dict) -> dict:
    return {
        "schema_version": "research.job.v1",
        "id": job_id,
        "engine": "matlab",
        "operation": "chain_dynamics",
        "inputs": {},
        "parameters": {
            "case": case,
            "n": n,
            "mass": mass,
            "stiffness": stiffness,
            "damping": damping,
            "forcing": forcing,
            "t_end": t_end,
            "n_samples": n_samples,
            "solver": solver,
            "plot": True,
        },
        "timeout_s": 600,
    }


def main() -> int:
    JOBS.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "chain-uniform-n12.json": job(
            "chain-uniform-n12", "uniform", 12,
            {"kind": "uniform", "value": 1.0},
            {"kind": "uniform", "value": 100.0},
            {"alpha": 0.02, "beta": 0.0005},
            {"nodes": [3, 7], "amplitudes": [0.6, 0.4],
             "frequencies_hz": [0.8, 2.1], "phases": [0.0, 0.7]},
            2.0, 2001, {"rel_tol": 1e-9, "abs_tol": 1e-11, "max_step": 0.002},
        ),
        "chain-graded-n48.json": job(
            "chain-graded-n48", "graded", 48,
            {"kind": "values", "values": mass_graded(48, 0.7, 1.4)},
            {"kind": "values", "values": stiffness_graded(48, 80.0, 140.0, alternating=1.25)},
            {"alpha": 0.03, "beta": 0.0008},
            {"nodes": [5, 24, 40], "amplitudes": [0.5, 0.35, 0.25],
             "frequencies_hz": [0.6, 1.7, 3.2], "phases": [0.0, 0.5, 1.1]},
            1.5, 1501, {"rel_tol": 1e-9, "abs_tol": 1e-11, "max_step": 0.0015},
        ),
        "chain-highstiff-n96.json": job(
            "chain-highstiff-n96", "high_stiffness", 96,
            {"kind": "values", "values": mass_graded(96, 0.9, 1.1)},
            {"kind": "values", "values": stiffness_high(96, 2000.0, 8000.0)},
            {"alpha": 0.01, "beta": 2e-5},
            {"nodes": [10, 80], "amplitudes": [0.4, 0.3],
             "frequencies_hz": [0.9, 4.0], "phases": [0.0, 0.25]},
            1.0, 2001, {"rel_tol": 1e-9, "abs_tol": 1e-12, "max_step": 0.001},
        ),
    }
    for name, value in fixtures.items():
        path = JOBS / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
