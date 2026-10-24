"""Real Zotero acceptance in a dedicated, disposable profile and synthetic library.

The connector HTTP import endpoint seeds this isolated fixture only. The shipped
agent bridge remains read-only. No existing profile, account or library is used.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_bridge.core import compile_job, run_compiled, save_json
from research_bridge.catalog import load_config

def main():
    p=argparse.ArgumentParser(); p.add_argument("workspace",type=Path); p.add_argument("--app",default=r"E:\ResearchTools\Literature\Zotero\zotero.exe")
    a=p.parse_args(); root=a.workspace.resolve(); root.mkdir(parents=True,exist_ok=True)
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1",23119))==0:
            raise RuntimeError("Port 23119 is occupied; refusing to seed any existing Zotero instance")
    profile=root/"profile"; data=root/"library"; profile.mkdir(exist_ok=True); data.mkdir(exist_ok=True)
    prefs={"extensions.zotero.firstRun2":False,"extensions.zotero.firstRunGuidance":False,"extensions.zotero.useDataDir":True,"extensions.zotero.dataDir":str(data),"extensions.zotero.httpServer.enabled":True,"extensions.zotero.httpServer.localAPI.enabled":True,"extensions.zotero.httpServer.port":23119,"extensions.zotero.sync.autoSync":False,"app.update.auto":False,"browser.shell.checkDefaultBrowser":False}
    (profile/"user.js").write_text("\n".join("user_pref("+json.dumps(k)+", "+json.dumps(v)+");" for k,v in prefs.items()),encoding="utf-8")
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def request(path,payload=None):
        body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
        headers={"Zotero-API-Version":"3","Zotero-Connector-API-Version":"3","Zotero-Connector-Version":"6.0.0","Content-Type":"application/json","Accept":"application/json"}
        with opener.open(urllib.request.Request("http://127.0.0.1:23119"+path,data=body,headers=headers),timeout=15) as r:
            raw=r.read(); return (r.status,json.loads(raw) if raw else None,dict(r.headers))
    startup=None
    if os.name=="nt":
        startup=subprocess.STARTUPINFO(); startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow=0
    env={**os.environ,"MOZ_HEADLESS":"1"}
    log=(root/"zotero-process.log").open("wb")
    proc=subprocess.Popen([a.app,"-no-remote","-profile",str(profile),"-headless","-ZoteroDebugText"],env=env,stdout=log,stderr=subprocess.STDOUT,startupinfo=startup)
    report=dict(status="running",synthetic_library=True,profile=str(profile),pid=proc.pid,checks=[])
    save_json(root/"zotero-acceptance.json",report)
    try:
        deadline=time.monotonic()+75
        while time.monotonic()<deadline:
            try:
                status,initial,headers=request("/api/users/0/items?limit=1")
                if status==200: break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("isolated Zotero did not expose its API within 75 seconds")
        if not (data/"zotero.sqlite").is_file():
            raise RuntimeError("Zotero is not using the isolated fixture library; refusing to import")
        items=[]
        for i in range(12):
            items.append(dict(id="fixture-"+str(i),itemType="journalArticle",title="DSHBRIDGEFIXTURE "+str(i)+" 中文与 longitudinal research",creators=[dict(firstName="Synthetic",lastName="Author",creatorType="author")],date="2026",publicationTitle="Synthetic validation fixtures",DOI="10.0000/dsh-fixture-"+str(i),tags=["synthetic","bridge-acceptance"],notes=[dict(note="<p>Analytic memo "+str(i)+": 缺失审计与研究方法。</p>")],attachments=[]))
        status,_,_=request("/connector/saveItems",dict(sessionID=uuid.uuid4().hex,uri="https://example.invalid/dsh-synthetic-fixture",items=items))
        if status!=201: raise AssertionError("fixture import did not return 201")
        cfg=load_config()
        def execute(id,op,params):
            job=dict(schema_version="research.job.v1",id=id,engine="zotero",operation=op,inputs={},parameters=params,timeout_s=20)
            directory=root/"runs"/id
            result=run_compiled(compile_job(job,directory,cfg))
            if result["status"]!="passed": raise AssertionError(str(result))
            report["checks"].append(dict(id=id,status="passed",workspace=str(directory),artifacts=result["artifacts"]))
            return directory
        directory=execute("search-synthetic-literature","search",dict(query="DSHBRIDGEFIXTURE",limit=100))
        found=json.loads((directory/"zotero-items.json").read_text(encoding="utf-8"))
        articles=[x for x in found if x.get("data",{}).get("itemType")=="journalArticle"]
        if len(articles)!=12: raise AssertionError("expected exactly 12 synthetic articles, got "+str(len(articles)))
        directory=execute("bounded-search","search",dict(query="DSHBRIDGEFIXTURE",limit=5))
        if len(json.loads((directory/"zotero-items.json").read_text(encoding="utf-8")))!=5: raise AssertionError("limit oracle mismatch")
        key=articles[0]["key"]
        directory=execute("retrieve-detail","item",dict(key=key))
        detail=json.loads((directory/"zotero-item.json").read_text(encoding="utf-8"))
        if "中文" not in detail["data"]["title"] or not detail["data"].get("DOI"): raise AssertionError("Unicode or DOI field lost")
        directory=execute("retrieve-child-note","children",dict(key=key))
        children=json.loads((directory/"zotero-children.json").read_text(encoding="utf-8"))
        if not any(c["data"]["itemType"]=="note" for c in children): raise AssertionError("child note not found")
        report.update(status="passed",articles=12,limit_verified=5,unicode_and_doi=True,child_note=True,application_version=headers.get("Zotero-Version"),scope="real Zotero desktop; isolated synthetic library; no user-library write")
    except Exception as e:
        report.update(status="failed",reason=type(e).__name__+": "+str(e))
    finally:
        if proc.poll() is None:
            if os.name=="nt": subprocess.run(["taskkill","/PID",str(proc.pid),"/T","/F"],capture_output=True,timeout=15)
            else: proc.terminate()
            try: proc.wait(timeout=15)
            except subprocess.TimeoutExpired: proc.kill()
        log.close()
        report["fixture_process_stopped"]=proc.poll() is not None
        save_json(root/"zotero-acceptance.json",report)
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["status"]=="passed" else 1

if __name__=="__main__": raise SystemExit(main())
