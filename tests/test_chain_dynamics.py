#!/usr/bin/env python3
"""Adapter-level tests for the new matlab/chain_dynamics operation.

These tests compile native source and exercise validation. They do not claim a
native run: real MATLAB execution is covered by the scenario runner on an
installed engine.
"""
from __future__ import annotations

import contextlib
import copy
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_bridge.adapters import chain_dynamics  # noqa: E402
from research_bridge.catalog import CATALOG  # noqa: E402
from research_bridge.core import JobError, compile_job, validate_job  # noqa: E402

TMP_ROOT = ROOT / "tests" / "_tmp"


@contextlib.contextmanager
def workspace_temp():
    # tempfile.mkdtemp applies a restrictive mode that the DSH sandbox turns into
    # an unreadable DACL here; a plainly created task-local directory is used.
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"chain-{uuid.uuid4().hex[:10]}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def base_job() -> dict:
    return json.loads((ROOT / "scenarios/chain_dynamics/jobs/chain-uniform-n12.json").read_text(encoding="utf-8"))


class ChainDynamicsCompileTests(unittest.TestCase):
    def test_catalog_operation_and_engine_count(self):
        self.assertIn("chain_dynamics", CATALOG["matlab"]["operations"])
        self.assertEqual(len(CATALOG), 29)
        self.assertEqual(CATALOG["matlab"]["mode"], "native")

    def test_compile_without_runtime_is_blocked_but_source_exists(self):
        job = base_job()
        with workspace_temp() as tmp:
            missing = tmp / "missing-matlab.exe"
            compiled = compile_job(job, tmp / "run", config={"executables": {"matlab": str(missing)}, "strict_executables": True})
            self.assertFalse(compiled["ready"])
            self.assertEqual(compiled["command"], [])
            self.assertIn("missing", compiled["reason"].lower())
            source = Path(compiled["source_path"])
            self.assertTrue(source.is_file())
            text = source.read_text(encoding="utf-8")
            self.assertIn("cfg = struct(", text)
            self.assertIn("eig(K, M)", text)
            self.assertIn("ode45(", text)
            self.assertIn("save(fullfile(out, 'chain_results.mat')", text)
            self.assertIn("jsonencode", text)
            self.assertNotIn("eval(", text)
            self.assertNotIn("system(", text)
            self.assertEqual(len(compiled["expected_artifacts"]), 8)
            self.assertEqual(compiled["required_markers"], ["RB_MATLAB_IDENTITY", "RB_CHAIN_DYNAMICS_COMPLETE"])
            self.assertTrue((tmp / "run" / "job.json").is_file())
            self.assertTrue((tmp / "run" / "compiled.json").is_file())

    def test_compile_with_fake_runtime_emits_explicit_batch_command(self):
        job = base_job()
        with workspace_temp() as tmp:
            fake = tmp / "matlab.exe"
            fake.write_bytes(b"MZ")
            compiled = compile_job(job, tmp / "run", config={"executables": {"matlab": str(fake)}, "strict_executables": True})
            self.assertTrue(compiled["ready"])
            self.assertEqual(compiled["command"][0], str(fake.resolve()))
            self.assertEqual(compiled["command"][1], "-sd")
            self.assertEqual(compiled["command"][3:], ["-batch", "rb_chain_dynamics"])
            self.assertEqual(compiled["mode"], "native")
            self.assertEqual(compiled["scope"], "native")

    def test_plot_false_drops_optional_png_artifact(self):
        job = base_job()
        job["parameters"]["plot"] = False
        with workspace_temp() as tmp:
            missing = tmp / "missing-matlab.exe"
            compiled = compile_job(job, tmp / "run", config={"executables": {"matlab": str(missing)}, "strict_executables": True})
            artifacts = [Path(item).name for item in compiled["expected_artifacts"]]
            self.assertEqual(len(artifacts), 7)
            self.assertNotIn("chain_summary.png", artifacts)
            self.assertIn("chain_results.mat", artifacts)
            text = Path(compiled["source_path"]).read_text(encoding="utf-8")
            self.assertIn("'make_plot', false", text)

    def test_uniform_analytic_formula_is_not_injected_code(self):
        job = base_job()
        with workspace_temp() as tmp:
            compiled = chain_dynamics.compile_job(job, tmp, {})
            text = Path(compiled["source_path"]).read_text(encoding="utf-8")
            self.assertIn("omega_exact = 2 * sqrt(k(1) / m(1)) * sin(r * pi / (2 * (n + 1)))", text)
            self.assertIn("mass_norm_error = max(abs(G - eye(n)), [], 'all')", text)


class ChainDynamicsValidationTests(unittest.TestCase):
    def _reject(self, mutate, needle: str):
        job = copy.deepcopy(base_job())
        mutate(job["parameters"])
        with workspace_temp() as tmp:
            with self.assertRaises(ValueError) as caught:
                chain_dynamics.compile_job(job, tmp, {})
        self.assertIn(needle, str(caught.exception))

    def test_zero_mass_rejected(self):
        self._reject(lambda p: p.update(mass={"kind": "values", "values": [1.0] * 11 + [0.0]}), "greater than 0")

    def test_negative_stiffness_rejected(self):
        self._reject(lambda p: p.update(stiffness={"kind": "values", "values": [100.0] * 12 + [-1.0]}), "greater than 0")

    def test_dimension_mismatch_rejected(self):
        self._reject(lambda p: p.update(mass={"kind": "values", "values": [1.0] * 11}), "exactly 12 numbers")

    def test_non_finite_rejected(self):
        self._reject(lambda p: p.update(mass={"kind": "values", "values": [float("inf")] + [1.0] * 11}), "finite")

    def test_zero_damping_rejected(self):
        self._reject(lambda p: p["damping"].update(alpha=0.0, beta=0.0), "alpha + beta > 0")

    def test_unknown_parameter_rejected(self):
        self._reject(lambda p: p.update(script="disp('x')"), "unsupported chain_dynamics parameters")

    def test_short_sample_grid_rejected(self):
        self._reject(lambda p: p.update(n_samples=1000), "between 1001 and 20001")

    def test_forcing_length_mismatch_rejected(self):
        self._reject(lambda p: p["forcing"].update(phases=[0.0]), "equal length")

    def test_invalid_engine_operation_rejected(self):
        job = base_job()
        job["operation"] = "analysis"
        with workspace_temp() as tmp:
            with self.assertRaises(ValueError):
                chain_dynamics.compile_job(job, tmp, {})

    def test_core_validate_job_accepts_chain_dynamics(self):
        validate_job(base_job())

    def test_core_rejects_chain_dynamics_for_octave(self):
        job = base_job()
        job["engine"] = "octave"
        with self.assertRaises(JobError):
            validate_job(job)


if __name__ == "__main__":
    unittest.main()
