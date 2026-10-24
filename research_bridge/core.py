"""Job validation, bounded process execution and evidence collection."""
import hashlib
import csv
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .catalog import CATALOG, discover, load_config

class JobError(ValueError):
    pass

def save_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

def inside(path, root):
    p, r = Path(path).resolve(), Path(root).resolve()
    if p != r and r not in p.parents:
        raise JobError("output path escapes job workspace: " + str(p))
    return p

def validate_job(job):
    if not isinstance(job, dict) or job.get("schema_version") != "research.job.v1":
        raise JobError("schema_version must be research.job.v1")
    if job.get("engine") not in CATALOG:
        raise JobError("unknown engine: " + str(job.get("engine")))
    if job.get("operation") not in CATALOG[job["engine"]]["operations"]:
        raise JobError("unsupported operation for engine")
    if not isinstance(job.get("inputs", {}), dict) or not isinstance(job.get("parameters", {}), dict):
        raise JobError("inputs and parameters must be objects")
    timeout = job.get("timeout_s", 120)
    if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not 0 < timeout <= 1800:
        raise JobError("timeout_s must be between 0 and 1800")
    return job

def read_job(path):
    p = Path(path).resolve()
    job = json.loads(p.read_text(encoding="utf-8-sig"))
    validate_job(job)
    for key, value in job.get("inputs", {}).items():
        if isinstance(value, str) and key not in ("key", "query", "url"):
            q = Path(value)
            job["inputs"][key] = str((p.parent / q).resolve()) if not q.is_absolute() else str(q.resolve())
    return job

def compile_job(job, workspace, config=None):
    validate_job(job)
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    found = discover(config)
    exes = {k: v["executable"] for k, v in found.items()}
    from .adapters import stats, documents, exchange, chain_dynamics
    # The chain_dynamics operation is an explicit, reviewed dispatch: it must not
    # be reachable through the generic script/analysis compilers.
    if job["engine"] == "matlab" and job["operation"] == "chain_dynamics":
        adapter = chain_dynamics
    else:
        adapter = stats if job["engine"] in stats.SUPPORTED_ENGINES else (documents if job["engine"] in documents.SUPPORTED_ENGINES else exchange)
    result = adapter.compile_job(job, workspace, exes)
    result.update(schema_version="research.compiled.v1", job_id=job.get("id", "job"),
                  mode=CATALOG[job["engine"]]["mode"], workspace=str(workspace))
    for artifact in result.get("expected_artifacts", []):
        inside(artifact, workspace)
    save_json(workspace / "job.json", job)
    save_json(workspace / "compiled.json", result)
    return result

def decode_output(data):
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", "replace")

def run_process(command, cwd, timeout_s=120, env=None):
    start = time.monotonic()
    command = [str(c) for c in command]
    actual = command
    if os.name == "nt" and Path(command[0]).suffix.lower() in (".cmd", ".bat"):
        if any(re.search(r"[&|<>^%!\r\n]", c) for c in command):
            return dict(status="failed", reason="batch arguments contain unsafe command metacharacters", exit_code=None, stdout="", stderr="", timed_out=False, duration_s=0)
        actual = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/v:off", "/s", "/c", subprocess.list2cmdline(command)]
    child_env = dict(os.environ)
    child_env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    child_env.update({k: str(v) for k,v in (env or {}).items()})
    ownership=None
    p=None
    try:
        if os.name=="nt":
            from .windows_job import WindowsJob
            ownership=WindowsJob()
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004 if os.name == "nt" else 0
        p = subprocess.Popen(actual, cwd=cwd, env=child_env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, creationflags=flags, start_new_session=(os.name != "nt"))
        if ownership:
            ownership.attach_and_resume(p)
        timed_out = False
        try:
            so, se = p.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            if ownership:
                ownership.terminate()
            else:
                os.killpg(p.pid, signal.SIGKILL)
            if p.poll() is None:
                p.kill()
            so, se = p.communicate(timeout=15)
        return dict(status="passed" if p.returncode == 0 and not timed_out else "failed",
                    exit_code=p.returncode, stdout=decode_output(so), stderr=decode_output(se),
                    timed_out=timed_out, duration_s=round(time.monotonic()-start, 3), command=command)
    except (OSError, subprocess.SubprocessError) as e:
        if p is not None and p.poll() is None:
            p.kill()
            try: p.communicate(timeout=5)
            except subprocess.SubprocessError: pass
        return dict(status="failed", exit_code=None, stdout="", stderr=str(e), timed_out=False,
                    duration_s=round(time.monotonic()-start, 3), command=command)
    finally:
        if ownership:
            ownership.close()

