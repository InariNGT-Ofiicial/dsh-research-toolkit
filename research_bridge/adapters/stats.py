"""Compile explicit, reviewable statistical jobs to each program's native language.

Compilation is not execution or acceptance. Missing runtimes still produce source,
but never produce a runnable command. Generated analyses use complete cases and
record excluded rows; they do not silently impute data or infer variable types.
"""
from __future__ import annotations

import json
import inspect
import re
from pathlib import Path

SUPPORTED_ENGINES = {"r", "python", "jamovi", "spss", "stata", "matlab", "octave", "julia", "sas"}
_EXT = {"r": ".R", "jamovi": ".R", "python": ".py", "spss": ".sps", "stata": ".do", "matlab": ".m", "octave": ".m", "julia": ".jl", "sas": ".sas"}
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")


def _native_string(value: str, language: str = "r") -> str:
    # Julia interpolates $ even in ordinary quoted strings. JSON escaping alone
    # is insufficient for a literal filesystem path in Julia source.
    if language == "julia":
        return json.dumps(value.replace("\\", "/"), ensure_ascii=False).replace("$", "\\$")
    if language == "r":
        return json.dumps(value.replace("\\", "/"), ensure_ascii=False)
    return "'" + value.replace("\\", "/").replace("'", "''") + "'"


def _model(parameters: dict) -> tuple[str, list[str]]:
    if parameters.get("method", "linear_regression") != "linear_regression":
        raise ValueError("analysis supports method='linear_regression'; use script for other native analyses")
    outcome = parameters.get("outcome", "score")
    predictors = parameters.get("predictors", ["time", "treatment", "time_treatment"])
    if not isinstance(predictors, list) or not predictors or len(predictors) > 30:
        raise ValueError("predictors must be a nonempty list of at most 30 numeric column names")
    columns = [outcome, *predictors]
    if any(not isinstance(x, str) or not _IDENTIFIER.fullmatch(x) for x in columns):
        raise ValueError("variable names must match [A-Za-z][A-Za-z0-9_]{0,31}")
    if len(set(columns)) != len(columns):
        raise ValueError("outcome and predictors must be distinct")
    return outcome, predictors


PYTHON_ANALYSIS = r'''import csv, json, math, os
from pathlib import Path
cfg = __CONFIG__
out = Path(os.environ.get("RB_OUTPUT_DIR", cfg["output"]))
out.mkdir(parents=True, exist_ok=True)
with open(os.environ.get("RB_INPUT_DATA", cfg["data"]), encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    columns = [cfg["outcome"], *cfg["predictors"]]
    missing_columns = [name for name in columns if name not in (reader.fieldnames or [])]
    if missing_columns: raise ValueError("Missing columns: " + repr(missing_columns))
    raw = list(reader)
rows = []
for row in raw:
    try: values = [float(row[name]) for name in columns]
    except (ValueError, TypeError): continue
    if all(math.isfinite(v) for v in values): rows.append(values)
n, p = len(rows), len(columns)
if n <= p: raise ValueError("Insufficient complete rows for residual degrees of freedom")
y = [row[0] for row in rows]
X = [[1.0, *row[1:]] for row in rows]
# Pivoted Gauss-Jordan oracle. Only small, well-conditioned design matrices are
# supported; native engines should be used for large or ill-conditioned models.
G = [[sum(row[i]*row[j] for row in X) for j in range(p)] + [float(i==j) for j in range(p)] for i in range(p)]
for k in range(p):
    pivot = max(range(k,p), key=lambda i: abs(G[i][k]))
    if abs(G[pivot][k]) < 1e-12: raise ValueError("Singular design matrix")
    G[k], G[pivot] = G[pivot], G[k]
    scale = G[k][k]
    G[k] = [v/scale for v in G[k]]
    for i in range(p):
        if i != k:
            factor = G[i][k]
            G[i] = [v-factor*w for v,w in zip(G[i],G[k])]
inverse = [row[p:] for row in G]
rhs = [sum(row[j]*v for row,v in zip(X,y)) for j in range(p)]
beta = [sum(v*w for v,w in zip(row,rhs)) for row in inverse]
resid = [v-sum(a*b for a,b in zip(row,beta)) for row,v in zip(X,y)]
sse = sum(v*v for v in resid)
sst = sum((v-sum(y)/n)**2 for v in y)
sigma2 = sse/(n-p)
if sst == 0: raise ValueError("Constant outcome has undefined R-squared")
with (out/"coefficients.csv").open("w",encoding="utf-8",newline="") as f:
    writer=csv.writer(f); writer.writerow(["term","estimate","std_error"])
    writer.writerows((term,b,math.sqrt(max(0,sigma2*inverse[i][i]))) for i,(term,b) in enumerate(zip(["Intercept",*cfg["predictors"]],beta)))
metrics={"backend":"python standard library", "n_rows":len(raw),"n_complete":n,"n_excluded":len(raw)-n,"n_predictors":p-1,"r_squared":1-sse/sst,"rmse":math.sqrt(sigma2),"missing_policy":"complete_case", "inference_note":"Ordinary OLS standard errors assume independent errors. Repeated measures require the mixed-model scenario."}
(out/"metrics.json").write_text(json.dumps(metrics,indent=2,allow_nan=False),encoding="utf-8")
print("RB_STATISTICS_COMPLETE",flush=True)
'''


