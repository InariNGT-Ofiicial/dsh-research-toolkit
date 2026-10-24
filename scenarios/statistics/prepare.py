"""Create a reproducible, synthetic longitudinal intervention study and jobs.

No participant data are used. The QR oracle uses only Python's standard library
and is independent of the generated OLS implementation and of R/jmv.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import random
from pathlib import Path

PREDICTORS = ["time", "treat_a", "treat_b", "time_a", "time_b", "baseline_c", "age_c"]


def qr_ols(rows: list[list[float]]) -> dict:
    y = [row[0] for row in rows]
    x = [[1.0, *row[1:]] for row in rows]
    n, p = len(rows), len(rows[0])
    q, upper = [], [[0.0] * p for _ in range(p)]
    for j in range(p):
        v = [row[j] for row in x]
        for k in range(j):
            upper[k][j] = sum(a*b for a,b in zip(q[k],v))
            v = [a-upper[k][j]*b for a,b in zip(v,q[k])]
        upper[j][j] = math.sqrt(sum(a*a for a in v))
        if upper[j][j] < 1e-12: raise ValueError("Singular oracle design")
        q.append([a/upper[j][j] for a in v])
    z = [sum(a*b for a,b in zip(col,y)) for col in q]
    beta = [0.0]*p
    for j in range(p-1,-1,-1):
        beta[j] = (z[j]-sum(upper[j][k]*beta[k] for k in range(j+1,p)))/upper[j][j]
    sse = sum((v-sum(a*b for a,b in zip(row,beta)))**2 for row,v in zip(x,y))
    sst = sum((v-sum(y)/n)**2 for v in y)
    invr = [[0.0]*p for _ in range(p)]
    for k in range(p):
        for j in range(p-1,-1,-1):
            invr[j][k] = ((1.0 if j==k else 0)-sum(upper[j][m]*invr[m][k] for m in range(j+1,p)))/upper[j][j]
    se = [math.sqrt(sse/(n-p)*sum(v*v for v in row)) for row in invr]
    return {"n_complete":n,"coefficients":dict(zip(["Intercept",*PREDICTORS],beta)),"standard_errors":dict(zip(["Intercept",*PREDICTORS],se)),"r_squared":1-sse/sst,"rmse":math.sqrt(sse/(n-p))}


def prepare_scenario(workspace: Path) -> dict:
    workspace=Path(workspace).resolve(); workspace.mkdir(parents=True,exist_ok=True)
    rng=random.Random(20261024)
    rows=[]
    for subject in range(1,145):
        group=(subject-1)%3
        a,b=int(group==1),int(group==2)
        age=round(rng.uniform(-14,14),6)
        baseline=round(rng.gauss(0,7),6)
        random_intercept=rng.gauss(0,4)
        for time in range(4):
            score=50-0.5*time+1.0*a-0.5*b+2.3*time*a+3.6*time*b+0.6*baseline+0.12*age+random_intercept+rng.gauss(0,2.0)
            # Prespecified follow-up loss depends on observed covariates and
            # visit number. Complete cases are audited; no imputation is claimed.
            missing=time>0 and rng.random() < (0.04+0.03*time+0.02*(baseline<0))
            rows.append({"subject":subject,"group":["control","active_a","active_b"][group],"time":time,"treat_a":a,"treat_b":b,"time_a":time*a,"time_b":time*b,"baseline_c":baseline,"age_c":age,"score":"" if missing else round(score,8)})
    data=workspace/"longitudinal.csv"
    with data.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    complete=[[float(row[name]) for name in ["score",*PREDICTORS]] for row in rows if row["score"]!=""]
    oracle=qr_ols(complete)
    oracle.update(n_rows=len(rows),n_excluded=len(rows)-len(complete),seed=20261024,study="Synthetic three-arm longitudinal study: 144 subjects x 4 visits",missing_policy="complete_case",tolerance={"coefficient_abs":1e-7,"standard_error_abs":1e-7,"metric_abs":1e-9})
    (workspace/"oracle.json").write_text(json.dumps(oracle,indent=2),encoding="utf-8")
    jobs=[]
    for engine in ["python","r","jamovi","spss","stata","matlab","octave","julia","sas"]:
        jobs.append({"schema_version":"research.job.v1","id":"longitudinal_ols_"+engine,"engine":engine,"operation":"analysis","inputs":{"data":str(data)},"parameters":{"method":"linear_regression","outcome":"score","predictors":PREDICTORS},"timeout_s":180})
    complex_script=Path(__file__).with_name("longitudinal_mixed.R").resolve()
    jobs.append({"schema_version":"research.job.v1","id":"longitudinal_mixed_r","engine":"r","operation":"script","inputs":{"script":str(complex_script),"data":str(data)},"parameters":{"required_markers":["RB_LONGITUDINAL_COMPLETE"],"expected_artifacts":["mixed_coefficients.csv","mixed_variances.json","contrasts_holm.csv","bootstrap.json","diagnostics.csv","mixed_report.txt"]},"timeout_s":180})
    (workspace/"jobs.json").write_text(json.dumps(jobs,indent=2),encoding="utf-8")
    return {"data":str(data),"oracle":str(workspace/"oracle.json"),"jobs":str(workspace/"jobs.json"),"n_rows":len(rows),"n_complete":len(complete),"n_missing":len(rows)-len(complete)}


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("workspace",type=Path)
    print(json.dumps(prepare_scenario(parser.parse_args().workspace),indent=2))