def artifact_record(path):
    p = Path(path)
    return dict(path=str(p.resolve()), bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(), modified_ns=p.stat().st_mtime_ns)

def validate_artifact(path):
    p=Path(path)
    suffix=p.suffix.lower()
    if suffix==".pdf" and not p.read_bytes().startswith(b"%PDF-"):
        raise JobError("PDF signature mismatch")
    if suffix==".png" and not p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise JobError("PNG signature mismatch")
    if suffix in (".docx",".xlsx",".pptx",".odt"):
        required={".docx":"word/document.xml",".xlsx":"xl/workbook.xml",".pptx":"ppt/presentation.xml",".odt":"mimetype"}[suffix]
        with zipfile.ZipFile(p) as z:
            if required not in z.namelist(): raise JobError("native document package is missing "+required)
    if suffix in (".json",".ipynb"):
        def nonfinite(value): raise ValueError("non-finite JSON number: "+value)
        value=json.loads(p.read_text(encoding="utf-8-sig"),parse_constant=nonfinite)
        if suffix==".ipynb" and (not isinstance(value,dict) or value.get("nbformat")!=4):
            raise JobError("notebook does not declare nbformat=4")
    if suffix in (".svg",".xml",".qdc"):
        ET.parse(p)
    if suffix==".csv":
        with p.open(encoding="utf-8-sig",newline="") as f:
            rows=csv.reader(f); header=next(rows,None)
            if not header or len(set(header))!=len(header) or any(len(row)!=len(header) for row in rows):
                raise JobError("CSV is empty, has duplicate columns or is not rectangular")

def run_compiled(compiled, max_timeout_s=300):
    root = Path(compiled["workspace"]).resolve()
    if not compiled.get("ready", True) or not (compiled.get("command") or compiled.get("commands")):
        result = dict(status="blocked", engine=compiled["engine"],
                      reason=compiled.get("reason", "native executable or dependency missing"),
                      application_verified=False, artifacts=[], workspace=str(root))
        save_json(root / "result.json", result)
        return result
    expected = [inside(p, root) for p in compiled.get("expected_artifacts", [])]
    # Each job directory is fresh. Existing expected outputs invalidate the run, rather than count as evidence.
    if any(p.exists() for p in expected):
        raise JobError("expected output already exists before execution; use a fresh workspace")
    results = []
    started_ns = time.time_ns()
    for command in compiled.get("commands", [compiled.get("command")]):
        p = run_process(command, compiled.get("cwd", str(root)),
                        min(float(compiled.get("timeout_s",120)), float(max_timeout_s)), compiled.get("env"))
        results.append(p)
        if p["status"] != "passed":
            break
    output = "\n".join(r["stdout"] + "\n" + r["stderr"] for r in results)
    errors = []
    for marker in compiled.get("required_markers", []):
        if marker not in output:
            errors.append("missing completion marker: " + marker)
    artifacts = []
    for p in expected:
        if not p.is_file() or p.stat().st_size == 0:
            errors.append("missing or empty output: " + str(p))
        elif p.stat().st_mtime_ns < started_ns - 2_000_000_000:
            errors.append("stale output: " + str(p))
        else:
            try:
                validate_artifact(p)
                artifacts.append(artifact_record(p))
            except Exception as e:
                errors.append("invalid output "+str(p)+": "+str(e))
    explicitly_blocked = any(r.get("exit_code")==2 and "RB_BLOCKED:" in (r.get("stdout","")+r.get("stderr","")) for r in results)
    status = "blocked" if explicitly_blocked else ("passed" if all(r["status"] == "passed" for r in results) and not errors else "failed")
    result = dict(schema_version="research.result.v1", status=status, engine=compiled["engine"],
                  operation=compiled["operation"], scope=compiled.get("scope", compiled["mode"]),
                  application_verified=status=="passed" and compiled["mode"] in ("native", "local_api"),
                  errors=errors, processes=results, artifacts=artifacts, workspace=str(root))
    save_json(root / "result.json", result)
    return result

def execute_job(job_path, workspace, config=None, max_timeout_s=300):
    job = read_job(job_path)
    slug = re.sub(r"[^A-Za-z0-9_-]", "-", str(job.get("id", job["engine"])))[:60]
    root = Path(workspace).resolve() / (slug + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    compiled = compile_job(job, root, config)
    return run_compiled(compiled, max_timeout_s)