def _r_analysis(cfg: dict, jamovi: bool) -> str:
    dep = _native_string(cfg["outcome"])
    covs = "c(" + ",".join(_native_string(x) for x in cfg["predictors"]) + ")"
    data, output = _native_string(cfg["data"]), _native_string(cfg["output"])
    fit = f'''result <- do.call(jmv::linReg,list(data=clean,dep={dep},covs=covs,blocks=list(as.list(covs)),ci=TRUE))
tab <- result$models[[1]]$coef$asDF
coeff <- data.frame(term=as.character(tab$term),estimate=tab$est,std_error=tab$se)
print(result)
backend <- "jmv R package"''' if jamovi else '''tab <- coef(summary(fit))
coeff <- data.frame(term=rownames(tab),estimate=tab[,1],std_error=tab[,2])
coeff$term[coeff$term=="(Intercept)"] <- "Intercept"
backend <- "R stats::lm"'''
    return f'''data_path <- Sys.getenv("RB_INPUT_DATA", {data})
output <- Sys.getenv("RB_OUTPUT_DIR", {output})
dir.create(output,recursive=TRUE,showWarnings=FALSE)
raw <- read.csv(data_path,check.names=FALSE,na.strings=c("","NA","NaN"))
dep <- {dep}; covs <- {covs}; columns <- c(dep,covs)
stopifnot(all(columns %in% names(raw)))
for (name in columns) raw[[name]] <- suppressWarnings(as.numeric(raw[[name]]))
keep <- complete.cases(raw[,columns,drop=FALSE]) & apply(raw[,columns,drop=FALSE],1,function(x) all(is.finite(x)))
clean <- raw[keep,,drop=FALSE]
if(nrow(clean)<=length(columns)) stop("Insufficient complete rows")
fit <- lm(reformulate(covs,dep),data=clean)
if(fit$rank!=length(columns)) stop("Singular design matrix")
if(sum((clean[[dep]]-mean(clean[[dep]]))^2)==0) stop("Constant outcome")
{fit}
write.csv(coeff,file.path(output,"coefficients.csv"),row.names=FALSE)
metrics <- sprintf('{{"backend":"%s","n_rows":%d,"n_complete":%d,"n_excluded":%d,"n_predictors":%d,"r_squared":%.16g,"rmse":%.16g,"missing_policy":"complete_case"}}',backend,nrow(raw),nrow(clean),sum(!keep),length(covs),summary(fit)$r.squared,summary(fit)$sigma)
writeLines(metrics,file.path(output,"metrics.json"))
cat("RB_STATISTICS_COMPLETE\\n")
'''


