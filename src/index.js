import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const name = 'research-toolkit';
export const inject = ['tools'];
const ROOT = fileURLToPath(new URL('../', import.meta.url));
const CLI = join(ROOT, 'runtime', 'cli.py');
const MAX_CAPTURE_BYTES = 8 * 1024 * 1024;
const OUTPUT_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' }, status: { type: 'string' }, exitCode: { type: 'integer' },
    command: { type: 'array', items: { type: 'string' } },
    data: {}, diagnostics: { type: 'string' }, durationMs: { type: 'integer' },
  },
  required: ['ok', 'status', 'exitCode', 'command', 'data', 'diagnostics', 'durationMs'],
  additionalProperties: false,
};
const str = (description) => ({ type: 'string', description });
const emptyArgs = { type: 'object', properties: {}, additionalProperties: false };
const jobArgs = {
  type: 'object',
  properties: {
    jobPath: str('Path to a research job JSON file. Source files are read without shell interpolation.'),
    workspace: str('Optional subdirectory within configured workspaceRoot. Omit to use workspaceRoot.'),
  },
  required: ['jobPath'], additionalProperties: false,
};
const reportArgs = {
  type: 'object', properties: { acceptanceDir: str('Directory containing a saved acceptance run and its evidence.') },
  required: ['acceptanceDir'], additionalProperties: false,
};

function validateArgs(args, schema) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new TypeError('Arguments must be an object');
  for (const key of Object.keys(args)) {
    if (!(key in schema.properties)) throw new TypeError(`Unknown argument: ${key}`);
    if (typeof args[key] !== schema.properties[key].type || !args[key].trim()) {
      throw new TypeError(`${key} must be a non-empty ${schema.properties[key].type}`);
    }
  }
  for (const key of schema.required ?? []) if (!(key in args)) throw new TypeError(`Missing argument: ${key}`);
}

function within(root, path) {
  const rel = relative(root, path);
  return rel === '' || (rel !== '..' && !rel.startsWith(`..${process.platform === 'win32' ? '\\' : '/'}`) && !isAbsolute(rel));
}

function existingAncestor(path) {
  let current = path;
  while (!existsSync(current) && dirname(current) !== current) current = dirname(current);
  return realpathSync(current);
}

function workspaceFor(cfg, args) {
  const target = resolve(cfg.workspaceRoot, args.workspace ?? '.');
  if (!within(cfg.workspaceRoot, target)) throw new Error('workspace must remain within configured workspaceRoot');
  // A symlink or junction below the configured root must not redirect writes elsewhere.
  if (existsSync(cfg.workspaceRoot) && !within(realpathSync(cfg.workspaceRoot), existingAncestor(target))) {
    throw new Error('workspace resolves outside configured workspaceRoot through a filesystem link');
  }
  return target;
}

function configuration(config = {}) {
  const timeout = config.maxTimeoutSeconds ?? 600;
  if (!Number.isFinite(timeout) || timeout < 1 || timeout > 43200) {
    throw new TypeError('maxTimeoutSeconds must be between 1 and 43200');
  }
  if (config.pythonPath !== undefined && typeof config.pythonPath !== 'string') throw new TypeError('pythonPath must be a string');
  if (config.workspaceRoot !== undefined && typeof config.workspaceRoot !== 'string') throw new TypeError('workspaceRoot must be a string');
  return {
    pythonPath: config.pythonPath || process.env.DSH_RESEARCH_PYTHON || 'python',
    workspaceRoot: resolve(config.workspaceRoot || join(process.cwd(), 'research-workspace')),
    maxTimeoutSeconds: timeout,
  };
}

async function stopTree(child) {
  if (!child.pid) return;
  if (process.platform === 'win32') {
    await new Promise((done) => {
      const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore', shell: false });
      killer.once('error', () => { child.kill(); done(); });
      killer.once('close', () => { if (child.exitCode === null) child.kill(); done(); });
    });
  } else {
    try { process.kill(-child.pid, 'SIGTERM'); } catch { child.kill('SIGTERM'); }
  }
}

