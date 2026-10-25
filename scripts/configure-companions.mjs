import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const args = new Map();
for (let i = 2; i < process.argv.length; i++) {
  const key = process.argv[i];
  if (!['--profile-root','--matlab-server','--matlab-root','--workspace','--apply'].includes(key)) throw new Error(`Unknown option ${key}`);
  if (args.has(key)) throw new Error(`Duplicate option ${key}`);
  args.set(key, key === '--apply' ? true : process.argv[++i]);
}
const required = (key) => {
  const value = args.get(key);
  if (typeof value !== 'string' || !path.isAbsolute(value)) throw new Error(`${key} must be an absolute path`);
  return path.resolve(value);
};
const profile = required('--profile-root'), server = required('--matlab-server');
const matlab = required('--matlab-root'), workspace = required('--workspace');
if (!fs.statSync(server).isFile() || !fs.statSync(matlab).isDirectory()) throw new Error('MATLAB/server paths are invalid');
const manifest = JSON.parse(fs.readFileSync(path.join(profile, 'package.json'), 'utf8'));
for (const pkg of ['@lovedheart/dsh-matlab-mcp-plugin','dsh-zotero']) {
  if (!manifest.dependencies?.[pkg] || !manifest.dsh?.profile?.bundles?.includes(pkg)) throw new Error(`Install and enable companion bundle first: ${pkg}`);
}
const rows = [
  { id: 'matlab-mcp', name: '@deepseek-ai/dsh-mcp-client', config: {
    serverName: 'matlab', transport: 'stdio', command: server,
    args: ['--matlab-session-mode=new','--matlab-display-mode=nodesktop',`--matlab-root=${matlab}`,`--initial-working-folder=${workspace}`,'--disable-telemetry=true','--initialize-matlab-on-startup=false'],
    env: process.platform === 'win32' ? { WINDIR: process.env.WINDIR || 'C:\\Windows', SystemRoot: process.env.SystemRoot || 'C:\\Windows' } : {},
    cwd: workspace, toolCallTimeoutMs: 180000, failOnStartupError: false,
  } },
  { id: 'tool-zotero', name: 'dsh-zotero', config: { baseUrl: 'http://127.0.0.1:23119', library: 'user', timeoutMs: 15000 } },
];
const begin = '# BEGIN DSH RESEARCH COMPANIONS', end = '# END DSH RESEARCH COMPANIONS';
const scalar = (x) => JSON.stringify(x);
const yaml = rows.map((r) => `- id: ${r.id}\n  name: ${scalar(r.name)}\n  config: ${JSON.stringify(r.config)}`).join('\n');
const target = path.join(profile, 'cordis.patch.yml');
const before = fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : '[]\n';
const start = before.indexOf(begin), finish = before.indexOf(end);
if ((start < 0) !== (finish < 0) || (start >= 0 && (finish < start || before.indexOf(begin,start+1)>=0 || before.indexOf(end,finish+1)>=0))) throw new Error('Ambiguous managed block; preserve profile and resolve manually');
const base = start < 0 ? before : before.slice(0,start) + before.slice(finish+end.length);
// An empty YAML root must become a list before append; nonempty profile rows stay intact.
const content = /^\s*\[\]\s*$/.test(base) ? '' : base.trimEnd()+'\n';
const after = content+'\n'+begin+'\n'+yaml+'\n'+end+'\n';
const hash = (s) => createHash('sha256').update(s).digest('hex');
const report = { applied: false, profile, beforeSha256: hash(before), afterSha256: hash(after), rows: rows.map((r)=>r.id) };
if (args.get('--apply')) {
  fs.mkdirSync(workspace, {recursive:true});
  const backup=path.join(profile,`research-companions-before-${Date.now()}.yml`);
  fs.writeFileSync(backup,before,{flag:'wx'});
  fs.writeFileSync(target,after);
  report.applied=true; report.backup=backup;
}
console.log(JSON.stringify(report,null,2));
