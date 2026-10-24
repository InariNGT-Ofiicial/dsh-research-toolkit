"""Explicit capabilities, discovery paths and primary documentation."""
import json
import os
import shutil
import sys
from pathlib import Path

TOOLS_ROOT = Path(os.environ.get("RB_TOOLS_ROOT", r"D:\Codex\ResearchToolkit"))

def entry(title, family, mode, operations, names=(), paths=(), docs="", commercial=False):
    return dict(title=title, family=family, mode=mode, operations=list(operations),
                names=list(names), paths=list(paths), docs=docs, commercial=commercial)

CATALOG = {
 "r": entry("R", "statistics", "native", ["script", "analysis"], ["Rscript"], [r"E:\ResearchTools\R\bin\Rscript.exe"], "https://stat.ethz.ch/R-manual/R-devel/library/utils/html/Rscript.html"),
 "python": entry("Scientific Python", "statistics", "native", ["script", "analysis"], ["python"], [str(TOOLS_ROOT / "python-venv/Scripts/python.exe"), sys.executable], "https://docs.python.org/3/using/cmdline.html"),
 "jamovi": entry("jamovi (jmv backend)", "statistics", "native", ["script", "analysis"], ["Rscript"], [r"E:\ResearchTools\R\bin\Rscript.exe"], "https://www.jamovi.org/jmv/"),
 "spss": entry("IBM SPSS Statistics", "statistics", "native", ["probe", "script", "analysis"], [], [r"E:\SPSS Files\Python3\python.exe"], "https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=programs-running-spss-statistics-from-external-python-process", True),
 "stata": entry("Stata", "statistics", "native", ["script", "analysis"], ["StataMP-64.exe", "StataSE-64.exe", "StataBE-64.exe", "stata"], [r"C:\Program Files\Stata19\StataMP-64.exe",r"E:\ResearchTools\Stata\StataMP-64.exe"], "https://www.stata.com/manuals/gsw16.pdf", True),
 "sas": entry("SAS", "statistics", "native", ["script", "analysis"], ["sas"], [r"C:\Program Files\SASHome\SASFoundation\9.4\sas.exe"], "https://documentation.sas.com/", True),
 "matlab": entry("MATLAB", "numerical", "native", ["script", "analysis", "chain_dynamics"], ["matlab"], [r"E:\MATLAB\bin\matlab.exe", r"E:\MATLAB\R2026a\bin\matlab.exe", r"E:\ResearchTools\MATLAB\R2026a\bin\matlab.exe", r"C:\Program Files\MATLAB\R2026b\bin\matlab.exe"], "https://www.mathworks.com/help/matlab/ref/matlabwindows.html", True),
 "octave": entry("GNU Octave", "numerical", "native", ["script", "analysis"], ["octave-cli", "octave"], [str(TOOLS_ROOT / "tools/Octave/mingw64/bin/octave-cli.exe")], "https://docs.octave.org/latest/Command-Line-Options.html"),
 "julia": entry("Julia", "numerical", "native", ["script", "analysis"], ["julia"], [str(TOOLS_ROOT / "tools/Julia/bin/julia.exe")], "https://docs.julialang.org/en/v1/manual/command-line-interface/"),
 "jupyter": entry("Jupyter", "reproducibility", "native", ["execute"], ["python"], [str(TOOLS_ROOT / "python-venv/Scripts/python.exe")], "https://nbconvert.readthedocs.io/en/latest/execute.html"),
 "pandoc": entry("Pandoc", "publishing", "native", ["convert"], ["pandoc"], [r"E:\ResearchTools\Typesetting\Pandoc\pandoc.exe"], "https://pandoc.org/MANUAL.html"),
 "quarto": entry("Quarto", "publishing", "native", ["render"], ["quarto"], [r"E:\ResearchTools\Typesetting\Quarto\bin\quarto.cmd"], "https://quarto.org/docs/reference/cli.html"),
 "latex": entry("XeLaTeX / MiKTeX", "publishing", "native", ["render"], ["xelatex"], [r"E:\ResearchTools\Typesetting\MiKTeX\miktex\bin\x64\xelatex.exe"], "https://docs.miktex.org/manual/xetex.html"),
 "libreoffice": entry("LibreOffice", "office", "native", ["convert"], ["soffice"], [str(TOOLS_ROOT / "tools/LibreOffice/program/soffice.com"),r"C:\Program Files\LibreOffice\program\soffice.com"], "https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html"),
 "office": entry("Microsoft Word / Excel / PowerPoint", "office", "native", ["convert", "recalculate"], ["powershell.exe"], [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"], "https://learn.microsoft.com/en-us/office/vba/api/overview/", True),
 "inkscape": entry("Inkscape", "figures", "native", ["export"], ["inkscape.com", "inkscape"], [str(TOOLS_ROOT / "tools/Inkscape/bin/inkscape.com"),str(TOOLS_ROOT / "tools/Inkscape/PFiles64/Inkscape/bin/inkscape.com"),r"C:\Program Files\Inkscape\bin\inkscape.com"], "https://inkscape.org/doc/inkscape-man.html"),
 "graphviz": entry("Graphviz", "figures", "native", ["render"], ["dot"], [str(TOOLS_ROOT / "tools/Graphviz/bin/dot.exe")], "https://graphviz.org/doc/info/command.html"),
 "imagej": entry("ImageJ", "imaging", "native", ["macro"], ["ImageJ-win64.exe"], [str(TOOLS_ROOT / "tools/ImageJ/ImageJ.exe"),str(TOOLS_ROOT / "tools/ImageJ/ImageJ-win64.exe")], "https://imagej.net/ij/developer/macro/macros.html"),
 "zotero": entry("Zotero local API", "literature", "local_api", ["search", "item", "children"], [], [r"E:\ResearchTools\Literature\Zotero\zotero.exe"], "https://www.zotero.org/support/dev/web_api/v3/basics"),
 "jabref": entry("JabRef / BibTeX", "literature", "file_interchange", ["bibliography"], ["JabRef"], [], "https://docs.jabref.org/advanced/commandline"),
 "endnote": entry("EndNote / RIS", "literature", "file_interchange", ["bibliography"], [], [], "https://support.clarivate.com/Endnote/", True),
 "nvivo": entry("NVivo / REFI-QDA", "qualitative", "file_interchange", ["codebook", "import_codebook"], [], [], "https://www.qdasoftware.org/codebook-implementation-files", True),
 "maxqda": entry("MAXQDA / REFI-QDA", "qualitative", "file_interchange", ["codebook", "import_codebook"], [], [], "https://www.maxqda.com/help/report-and-export/export-and-import-refi-qda-projects", True),
 "atlas-ti": entry("ATLAS.ti / REFI-QDA", "qualitative", "file_interchange", ["codebook", "import_codebook"], [], [], "https://www.qdasoftware.org/", True),
 "origin": entry("Origin", "figures", "native", ["script"], ["powershell.exe"], [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"], "https://www.originlab.com/doc/COM", True),
 "prism": entry("GraphPad Prism", "figures", "file_interchange", ["table"], [], [], "https://www.graphpad.com/guides/prism/latest/user-guide/using_script_commands.htm", True),
 "jasp": entry("JASP", "statistics", "file_interchange", ["table"], [], [], "https://jasp-stats.org/faq/"),
 "rstudio": entry("RStudio", "ide", "file_interchange", ["project"], [], [r"E:\ResearchTools\RStudio\rstudio.exe"], "https://docs.posit.co/ide/user/ide/guide/code/projects.html"),
 "git": entry("Git", "reproducibility", "native", ["snapshot"], ["git"], [r"D:\Git\cmd\git.exe"], "https://git-scm.com/docs/git"),
}

def load_config(path=None):
    p = Path(path or os.environ.get("RB_CONFIG", str(TOOLS_ROOT / "bridge-config.json")))
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else {}

def discover(config=None):
    cfg = config if config is not None else load_config()
    overrides = cfg.get("executables", cfg)
    strict = bool(cfg.get("strict_executables", False))
    rows = {}
    for engine, spec in CATALOG.items():
        if strict:
            # An explicit experiment pin: no fallback paths or PATH lookup may
            # silently substitute another installation for the requested one.
            candidates = [overrides[engine]] if overrides.get(engine) else []
        else:
            candidates = ([overrides[engine]] if overrides.get(engine) else []) + spec["paths"]
        if not strict and engine == "julia":
            candidates += [str(p) for p in sorted((TOOLS_ROOT/"tools/Julia").glob("*/bin/julia.exe"),reverse=True)]
        elif not strict and engine == "octave":
            candidates += [str(p) for p in sorted((TOOLS_ROOT/"tools/Octave").glob("*/mingw64/bin/octave-cli.exe"),reverse=True)]
        elif not strict and engine == "matlab":
            # Versioned installation roots are discovered locally; the explicit
            # candidates above remain the reviewed fallback.
            for root in (Path(r"E:\MATLAB"), Path(r"E:\ResearchTools\MATLAB"), Path(r"C:\Program Files\MATLAB")):
                if root.is_dir():
                    candidates += [str(p) for p in sorted(root.glob("R*/bin/matlab.exe"), reverse=True)]
        if not strict:
            candidates += [shutil.which(n) for n in spec["names"]]
        found = next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()), None)
        rows[engine] = {**spec, "engine": engine, "executable": found,
                        "installed": bool(found), "probe_status": "not_run",
                        "application_verified": False}
        if spec["mode"] == "file_interchange":
            rows[engine]["availability"] = "file_interchange_only"
        elif found:
            rows[engine]["availability"] = "executable_found_not_validated"
        else:
            rows[engine]["availability"] = "requires_license_and_installation" if spec["commercial"] else "not_installed"
        if engine in ("office", "origin"):
            rows[engine]["availability"] = "requires_com_application_probe"
            registered=False
            if os.name=="nt":
                import winreg
                progids=("Word.Application","Excel.Application","PowerPoint.Application") if engine=="office" else ("Origin.ApplicationSI",)
                for progid in progids:
                    try:
                        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,progid+"\\CLSID"):
                            registered=True
                    except OSError:
                        pass
            rows[engine]["installed"]=registered
            if not registered:
                rows[engine]["executable"]=None
                rows[engine]["availability"]="requires_license_and_installation"
    return rows
