"""Re-verify saved evidence rather than trusting a previous 'passed' label."""
import hashlib
import json
from collections import Counter
from pathlib import Path

def verify_directory(directory):
    root=Path(directory).resolve()
    if not root.is_dir():
        return dict(status="failed",reason="evidence directory does not exist",checks=[])
    records=[]
    files=list(root.rglob("result.json"))
    for path in sorted(files):
        try:
            result=json.loads(path.read_text(encoding="utf-8-sig"))
            if result.get("schema_version")!="research.result.v1" and result.get("status")!="blocked":
                continue
            errors=[]
            for artifact in result.get("artifacts",[]):
                p=Path(artifact["path"])
                if not p.is_absolute():
                    p=path.parent/p
                if not p.is_file():
                    errors.append("missing artifact: "+str(p))
                elif hashlib.sha256(p.read_bytes()).hexdigest()!=artifact.get("sha256"):
                    errors.append("artifact hash mismatch: "+str(p))
                else:
                    from .core import validate_artifact
                    try: validate_artifact(p)
                    except Exception as e: errors.append("invalid artifact: "+str(e))
            if result.get("status")=="passed":
                if not result.get("processes"):
                    errors.append("passed record has no process execution evidence")
                for process in result.get("processes",[]):
                    if process.get("status")!="passed" or process.get("exit_code")!=0 or process.get("timed_out"):
                        errors.append("unsuccessful process in a passed record")
            records.append(dict(engine=result.get("engine"),status="failed" if errors else result.get("status","failed"),errors=errors,result_path=str(path),scope=result.get("scope"),application_verified=result.get("application_verified",False)))
        except Exception as e:
            records.append(dict(status="failed",result_path=str(path),errors=[str(e)]))
    counts=dict(Counter(r["status"] for r in records))
    if not records:
        return dict(status="failed",reason="no supported result.json execution records found",checks=[],counts={})
    acceptance=None
    acceptance_path=root/"acceptance.json"
    if acceptance_path.is_file():
        try:
            candidate=json.loads(acceptance_path.read_text(encoding="utf-8-sig"))
            if candidate.get("schema_version")=="research.acceptance.v1":
                acceptance=candidate
        except Exception as e:
            return dict(status="failed",reason="invalid acceptance manifest: "+str(e),checks=records,counts=counts)
    oracle_failed=bool(acceptance and (acceptance.get("status")=="failed" or any(c.get("status")=="failed" for c in acceptance.get("checks",[]))))
    status="failed" if counts.get("failed") or oracle_failed else ("blocked" if counts.get("blocked") and not counts.get("passed") else "passed")
    return dict(status=status,checks=records,counts=counts,acceptance=acceptance,scope="artifact_integrity_and_process_evidence_with_saved_oracles",complete_native_coverage=not bool(counts.get("blocked")),note="File exchange validates the interchange scope, not execution inside the named GUI application.")