async function invoke(cfg, cliArgs, signal) {
  const started = Date.now();
  const command = [cfg.pythonPath, CLI, ...cliArgs];
  const result = (exitCode, status, data, diagnostics = '') => ({
    ok: exitCode === 0, status, exitCode, command, data, diagnostics,
    durationMs: Date.now() - started,
  });
  if (!existsSync(CLI)) return result(2, 'blocked', null, `Bundled CLI is missing: ${CLI}`);
  if (signal?.aborted) return result(1, 'aborted', null, 'Cancelled before process start');
  return new Promise((done) => {
    let stdout = '', stderr = '', bytes = 0, stopped = '', spawnError;
    let child;
    try { child = spawn(cfg.pythonPath, [CLI, ...cliArgs], {
      cwd: ROOT, shell: false, windowsHide: true, detached: process.platform !== 'win32',
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1' },
      stdio: ['ignore', 'pipe', 'pipe'],
    }); } catch (error) { done(result(2, 'blocked', null, `Cannot start Python: ${error.message}`)); return; }
    const stop = (reason) => { if (!stopped) { stopped = reason; void stopTree(child); } };
    const timer = setTimeout(() => stop('timeout'), cfg.maxTimeoutSeconds * 1000);
    const abort = () => stop('aborted');
    signal?.addEventListener('abort', abort, { once: true });
    child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8');
    const capture = (kind, chunk) => {
      bytes += Buffer.byteLength(chunk);
      if (bytes > MAX_CAPTURE_BYTES) { stop('output-limit'); return; }
      if (kind === 'out') stdout += chunk; else stderr += chunk;
    };
    child.stdout.on('data', (chunk) => capture('out', chunk));
    child.stderr.on('data', (chunk) => capture('err', chunk));
    child.once('error', (error) => { spawnError = error; });
    child.once('close', (code) => {
      clearTimeout(timer); signal?.removeEventListener('abort', abort);
      if (spawnError) return done(result(2, 'blocked', null, `Cannot start Python: ${spawnError.message}`));
      if (stopped) return done(result(1, stopped, null, `${stopped}\n${stderr}`.trim()));
      const exitCode = Number.isInteger(code) ? code : 1;
      let data;
      try { data = JSON.parse(stdout.trim()); }
      catch { return done(result(1, 'failed', null, `CLI stdout was not one JSON value (exit ${exitCode}).\n${stderr}\n${stdout.slice(-2000)}`.trim())); }
      if (![0, 1, 2].includes(exitCode)) return done(result(1, 'failed', data, `Unexpected CLI exit ${exitCode}.\n${stderr}`.trim()));
      return done(result(exitCode, exitCode === 2 ? 'blocked' : exitCode === 1 ? 'failed' : String(data?.status ?? 'passed'), data, stderr.trim()));
    });
  });
}

const SKILLS = [
  { name: 'research-toolkit', description: 'Compile and run reproducible jobs in installed research software, inspect native artifacts, and report verified or blocked capabilities.' },
  { name: 'research-bridge-lab', description: 'Research and prototype bridges for unfamiliar local scientific software using official interfaces, isolated candidate code and real application evidence before promoting an adapter.' },
];

export async function apply(ctx, config = {}) {
  const cfg = configuration(config);
  const tools = ctx.tools ?? ctx.get?.('tools');
  if (!tools || typeof tools.register !== 'function') throw new Error('research-toolkit requires the DSH tools service');
  const lifetime = new AbortController();
  const inFlight = new Set();
  ctx.effect(() => async () => {
    lifetime.abort('Research toolkit plugin unloaded');
    await Promise.allSettled([...inFlight]);
  });
  const add = (toolName, description, parameters, readOnly, argsFor) => tools.register({
    name: toolName, description, parameters,
    timeoutMs: (cfg.maxTimeoutSeconds + 15) * 1000,
    isConcurrencySafe: () => readOnly,
    output: {
      schema: OUTPUT_SCHEMA,
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args, exec) {
      validateArgs(args, parameters);
      const signal = exec?.signal ? AbortSignal.any([exec.signal, lifetime.signal]) : lifetime.signal;
      const task = invoke(cfg, argsFor(args), signal);
      inFlight.add(task);
      try { return await task; }
      finally { inFlight.delete(task); }
    },
  });
  add('research_discover', 'Inspect locally installed research software and callable interfaces. Discovery does not establish that a licensed engine can execute a real task.', emptyArgs, true, () => ['discover', '--json']);
  add('research_catalog', 'List supported research adapters, job operations, and native execution routes. A catalog entry is a compiler capability, not a successful local acceptance.', emptyArgs, true, () => ['catalog', '--json']);
  add('research_compile', 'Compile a research job JSON into native scripts and a reproducible plan in a fresh directory. Missing software may still produce source with ready=false; this is not execution evidence.', jobArgs, false, (args) => ['compile', resolve(args.jobPath), '--workspace', join(workspaceFor(cfg, args), `compile-${Date.now()}-${randomUUID().slice(0, 8)}`)]);
  add('research_run', 'Execute a compiled research job in its real local software, retaining native scripts, logs, artifacts and verification evidence. Unavailable engines return blocked rather than simulated success.', jobArgs, false, (args) => ['run', resolve(args.jobPath), '--workspace', workspaceFor(cfg, args), '--max-timeout', String(cfg.maxTimeoutSeconds)]);
  add('research_acceptance_report', 'Read and verify a saved research acceptance directory. Report passed, failed and blocked software separately; a generated script alone cannot establish a passed run.', reportArgs, true, (args) => ['verify', resolve(args.acceptanceDir), '--json']);
  if (typeof ctx.inject === 'function') ctx.inject(['skills'], (skillCtx) => {
    for (const skill of SKILLS) {
      const path = join(ROOT, 'skills', skill.name, 'SKILL.md');
      const raw = readFileSync(path, 'utf8');
      const content = raw.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n)?/, '').trim();
      skillCtx.skills.register({ ...skill, content, source: 'dsh-research-toolkit', path, resourceBase: { kind: 'directory', path: dirname(path) } });
    }
  });
}
