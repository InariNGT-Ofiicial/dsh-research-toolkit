"""Independent acceptance checks for numeric OLS and random-intercept GLS."""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

PREDICTORS=["time","treat_a","treat_b","time_a","time_b","baseline_c","age_c"]


def coefficients(path: Path) -> dict:
    with path.open(encoding="utf-8-sig",newline="") as f:
        return {row["term"].replace("(Intercept)","Intercept"):row for row in csv.DictReader(f)}


def check_ols(directory: Path, oracle: dict) -> dict:
    table=coefficients(directory/"coefficients.csv")
    metrics=json.loads((directory/"metrics.json").read_text(encoding="utf-8-sig"))
    errors=[]
    for term,estimate in oracle["coefficients"].items():
        if term not in table: raise AssertionError("Missing coefficient "+term)
        errors.append(abs(float(table[term]["estimate"])-estimate))
        assert errors[-1]<1e-7,(directory,term,errors[-1])
        assert abs(float(table[term]["std_error"])-oracle["standard_errors"][term])<1e-7
    for name in ["n_rows","n_complete","n_excluded"]: assert metrics[name]==oracle[name],(directory,name)
    for name in ["r_squared","rmse"]: assert abs(metrics[name]-oracle[name])<1e-9,(directory,name)
    return {"status":"passed","max_coefficient_abs_error":max(errors),"n_complete":metrics["n_complete"]}


def solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    m=[list(row)+[value] for row,value in zip(matrix,rhs)]
    n=len(rhs)
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(m[i][k])); m[k],m[pivot]=m[pivot],m[k]
        if abs(m[k][k])<1e-12: raise ValueError("Singular GLS information")
        for i in range(k+1,n):
            factor=m[i][k]/m[k][k]
            for j in range(k,n+1): m[i][j]-=factor*m[k][j]
    beta=[0.0]*n
    for i in range(n-1,-1,-1): beta[i]=(m[i][n]-sum(m[i][j]*beta[j] for j in range(i+1,n)))/m[i][i]
    return beta


def check_mixed(directory: Path, data: Path) -> dict:
    variances=json.loads((directory/"mixed_variances.json").read_text())
    tau2,sigma2=variances["random_intercept_variance"],variances["residual_variance"]
    groups=defaultdict(list)
    with data.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            if row["score"]: groups[row["subject"]].append((float(row["score"]),[1.0,*[float(row[name]) for name in PREDICTORS]]))
    p=8; information=[[0.0]*p for _ in range(p)]; rhs=[0.0]*p
    # Sherman-Morrison inverse of each independent subject block:
    # (sigma2 I + tau2 11')^-1 = I/sigma2 - c 11'.
    for rows in groups.values():
        m=len(rows); c=tau2/(sigma2*(sigma2+m*tau2))
        sx=[sum(x[j] for _,x in rows) for j in range(p)]; sy=sum(y for y,_ in rows)
        for j in range(p):
            rhs[j]+=sum(x[j]*y for y,x in rows)/sigma2-c*sx[j]*sy
            for k in range(p): information[j][k]+=sum(x[j]*x[k] for _,x in rows)/sigma2-c*sx[j]*sx[k]
    independent=solve(information,rhs)
    actual=coefficients(directory/"mixed_coefficients.csv")
    differences=[abs(float(actual[term]["estimate"])-value) for term,value in zip(["Intercept",*PREDICTORS],independent)]
    assert max(differences)<1e-7,differences
    assert 5<tau2<40 and 1<sigma2<9,variances
    assert float(actual["time_a"]["estimate"])>1 and float(actual["time_b"]["estimate"])>2
    with (directory/"contrasts_holm.csv").open(encoding="utf-8-sig",newline="") as f: comparisons=list(csv.DictReader(f))
    assert len(comparisons)==12
    ordered=sorted(range(12),key=lambda i:float(comparisons[i]["p_raw"]))
    previous=0.0; errors=[]
    for rank,index in enumerate(ordered):
        previous=min(1,max(previous,(12-rank)*float(comparisons[index]["p_raw"])))
        errors.append(abs(previous-float(comparisons[index]["p.value"])))
    assert max(errors)<1e-10
    bootstrap=json.loads((directory/"bootstrap.json").read_text())
    assert bootstrap["repeat_identical"] and bootstrap["replicates"]==200
    assert math.isfinite(bootstrap["mean"]) and bootstrap["ci_lower"]<bootstrap["ci_upper"]
    return {"status":"passed","gls_max_coefficient_abs_error":max(differences),"holm_max_abs_error":max(errors),"comparisons":12,"bootstrap_replicates":200,"variance_components":variances}


def validate(workspace: Path) -> dict:
    workspace=Path(workspace).resolve()
    oracle=json.loads((workspace/"oracle.json").read_text())
    report={"scenario":"synthetic_longitudinal_intervention","oracle":"independent Python QR OLS; block GLS at fitted variance components","engines":{}}
    for engine in ["python","r","jamovi","octave","matlab","julia","stata","spss"]:
        directory=workspace/("longitudinal_ols_"+engine)
        if engine=="spss" and not (directory/"coefficients.csv").is_file():
            candidates=[p for p in workspace.glob("longitudinal_ols_spss-*") if (p/"coefficients.csv").is_file() and (p/"result.json").is_file() and json.loads((p/"result.json").read_text()).get("status")=="passed"]
            if candidates: directory=max(candidates,key=lambda p:(p/"result.json").stat().st_mtime_ns)
        if directory.exists() and (directory/"coefficients.csv").is_file(): report["engines"][engine]=check_ols(directory,oracle)
    mixed=workspace/"longitudinal_mixed_r"
    if mixed.exists() and (mixed/"mixed_coefficients.csv").is_file(): report["mixed_r"]=check_mixed(mixed,workspace/"longitudinal.csv")
    report["status"]="passed" if report["engines"] else "no_results"
    (workspace/"acceptance.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("workspace",type=Path)
    print(json.dumps(validate(parser.parse_args().workspace),indent=2))
