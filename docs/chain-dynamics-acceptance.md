# MATLAB chain dynamics: bridge acceptance design

## Scope

`matlab/chain_dynamics` is a new native operation in 0.3.0. It compiles parameter
data into a complete base-MATLAB program for a fixed-fixed mass-spring-damper
chain and never accepts free-form MATLAB source. The existing `script` and
`analysis` compilers are unchanged and do not count as evidence for this
operation.

Official interface basis (retrieved 2026-10-24, R2026a reference pages):

| Topic | Official page | Used contract |
|---|---|---|
| batch startup | `matlab (Windows)` | `-batch statement`, non-interactive, exit 0 on success/nonzero otherwise; `-sd` initial folder |
| generalized eigenproblem | `eig` | `[V,D]=eig(A,B)` solves `A*V=B*V*D`; symmetric A + SPD B uses Cholesky and B-normalizes columns |
| ODE integration | `ode45` | `[t,y]=ode45(odefun,tspan,y0,options)`; `tspan` with >2 elements requests those outputs |
| solver options | `odeset` | `RelTol`, `AbsTol`, `MaxStep` |
| MAT output | `save` | `save(filename,variables,'-v7')` |
| identity | `version`, `matlabroot` | `version('-release')`, full MATLAB root |

Raw pages, plain-text projections, fetch script and SHA-256 values are stored
under `candidate/matlab-chain-dynamics/sources/`.

## Generated program

1. Build `M`, tridiagonal fixed-fixed `K`, Rayleigh `C`.
2. `[V,D]=eig(K,M)`; sort; compute `V'MV`, `K V - M V Lambda`, and the uniform
   closed-form frequency error. Uniform chains must match the analytic formula.
3. Build the first-order state matrix and call `eig` for damped eigenvalues,
   damped frequencies and damping ratios.
4. Integrate multi-frequency nodal forcing with `ode45` at the requested grid
   (`>=1001` samples), `RelTol/AbsTol/MaxStep` from the job.
5. Energy: kinetic, potential, work `cumtrapz(t,f'v)`, damping dissipation
   `cumtrapz(t,v'Cv)`, balance `E-E0-W+D`.
6. Dynamic residual with second-order central and one-sided difference
   stencils; internal thresholds are fixed in the generated program.
7. Write `identity.json`, `modal.csv`, `damped_modes.csv`,
   `time_history.csv`, `energy.csv`, `results.json`, `chain_results.mat`
   (v7), and `chain_summary.png` only when `plot:true`.
8. Print `RB_MATLAB_IDENTITY` and, only after all checks pass,
   `RB_CHAIN_DYNAMICS_COMPLETE`.

## Independent acceptance

`scenarios/chain_dynamics/oracle.py` freezes analytic/SciPy expectations and
tolerances before any MATLAB execution. `compare.py` rejects NaN/Inf, truncated
or wrongly shaped files, stale hashes and non-native MAT files. Tolerances are
declared per metric in `expectations.json`; no tolerance is relaxed after seeing
MATLAB output.

## Negative controls

Compile-time rejections: zero mass, negative stiffness, dimension mismatch,
non-finite mass, zero Rayleigh damping, and injected free-form `script`.
Runtime controls: missing runtime, native `error`, missing artifact, one-second
timeout. Recovery runs a fresh legal job through the oracle.

## Evidence status (native, 2026-10-24)

- MATLAB identity from a bounded `-batch` probe:
  `release=2026a`, `version=26.1.0.3203278 (R2026a)`, `matlabroot=E:\MATLAB`,
  `batchStartupOptionUsed=true`; executable SHA-256
  `FBB176E41B5FF95FB84AAEA3580C44B26EC1223CEA800C69171F76A626152D88`.
  No license file, token or account data was read.
- Three jobs x two fresh runs: all six MATLAB processes exited 0; every run
  passed the frozen SciPy comparison. Repetition maxima were exactly `0.0` and
  each job JSON hash was unchanged before/after.
- Negative controls: six compile rejections, simulated missing runtime
  (`strict_executables`, no fallback to the real installation), native `error`
  (exit 1), missing artifact and one-second timeout all matched expectations;
  recovery passed the oracle. Expectations hash was unchanged before/after.
- Native DSH host tests (0.3.0 source): 14/14 host pipeline + 3/3 official
  skill-tool checks. An independent normal-host review ran 58/58 Python tests.
- Full package build and extracted-copy host test: passed (release-final).
- Actual-model acceptance of the installed 0.3.0 bundle is still a later phase;
  host tests, direct CLI execution and the outer python runner do not establish
  it, and the package has not been installed by this stage.

## Lessons recorded by this run

- MATLAB `version('-release')` returns `2026a` without the `R` prefix; `R2026a`
  appears inside the full `version` string. Comparisons must not require
  `R2026a` from `-release`.
- MAT-file version 7 keeps the `MATLAB 5.0 MAT-file` header. Signature checks
  must accept that header and then verify the variables with `loadmat`.
- An expected-blocked control that actually ran and matched its expectation is a
  success. Only required native controls that were never executed make the
  suite `blocked`.
- Packaged runners must not derive the study root from their installation path:
  outputs default to the current working directory and expectations are passed
  explicitly.
