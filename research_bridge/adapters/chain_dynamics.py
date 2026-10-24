"""Compile the fixed-fixed mass-spring-damper chain study as native base MATLAB.

This adapter is an explicit, narrow interface: it accepts parameter data only,
never free-form MATLAB code, and generates a complete program that uses base
MATLAB functions (eig, ode45, odeset, save, jsonencode). Compilation is not
execution; when MATLAB is absent the plan stays ready:false with a concrete
reason.
"""
from __future__ import annotations

import math
from pathlib import Path

ENGINE = "matlab"
OPERATION = "chain_dynamics"
SUPPORTED_ENGINES = {ENGINE}
CASES = {"uniform", "graded", "high_stiffness"}
ALLOWED_PARAMETERS = {
    "case",
    "n",
    "mass",
    "stiffness",
    "damping",
    "forcing",
    "t_end",
    "n_samples",
    "solver",
    "plot",
}
MAX_N = 256
MAX_COMPONENTS = 8
PLUGIN_VERSION = "0.3.0"


def _number(value, name, *, low=None, high=None, strict=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if low is not None:
        if strict and not number > low:
            raise ValueError(f"{name} must be greater than {low}")
        if not strict and number < low:
            raise ValueError(f"{name} must be at least {low}")
    if high is not None and number > high:
        raise ValueError(f"{name} must be at most {high}")
    return number


def _integer(value, name, *, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _positive_vector(spec, expected_length, name, maximum):
    if not isinstance(spec, dict):
        raise ValueError(f"{name} must be an object with kind uniform|values")
    unknown = set(spec) - {"kind", "value", "values"}
    if unknown:
        raise ValueError(f"{name} has unsupported fields: {sorted(unknown)}")
    kind = spec.get("kind")
    if kind == "uniform":
        if "values" in spec:
            raise ValueError(f"{name} kind='uniform' must not combine with values")
        value = _number(spec.get("value"), f"{name}.value", low=0, high=maximum, strict=True)
        values = [value] * expected_length
    elif kind == "values":
        if "value" in spec:
            raise ValueError(f"{name} kind='values' must not combine with value")
        raw = spec.get("values")
        if not isinstance(raw, list) or len(raw) != expected_length:
            raise ValueError(f"{name}.values must contain exactly {expected_length} numbers")
        values = [
            _number(item, f"{name}.values[{index}]", low=0, high=maximum, strict=True)
            for index, item in enumerate(raw)
        ]
    else:
        raise ValueError(f"{name}.kind must be 'uniform' or 'values'")
    return values


def _forcing(parameters, n):
    forcing = parameters.get("forcing")
    if not isinstance(forcing, dict):
        raise ValueError("parameters.forcing must be an object")
    unknown = set(forcing) - {"nodes", "amplitudes", "frequencies_hz", "phases"}
    if unknown:
        raise ValueError(f"parameters.forcing has unsupported fields: {sorted(unknown)}")
    keys = ("nodes", "amplitudes", "frequencies_hz", "phases")
    for key in keys:
        if not isinstance(forcing.get(key), list):
            raise ValueError(f"parameters.forcing.{key} must be an array")
    lengths = {len(forcing[key]) for key in keys}
    if len(lengths) != 1:
        raise ValueError("forcing nodes/amplitudes/frequencies_hz/phases must have equal length")
    count = lengths.pop()
    if not 1 <= count <= MAX_COMPONENTS:
        raise ValueError(f"forcing must contain between 1 and {MAX_COMPONENTS} components")
    nodes = []
    for index, node in enumerate(forcing["nodes"]):
        if isinstance(node, bool) or not isinstance(node, int) or not 1 <= node <= n:
            raise ValueError(f"forcing.nodes[{index}] must be an integer DOF index between 1 and {n}")
        nodes.append(node)
    if len(set(nodes)) > MAX_COMPONENTS:
        raise ValueError("too many distinct forcing nodes")
    amplitudes = [
        _number(value, f"forcing.amplitudes[{i}]", low=-1e6, high=1e6)
        for i, value in enumerate(forcing["amplitudes"])
    ]
    frequencies = [
        _number(value, f"forcing.frequencies_hz[{i}]", low=0, high=1e4, strict=True)
        for i, value in enumerate(forcing["frequencies_hz"])
    ]
    phases = [
        _number(value, f"forcing.phases[{i}]", low=-1e6, high=1e6)
        for i, value in enumerate(forcing["phases"])
    ]
    return nodes, amplitudes, frequencies, phases


def _normalize(job):
    parameters = job.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    unknown = set(parameters) - ALLOWED_PARAMETERS
    if unknown:
        raise ValueError(f"unsupported chain_dynamics parameters: {sorted(unknown)}")
    case = parameters.get("case", "uniform")
    if case not in CASES:
        raise ValueError(f"parameters.case must be one of {sorted(CASES)}")
    n = _integer(parameters.get("n"), "parameters.n", low=3, high=MAX_N)
    mass = _positive_vector(parameters.get("mass"), n, "parameters.mass", 1e9)
    stiffness = _positive_vector(parameters.get("stiffness"), n + 1, "parameters.stiffness", 1e12)
    damping = parameters.get("damping")
    if not isinstance(damping, dict):
        raise ValueError("parameters.damping must be an object with alpha and beta")
    unknown = set(damping) - {"alpha", "beta"}
    if unknown:
        raise ValueError(f"parameters.damping has unsupported fields: {sorted(unknown)}")
    alpha = _number(damping.get("alpha"), "parameters.damping.alpha", low=0, high=1e6)
    beta = _number(damping.get("beta"), "parameters.damping.beta", low=0, high=1e6)
    if alpha + beta <= 0:
        raise ValueError("Rayleigh damping requires alpha + beta > 0")
    nodes, amplitudes, frequencies, phases = _forcing(parameters, n)
    t_end = _number(parameters.get("t_end"), "parameters.t_end", low=0, high=120, strict=True)
    n_samples = _integer(parameters.get("n_samples", 2001), "parameters.n_samples", low=1001, high=20001)
    solver = parameters.get("solver", {})
    if not isinstance(solver, dict):
        raise ValueError("parameters.solver must be an object")
    unknown = set(solver) - {"rel_tol", "abs_tol", "max_step"}
    if unknown:
        raise ValueError(f"parameters.solver has unsupported fields: {sorted(unknown)}")
    rel_tol = _number(solver.get("rel_tol", 1e-9), "parameters.solver.rel_tol", low=1e-13, high=1e-3)
    abs_tol = _number(solver.get("abs_tol", 1e-11), "parameters.solver.abs_tol", low=1e-15, high=1e-3)
    max_step = _number(solver.get("max_step", min(0.002, t_end / 1000.0)), "parameters.solver.max_step", low=0, high=t_end, strict=True)
    plot = parameters.get("plot", True)
    if not isinstance(plot, bool):
        raise ValueError("parameters.plot must be a boolean")
    return {
        "case": case,
        "n": n,
        "mass": mass,
        "stiffness": stiffness,
        "alpha": alpha,
        "beta": beta,
        "nodes": nodes,
        "amplitudes": amplitudes,
        "frequencies": frequencies,
        "phases": phases,
        "t_end": t_end,
        "n_samples": n_samples,
        "rel_tol": rel_tol,
        "abs_tol": abs_tol,
        "max_step": max_step,
        "plot": plot,
    }


def _quote(value: str) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _row(values) -> str:
    return "[" + " ".join(format(float(value), ".17g") for value in values) + "]"


def _config_literal(config, output_dir) -> str:
    pairs = [
        ("output_dir", _quote(output_dir)),
        ("case_name", _quote(config["case"])),
        ("n", str(config["n"])),
        ("mass", _row(config["mass"])),
        ("stiffness", _row(config["stiffness"])),
        ("alpha", format(config["alpha"], ".17g")),
        ("beta", format(config["beta"], ".17g")),
        ("force_nodes", _row(config["nodes"])),
        ("force_amps", _row(config["amplitudes"])),
        ("force_freqs", _row(config["frequencies"])),
        ("force_phases", _row(config["phases"])),
        ("t_end", format(config["t_end"], ".17g")),
        ("n_samples", str(config["n_samples"])),
        ("rel_tol", format(config["rel_tol"], ".17g")),
        ("abs_tol", format(config["abs_tol"], ".17g")),
        ("max_step", format(config["max_step"], ".17g")),
        ("make_plot", "true" if config["plot"] else "false"),
    ]
    body = ", ...\n    ".join(f"{_quote(name)}, {value}" for name, value in pairs)
    return "struct( ...\n    " + body + ")"


MATLAB_TEMPLATE = r"""function rb_chain_dynamics()
% Generated by dsh-research-toolkit __PLUGIN_VERSION__ for engine matlab,
% operation chain_dynamics. Base MATLAB only: eig, ode45, odeset, save,
% jsonencode. The adapter supplies parameter data, never free-form code.
cfg = __CONFIG__;
out = cfg.output_dir;
if ~exist(out, 'dir')
    mkdir(out);
end
t_start = tic;

identity = struct( ...
    'engine', 'matlab', ...
    'operation', 'chain_dynamics', ...
    'plugin_version', '__PLUGIN_VERSION__', ...
    'release', version('-release'), ...
    'version', version, ...
    'matlabroot', matlabroot, ...
    'computer', computer, ...
    'batch_startup', logical(batchStartupOptionUsed()), ...
    'generated_at', datestr(now, 30));
write_text_json(fullfile(out, 'identity.json'), identity);
fprintf('RB_MATLAB_IDENTITY release=%s root=%s\n', identity.release, identity.matlabroot);

n = cfg.n;
m = cfg.mass(:);
k = cfg.stiffness(:);
if numel(m) ~= n
    error('mass vector length does not match n');
end
if numel(k) ~= n + 1
    error('stiffness vector length must be n+1');
end
if ~all(isfinite(m)) || ~all(m > 0)
    error('mass must be finite and strictly positive');
end
if ~all(isfinite(k)) || ~all(k > 0)
    error('stiffness must be finite and strictly positive');
end

M = diag(m);
K = zeros(n);
for i = 1:n
    K(i, i) = k(i) + k(i + 1);
    if i < n
        K(i, i + 1) = -k(i + 1);
        K(i + 1, i) = -k(i + 1);
    end
end
C = cfg.alpha * M + cfg.beta * K;
if ~all(isfinite(M(:))) || ~all(isfinite(K(:))) || ~all(isfinite(C(:)))
    error('non-finite system matrix');
end

[V, D] = eig(K, M);
omega2 = diag(D);
[omega2, order] = sort(omega2, 'ascend');
V = V(:, order);
if ~all(isfinite(omega2)) || ~all(omega2 > 0)
    error('generalized eigenvalues must be finite and positive');
end
omega = sqrt(omega2);

G = V' * M * V;
mass_norm_error = max(abs(G - eye(n)), [], 'all');
eig_residual = K * V - M * V * diag(omega2);
eig_residual_rel = norm(eig_residual, 'fro') / max(norm(K, 'fro'), realmin);
mode_residual = zeros(n, 1);
for i = 1:n
    mode_residual(i) = norm(eig_residual(:, i)) / max(norm(K, 'fro') * norm(V(:, i)), realmin);
end

mass_uniform = all(abs(m - m(1)) <= 1e-12 * abs(m(1)));
stiff_uniform = all(abs(k - k(1)) <= 1e-12 * abs(k(1)));
analytic_rel = -1;
if mass_uniform && stiff_uniform
    r = (1:n)';
    omega_exact = 2 * sqrt(k(1) / m(1)) * sin(r * pi / (2 * (n + 1)));
    analytic_rel = max(abs(omega - omega_exact) ./ omega_exact);
end

MK = K ./ m;
MC = C ./ m;
state_matrix = [zeros(n), eye(n); -MK, -MC];
lam = eig(state_matrix);
[~, order2] = sortrows([-imag(lam), -real(lam)]);
lam = lam(order2);
omega_d = abs(imag(lam));
zeta = -real(lam) ./ max(abs(lam), realmin);
damped_stable = all(isfinite(lam)) && all(real(lam) <= 1e-9);

nodes = cfg.force_nodes(:);
amps = cfg.force_amps(:);
freqs = cfg.force_freqs(:);
phases = cfg.force_phases(:);
if numel(nodes) ~= numel(amps) || numel(nodes) ~= numel(freqs) || numel(nodes) ~= numel(phases)
    error('forcing vectors must have equal length');
end
force = @(t) force_vector(t, n, nodes, amps, freqs, phases);

t = linspace(0, cfg.t_end, cfg.n_samples).';
if numel(t) ~= cfg.n_samples || any(diff(t) <= 0)
    error('invalid sample grid');
end
F = zeros(cfg.n_samples, n);
for ii = 1:cfg.n_samples
    F(ii, :) = force(t(ii)).';
end

opts = odeset('RelTol', cfg.rel_tol, 'AbsTol', cfg.abs_tol, 'MaxStep', cfg.max_step);
y0 = zeros(2 * n, 1);
[tout, yout] = ode45(@(tt, yy) chain_rhs(tt, yy, n, m, K, C, force), t, y0, opts);
if numel(tout) ~= cfg.n_samples
    error('ode45 did not return the requested number of samples');
end
if max(abs(tout - t)) > 1e-12 * max(1, cfg.t_end)
    error('ode45 output times differ from the requested grid');
end
t = tout;
x = yout(:, 1:n);
v = yout(:, n + 1:2 * n);
if ~all(isfinite(x(:))) || ~all(isfinite(v(:)))
    error('non-finite transient solution');
end

a_num = zeros(size(v));
step = diff(t);
if max(abs(step - step(1))) > 1e-12 * max(1, cfg.t_end)
    error('sample grid must be uniform for the residual stencil');
end
h = step(1);
% Second-order one-sided stencils at both ends; a first-order endpoint rule
% would dominate the residual metric.
a_num(1, :) = (-3 * v(1, :) + 4 * v(2, :) - v(3, :)) / (2 * h);
a_num(end, :) = (3 * v(end, :) - 4 * v(end - 1, :) + v(end - 2, :)) / (2 * h);
a_num(2:end - 1, :) = (v(3:end, :) - v(1:end - 2, :)) / (2 * h);

residual = a_num .* (m.') + v * C + x * K - F;
residual_norm = sqrt(sum(residual .^ 2, 2));
denominator = max( ...
    sqrt(sum((a_num .* (m.')).^2, 2)) + sqrt(sum((v * C).^2, 2)) + ...
    sqrt(sum((x * K).^2, 2)) + sqrt(sum(F.^2, 2)));
dynamic_residual_rel = max(residual_norm) / max(denominator, realmin);

Ekin = 0.5 * sum(v .* (v * M.'), 2);
Epot = 0.5 * sum(x .* (x * K.'), 2);
Etot = Ekin + Epot;
P = sum(F .* v, 2);
W = cumtrapz(t, P);
Pd = sum(v .* (v * C.'), 2);
Ddiss = cumtrapz(t, Pd);
balance = Etot - Etot(1) - W + Ddiss;
energy_balance_abs = max(abs(balance));
energy_scale = max([max(abs(Etot)); max(abs(W)); max(abs(Ddiss)); realmin]);
energy_balance_rel = energy_balance_abs / energy_scale;

tol_mass = 1e-8;
tol_eig = 1e-7;
tol_analytic = 1e-8;
tol_energy = 1e-2;
tol_dynamic = 1e-2;

checks = struct();
checks.mass_orthogonality = mass_norm_error <= tol_mass;
checks.eigen_residual = eig_residual_rel <= tol_eig;
checks.analytic_frequencies = (analytic_rel < 0) || (analytic_rel <= tol_analytic);
checks.finite_outputs = all(isfinite([x(:); v(:); Etot(:); W(:); Ddiss(:)]));
checks.energy_balance = energy_balance_rel <= tol_energy;
checks.dynamic_residual = dynamic_residual_rel <= tol_dynamic;
checks.damped_stability = damped_stable;

names = fieldnames(checks);
all_pass = true;
for ii = 1:numel(names)
    all_pass = all_pass && checks.(names{ii});
end

modal = [(1:n).', omega, omega / (2 * pi), abs(diag(G) - 1), mode_residual];
write_matrix_csv(fullfile(out, 'modal.csv'), ...
    'mode,omega_rad_s,frequency_hz,mass_norm_error,mode_residual_rel', modal);

damped = [(1:2 * n).', real(lam), imag(lam), omega_d, zeta];
write_matrix_csv(fullfile(out, 'damped_modes.csv'), ...
    'mode,eigenvalue_real,eigenvalue_imag,omega_d_rad_s,zeta', damped);

history = [t, x, v];
history_header = ['t', sprintf(',x_%d', 1:n), sprintf(',v_%d', 1:n)];
write_matrix_csv(fullfile(out, 'time_history.csv'), history_header, history);

energy = [t, Ekin, Epot, Etot, W, Ddiss, balance];
write_matrix_csv(fullfile(out, 'energy.csv'), ...
    't,kinetic,potential,total,work,dissipation,balance_residual', energy);

summary = struct();
summary.status = ternary(all_pass, 'passed', 'failed');
summary.engine = 'matlab';
summary.operation = 'chain_dynamics';
summary.plugin_version = '__PLUGIN_VERSION__';
summary.case_name = cfg.case_name;
summary.n = n;
summary.n_samples = cfg.n_samples;
summary.t_end = cfg.t_end;
summary.mass_uniform = mass_uniform;
summary.stiffness_uniform = stiff_uniform;
summary.max_mass_orthogonality_error = mass_norm_error;
summary.max_eigen_residual_relative = eig_residual_rel;
summary.max_analytic_frequency_relative_error = analytic_rel;
summary.max_dynamic_residual_relative = dynamic_residual_rel;
summary.energy_balance_relative = energy_balance_rel;
summary.energy_balance_absolute = energy_balance_abs;
summary.min_omega_rad_s = min(omega);
summary.max_omega_rad_s = max(omega);
summary.max_abs_displacement = max(abs(x(:)));
summary.max_abs_velocity = max(abs(v(:)));
summary.max_abs_force = max(abs(F(:)));
summary.checks = checks;
summary.tolerances = struct('mass_orthogonality', tol_mass, 'eigen_residual', tol_eig, ...
    'analytic_frequencies', tol_analytic, 'energy_balance', tol_energy, 'dynamic_residual', tol_dynamic);
summary.elapsed_s = toc(t_start);
summary.matlab_release = version('-release');
summary.matlabroot = matlabroot;
write_text_json(fullfile(out, 'results.json'), summary);

save(fullfile(out, 'chain_results.mat'), 'M', 'K', 'C', 'omega', 'V', 'lam', ...
    't', 'x', 'v', 'Ekin', 'Epot', 'Etot', 'W', 'Ddiss', 'cfg', 'identity', '-v7');

if cfg.make_plot
    fig = figure('Visible', 'off', 'Color', 'w', 'Position', [80 80 1280 860]);
    subplot(2, 2, 1);
    plot(1:n, V(:, 1:min(4, n)), '-o', 'LineWidth', 0.8);
    grid on;
    xlabel('DOF index');
    ylabel('mass-normalized \phi');
    title('Generalized mode shapes');
    subplot(2, 2, 2);
    semilogy(1:n, omega, 'o-');
    grid on;
    xlabel('mode');
    ylabel('\omega (rad/s)');
    title('Undamped natural frequencies');
    subplot(2, 2, 3);
    plot(t, x(:, 1), '-', t, x(:, ceil(n / 2)), '--');
    grid on;
    xlabel('t (s)');
    ylabel('displacement');
    title('Transient response');
    legend('x1', 'xmid');
    subplot(2, 2, 4);
    plot(t, Etot, '-', t, Etot(1) + W - Ddiss, '--');
    grid on;
    xlabel('t (s)');
    ylabel('energy');
    title('Energy balance');
    legend('E(t)', 'E(0)+W-D');
    print(fig, '-dpng', '-r120', fullfile(out, 'chain_summary.png'));
    close(fig);
end

if ~all_pass
    error('RB_CHAIN_DYNAMICS_CHECK_FAILED: one or more scientific checks failed');
end
fprintf('RB_CHAIN_DYNAMICS_COMPLETE\n');
end

function value = ternary(condition, when_true, when_false)
if condition
    value = when_true;
else
    value = when_false;
end
end

function f = force_vector(t, n, nodes, amps, freqs, phases)
f = zeros(n, 1);
for j = 1:numel(nodes)
    f(nodes(j)) = f(nodes(j)) + amps(j) * sin(2 * pi * freqs(j) * t + phases(j));
end
end

function dydt = chain_rhs(t, y, n, m, K, C, force)
x = y(1:n);
v = y(n + 1:2 * n);
dydt = [v; (force(t) - C * v - K * x) ./ m];
end

function write_matrix_csv(path, header, data)
fid = fopen(path, 'w');
if fid < 0
    error('cannot open output file: %s', path);
end
fprintf(fid, '%s\n', header);
format = [repmat('%.17g,', 1, size(data, 2) - 1), '%.17g\n'];
fprintf(fid, format, data.');
fclose(fid);
end

function write_text_json(path, value)
fid = fopen(path, 'w', 'n', 'UTF-8');
if fid < 0
    error('cannot open output file: %s', path);
end
fprintf(fid, '%s', jsonencode(value));
fclose(fid);
end
"""


def _source(config, output_dir) -> str:
    return (
        MATLAB_TEMPLATE.replace("__PLUGIN_VERSION__", PLUGIN_VERSION)
        .replace("__CONFIG__", _config_literal(config, output_dir))
    )


def compile_job(job: dict, workspace: Path, executables: dict) -> dict:
    if job.get("engine") != ENGINE or job.get("operation") != OPERATION:
        raise ValueError("chain_dynamics adapter only implements matlab/chain_dynamics")
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    config = _normalize(job)
    source = root / "rb_chain_dynamics.m"
    source.write_text(_source(config, str(root)), encoding="utf-8")
    executable = executables.get(ENGINE)
    ready = bool(executable and Path(executable).is_file())
    artifacts = [
        root / "identity.json",
        root / "modal.csv",
        root / "damped_modes.csv",
        root / "time_history.csv",
        root / "energy.csv",
        root / "results.json",
        root / "chain_results.mat",
    ]
    if config["plot"]:
        artifacts.append(root / "chain_summary.png")
    timeout = float(job.get("timeout_s", 600))
    plan = {
        "engine": ENGINE,
        "operation": OPERATION,
        "status": "compiled",
        "scope": "native",
        "source_path": str(source),
        "command": [str(executable), "-sd", str(root), "-batch", "rb_chain_dynamics"] if ready else [],
        "cwd": str(root),
        "timeout_s": timeout,
        "env": {},
        "expected_artifacts": [str(path) for path in artifacts],
        "required_markers": ["RB_MATLAB_IDENTITY", "RB_CHAIN_DYNAMICS_COMPLETE"],
        "ready": ready,
        "validation_scope": "Base MATLAB eig/ode45/save native execution; requires an installed licensed MATLAB matching the requested release",
        "scientific_scope": "Fixed-fixed mass-spring-damper chain: generalized modes, Rayleigh damping, multi-frequency forcing, energy balance and dynamic residual; independent SciPy oracle required",
    }
    if not ready:
        plan["reason"] = "MATLAB executable is missing or not configured; native source compiled but execution is blocked"
    return plan
