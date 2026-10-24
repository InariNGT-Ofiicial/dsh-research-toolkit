"""Read-only local API and honest, vendor-independent interchange bridges."""
import json
import sys
from pathlib import Path

def compile_job(job, workspace, executables):
    root = Path(workspace).resolve()
    engine, op = job["engine"], job["operation"]
    worker = Path(__file__).with_name("exchange_worker.py")
    payload = root / "exchange-request.json"
    payload.write_text(json.dumps(job,ensure_ascii=False),encoding="utf-8")
    ext = {"bibliography":("references.bib" if engine=="jabref" else "references.ris"),
           "codebook":"codebook.qdc", "import_codebook":"codebook.json", "table":"data.csv", "project":"research.Rproj",
           "search":"zotero-items.json", "item":"zotero-item.json", "children":"zotero-children.json"}[op]
    result = dict(status="compiled",engine=engine,operation=op,ready=True,
                  command=[sys.executable,"-B",str(worker),str(payload),str(root)],
                  source_path=str(payload),cwd=str(root),env={},timeout_s=job.get("timeout_s",30),
                  required_markers=["RB_EXCHANGE_COMPLETE"],expected_artifacts=[str(root/ext)],
                  scope="local_api" if engine=="zotero" else "file_interchange",
                  application_verified=False)
    return result
