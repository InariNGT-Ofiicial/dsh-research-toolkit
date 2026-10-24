// Regression for the actual model-facing DSH skill tool, including output
// schema validation and rendering. No skill/tool/runtime implementation is mocked.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { extractHost, loadHost } from './dsh-host-loader.mjs';

const ROOT = path.resolve(process.env.DSH_TEST_PLUGIN_ROOT || fileURLToPath(new URL('../', import.meta.url)));
const BASE = path.resolve(process.env.DSH_TEST_WORKSPACE || path.join(process.cwd(), '.research-host-test'));
fs.mkdirSync(BASE, { recursive: true });
const WORK = fs.mkdtempSync(path.join(BASE, 'skill-native-'));
const source = process.env.DSH_HOST_ASAR;
let hostInfo;
if (source) hostInfo = extractHost(source, path.resolve(process.env.DSH_HOST_CACHE || path.join(BASE, 'skill-host-runtime')), ['@deepseek-ai/dsh-tool-skill']);
else if (process.env.DSH_HOST_MODULE_ROOT) hostInfo = { root: path.resolve(process.env.DSH_HOST_MODULE_ROOT), source: 'provided module root' };
else throw new Error('Set DSH_HOST_ASAR or DSH_HOST_MODULE_ROOT to the installed native DSH runtime.');
const host = await loadHost(hostInfo);
const toolDir = path.join(hostInfo.root, 'node_modules', '@deepseek-ai/dsh-tool-skill');
const toolManifest = JSON.parse(fs.readFileSync(path.join(toolDir, 'package.json'), 'utf8'));
const toolEntry = path.join(toolDir, toolManifest.main);
const skillTool = await import(pathToFileURL(toolEntry).href);
const plugin = await import(pathToFileURL(path.join(ROOT, 'src/index.js')).href);
const { Context, Service } = host.cordis;
const evidence = {
  status: 'running', pluginRoot: ROOT, workspace: WORK, host: hostInfo,
  boundary: 'Actual official dsh-tool-skill, SkillRegistry, ToolRuntime and Cordis; only unrelated prompt, agents and working-directory services are test fixtures. No Desktop profile, session, model API or credentials are loaded.',
  toolSkill: { version: toolManifest.version, entrySha256: createHash('sha256').update(fs.readFileSync(toolEntry)).digest('hex') },
  checks: [],
};
class TestPrompt extends Service {
  constructor(ctx) { super(ctx, 'systemPrompt'); }
  tools() { return () => {}; }
}
class TestAgents extends Service { constructor(ctx) { super(ctx, 'agents'); } }
class TestWorkingDirectory extends Service {
  constructor(ctx) { super(ctx, 'workingDirectory'); }
  async ensure() { return WORK; }
}
const ctx = new Context();
let serial = 0;
const call = (name) => ctx.tools.execute({ name: 'skill', arguments: { name }, callId: `skill-native-${++serial}`, signal: new AbortController().signal });
async function check(name, fn) {
  await test(name, async () => {
    try { await fn(); evidence.checks.push({ name, status: 'passed' }); }
    catch (error) { evidence.checks.push({ name, status: 'failed', reason: error.message }); throw error; }
  });
}
try {
  for (const service of [TestPrompt, TestAgents, TestWorkingDirectory, host.tools.ToolRuntime, host.skills.SkillRegistry]) await ctx.plugin(service).await();
  await ctx.plugin(plugin, { pythonPath: process.env.DSH_TEST_PYTHON || 'python', workspaceRoot: path.join(WORK, 'jobs'), maxTimeoutSeconds: 60 }).await();
  await ctx.plugin(skillTool).await();
  await check('Official skill tool loads and renders the bundled skill through ToolRuntime.execute', async () => {
    assert.ok(ctx.tools.schemas().some((tool) => tool.name === 'skill'), 'Official tool is registered');
    const result = await call('research-toolkit');
    assert.equal(result.isError, false, JSON.stringify(result.error));
    const directory = path.join(ROOT, 'skills/research-toolkit');
    assert.deepEqual(result.value.resourceBase, { kind: 'directory', path: directory });
    assert.equal(result.value.name, 'research-toolkit');
    assert.ok(result.value.content.includes('research_compile'));
    const rendered = result.content.filter((block) => block.type === 'text').map((block) => block.text).join('\n');
    assert.ok(rendered.includes('<skill_content name="research-toolkit">'));
    const escapedDirectory = directory.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    assert.ok(rendered.includes(`Base directory for this skill: ${escapedDirectory}`));
    assert.ok(fs.existsSync(path.resolve(result.value.resourceBase.path, '../../docs/jobs.md')));
    evidence.success = { isError: result.isError, name: result.value.name, resourceBase: result.value.resourceBase, content: result.content };
  });
  await check('Official output validation rejects the former string resourceBase contract', async () => {
    const dispose = ctx.skills.register({ name: 'resource-base-regression-invalid', description: 'Test-only legacy invalid contract', content: 'Invalid resource base sentinel.', source: 'native-skill-test', resourceBase: path.join(ROOT, 'skills/research-toolkit') });
    try {
      const result = await call('resource-base-regression-invalid');
      assert.equal(result.isError, true);
      assert.match(result.error.message, /resourceBase.*oneOf/);
      evidence.negativeControl = { isError: result.isError, error: result.error };
    } finally { dispose(); }
  });
  await check('Official skill tool loads the unfamiliar-software research guide from the installed bundle', async () => {
    const result = await call('research-bridge-lab');
    assert.equal(result.isError, false, JSON.stringify(result.error));
    assert.equal(result.value.name, 'research-bridge-lab');
    assert.deepEqual(result.value.resourceBase, { kind: 'directory', path: path.join(ROOT, 'skills/research-bridge-lab') });
    assert.ok(result.value.content.length > 120);
    assert.ok(result.value.content.includes('bridge-research-guide.md'));
    assert.ok(fs.existsSync(path.join(ROOT, 'docs/bridge-research-guide.md')));
    evidence.extensionGuide = { name: result.value.name, resourceBase: result.value.resourceBase, isError: result.isError };
  });
} finally {
  await ctx.fiber.dispose();
  evidence.status = evidence.checks.length === 3 && evidence.checks.every((check) => check.status === 'passed') ? 'passed' : 'failed';
  const report = path.join(WORK, 'skill-native-host-report.json');
  fs.writeFileSync(report, JSON.stringify(evidence, null, 2));
  console.log(`Native skill evidence: ${report}`);
}