def normalize_spss_xml(xml_path, output, predictors, audit):
    """Read full-precision numeric OXML attributes, never rounded display text."""
    import csv
    import json
    import math
    import xml.etree.ElementTree as ET
    from pathlib import Path
    output=Path(output)
    namespace="{http://www.ibm.com/software/analytics/spss/xml/oms}"
    tree=ET.parse(xml_path)
    tables={p.get("subType"):p for p in tree.findall(".//"+namespace+"pivotTable")}
    coefficient_table=tables["Coefficients"]
    rows=coefficient_table.findall("./"+namespace+"dimension/"+namespace+"category/"+namespace+"dimension/"+namespace+"category")
    coefficients=[]
    for row in rows:
        term=row.get("varName") or "Intercept"
        cells=row.findall(".//"+namespace+"cell")
        estimate,std_error=(float(cells[i].get("number")) for i in (0,1))
        if not math.isfinite(estimate) or not math.isfinite(std_error): raise ValueError("Nonfinite SPSS coefficient")
        coefficients.append((term,estimate,std_error))
    if {r[0] for r in coefficients}!={"Intercept",*predictors} or len(coefficients)!=len(predictors)+1:
        raise ValueError("SPSS coefficient terms do not match the requested model")
    model=tables["Model Summary"]
    cells=model.findall(".//"+namespace+"cell")
    r_squared,rmse=float(cells[1].get("number")),float(cells[3].get("number"))
    if not math.isfinite(r_squared) or not math.isfinite(rmse): raise ValueError("Invalid SPSS fit metrics")
    descriptive=tables["Descriptive Statistics"]
    descriptive_rows=[]
    for row in descriptive.findall("./"+namespace+"dimension/"+namespace+"category"):
        if not row.get("varName"): continue
        numbers=[float(cell.get("number")) for cell in row.findall(".//"+namespace+"cell")]
        if len(numbers)!=5 or numbers[0]!=audit["n_complete"]: raise ValueError("SPSS descriptive count differs from data audit")
        descriptive_rows.append((row.get("varName"),*numbers))
    if len(descriptive_rows)!=len(predictors)+1: raise ValueError("Missing SPSS descriptive rows")
    with (output/"coefficients.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f); writer.writerow(["term","estimate","std_error"]); writer.writerows(coefficients)
    with (output/"descriptives.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f); writer.writerow(["variable","n","minimum","maximum","mean","std_deviation"]); writer.writerows(descriptive_rows)
    metrics={**audit,"backend":"IBM SPSS Statistics OMS OXML","n_predictors":len(predictors),"r_squared":r_squared,"rmse":rmse}
    (output/"metrics.json").write_text(json.dumps(metrics,indent=2,allow_nan=False),encoding="utf-8")
    return metrics


SPSS_WORKER = r'''import csv, json, math, os, sys, traceback
from pathlib import Path
__XML_NORMALIZER__
cfg=__CONFIG__
output=Path(os.environ.get("RB_OUTPUT_DIR",cfg["output"]))
output.mkdir(parents=True,exist_ok=True)
def quote(value): return "'"+str(value).replace("\\","/").replace("'","''")+"'"
started=False
stage="import_engine"
lock_handle=None
lock_owned=False
kernel=None
try:
    if os.name=="nt":
        # A local, current-user and installation-specific named mutex prevents
        # two plugin jobs starting the same SPSS backend concurrently. It does
        # not select, block, or kill a user's independent GUI session.
        import ctypes, getpass, hashlib
        from ctypes import wintypes
        installation=str(Path(sys.executable).resolve().parent.parent).lower()
        identity=getpass.getuser()+"|"+str(Path.home()).lower()+"|"+installation
        mutex_name="Local\\DSHResearchSPSS_"+hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]; kernel.CreateMutexW.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]; kernel.WaitForSingleObject.restype=wintypes.DWORD
        kernel.ReleaseMutex.argtypes=[wintypes.HANDLE]; kernel.ReleaseMutex.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]; kernel.CloseHandle.restype=wintypes.BOOL
        stage="acquire_installation_lock"
        lock_handle=kernel.CreateMutexW(None,False,mutex_name)
        if not lock_handle: raise ctypes.WinError(ctypes.get_last_error())
        waited=kernel.WaitForSingleObject(lock_handle,int(cfg.get("lock_wait_s",10)*1000))
        if waited==0x00000102:
            (output/"spss_busy.json").write_text(json.dumps({"status":"blocked","reason":"Another plugin job is using this SPSS installation","lock_wait_s":cfg.get("lock_wait_s",10)}),encoding="utf-8")
            print("RB_BLOCKED: SPSS installation busy; another plugin job holds its current-user lock",flush=True)
            sys.exit(2)
        if waited not in (0,0x00000080): raise ctypes.WinError(ctypes.get_last_error())
        lock_owned=True
    stage="start_engine"
    print("RB_SPSS_STARTING_ENGINE",flush=True)
    import spss
    spss.StartSPSS()
    started=True
    spss.SetOutput("ON")
    if cfg["operation"] == "probe":
        spss.Submit("NEW FILE.\nDATA LIST FREE /rb_probe (F8.0).\nBEGIN DATA\n7\n11\nEND DATA.\nEXECUTE.")
        level=spss.GetLastErrorLevel()
        if level>=3: raise RuntimeError(spss.GetLastErrorMessage())
        count=spss.GetCaseCount()
        if count!=2 or spss.GetVariableCount()!=1: raise RuntimeError("SPSS sentinel dataset failed")
        evidence={"status":"engine_verified","case_count":count,"plugin_version":str(spss.GetDefaultPlugInVersion()),"error_level":level}
        (output/"spss_probe.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    else:
        if cfg["operation"]=="analysis":
            with open(os.environ.get("RB_INPUT_DATA",cfg["data"]),encoding="utf-8-sig",newline="") as f:
                reader=csv.DictReader(f); required=[cfg["outcome"],*cfg["predictors"]]
                if not all(k in (reader.fieldnames or []) for k in required): raise ValueError("Missing columns")
                raw=list(reader)
            rows=[]
            for row in raw:
                try: values=[float(row[k]) for k in required]
                except (ValueError,TypeError): continue
                if all(math.isfinite(x) for x in values): rows.append(values)
            if len(rows)<=len(required): raise ValueError("Insufficient complete rows")
            # SPSS requires one format per variable. A single trailing F format
            # for a list of 8 variables causes errLevel 3, even though the
            # single-variable sentinel succeeds.
            data="DATA LIST FREE /"+" ".join(name+" (F40.15)" for name in required)+".\nBEGIN DATA\n"+"\n".join(" ".join(format(x,".17g") for x in row) for row in rows)+"\nEND DATA.\nEXECUTE.\n"
            native=Path(cfg["source"]).read_text(encoding="utf-8-sig")
            (output/"data_import.sps").write_text(data,encoding="utf-8")
            stage="import_complete_cases"
            spss.Submit(data)
            if spss.GetCaseCount()!=len(rows) or spss.GetVariableCount()!=len(required): raise RuntimeError("SPSS imported dataset dimensions differ from audit")
            syntax=native
            audit={"n_rows":len(raw),"n_complete":len(rows),"n_excluded":len(raw)-len(rows),"missing_policy":"complete_case"}
            (output/"data_audit.json").write_text(json.dumps(audit),encoding="utf-8")
        else: syntax=Path(cfg["source"]).read_text(encoding="utf-8-sig")
        stage="execute_analysis" if cfg["operation"]=="analysis" else "execute_script"
        spss.Submit(syntax)
        level=spss.GetLastErrorLevel()
        if level>=3: raise RuntimeError("SPSS error %s: %s"%(level,spss.GetLastErrorMessage()))
        if cfg["operation"]=="analysis":
            stage="validate_native_oms_output"
            normalize_spss_xml(output/"results.xml",output,cfg["predictors"],audit)
        (output/"spss_execution.json").write_text(json.dumps({"status":"syntax_completed","error_level":level,"plugin_version":str(spss.GetDefaultPlugInVersion())}),encoding="utf-8")
    print("RB_SPSS_VERIFIED_COMPLETE",flush=True)
except Exception as exc:
    engine_message=""
    try: engine_message=spss.GetLastErrorMessage()
    except Exception: pass
    traceback.print_exc()
    (output/"spss_error.json").write_text(json.dumps({"status":"failed","stage":stage,"type":type(exc).__name__,"message":str(exc),"engine_message":engine_message},indent=2),encoding="utf-8")
    sys.exit(2)
finally:
    if started:
        try: spss.StopSPSS()
        except Exception: traceback.print_exc()
    if lock_handle and kernel:
        if lock_owned: kernel.ReleaseMutex(lock_handle)
        kernel.CloseHandle(lock_handle)
'''


def _stata_analysis(cfg: dict) -> str:
    # Stata returns through a log, not a dependable Windows stdout pipe.
    columns = [cfg["outcome"], *cfg["predictors"]]
    return f'''clear all
set more off
cd {_native_string(cfg['output'])}
log using "analysis.log", text replace
import delimited using {_native_string(cfg['data'])}, varnames(1) case(preserve) asdouble clear
local n_rows = _N
foreach v in {' '.join(columns)} {{
    capture confirm numeric variable `v'
    if _rc destring `v', replace force
}}
egen missing_count = rowmiss({' '.join(columns)})
drop if missing_count > 0
regress {cfg['outcome']} {' '.join(cfg['predictors'])}
if e(rank) != {len(cfg['predictors'])+1} error 459
if e(df_r) <= 0 error 2001
if missing(e(r2)) error 498
file open coeff using "coefficients.csv", write replace
file write coeff "term,estimate,std_error" _n
file write coeff "Intercept," %21.16g (_b[_cons]) "," %21.16g (_se[_cons]) _n
foreach v in {' '.join(cfg['predictors'])} {{
    file write coeff "`v'," %21.16g (_b[`v']) "," %21.16g (_se[`v']) _n
}}
file close coeff
file open metrics using "metrics.json", write replace
file write metrics "{{" _n
file write metrics char(34) "n_rows" char(34) ":" %12.0f (`n_rows') "," _n
file write metrics char(34) "n_complete" char(34) ":" %12.0f (e(N)) "," _n
file write metrics char(34) "n_excluded" char(34) ":" %12.0f (`n_rows'-e(N)) "," _n
file write metrics char(34) "r_squared" char(34) ":" %21.16g (e(r2)) "," _n
file write metrics char(34) "rmse" char(34) ":" %21.16g (e(rmse)) "}}" _n
file close metrics
display "RB_STATISTICS_COMPLETE"
log close
'''


def _matrix_analysis(cfg: dict, octave: bool) -> str:
    # readtable is absent on a default Octave install; textscan handles quoted
    # headers and plain numeric CSV columns without extra packages.
    cols = [cfg["outcome"], *cfg["predictors"]]
    names = "{" + ",".join(_native_string(x, "matrix") for x in cols) + "}"
    parse = f'''fid=fopen({_native_string(cfg['data'],'matrix')},'r');
header=strsplit(strtrim(fgetl(fid)),',');
body_position=ftell(fid); body=fread(fid,Inf,'*char')';
if any(body=='"'), error('Octave simple CSV backend rejects quoted fields; use script with a CSV parser'); end
lines=regexp(strtrim(body),'\\r\\n|\\n|\\r','split');
for line_index=1:numel(lines)
    if sum(lines{{line_index}}==',')~=numel(header)-1, error('CSV row width differs from header'); end
end
fseek(fid,body_position,'bof');
cells=textscan(fid,repmat('%s',1,numel(header)),'Delimiter',',','EndOfLine','\\n'); fclose(fid);
names={names}; raw=zeros(numel(cells{{1}}),numel(names));
for j=1:numel(names)
    k=find(strcmp(strrep(header,'"',''),names{{j}}),1);
    if isempty(k), error('Missing input column'); end
    raw(:,j)=str2double(cells{{k}});
end''' if octave else f'''table_data=readtable({_native_string(cfg['data'],'matrix')},'VariableNamingRule','preserve');
names={names}; raw=zeros(height(table_data),numel(names));
for j=1:numel(names)
    values=table_data.(names{{j}});
    if isnumeric(values), raw(:,j)=values; else, raw(:,j)=str2double(string(values)); end
end'''
    return f'''% Complete-case numeric OLS; coefficients and standard errors are machine readable.
{parse}
n_rows=size(raw,1); clean=raw(all(isfinite(raw),2),:);
y=clean(:,1); X=[ones(size(clean,1),1),clean(:,2:end)]; [n,p]=size(X);
if n<=p || rank(X)<p, error('Insufficient rows or singular design'); end
b=X\\y; residual=y-X*b; sse=residual'*residual; sigma2=sse/(n-p);
covb=sigma2*((X'*X)\\eye(p)); se=sqrt(diag(covb));
output={_native_string(cfg['output'],'matrix')}; if ~exist(output,'dir'), mkdir(output); end
fid=fopen(fullfile(output,'coefficients.csv'),'w'); fprintf(fid,'term,estimate,std_error\\n');
terms=[{{'Intercept'}},names(2:end)];
for j=1:p, fprintf(fid,'%s,%.17g,%.17g\\n',terms{{j}},b(j),se(j)); end
fclose(fid); sst=sum((y-mean(y)).^2); if sst==0, error('Constant outcome'); end
fid=fopen(fullfile(output,'metrics.json'),'w');
fprintf(fid,'{{"n_rows":%d,"n_complete":%d,"n_excluded":%d,"r_squared":%.17g,"rmse":%.17g}}',n_rows,n,n_rows-n,1-sse/sst,sqrt(sigma2)); fclose(fid);
disp('RB_STATISTICS_COMPLETE');
'''


def _julia_analysis(cfg: dict) -> str:
    # Requires no third-party Julia packages. This CSV path intentionally accepts
    # the plain numeric research fixture; general quoted CSV needs CSV.jl.
    names = "[" + ",".join(_native_string(x, "julia") for x in [cfg["outcome"], *cfg["predictors"]]) + "]"
    return f'''using LinearAlgebra, Statistics
lines=readlines({_native_string(cfg['data'], 'julia')}); header=replace.(split(lines[1],','),"\\\""=>"")
names={names}; indices=[findfirst(==(name),header) for name in names]
any(isnothing,indices) && error("Missing columns")
rows=Vector{{Float64}}[]
for line in lines[2:end]
    occursin('"',line) && error("Julia simple CSV backend rejects quoted fields; use script with CSV.jl")
    values=split(line,',',keepempty=true)
    length(values)==length(header) || error("CSV row width differs from header")
    row=[something(tryparse(Float64,values[i]),NaN) for i in indices]
    all(isfinite,row) && push!(rows,row)
end
data=permutedims(hcat(rows...)); y=data[:,1]; X=hcat(ones(size(data,1)),data[:,2:end]); n,p=size(X)
(n>p && rank(X)==p) || error("Insufficient rows or singular design")
b=X\\y; sigma2=sum(abs2,y-X*b)/(n-p); se=sqrt.(diag(sigma2*inv(X'X)))
output={_native_string(cfg['output'], 'julia')}; mkpath(output)
open(joinpath(output,"coefficients.csv"),"w") do f
    println(f,"term,estimate,std_error")
    for (i,name) in enumerate(vcat(["Intercept"],names[2:end])); println(f,name,",",b[i],",",se[i]); end
end
sst=sum(abs2,y.-mean(y)); sst>0 || error("Constant outcome")
r2=1-sum(abs2,y-X*b)/sst
open(joinpath(output,"metrics.json"),"w") do f
    print(f,"{{\\\"n_rows\\\":",length(lines)-1,",\\\"n_complete\\\":",n,",\\\"n_excluded\\\":",length(lines)-1-n,",\\\"r_squared\\\":",r2,",\\\"rmse\\\":",sqrt(sigma2),"}}")
end
println("RB_STATISTICS_COMPLETE")
'''


def _sas_analysis(cfg: dict) -> str:
    names = " ".join([cfg["outcome"], *cfg["predictors"]])
    return f'''/* Requires SAS/STAT. Only validated numeric columns are supported. */
options errorabend;
%macro rb_analysis;
proc import datafile={_native_string(cfg['data'],'sas')} out=work.raw dbms=csv replace; guessingrows=max; getnames=yes; run;
%if &syscc > 4 %then %abort cancel;
data work.clean; set work.raw; if nmiss(of {names})=0; run;
%if &syscc > 4 %then %abort cancel;
proc sql noprint;
 select count(*) into :rb_total trimmed from work.raw;
 select count(*),mean({cfg['outcome']}) into :rb_n trimmed,:rb_mean trimmed from work.clean;
quit;
%if &rb_n <= {len(cfg['predictors'])+1} %then %abort cancel;
ods exclude all;
ods output ParameterEstimates=work.rb_parameters;
proc reg data=work.clean;
 model {cfg['outcome']}={' '.join(cfg['predictors'])} / clb;
 output out=work.rb_fitted p=rb_prediction r=rb_residual;
run; quit;
ods exclude none;
%if &syscc > 4 %then %abort cancel;
%if not %sysfunc(exist(work.rb_parameters)) %then %abort cancel;
%local rb_bad rb_nparams;
data _null_;
 set work.rb_parameters end=last;
 retain bad 0 parameter_count 0;
 if missing(Estimate) or missing(StdErr) then bad+1;
 parameter_count+1;
 if last then do; call symputx('rb_bad',bad,'L'); call symputx('rb_nparams',parameter_count,'L'); end;
run;
%if &rb_bad > 0 or &rb_nparams ne {len(cfg['predictors'])+1} %then %abort cancel;
data work.rb_standard;
 length term $32 estimate std_error 8;
 set work.rb_parameters;
 term=strip(Variable); std_error=StdErr;
 keep term estimate std_error;
run;
proc export data=work.rb_standard outfile={_native_string(str(Path(cfg['output'])/'coefficients.csv'),'sas')} dbms=csv replace; run;
proc sql noprint;
 select sum(rb_residual*rb_residual),sum(({cfg['outcome']}-&rb_mean)*({cfg['outcome']}-&rb_mean))
 into :rb_sse trimmed,:rb_sst trimmed from work.rb_fitted;
quit;
%if %sysevalf(&rb_sst <= 0) %then %abort cancel;
data _null_;
 file {_native_string(str(Path(cfg['output'])/'metrics.json'),'sas')};
 n_rows=&rb_total; n_complete=&rb_n; n_excluded=n_rows-n_complete;
 r_squared=1-&rb_sse/&rb_sst; rmse=sqrt(&rb_sse/(&rb_n-{len(cfg['predictors'])+1}));
 put '{{"n_rows":' n_rows best32. ',"n_complete":' n_complete best32. ',"n_excluded":' n_excluded best32. ',"r_squared":' r_squared best32. ',"rmse":' rmse best32. '}}';
run;
%if &syscc > 4 %then %abort cancel;
data _null_; file {_native_string(str(Path(cfg['output'])/'sas_complete.txt'),'sas')}; put 'RB_STATISTICS_COMPLETE'; run;
%mend rb_analysis;
%rb_analysis;
'''


def compile_job(job: dict, workspace: Path, executables: dict) -> dict:
    engine = str(job.get("engine", "")).lower()
    if engine not in SUPPORTED_ENGINES:
        raise ValueError("Unsupported statistical engine: " + engine)
    operation = job.get("operation", "script")
    if operation not in {"script", "analysis", "probe"} or (operation == "probe" and engine != "spss"):
        raise ValueError("Unsupported operation for " + engine + ": " + str(operation))
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    parameters, inputs = job.get("parameters", {}), job.get("inputs", {})
    timeout = float(job.get("timeout_s", 120))
    if not 0 < timeout <= 3600:
        raise ValueError("timeout_s must be greater than zero and at most 3600")
    data = str(Path(inputs["data"]).resolve()) if inputs.get("data") else ""
    cfg = {"data": data, "output": str(workspace), "operation": operation}
    if engine=="spss":
        lock_wait=parameters.get("lock_wait_s",10)
        if isinstance(lock_wait,bool) or not isinstance(lock_wait,(int,float)) or not 0<=lock_wait<=30:
            raise ValueError("lock_wait_s must be a number between 0 and 30 seconds")
        cfg["lock_wait_s"]=lock_wait
    source = workspace / ("analysis" + _EXT[engine])
    artifacts, markers = [], ["RB_STATISTICS_COMPLETE"]
    if operation == "script":
        original = Path(inputs.get("script", ""))
        if not original.is_absolute() or not original.is_file():
            raise ValueError("inputs.script must be an existing absolute path")
        # Copy bytes to preserve the exact supplied script, including encodings.
        source.write_bytes(original.read_bytes())
        markers = list(parameters.get("required_markers", []))
        for name in parameters.get("expected_artifacts", []):
            path = (workspace / str(name)).resolve()
            if not path.is_relative_to(workspace):
                raise ValueError("Expected artifacts must remain within the job workspace")
            artifacts.append(str(path))
    elif operation == "analysis":
        if not data or not Path(data).is_file():
            raise ValueError("inputs.data must be an existing CSV file")
        outcome, predictors = _model(parameters)
        cfg.update(outcome=outcome, predictors=predictors)
        if engine == "python": text = PYTHON_ANALYSIS.replace("__CONFIG__", repr(cfg))
        elif engine in {"r", "jamovi"}: text = _r_analysis(cfg, engine == "jamovi")
        elif engine == "stata": text = _stata_analysis(cfg)
        elif engine in {"matlab", "octave"}: text = _matrix_analysis(cfg, engine == "octave")
        elif engine == "julia": text = _julia_analysis(cfg)
        elif engine == "sas": text = _sas_analysis(cfg)
        else:
            text = "OMS /SELECT TABLES /DESTINATION FORMAT=OXML OUTFILE=" + _native_string(str(workspace / "results.xml"), "spss") + ".\n"
            text += "DESCRIPTIVES VARIABLES=" + " ".join([outcome, *predictors]) + ".\n"
            text += "REGRESSION /MISSING LISTWISE /STATISTICS COEFF R ANOVA CI(95) /DEPENDENT " + outcome + " /METHOD=ENTER " + " ".join(predictors) + ".\nOMSEND.\n"
        source.write_text(text, encoding="utf-8")
        artifacts = [str(workspace / name) for name in ("coefficients.csv", "metrics.json")]
        if engine == "spss": artifacts = [str(workspace / name) for name in ("results.xml", "data_audit.json", "spss_execution.json", "coefficients.csv", "metrics.json", "descriptives.csv")]
        if engine == "sas": artifacts = [str(workspace / name) for name in ("coefficients.csv", "metrics.json", "sas_complete.txt")]
    else:
        source = workspace / "spss_probe.py"
        artifacts = [str(workspace / "spss_probe.json")]
    executable = executables.get(engine)
    command, env = [], {"RB_INPUT_DATA": data, "RB_OUTPUT_DIR": str(workspace)}
    if engine == "spss":
        cfg["source"] = str(source)
        worker = workspace / "spss_worker.py"
        worker.write_text(SPSS_WORKER.replace("__CONFIG__", repr(cfg)).replace("__XML_NORMALIZER__",inspect.getsource(normalize_spss_xml)), encoding="utf-8")
        if operation == "probe": source = worker
        markers = ["RB_SPSS_VERIFIED_COMPLETE"]
        if operation == "script": artifacts.append(str(workspace / "spss_execution.json"))
        if executable: command = [str(executable), "-u", str(worker)]
    elif executable:
        if engine in {"r", "jamovi"}: command = [str(executable), "--vanilla", str(source)]
        elif engine == "python": command = [str(executable), "-u", str(source)]
        elif engine == "stata": command = [str(executable), "/e", "do", str(source)]
        elif engine == "matlab": command = [str(executable), "-batch", "run(" + _native_string(str(source), "matrix") + ")"]
        elif engine == "octave": command = [str(executable), "--no-gui", "--quiet", "--no-history", "--no-init-file", str(source)]
        elif engine == "julia": command = [str(executable), "--startup-file=no", str(source)]
        elif engine == "sas": command = [str(executable), "-sysin", str(source), "-log", str(workspace / "analysis.log"), "-print", str(workspace / "analysis.lst")]
    if engine in {"stata", "sas"}: markers = []
    if engine == "julia":
        env.update(JULIA_DEPOT_PATH=str(workspace / "julia_depot"), JULIA_HISTORY=str(workspace / "julia_history"))
    ready = bool(executable and Path(executable).is_file())
    if not ready: command = []
    result = {"status": "compiled", "engine": engine, "operation": operation, "source_path": str(source), "command": command, "cwd": str(workspace), "timeout_s": timeout, "env": env, "expected_artifacts": artifacts, "required_markers": markers, "ready": ready}
    if not ready: result["reason"] = "Runtime not installed or configured; native source compiled but execution is blocked"
    if engine in {"stata", "matlab", "octave", "julia", "sas"}: result["validation_scope"] = "Native template; runtime acceptance required on an installed, licensed engine"
    if engine == "jamovi": result["validation_scope"] = "jmv R-package analysis backend; does not control a jamovi GUI session"
    return result
