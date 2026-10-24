#!/usr/bin/env python3
"""Independent acceptance comparator for MATLAB chain_dynamics runs.

Rejects non-finite numbers, truncated/wrongly shaped files, stale expectation
hashes and any metric outside the tolerances frozen by the SciPy oracle before
the native run. It never derives expectations from MATLAB output.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat

MODAL_COLUMNS = ["mode", "omega_rad_s", "frequency_hz", "mass_norm_error", "mode_residual_rel"]
DAMPED_COLUMNS = ["mode", "eigenvalue_real", "eigenvalue_imag", "omega_d_rad_s", "zeta"]
ENERGY_COLUMNS = ["t", "kinetic", "potential", "total", "work", "dissipation", "balance_residual"]


class CheckFailure(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _reject_constant(token):
    raise CheckFailure(f"non-finite JSON constant rejected: {token}")


def load_json_strict(path: Path) -> dict:
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=_reject_constant)
    except json.JSONDecodeError as error:
        raise CheckFailure(f"{path.name}: invalid JSON: {error}") from error
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise CheckFailure(f"{path.name}: non-finite number rejected")
    return value


def read_csv(path: Path, expected_header: list[str]) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise CheckFailure(f"missing artifact: {path.name}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise CheckFailure(f"{path.name}: empty CSV")
    header = rows[0]
    if header != expected_header:
        raise CheckFailure(f"{path.name}: header mismatch: {header!r} != {expected_header!r}")
    if len(rows) - 1 < 1:
        raise CheckFailure(f"{path.name}: no data rows")
    try:
        data = np.asarray(rows[1:], dtype=float)
    except ValueError as error:
        raise CheckFailure(f"{path.name}: non-numeric or ragged row: {error}") from error
    if data.ndim != 2 or data.shape[1] != len(header):
        raise CheckFailure(f"{path.name}: shape {data.shape} does not match {len(header)} columns")
    if not np.isfinite(data).all():
        raise CheckFailure(f"{path.name}: NaN or Inf present")
    return data


def relative_l2(observed: np.ndarray, expected: np.ndarray) -> float:
    if observed.shape != expected.shape:
        raise CheckFailure(f"shape mismatch: observed {observed.shape} expected {expected.shape}")
    if not np.isfinite(observed).all() or not np.isfinite(expected).all():
        raise CheckFailure("non-finite values in comparison")
    denominator = np.linalg.norm(expected)
    return float(np.linalg.norm(observed - expected) / max(denominator, np.finfo(float).tiny))


def compare(run_dir: Path, expectations_dir: Path, job_path: Path | None = None) -> dict:
    run_dir = Path(run_dir).resolve()
    expectations_dir = Path(expectations_dir).resolve()
    checks: list[dict] = []

    def record(name: str, passed: bool, observed, expected, tolerance, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "observed": observed,
                       "expected": expected, "tolerance": tolerance, "detail": detail})

    manifest_path = expectations_dir / "expectations.json"
    if not manifest_path.is_file():
        raise CheckFailure(f"missing expectations manifest: {manifest_path}")
    manifest = load_json_strict(manifest_path)
    if manifest.get("schema_version") != "research.chain.expectations.v1":
        raise CheckFailure("unexpected expectations schema")
    arrays_path = expectations_dir / manifest["arrays"]["file"]
    if sha256_file(arrays_path) != manifest["arrays"]["sha256"]:
        raise CheckFailure("expected arrays hash mismatch; expectations were modified")
    with np.load(arrays_path, allow_pickle=False) as archive:
        expected = {name: archive[name] for name in archive.files}
    for name, shape in manifest["arrays"]["shapes"].items():
        if list(expected[name].shape) != shape:
            raise CheckFailure(f"expected array {name} shape changed")
        if not np.isfinite(expected[name]).all():
            raise CheckFailure(f"expected array {name} is non-finite")
    tolerance = manifest["tolerances"]
    parameters = manifest["parameters"]
    n = int(parameters["n"])
    n_samples = int(parameters["n_samples"])

    if job_path is not None:
        digest = sha256_file(Path(job_path))
        record("job_input_hash", digest == manifest["job_sha256"], digest, manifest["job_sha256"], "exact",
               "original job JSON must be unchanged since expectations were frozen")

    identity_path = run_dir / "identity.json"
    if not identity_path.is_file():
        raise CheckFailure("missing identity.json")
    identity = load_json_strict(identity_path)
    record("identity_release", identity.get("release") == "2026a", identity.get("release"), "2026a", "exact",
           "version('-release') returns the release without the R prefix")
    record("identity_version_label", "(R2026a)" in str(identity.get("version", "")),
           str(identity.get("version", ""))[:60], "contains (R2026a)", "substring")
    record("identity_version", bool(re.match(r"^26\.1\.\d+", str(identity.get("version", "")))),
           str(identity.get("version", ""))[:60], "26.1.*", "regex")
    record("identity_matlabroot", bool(str(identity.get("matlabroot", "")).strip()),
           identity.get("matlabroot"), "non-empty", "non-empty")
    record("identity_batch_startup", identity.get("batch_startup") is True, identity.get("batch_startup"), True, "exact")
    record("identity_engine_operation",
           identity.get("engine") == "matlab" and identity.get("operation") == "chain_dynamics",
           f"{identity.get('engine')}/{identity.get('operation')}", "matlab/chain_dynamics", "exact")

    results_path = run_dir / "results.json"
    if not results_path.is_file():
        raise CheckFailure("missing results.json")
    results = load_json_strict(results_path)
    record("results_status", results.get("status") == "passed", results.get("status"), "passed", "exact")
    record("results_dimensions", results.get("n") == n and results.get("n_samples") == n_samples,
           f"{results.get('n')}/{results.get('n_samples')}", f"{n}/{n_samples}", "exact")
    record("results_matlab_release", results.get("matlab_release") == "2026a",
           results.get("matlab_release"), "2026a", "exact",
           "MATLAB writes the release without the R prefix")
    internal = results.get("checks") or {}
    record("results_internal_checks", bool(internal) and all(value is True for value in internal.values()),
           internal, {key: True for key in internal}, "all true")

    modal = read_csv(run_dir / "modal.csv", MODAL_COLUMNS)
    if modal.shape != (n, len(MODAL_COLUMNS)):
        raise CheckFailure(f"modal.csv shape {modal.shape}, expected {(n, len(MODAL_COLUMNS))}")
    omega = modal[:, 1]
    if not np.all(np.diff(omega) > 0):
        raise CheckFailure("modal frequencies are not strictly ascending")
    omega_rel = float(np.max(np.abs(omega - expected["omega"]) / expected["omega"]))
    record("modal_frequency_vs_scipy", omega_rel <= tolerance["scipy_frequency_rel"], omega_rel,
           tolerance["scipy_frequency_rel"], tolerance["scipy_frequency_rel"], "max relative error")
    mass_uniform = bool(results.get("mass_uniform"))
    stiffness_uniform = bool(results.get("stiffness_uniform"))
    if mass_uniform and stiffness_uniform:
        mass = np.asarray(parameters["mass"]["values"] if parameters["mass"]["kind"] == "values"
                          else [parameters["mass"]["value"]] * n)
        stiffness = np.asarray(parameters["stiffness"]["values"] if parameters["stiffness"]["kind"] == "values"
                               else [parameters["stiffness"]["value"]] * (n + 1))
        r = np.arange(1, n + 1)
        exact = 2.0 * math.sqrt(float(stiffness[0]) / float(mass[0])) * np.sin(r * math.pi / (2 * (n + 1)))
        analytic_rel = float(np.max(np.abs(omega - exact) / exact))
        record("modal_frequency_vs_analytic", analytic_rel <= tolerance["analytic_frequency_rel"], analytic_rel,
               tolerance["analytic_frequency_rel"], tolerance["analytic_frequency_rel"],
               "uniform closed-form omega_r = 2 sqrt(k/m) sin(r pi/(2(N+1)))")
    record("modal_mass_orthogonality", float(modal[:, 3].max()) <= tolerance["mass_orthogonality_abs"],
           float(modal[:, 3].max()), tolerance["mass_orthogonality_abs"], tolerance["mass_orthogonality_abs"],
           "max |V'MV - I|")
    record("modal_eigen_residual", float(modal[:, 4].max()) <= tolerance["eigen_residual_rel"],
           float(modal[:, 4].max()), tolerance["eigen_residual_rel"], tolerance["eigen_residual_rel"],
           "max column relative residual of K V - M V Lambda")

    damped = read_csv(run_dir / "damped_modes.csv", DAMPED_COLUMNS)
    if damped.shape != (2 * n, len(DAMPED_COLUMNS)):
        raise CheckFailure(f"damped_modes.csv shape {damped.shape}, expected {(2 * n, len(DAMPED_COLUMNS))}")
    lam_expected = expected["lam"]
    order_m = np.lexsort((damped[:, 1], damped[:, 3]))
    order_e = np.lexsort((lam_expected.real, np.abs(lam_expected.imag)))
    omega_d_m, omega_d_e = damped[order_m, 3], np.abs(lam_expected[order_e].imag)
    zeta_m = damped[order_m, 4]
    zeta_e = -lam_expected[order_e].real / np.maximum(np.abs(lam_expected[order_e]), np.finfo(float).tiny)
    denom = np.maximum(omega_d_e, np.finfo(float).tiny)
    damped_rel = float(np.max(np.abs(omega_d_m - omega_d_e) / denom))
    zeta_abs = float(np.max(np.abs(zeta_m - zeta_e)))
    record("damped_omega_vs_scipy", damped_rel <= tolerance["damped_omega_rel"], damped_rel,
           tolerance["damped_omega_rel"], tolerance["damped_omega_rel"], "sorted damped natural frequencies")
    record("damped_zeta_vs_scipy", zeta_abs <= tolerance["damped_zeta_abs"], zeta_abs,
           tolerance["damped_zeta_abs"], tolerance["damped_zeta_abs"], "sorted damping ratios")

    history_header = ["t"] + [f"x_{i}" for i in range(1, n + 1)] + [f"v_{i}" for i in range(1, n + 1)]
    history = read_csv(run_dir / "time_history.csv", history_header)
    if history.shape != (n_samples, 2 * n + 1):
        raise CheckFailure(f"time_history.csv shape {history.shape}, expected {(n_samples, 2 * n + 1)}")
    time_error = float(np.max(np.abs(history[:, 0] - expected["t"])))
    record("time_grid", time_error <= 1e-12 * max(1.0, float(parameters["t_end"])), time_error, 0.0,
           1e-12 * max(1.0, float(parameters["t_end"])), "sample times")
    x_obs, v_obs = history[:, 1:n + 1], history[:, n + 1:]
    x_rel = relative_l2(x_obs, expected["x"])
    v_rel = relative_l2(v_obs, expected["v"])
    record("transient_displacement_vs_scipy", x_rel <= tolerance["transient_displacement_rel_l2"], x_rel,
           tolerance["transient_displacement_rel_l2"], tolerance["transient_displacement_rel_l2"],
           "relative Frobenius error over all DOF and samples")
    record("transient_velocity_vs_scipy", v_rel <= tolerance["transient_velocity_rel_l2"], v_rel,
           tolerance["transient_velocity_rel_l2"], tolerance["transient_velocity_rel_l2"],
           "relative Frobenius error over all DOF and samples")

    energy = read_csv(run_dir / "energy.csv", ENERGY_COLUMNS)
    if energy.shape != (n_samples, len(ENERGY_COLUMNS)):
        raise CheckFailure(f"energy.csv shape {energy.shape}, expected {(n_samples, len(ENERGY_COLUMNS))}")
    energy_rel_l2 = relative_l2(energy[:, 3], expected["Etot"])
    record("energy_total_vs_scipy", energy_rel_l2 <= tolerance["transient_energy_rel_l2"], energy_rel_l2,
           tolerance["transient_energy_rel_l2"], tolerance["transient_energy_rel_l2"],
           "total mechanical energy trajectory")
    balance_scale = max(float(np.max(np.abs(energy[:, 3]))), float(np.max(np.abs(energy[:, 4]))),
                        float(np.max(np.abs(energy[:, 5]))), np.finfo(float).tiny)
    balance_rel = float(np.max(np.abs(energy[:, 6])) / balance_scale)
    record("energy_balance", balance_rel <= tolerance["energy_balance_rel"], balance_rel,
           tolerance["energy_balance_rel"], tolerance["energy_balance_rel"],
           "max |E(t)-E(0)-W+D| / max|E|")
    dyn_from_results = float(results.get("max_dynamic_residual_relative", float("nan")))
    record("dynamic_residual", math.isfinite(dyn_from_results) and dyn_from_results <= tolerance["dynamic_residual_rel"],
           dyn_from_results, tolerance["dynamic_residual_rel"], tolerance["dynamic_residual_rel"],
           "max ||M a + C v + K x - f|| / scale")

    metric_consistency = max(
        abs(float(results.get("max_mass_orthogonality_error", 0.0)) - float(modal[:, 3].max())),
        abs(float(results.get("max_eigen_residual_relative", 0.0)) - float(modal[:, 4].max())),
        abs(float(results.get("energy_balance_relative", 0.0)) - balance_rel),
    )
    record("internal_metric_consistency", metric_consistency <= tolerance["internal_metric_consistency"],
           metric_consistency, tolerance["internal_metric_consistency"], tolerance["internal_metric_consistency"],
           "results.json metrics must match CSV-derived metrics")

    mat_path = run_dir / "chain_results.mat"
    if not mat_path.is_file():
        raise CheckFailure("missing chain_results.mat")
    header = mat_path.read_bytes()[:116]
    record("mat_native_signature", header.startswith(b"MATLAB 5.0 MAT-file"), header[:48].decode("latin-1", "replace"),
           "MATLAB 5.0 MAT-file", "signature",
           "MAT v7 files retain the 5.0 header; scipy.io.loadmat below verifies the structure")
    mat = loadmat(mat_path)
    required = {"M", "K", "C", "omega", "V", "lam", "t", "x", "v", "Ekin", "Epot", "Etot", "W", "Ddiss", "cfg"}
    missing = sorted(required - set(mat))
    if missing:
        raise CheckFailure(f"chain_results.mat missing variables: {missing}")
    record("mat_shapes", mat["M"].shape == (n, n) and mat["K"].shape == (n, n) and mat["C"].shape == (n, n)
           and mat["omega"].shape == (n, 1) and mat["t"].shape == (n_samples, 1)
           and mat["x"].shape == (n_samples, n) and mat["v"].shape == (n_samples, n),
           {key: list(mat[key].shape) for key in ("M", "K", "C", "omega", "t", "x", "v")},
           f"n={n}, samples={n_samples}", "exact")
    mat_finite = all(np.isfinite(mat[key]).all() for key in ("M", "K", "C", "omega", "V", "lam", "t", "x", "v"))
    record("mat_finite", mat_finite, mat_finite, True, "exact")
    omega_mat_rel = float(np.max(np.abs(mat["omega"].ravel() - omega) / omega))
    record("mat_omega_matches_csv", omega_mat_rel <= 1e-12, omega_mat_rel, 1e-12, 1e-12, "native MAT vs modal.csv")
    x_mat = float(np.max(np.abs(mat["x"] - x_obs)))
    record("mat_history_matches_csv", x_mat <= 1e-12, x_mat, 1e-12, 1e-12, "native MAT vs time_history.csv")
    v_abs_diff = float(np.max(np.abs(np.abs(mat["V"]) - np.abs(expected["V"]))))
    record("mat_mode_shapes_vs_scipy", v_abs_diff <= tolerance["mode_shape_abs"], v_abs_diff,
           tolerance["mode_shape_abs"], tolerance["mode_shape_abs"], "absolute shapes; eigenvector signs are arbitrary")

    mass = np.asarray(parameters["mass"]["values"] if parameters["mass"]["kind"] == "values"
                      else [parameters["mass"]["value"]] * n)
    stiffness = np.asarray(parameters["stiffness"]["values"] if parameters["stiffness"]["kind"] == "values"
                           else [parameters["stiffness"]["value"]] * (n + 1))
    K_reference = np.zeros((n, n))
    for i in range(n):
        K_reference[i, i] = stiffness[i] + stiffness[i + 1]
        if i < n - 1:
            K_reference[i, i + 1] = K_reference[i + 1, i] = -stiffness[i + 1]
    C_reference = float(parameters["damping"]["alpha"]) * np.diag(mass) + float(parameters["damping"]["beta"]) * K_reference
    matrix_error = max(float(np.max(np.abs(mat["M"] - np.diag(mass)))),
                       float(np.max(np.abs(mat["K"] - K_reference))),
                       float(np.max(np.abs(mat["C"] - C_reference))))
    record("mat_system_matrices", matrix_error <= 1e-12 * max(1.0, float(np.max(K_reference))), matrix_error,
           1e-12 * max(1.0, float(np.max(K_reference))), "1e-12 * max|K|", "MAT matrices vs job parameters")

    png = run_dir / "chain_summary.png"
    make_plot = bool(parameters.get("plot", True))
    if make_plot:
        if not png.is_file():
            raise CheckFailure("missing chain_summary.png")
        png_bytes = png.read_bytes()
        record("png_signature", png_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(png_bytes) > 5000,
               len(png_bytes), ">5000 bytes", "signature+size")
    else:
        record("png_absent_when_plot_disabled", not png.exists(), png.exists(), False, "exact",
               "plot:false must not declare or create the optional figure")

    passed = all(item["passed"] for item in checks)
    report = {
        "schema_version": "research.chain.comparison.v1",
        "status": "passed" if passed else "failed",
        "job_id": manifest.get("job_id"),
        "run_dir": str(run_dir),
        "expectations_dir": str(expectations_dir),
        "expectations_sha256": sha256_file(manifest_path),
        "tolerances": tolerance,
        "checks": checks,
    }
    return report


def compare_runs(run_a: Path, run_b: Path, expectations_dir: Path) -> dict:
    manifest = json.loads((Path(expectations_dir) / "expectations.json").read_text(encoding="utf-8-sig"))
    n = int(manifest["parameters"]["n"])
    header = ["t"] + [f"x_{i}" for i in range(1, n + 1)] + [f"v_{i}" for i in range(1, n + 1)]
    a = read_csv(Path(run_a) / "time_history.csv", header)
    b = read_csv(Path(run_b) / "time_history.csv", header)
    if a.shape != b.shape:
        raise CheckFailure("repeated runs returned different shapes")
    max_diff = float(np.max(np.abs(a - b)))
    modal_a = read_csv(Path(run_a) / "modal.csv", MODAL_COLUMNS)
    modal_b = read_csv(Path(run_b) / "modal.csv", MODAL_COLUMNS)
    modal_diff = float(np.max(np.abs(modal_a - modal_b)))
    return {
        "status": "passed" if max_diff <= 1e-10 and modal_diff <= 1e-10 else "failed",
        "fresh_directories": str(Path(run_a).resolve()) != str(Path(run_b).resolve()),
        "run_a": str(Path(run_a).resolve()),
        "run_b": str(Path(run_b).resolve()),
        "time_history_max_abs_diff": max_diff,
        "modal_max_abs_diff": modal_diff,
        "sha256_run_a": sha256_file(Path(run_a) / "time_history.csv"),
        "sha256_run_b": sha256_file(Path(run_b) / "time_history.csv"),
        "tolerance": 1e-10,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--run-b")
    parser.add_argument("--expectations", required=True)
    parser.add_argument("--job")
    parser.add_argument("--out")
    args = parser.parse_args()
    try:
        report = compare(Path(args.run), Path(args.expectations), Path(args.job) if args.job else None)
        if args.run_b:
            report["repetition"] = compare_runs(Path(args.run), Path(args.run_b), Path(args.expectations))
            if report["repetition"]["status"] != "passed":
                report["status"] = "failed"
        text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        print(text)
        return 0 if report["status"] == "passed" else 1
    except CheckFailure as error:
        report = {"schema_version": "research.chain.comparison.v1", "status": "failed", "reason": str(error)}
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        print(text)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
