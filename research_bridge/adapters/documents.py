"""Compile publishing, office, graphics and reproducibility jobs to native commands."""
import json
import os
import shutil
import sys
from pathlib import Path

SUPPORTED_ENGINES = {"pandoc", "quarto", "latex", "libreoffice", "office", "inkscape", "graphviz", "imagej", "jupyter", "git", "origin"}

def _source(job, *keys):
    for key in keys:
        p = job.get("inputs", {}).get(key)
        if p and Path(p).is_file():
            return Path(p).resolve()
    raise ValueError("input file is required: " + ", ".join(keys))

def _ps(value):
    return "'" + str(value).replace("'", "''") + "'"

def _imagej_macro_source(macro):
    """ImageJ 1.x reads macro files as ISO-8859-1, even on a UTF-8 JVM."""
    if macro.isascii():
        return macro
    # Restore the complete Unicode program inside ImageJ's macro interpreter.
    # fromCharCode uses a fixed char[100] in ImageJ 1.x: keep each call smaller.
    raw = macro.encode("utf-16-le")
    units = [int.from_bytes(raw[i:i+2], "little") for i in range(0, len(raw), 2)]
    chunks = ["fromCharCode(" + ",".join(map(str, units[i:i+96])) + ")" for i in range(0, len(units), 96)]
    return "eval(" + "+\n".join(chunks) + ");\n"

def _copy_resources(job,source,root):
    mapping={}
    resource_map=job.get("parameters",{}).get("resource_map",{})
    if not isinstance(resource_map,dict):
        raise ValueError("resource_map must map input names to relative job paths")
    for key,value in job.get("inputs",{}).items():
        if key in ("source","script") or not isinstance(value,str) or not Path(value).is_file():
            continue
        original=Path(value).resolve()
        if key in resource_map:
            relative=Path(str(resource_map[key]))
        else:
            try: relative=original.relative_to(source.parent)
            except ValueError: relative=Path(original.name)
        target=(root/relative).resolve()
        if root not in target.parents or target.name in (source.name,"job.json","compiled.json","result.json"):
            raise ValueError("resource destination escapes or collides with job files")
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,target)
        mapping[str(original)]=str(target)
    return mapping

