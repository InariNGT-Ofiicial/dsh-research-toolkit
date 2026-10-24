"""Isolated target-API prototype. Copy before editing; never auto-loaded by DSH.

The arguments below belong to this wrapper, not to an unknown application.
All three target-specific functions intentionally block until implemented from
official, version-matched documentation and independent scientific evidence.
"""
import argparse
import json
import sys
from pathlib import Path


class BridgeBlocked(RuntimeError):
    """A proven dependency/interface gap; do not turn it into success."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise BridgeBlocked("wrapper arguments: " + message)


def run_target_native(job, output_dir):
    """Implement one narrow official target operation in an owned instance.

    Do not accept an arbitrary module, code string or shell command from job.
    Record target version/identity and fresh native artifacts. For subprocesses,
    use the package's bounded owned-process runner during integration. For an
    API/COM backend, close only this task's own objects in try/finally.
    """
    raise BridgeBlocked("target official interface not implemented; no target application was executed")


def verify_target_identity(receipt, output_dir):
    """Return observed target identity only after checking native evidence.

    A Python wrapper exit code, package import or supplied receipt boolean does
    not establish that the named target performed the operation.
    """
    raise BridgeBlocked("target identity verifier not implemented")


def verify_scientific_oracle(job, receipt, output_dir):
    """Recompute the declared scientific/structural oracle independently.

    Return True only after reading the actual fresh artifacts and comparing
    against fixed expectations. Do not trust receipt['status'] or a marker.
    Save expected/observed values, preprocessing and tolerance in a report.
    """
    raise BridgeBlocked("independent scientific verifier not implemented")


def main(argv=None):
    output = None
    try:
        parser = Parser(description=__doc__, add_help=False)
        parser.add_argument("--request", required=True)
        parser.add_argument("--workspace", required=True)
        args = parser.parse_args(argv)
        request = Path(args.request).resolve(strict=True)
        output = Path(args.workspace).resolve()
        job = json.loads(request.read_text(encoding="utf-8-sig"))
        if not isinstance(job, dict):
            raise ValueError("request must be a JSON object")
        # Every run gets a new directory. Do not remove or reuse previous evidence.
        if output.exists() and any(output.iterdir()):
            raise BridgeBlocked("prototype output directory is not empty; choose a new workspace")
        output.mkdir(parents=True, exist_ok=True)
        receipt = run_target_native(job, output)
        identity = verify_target_identity(receipt, output)
        if not isinstance(identity, dict) or identity.get("observed") is not True:
            raise BridgeBlocked("target native identity was not independently observed")
        if verify_scientific_oracle(job, receipt, output) is not True:
            raise ValueError("independent scientific oracle did not pass")
        result = {
            "schema_version": "research.bridge.prototype.v1",
            "status": "prototype_verified",
            "python_wrapper_ran": True,
            "target_native_observed": True,
            "application_verified": False,
            "scope": "isolated_prototype_not_catalog_or_dsh_acceptance",
            "workspace": str(output),
            "target_identity": identity,
            "note": "Promote only through explicit catalog integration and actual DSH Agent acceptance.",
        }
        print("RB_TARGET_NATIVE_COMPLETE", file=sys.stderr)
        code = 0
    except BridgeBlocked as error:
        result = {"schema_version": "research.bridge.prototype.v1", "status": "blocked",
                  "application_verified": False, "reason": str(error), "workspace": str(output) if output else None}
        print("RB_BLOCKED: " + str(error), file=sys.stderr)
        code = 2
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        result = {"schema_version": "research.bridge.prototype.v1", "status": "failed",
                  "application_verified": False, "reason": str(error), "workspace": str(output) if output else None}
        print(str(error), file=sys.stderr)
        code = 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
