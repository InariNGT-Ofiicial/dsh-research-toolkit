#!/usr/bin/env python3
"""Regression for negative-control classification.

An expected-blocked control that ran and matched its expectation is a success;
only required native controls that were never executed make the suite blocked.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scenarios" / "chain_dynamics"))

import negative_controls  # noqa: E402


def control(name, status, passed, executed=True, expected="failed"):
    return {"name": name, "status": status, "passed": passed, "executed": executed,
            "expected_outcome": expected}


def report(controls, compile_ok=True, recovery_ok=True):
    return {
        "compile_rejections": [{"name": "x", "passed": compile_ok}],
        "runtime_controls": controls,
        "recovery": {"status": "passed" if recovery_ok else "failed", "passed": recovery_ok},
    }


class NegativeSummaryTests(unittest.TestCase):
    def test_expected_blocked_that_ran_does_not_block_suite(self):
        controls = [
            control("missing-runtime", "blocked", True, expected="blocked"),
            control("native-script-failure", "failed", True),
            control("missing-artifact", "failed", True),
            control("timeout", "failed", True),
        ]
        verdict = negative_controls.summarize(report(controls))
        self.assertEqual(verdict["status"], "passed", verdict)

    def test_unexecuted_native_controls_make_suite_blocked(self):
        controls = [
            control("missing-runtime", "blocked", True, expected="blocked"),
            control("native-script-failure", "not_run", False, executed=False),
            control("missing-artifact", "not_run", False, executed=False),
            control("timeout", "not_run", False, executed=False),
        ]
        verdict = negative_controls.summarize(report(controls))
        self.assertEqual(verdict["status"], "blocked", verdict)
        self.assertIn("not executed", verdict["reason"])

    def test_failed_native_control_fails_suite(self):
        controls = [
            control("missing-runtime", "blocked", True, expected="blocked"),
            control("native-script-failure", "failed", False),
            control("missing-artifact", "failed", True),
            control("timeout", "failed", True),
        ]
        verdict = negative_controls.summarize(report(controls))
        self.assertEqual(verdict["status"], "failed", verdict)

    def test_compile_rejection_failure_fails_suite(self):
        controls = [
            control("missing-runtime", "blocked", True, expected="blocked"),
            control("native-script-failure", "failed", True),
            control("missing-artifact", "failed", True),
            control("timeout", "failed", True),
        ]
        verdict = negative_controls.summarize(report(controls, compile_ok=False))
        self.assertEqual(verdict["status"], "failed", verdict)

    def test_recovery_failure_fails_suite(self):
        controls = [
            control("missing-runtime", "blocked", True, expected="blocked"),
            control("native-script-failure", "failed", True),
            control("missing-artifact", "failed", True),
            control("timeout", "failed", True),
        ]
        verdict = negative_controls.summarize(report(controls, recovery_ok=False))
        self.assertEqual(verdict["status"], "failed", verdict)


if __name__ == "__main__":
    unittest.main()