def compile_job(job, workspace, executables):
    root = Path(workspace).resolve()
    engine, op, params = job["engine"], job["operation"], job.get("parameters", {})
    exe = executables.get(engine)
    result = dict(status="compiled", engine=engine, operation=op, ready=bool(exe),
                  command=[], cwd=str(root), env={}, timeout_s=job.get("timeout_s",120),
                  expected_artifacts=[], required_markers=[], source_path=None)
    if not exe:
        result["reason"] = engine + " executable not found; configure its absolute path"
    source = None
    if engine not in ("git",):
        source = _source(job, "source", "script", "data")
        result["source_path"] = str(source)
    fmt = str(params.get("format", "pdf")).lower()
    if engine == "pandoc":
        if fmt not in ("pdf", "html", "docx", "odt", "md", "rst", "latex"):
            raise ValueError("unsupported pandoc output format")
        out = root / ("report." + ("tex" if fmt=="latex" else fmt))
        cmd = [exe, str(source), "--standalone", "--resource-path=" + str(source.parent), "-o", str(out)]
        if fmt == "pdf":
            cmd += ["--pdf-engine=xelatex", "-V", "CJKmainfont=Microsoft YaHei"]
        for key, flag in (("bibliography", "--bibliography"), ("csl", "--csl")):
            if job.get("inputs",{}).get(key):
                cmd += [flag, job["inputs"][key]]
                if key == "bibliography":
                    cmd += ["--citeproc"]
        result.update(command=cmd, expected_artifacts=[str(out)])
    elif engine == "quarto":
        if fmt not in ("html", "pdf", "docx"):
            raise ValueError("quarto format must be html/pdf/docx")
        copy = root / source.name
        shutil.copy2(source, copy)
        result["input_map"]=_copy_resources(job,source,root)
        out = root / ("report." + fmt)
        result.update(source_path=str(copy), command=[exe,"render",str(copy),"--to",fmt,"--output",out.name], expected_artifacts=[str(out)])
        py = executables.get("python")
        if py:
            result["env"]["QUARTO_PYTHON"] = py
        r = executables.get("r")
        if r:
            result["env"]["QUARTO_R"] = str(Path(r).parent)
    elif engine == "latex":
        copy = root / source.name
        shutil.copy2(source, copy)
        result["input_map"]=_copy_resources(job,source,root)
        out = root / (source.stem + ".pdf")
        # MiKTeX's default missing-package installer can wait for a GUI prompt
        # even in nonstopmode. Keep runtime compilation noninteractive; install
        # missing free packages explicitly through miktex packages install.
        cmd = [exe,"-interaction=nonstopmode","-halt-on-error","-no-shell-escape"]
        if exe and Path(exe).with_name("miktex.exe").is_file():
            cmd.append("--disable-installer")
        cmd.append(copy.name)
        result.update(source_path=str(copy),command=cmd,commands=[cmd,cmd],expected_artifacts=[str(out)])
    elif engine == "libreoffice":
        if fmt not in ("pdf", "docx", "odt", "xlsx", "csv", "html", "pptx"):
            raise ValueError("unsupported LibreOffice output format")
        out = root / (source.stem + "." + fmt)
        profile = (root / "office-profile").as_uri()
        result.update(command=[exe,"-env:UserInstallation="+profile,"--headless","--convert-to",fmt,"--outdir",str(root),str(source)],expected_artifacts=[str(out)])
    elif engine == "office":
        kind = str(params.get("application", "excel" if source.suffix.lower() in (".xlsx", ".xls", ".csv") else "word")).lower()
        if kind not in ("word","excel","powerpoint"):
            raise ValueError("office application must be word/excel/powerpoint")
        if op=="recalculate" and kind!="excel":
            raise ValueError("recalculate requires application=excel")
        out = root / ("recalculated.xlsx" if op=="recalculate" else "report.pdf")
        # A separate automation instance opens source read-only and writes only into the job workspace.
        pre = "$ErrorActionPreference='Stop'\n$app=$null; $doc=$null\ntry {\n"
        if kind == "word":
            body = "$app=New-Object -ComObject Word.Application\n$app.Visible=$false; $app.DisplayAlerts=0; $app.AutomationSecurity=3\n$doc=$app.Documents.Open("+_ps(source)+",$false,$true)\n$doc.ExportAsFixedFormat("+_ps(out)+",17)\n"
            close = "$doc.Close(0)"
        elif kind == "excel":
            body = "$app=New-Object -ComObject Excel.Application\n$app.Visible=$false; $app.DisplayAlerts=$false; $app.AskToUpdateLinks=$false\n$app.AutomationSecurity=3\n$doc=$app.Workbooks.Open("+_ps(source)+",0,$true)\n$app.CalculateFullRebuild()\n"
            if op == "recalculate":
                body += "$doc.SaveAs("+_ps(out)+",51)\n"
            else:
                body += "$doc.ExportAsFixedFormat(0,"+_ps(out)+")\n"
            close = "$doc.Close($false)"
        else:
            body = "$app=New-Object -ComObject PowerPoint.Application\n$doc=$app.Presentations.Open("+_ps(source)+",$true,$false,$false)\n$doc.SaveAs("+_ps(out)+",32)\n"
            close = "$doc.Close()"
        script = root / "office-job.ps1"
        script.write_text(pre+body+"Write-Output 'RB_OFFICE_COMPLETE'\n} catch { Write-Error $_; exit 1 } finally { if ($doc) { "+close+"; [void][Runtime.InteropServices.Marshal]::ReleaseComObject($doc) }; if ($app) { $app.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) } }\n",encoding="utf-8-sig")
        result.update(source_path=str(script),command=[exe,"-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",str(script)],required_markers=["RB_OFFICE_COMPLETE"],expected_artifacts=[str(out)])
    elif engine == "inkscape":
        if fmt not in ("pdf", "png", "svg", "eps"):
            raise ValueError("unsupported Inkscape format")
        out = root / ("figure."+fmt)
        dpi = float(params.get("dpi",300))
        if not 36 <= dpi <= 2400:
            raise ValueError("dpi outside 36..2400")
        result.update(command=[exe,str(source),"--export-type="+fmt,"--export-filename="+str(out),"--export-dpi="+str(dpi)],expected_artifacts=[str(out)])
    elif engine == "graphviz":
        if fmt not in ("svg","pdf","png"):
            raise ValueError("unsupported Graphviz format")
        out = root / ("diagram."+fmt)
        result.update(command=[exe,"-T"+fmt,str(source),"-o",str(out)],expected_artifacts=[str(out)])
    elif engine == "jupyter":
        copy=root/source.name
        shutil.copy2(source,copy)
        result["input_map"]=_copy_resources(job,source,root)
        out = root / "executed.ipynb"
        result.update(source_path=str(copy),command=[exe,"-m","nbconvert","--to","notebook","--execute",str(copy),"--output","executed.ipynb","--output-dir",str(root),"--ExecutePreprocessor.timeout="+str(int(job.get("timeout_s",120)))],expected_artifacts=[str(out)])
        result["env"]["JUPYTER_RUNTIME_DIR"] = str(root / "jupyter-runtime")
        result["env"]["IPYTHONDIR"] = str(root / "ipython")
        result["env"]["RB_OUTPUT_DIR"] = str(root)
        if exe:
            share=Path(exe).parent.parent/"share/jupyter"
            if share.is_dir():
                result["env"]["JUPYTER_PATH"] = str(share)
    elif engine == "imagej":
        copy = root / "analysis.ijm"
        output_name = str(params.get("output", "measurements.csv"))
        if Path(output_name).name != output_name:
            raise ValueError("ImageJ output must be a basename")
        macro = source.read_text(encoding="utf-8-sig").replace("{{OUTPUT_DIR}}",root.as_posix()).replace("{{INPUT_DATA}}",Path(job.get("inputs",{}).get("data", source)).as_posix())
        rendered = macro+"\nprint(\"RB_IMAGEJ_COMPLETE\");\n"
        (root / "analysis.utf8.ijm").write_text(rendered, encoding="utf-8")
        copy.write_text(_imagej_macro_source(rendered), encoding="ascii")
        home=Path(exe).parent if exe else Path('.')
        java=home/"jre/bin/java.exe"
        # ImageJ 1.x -batch suppresses the main window. AWT headless=true breaks
        # menu-backed commands (Fill, Analyze Particles); ImageJ2/Fiji uses a different launcher.
        command=[str(java),"-jar",str(home/"ij.jar"),"-batch",str(copy)] if java.is_file() and (home/"ij.jar").is_file() else [exe,"-batch",str(copy)]
        result.update(source_path=str(copy),command=command,required_markers=["RB_IMAGEJ_COMPLETE"],expected_artifacts=[str(root/output_name)])
    elif engine == "git":
        # Snapshot only a new job-local repository; never modifies the source repository or global Git config.
        script = root / "snapshot.py"
        src = job.get("inputs",{}).get("source")
        if not src or not Path(src).exists():
            raise ValueError("Git snapshot requires source file or directory")
        source_path=Path(src).resolve()
        if source_path.is_dir() and (source_path==root or source_path in root.parents):
            raise ValueError("Git snapshot workspace must be outside the source directory to prevent recursive copying")
        payload = dict(executable=exe,source=src,root=str(root))
        script.write_text("import json,pathlib,shutil,subprocess\np="+repr(payload)+"\nr=pathlib.Path(p['root'])/'snapshot'; r.mkdir()\ns=pathlib.Path(p['source'])\nif s.is_dir(): shutil.copytree(s,r/'source',ignore=shutil.ignore_patterns('.git','node_modules','__pycache__'))\nelse: shutil.copy2(s,r/s.name)\nfor args in [['init'],['add','--all'],['-c','user.name=Research Bridge','-c','user.email=local@invalid','commit','-m','Reproducible research snapshot']]:\n subprocess.run([p['executable'],*args],cwd=r,check=True,capture_output=True)\nv=subprocess.check_output([p['executable'],'rev-parse','HEAD'],cwd=r,text=True).strip()\n(pathlib.Path(p['root'])/'snapshot.json').write_text(json.dumps({'commit':v,'source':p['source']}),encoding='utf-8')\nprint('RB_GIT_COMPLETE')\n",encoding="utf-8")
        result.update(source_path=str(script),command=[sys.executable,"-B",str(script)],required_markers=["RB_GIT_COMPLETE"],expected_artifacts=[str(root/"snapshot.json")])
    elif engine == "origin":
        script = root / "origin-job.ps1"
        out = root/"origin-result.opju"
        script.write_text("$ErrorActionPreference='Stop'\n$app=$null\ntry { $app=New-Object -ComObject Origin.ApplicationSI; $app.Visible=0; $ok=$app.Execute("+_ps(source.read_text(encoding="utf-8-sig"))+"); if (!$ok) { throw 'Origin LabTalk execution failed' }; if (!$app.Save("+_ps(out)+")) { throw 'Origin project save failed' }; Write-Output 'RB_ORIGIN_COMPLETE' } finally { if ($app) { $app.Exit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) } }\n",encoding="utf-8-sig")
        result.update(source_path=str(script),command=[exe,"-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",str(script)],required_markers=["RB_ORIGIN_COMPLETE"],expected_artifacts=[str(out)])
    if not exe:
        result["command"] = []
        result.pop("commands",None)
    return result
