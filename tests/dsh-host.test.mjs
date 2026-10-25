import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { extractHost, loadHost } from './dsh-host-loader.mjs';

const ROOT = path.resolve(process.env.DSH_TEST_PLUGIN_ROOT || fileURLToPath(new URL('../', import.meta.url)));
const plugin = await import(pathToFileURL(path.join(ROOT, 'src', 'index.js')).href);
const BASE = path.resolve(process.env.DSH_TEST_WORKSPACE || path.join(process.cwd(), '.research-host-test'));
fs.mkdirSync(BASE, { recursive: true });
const WORK = fs.mkdtempSync(path.join(BASE, 'native-'));
const evidence = {
  status: 'running', boundary: 'Real Cordis Context, ToolRuntime and SkillRegistry; lightweight system-prompt test service; no Desktop UI or model API.',
  workspace: WORK, checks: [],
};
const source = process.env.DSH_HOST_ASAR;
let hostInfo;
if (source) hostInfo = extractHost(source, path.resolve(process.env.DSH_HOST_CACHE || path.join(BASE, 'host-runtime')));
else if (process.env.DSH_HOST_MODULE_ROOT) hostInfo = { root: path.resolve(process.env.DSH_HOST_MODULE_ROOT), source: 'provided module root' };
else throw new Error('Set DSH_HOST_ASAR to the installed app.asar, or DSH_HOST_MODULE_ROOT to a directory containing the native DSH node_modules.');
evidence.host = hostInfo;
const host = await loadHost(hostInfo);
const { Context, Service } = host.cordis;
class TestPrompt extends Service {
  constructor(ctx) { super(ctx, 'systemPrompt'); }
  tools(producer) { this.producer = producer; return () => { this.producer = undefined; }; }
}
async function mount(config = {}) {
  const ctx = new Context();
  await ctx.plugin(TestPrompt).await();
  await ctx.plugin(host.tools.ToolRuntime).await();
  await ctx.plugin(host.skills.SkillRegistry).await();
  const fiber = ctx.plugin(plugin, {
    pythonPath: process.env.DSH_TEST_PYTHON || 'python', workspaceRoot: path.join(WORK, 'jobs'),
    maxTimeoutSeconds: 60, ...config,
  });
  await fiber.await();
  return { ctx, fiber };
}
let serial = 0;
async function call(ctx, name, args, signal = new AbortController().signal) {
  return ctx.tools.execute({ name, arguments: args, callId: `research-native-${++serial}`, signal });
}
function value(result) {
  assert.equal(result.isError, false, JSON.stringify(result.error));
  assert.ok(result.content?.[0]?.text, 'Native pipeline rendered a content block');
  assert.ok(result.value !== undefined, 'Native pipeline retained the canonical JSON value');
  return result.value;
}
async function check(name, fn) {
  await test(name, async () => {
    try { await fn(); evidence.checks.push({ name, status: 'passed' }); }
    catch (error) { evidence.checks.push({ name, status: 'failed', reason: error.message }); throw error; }
  });
}
const { ctx, fiber } = await mount();
let discovered, runValue;
const fixtureDir = path.join(WORK, '中文 inputs & literal $');
fs.mkdirSync(fixtureDir, { recursive: true });
const csv = path.join(fixtureDir, 'observations.csv');
const residuals = [1, -1, -1, 1, 1, -1, -1, 1];
fs.writeFileSync(csv, 'x,y\n' + residuals.map((e, x) => `${x},${3 + 2 * x + 0.25 * e}`).join('\n') + '\n,20\n');
const jobPath = path.join(fixtureDir, 'analysis.json');
fs.writeFileSync(jobPath, JSON.stringify({
  schema_version: 'research.job.v1', id: 'dsh-host-ols', engine: 'python', operation: 'analysis',
  inputs: { data: csv }, parameters: { method: 'linear_regression', outcome: 'y', predictors: ['x'] }, timeout_s: 30,
}, null, 2));

