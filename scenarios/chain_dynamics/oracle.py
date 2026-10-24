#!/usr/bin/env python3
"""Independent SciPy oracle for the fixed-fixed chain study.

This module never executes MATLAB. It computes analytic (uniform chain) and
SciPy reference values from the same frozen job parameters, and writes an
expectations bundle with declared tolerances before any native run. The
comparator consumes that bundle and rejects NaN/Inf, wrong shapes and stale
hashes.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import linalg as la
from scipy.integrate import solve_ivp

ORACLE_NAME = "scipy-chain-oracle"
ORACLE_VERSION = "1.0.0"
EXPECTATION_SCHEMA = "research.chain.expectations.v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_job(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def build_system(parameters: dict):
    n = int(parameters["n"])
    mass = np.asarray(parameters["mass"]["values"] if parameters["mass"]["kind"] == "values"
                      else [parameters["mass"]["value"]] * n, dtype=float)
    stiffness = np.asarray(
        parameters["stiffness"]["values"] if parameters["stiffness"]["kind"] == "values"
        else [parameters["stiffness"]["value"]] * (n + 1), dtype=float)
    if mass.shape != (n,) or stiffness.shape != (n + 1,):
        raise ValueError("oracle received inconsistent mass/stiffness lengths")
    if not np.isfinite(mass).all() or not (mass > 0).all():
        raise ValueError("oracle requires finite positive masses")
    if not np.isfinite(stiffness).all() or not (stiffness > 0).all():
        raise ValueError("oracle requires finite positive stiffness")
    M = np.diag(mass)
    K = np.zeros((n, n))
    for i in range(n):
        K[i, i] = stiffness[i] + stiffness[i + 1]
        if i < n - 1:
            K[i, i + 1] = K[i + 1, i] = -stiffness[i + 1]
    alpha = float(parameters["damping"]["alpha"])
    beta = float(parameters["damping"]["beta"])
    C = alpha * M + beta * K
    return n, mass, stiffness, M, K, C


def cumulative_trapezoid(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    out = np.zeros_like(y)
    if len(x) > 1:
        out[1:] = np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(x))
    return out


def forcing_matrix(t: np.ndarray, parameters: dict, n: int) -> np.ndarray:
    forcing = parameters["forcing"]
    nodes = np.asarray(forcing["nodes"], dtype=int) - 1
    amps = np.asarray(forcing["amplitudes"], dtype=float)
    freqs = np.asarray(forcing["frequencies_hz"], dtype=float)
    phases = np.asarray(forcing["phases"], dtype=float)
    if not (len(nodes) == len(amps) == len(freqs) == len(phases)):
        raise ValueError("oracle received inconsistent forcing arrays")
    F = np.zeros((len(t), n))
    for node, amp, freq, phase in zip(nodes, amps, freqs, phases):
        F[:, node] += amp * np.sin(2 * np.pi * freq * t + phase)
    return F


def compute(parameters: dict) -> dict:
    n, mass, stiffness, M, K, C = build_system(parameters)
    t_end = float(parameters["t_end"])
    n_samples = int(parameters["n_samples"])
    solver = parameters.get("solver", {})
    rtol = float(solver.get("rel_tol", 1e-9))
    atol = float(solver.get("abs_tol", 1e-11))
    max_step = float(solver.get("max_step", min(0.002, t_end / 1000.0)))
    t = np.linspace(0.0, t_end, n_samples)

    omega2, V = la.eigh(K, M)
    if not np.isfinite(omega2).all() or not (omega2 > 0).all():
        raise ValueError("oracle generalized eigenvalues are not finite positive")
    omega = np.sqrt(omega2)
    mass_orth = float(np.max(np.abs(V.T @ M @ V - np.eye(n))))
    residual = K @ V - M @ V @ np.diag(omega2)
    eig_residual_rel = float(np.linalg.norm(residual, "fro") / max(np.linalg.norm(K, "fro"), np.finfo(float).tiny))

    mass_uniform = bool(np.all(np.abs(mass - mass[0]) <= 1e-12 * abs(mass[0])))
    stiff_uniform = bool(np.all(np.abs(stiffness - stiffness[0]) <= 1e-12 * abs(stiffness[0])))
    analytic_rel = None
    if mass_uniform and stiff_uniform:
        r = np.arange(1, n + 1)
        exact = 2.0 * math.sqrt(float(stiffness[0]) / float(mass[0])) * np.sin(r * math.pi / (2 * (n + 1)))
        analytic_rel = float(np.max(np.abs(omega - exact) / exact))

    MK = K / mass[:, None]
    MC = C / mass[:, None]
    state = np.block([[np.zeros((n, n)), np.eye(n)], [-MK, -MC]])
    lam = la.eigvals(state)
    order = np.lexsort((-lam.real, -lam.imag))
    lam = lam[order]
    omega_d = np.abs(lam.imag)
    zeta = -lam.real / np.maximum(np.abs(lam), np.finfo(float).tiny)

    def rhs(tt, y):
        x, v = y[:n], y[n:]
        f = forcing_matrix(np.asarray([tt]), parameters, n)[0]
        return np.concatenate([v, (f - C @ v - K @ x) / mass])

    solution = solve_ivp(rhs, (0.0, t_end), np.zeros(2 * n), method="DOP853", t_eval=t,
                         rtol=rtol, atol=atol, max_step=max_step)
    if not solution.success:
        raise RuntimeError("oracle integration failed: " + str(solution.message))
    if solution.y.shape != (2 * n, n_samples):
        raise RuntimeError(f"oracle integration returned shape {solution.y.shape}, expected {(2 * n, n_samples)}")
    x = solution.y[:n].T.copy()
    v = solution.y[n:].T.copy()
    if not np.isfinite(x).all() or not np.isfinite(v).all():
        raise RuntimeError("oracle integration produced non-finite values")

    F = forcing_matrix(t, parameters, n)
    step = np.diff(t)
    h = float(step[0])
    if not np.allclose(step, h, rtol=0.0, atol=1e-12 * max(1.0, t_end)):
        raise ValueError("oracle requires a uniform sample grid")
    acceleration = np.zeros_like(v)
    # Second-order one-sided stencils at both ends avoid a first-order endpoint
    # artefact that would otherwise dominate the residual metric.
    acceleration[0] = (-3.0 * v[0] + 4.0 * v[1] - v[2]) / (2.0 * h)
    acceleration[-1] = (3.0 * v[-1] - 4.0 * v[-2] + v[-3]) / (2.0 * h)
    acceleration[1:-1] = (v[2:] - v[:-2]) / (2.0 * h)
    dynamic = acceleration * mass[None, :] + v @ C + x @ K - F
    dynamic_norm = np.linalg.norm(dynamic, axis=1)
    denominator = np.max(np.linalg.norm(acceleration * mass[None, :], axis=1)
                         + np.linalg.norm(v @ C, axis=1)
                         + np.linalg.norm(x @ K, axis=1)
                         + np.linalg.norm(F, axis=1))
    dynamic_rel = float(dynamic_norm.max() / max(float(denominator), np.finfo(float).tiny))

    Ekin = 0.5 * np.sum(v * (v @ M.T), axis=1)
    Epot = 0.5 * np.sum(x * (x @ K.T), axis=1)
    Etot = Ekin + Epot
    power = np.sum(F * v, axis=1)
    work = cumulative_trapezoid(t, power)
    dissipation_power = np.sum(v * (v @ C.T), axis=1)
    dissipation = cumulative_trapezoid(t, dissipation_power)
    balance = Etot - Etot[0] - work + dissipation
    energy_scale = max(float(np.max(np.abs(Etot))), float(np.max(np.abs(work))),
                       float(np.max(np.abs(dissipation))), np.finfo(float).tiny)
    energy_rel = float(np.max(np.abs(balance)) / energy_scale)

    tolerances = {
        "analytic_frequency_rel": 1e-10,
        "scipy_frequency_rel": 1e-8,
        "mass_orthogonality_abs": 1e-9,
        "eigen_residual_rel": 1e-9,
        "mode_shape_abs": 1e-5,
        "damped_omega_rel": 1e-6,
        "damped_zeta_abs": 1e-7,
        "transient_displacement_rel_l2": 1e-4,
        "transient_velocity_rel_l2": 1e-4,
        "transient_energy_rel_l2": 1e-4,
        "energy_balance_rel": max(1e-3, 10.0 * energy_rel),
        "dynamic_residual_rel": max(1e-3, 10.0 * dynamic_rel),
        "internal_metric_consistency": 1e-8,
    }
    scalars = {
        "n": n,
        "n_samples": n_samples,
        "t_end": t_end,
        "mass_uniform": mass_uniform,
        "stiffness_uniform": stiff_uniform,
        "analytic_frequency_rel": analytic_rel,
        "scipy_mass_orthogonality_abs": mass_orth,
        "scipy_eigen_residual_rel": eig_residual_rel,
        "oracle_energy_balance_rel": energy_rel,
        "oracle_dynamic_residual_rel": dynamic_rel,
        "oracle_max_abs_displacement": float(np.max(np.abs(x))),
        "oracle_max_abs_velocity": float(np.max(np.abs(v))),
        "oracle_max_abs_force": float(np.max(np.abs(F))),
        "omega_min": float(omega[0]),
        "omega_max": float(omega[-1]),
        "damped_min_real": float(lam.real.max()),
    }
    arrays = {
        "t": t, "x": x, "v": v, "omega": omega, "V": V, "lam": lam,
        "Ekin": Ekin, "Epot": Epot, "Etot": Etot, "W": work, "Ddiss": dissipation, "F": F,
    }
    return {"arrays": arrays, "tolerances": tolerances, "scalars": scalars}


def freeze(job_path: Path, out_dir: Path) -> dict:
    """Compute and freeze expectations before any native execution."""
    job_path = Path(job_path).resolve()
    job = load_job(job_path)
    result = compute(job["parameters"])
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    arrays_path = out_dir / "expected_arrays.npz"
    np.savez_compressed(arrays_path, **result["arrays"])
    manifest = {
        "schema_version": EXPECTATION_SCHEMA,
        "job_id": job.get("id"),
        "job_path": str(job_path),
        "job_sha256": sha256_file(job_path),
        "parameters": job["parameters"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "oracle": {
            "name": ORACLE_NAME,
            "version": ORACLE_VERSION,
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "method": "scipy.linalg.eigh generalized eigenproblem; DOP853 transient; cumulative trapezoid energy balance; central-difference dynamic residual",
            "independent_of_target": True,
        },
        "tolerances": result["tolerances"],
        "scalars": result["scalars"],
        "arrays": {
            "file": arrays_path.name,
            "sha256": sha256_file(arrays_path),
            "shapes": {name: list(value.shape) for name, value in result["arrays"].items()},
        },
    }
    (out_dir / "expectations.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("job")
    parser.add_argument("out")
    args = parser.parse_args()
    manifest = freeze(Path(args.job), Path(args.out))
    print(json.dumps({k: manifest[k] for k in ("job_id", "created_at_utc", "scalars")}, ensure_ascii=False, indent=2))