try {
  await check('Native app-boot parses the manifest, bundle YAML and exact host compatibility', async () => {
    const manifest = host.appBoot.readProfileManifest('research-host-test', ROOT);
    assert.equal(manifest.name, 'dsh-research-toolkit');
    assert.equal(manifest.dsh.manifestVersion, 1);
    assert.equal(host.appBoot.evaluatePluginCompatibility(manifest), undefined);
    const patches = host.appBoot.bundlePatchPaths(ROOT, manifest.dsh.bundle).flatMap((file) => host.appBoot.loadOverlayPatches('research-host-test', file));
    const entries = host.appBoot.composeEntries([patches]);
    assert.equal(entries.length, 1); assert.equal(entries[0].name, manifest.name);
    assert.equal(entries[0].id, 'research-toolkit');
    assert.deepEqual(Object.keys(entries[0].config).sort(), ['maxTimeoutSeconds','pythonPath','workspaceRoot']);
    evidence.bundle = { manifest: manifest.name + '@' + manifest.version, patchFiles: host.appBoot.bundlePatchPaths(ROOT,manifest.dsh.bundle),entries };
  });
  await check('Native Cordis registers all six wire schemas and the bundled skill', async () => {
    assert.deepEqual(ctx.tools.schemas().map((x) => x.name).sort(), [
      'research_acceptance_report', 'research_catalog', 'research_compile', 'research_discover', 'research_run', 'research_integrations',
    ].sort());
    for (const schema of ctx.tools.schemas()) host.tools.assertSupportedJsonSchema(schema.parameters);
    const loaded = await ctx.skills.get('research-toolkit', { cwd: WORK });
    assert.ok(loaded.content.includes('research_compile'));
    assert.ok(loaded.path.endsWith('SKILL.md'));
  });
  await check('Catalog executes Python through native ToolRuntime and validates canonical output', async () => {
    const v = value(await call(ctx, 'research_catalog', {}));
    assert.equal(v.ok, true, v.diagnostics);
    assert.equal(v.exitCode, 0);
    assert.equal(v.data.status, 'passed');
    assert.ok(Object.keys(v.data.engines).length >= 20);
    evidence.catalogEngines = Object.keys(v.data.engines);
  });
  await check('Discovery retains executable-found versus application-verified distinction', async () => {
    const v = value(await call(ctx, 'research_discover', {}));
    assert.equal(v.ok, true, v.diagnostics);
    discovered = v.data.engines;
    assert.equal(discovered.python.application_verified, false);
    assert.equal(discovered.python.probe_status, 'not_run');
  });
  await check('Compilation produces native source without claiming execution', async () => {
    const v = value(await call(ctx, 'research_compile', { jobPath, workspace: 'compile only' }));
    assert.equal(v.ok, true, v.diagnostics);
    assert.equal(v.data.status, 'compiled');
    assert.equal(v.data.ready, true);
    assert.equal(fs.existsSync(v.data.source_path), true);
    assert.equal(fs.existsSync(path.join(v.data.workspace, 'result.json')), false);
    const repeated = value(await call(ctx, 'research_compile', { jobPath, workspace: 'compile only' }));
    assert.equal(repeated.ok, true);
    assert.notEqual(repeated.data.workspace, v.data.workspace, 'Repeated compile preserves earlier reviewable source');
    assert.equal(fs.existsSync(v.data.source_path), true);
  });
  await check('Real Python OLS validates scientific estimates and retains native evidence', async () => {
    const v = value(await call(ctx, 'research_run', { jobPath, workspace: '真实执行 & literal $' }));
    assert.equal(v.ok, true, JSON.stringify(v));
    assert.equal(v.data.application_verified, true);
    assert.ok(v.data.artifacts.length >= 2);
    const coefficientArtifact = v.data.artifacts.find((a) => a.path.endsWith('coefficients.csv'));
    const metricsArtifact = v.data.artifacts.find((a) => a.path.endsWith('metrics.json'));
    const rows = fs.readFileSync(coefficientArtifact.path, 'utf8').trim().split(/\r?\n/).slice(1).map((line) => line.split(','));
    assert.ok(Math.abs(Number(rows.find((x) => x[0] === 'Intercept')[1]) - 3) < 1e-10);
    assert.ok(Math.abs(Number(rows.find((x) => x[0] === 'x')[1]) - 2) < 1e-10);
    const metrics = JSON.parse(fs.readFileSync(metricsArtifact.path, 'utf8'));
    assert.equal(metrics.n_complete, 8); assert.equal(metrics.n_excluded, 1);
    runValue = v;
    evidence.realRun = v.data;
  });
  await check('Saved acceptance evidence is verified through the native report tool', async () => {
    const v = value(await call(ctx, 'research_acceptance_report', { acceptanceDir: runValue.data.workspace }));
    assert.equal(v.ok, true, JSON.stringify(v));
    assert.equal(v.data.status, 'passed');
  });
  await check('Invalid arguments and workspace traversal fail before process execution', async () => {
    const missing = await call(ctx, 'research_compile', {});
    assert.equal(missing.isError, true);
    assert.match(missing.error.message, /Missing argument/);
    const escaping = await call(ctx, 'research_compile', { jobPath, workspace: '../outside' });
    assert.equal(escaping.isError, true);
    assert.match(escaping.error.message, /within configured workspaceRoot/);
  });
  await check('Native monotonic policy guard denies run before the bridge executes', async () => {
    const dispose = ctx.tools.guard((execution) => execution.name === 'research_run' ? 'isolated host test denial' : undefined);
    try {
      const v = await call(ctx, 'research_run', { jobPath, workspace: 'guard-must-not-run' });
      assert.equal(v.isError, true);
      assert.match(v.error.message, /isolated host test denial/);
      assert.equal(fs.existsSync(path.join(WORK, 'jobs', 'guard-must-not-run')), false);
    } finally { dispose(); }
  });
  await check('Unavailable Python remains a blocked capability in native output', async () => {
    const missing = await mount({ pythonPath: path.join(WORK, 'missing-python.exe') });
    try {
      const v = value(await call(missing.ctx, 'research_catalog', {}));
      assert.equal(v.ok, false); assert.equal(v.status, 'blocked'); assert.equal(v.exitCode, 2);
    } finally { await missing.ctx.fiber.dispose(); }
  });
  const sleepingScript = path.join(fixtureDir, 'sleep.py');
  const sleepingJob = path.join(fixtureDir, 'sleep.json');
  fs.writeFileSync(sleepingScript, 'import os,time\nfrom pathlib import Path\nout=Path(os.environ["RB_OUTPUT_DIR"])\n(out/"started.txt").write_text("started")\ntime.sleep(3)\n(out/"orphan.txt").write_text("still running")\n');
  fs.writeFileSync(sleepingJob, JSON.stringify({schema_version: 'research.job.v1',id: 'timeout-tree',engine: 'python',operation: 'script',inputs: {script: sleepingScript},parameters: {expected_artifacts: ['orphan.txt']},timeout_s: 10}));
  const findOrphans = (root) => !fs.existsSync(root) ? [] : fs.readdirSync(root, {withFileTypes: true}).flatMap((entry) => {
    const name = path.join(root, entry.name);
    return entry.isDirectory() ? findOrphans(name) : entry.name === 'orphan.txt' ? [name] : [];
  });
  await check('Bridge timeout stops its Python process tree before later writes', async () => {
    const short = await mount({ maxTimeoutSeconds: 1 });
    try {
      const v = value(await call(short.ctx, 'research_run', {jobPath: sleepingJob,workspace: 'timeout-tree'}));
      assert.equal(v.ok, false); assert.equal(v.status, 'timeout'); assert.equal(v.exitCode, 1);
      await new Promise((done) => setTimeout(done, 3300));
      assert.deepEqual(findOrphans(path.join(WORK,'jobs','timeout-tree')), []);
    } finally { await short.ctx.fiber.dispose(); }
  });
  await check('Native cancellation reaches the bridge and stops later child writes', async () => {
    const aborter = new AbortController();
    const timer = setTimeout(() => aborter.abort('isolated cancellation test'), 500);
    try {
      const v = await call(ctx,'research_run',{jobPath: sleepingJob,workspace:'cancel-tree'},aborter.signal);
      assert.equal(v.isError,true); assert.equal(v.error.info.code, 'ABORTED');
      await new Promise((done) => setTimeout(done, 3300));
      assert.deepEqual(findOrphans(path.join(WORK,'jobs','cancel-tree')), []);
    } finally { clearTimeout(timer); }
  });
  await check('Unloading an active plugin awaits cancellation of its process tree', async () => {
    const active = await mount();
    try {
      const pending = call(active.ctx,'research_run',{jobPath:sleepingJob,workspace:'dispose-tree'});
      await new Promise((done) => setTimeout(done,500));
      await active.fiber.dispose();
      const v = value(await pending);
      assert.equal(v.ok,false); assert.equal(v.status,'aborted');
      await new Promise((done) => setTimeout(done,3300));
      assert.deepEqual(findOrphans(path.join(WORK,'jobs','dispose-tree')),[]);
    } finally { await active.ctx.fiber.dispose(); }
  });
  await check('Disposing the plugin removes its tools and embedded skill', async () => {
    await fiber.dispose();
    assert.equal(ctx.tools.schemas().length, 0);
    assert.equal((await ctx.skills.list({ cwd: WORK })).length, 0);
  });
} finally {
  await ctx.fiber.dispose();
  evidence.status = evidence.checks.some((x) => x.status === 'failed') ? 'failed' : 'passed';
  fs.writeFileSync(path.join(WORK, 'dsh-native-host-report.json'), JSON.stringify(evidence, null, 2));
  console.log(`Native host evidence: ${path.join(WORK, 'dsh-native-host-report.json')}`);
}
