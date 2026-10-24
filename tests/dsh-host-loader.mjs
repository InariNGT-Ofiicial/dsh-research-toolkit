// Test-only loader: extract public runtime code from a user-supplied DSH ASAR.
// It never reads DSH profile state, credentials, sessions, or the live app.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

export function extractHost(archive, output, extraEntries = []) {
  const fd = fs.openSync(archive, 'r');
  try {
    const h = Buffer.alloc(16); fs.readSync(fd, h, 0, 16, 0);
    const headerSize = h.readUInt32LE(4), jsonSize = h.readUInt32LE(12);
    if (jsonSize > 128 * 1024 * 1024) throw new Error('ASAR header is unexpectedly large');
    const b = Buffer.alloc(jsonSize); fs.readSync(fd, b, 0, b.length, 16);
    const root = JSON.parse(b.toString('utf8'));
    const files = new Map();
    function walk(node, prefix = '') {
      for (const [key, value] of Object.entries(node.files ?? {})) {
        const filename = prefix ? `${prefix}/${key}` : key;
        if (value.files) walk(value, filename); else files.set(filename, value);
      }
    }
    walk(root);
    const records = [];
    function extractPackage(name) {
      if (!/^(?:@[a-z0-9_.-]+\/)?[a-z0-9_.-]+$/i.test(name)) throw new Error(`Invalid package name: ${name}`);
      if (records.some((r) => r.name === name)) throw new Error(`Already extracted missing package ${name}; dependency graph cannot be resolved`);
      const prefix = `dsh/node_modules/${name}/`;
      let count = 0;
      const deps = new Set();
      for (const [filename, info] of files) {
        if (!filename.startsWith(prefix) || filename.slice(prefix.length).startsWith('node_modules/')) continue;
        if (info.link) continue;
        const target = path.join(output, 'node_modules', name, filename.slice(prefix.length));
        fs.mkdirSync(path.dirname(target), { recursive: true });
        let content;
        if (info.unpacked) content = fs.readFileSync(`${archive}.unpacked/${filename}`);
        else {
          content = Buffer.alloc(info.size);
          fs.readSync(fd, content, 0, content.length, 8 + headerSize + Number(info.offset));
        }
        fs.writeFileSync(target, content); count++;
        if (/\.(?:m?js|cjs)$/.test(filename)) {
          const code = content.toString('utf8');
          const pattern = /(?:^|\n)\s*(?:import|export)\s+(?:[^'"\n]*?\s+from\s*)?['"]([^'"]+)['"]|(?:import|require|__require)\(\s*['"]([^'"]+)['"]/g;
          for (const found of code.matchAll(pattern)) {
            const spec = found[1] ?? found[2];
            if (spec.startsWith('.') || spec.startsWith('/') || spec.startsWith('node:')) continue;
            const pkg = spec.startsWith('@') ? spec.split('/').slice(0, 2).join('/') : spec.split('/')[0];
            if (files.has(`dsh/node_modules/${pkg}/package.json`)) deps.add(pkg);
          }
        }
      }
      if (!count) throw new Error(`Package ${name} is absent in the supplied ASAR`);
      const manifest = JSON.parse(fs.readFileSync(path.join(output, 'node_modules', name, 'package.json'), 'utf8'));
      records.push({ name, version: manifest.version, files: count });
      return deps;
    }
    const entries = ['@deepseek-ai/dsh-tools', '@deepseek-ai/cordis', '@deepseek-ai/dsh-skill', '@deepseek-ai/dsh-app-boot', ...extraEntries];
    const queue = [...entries];
    while (queue.length) {
      const pkg = queue.shift();
      if (records.some((r) => r.name === pkg)) continue;
      if (records.length >= 128) throw new Error('Native DSH dependency extraction exceeded 128 packages');
      queue.push(...extractPackage(pkg));
    }
    const toolsEntry = path.join(output, 'node_modules', '@deepseek-ai/dsh-tools/lib/index.js');
    return {
      root: output, packages: records,
      toolsEntrySha256: createHash('sha256').update(fs.readFileSync(toolsEntry)).digest('hex'),
    };
  } finally { fs.closeSync(fd); }
}

export async function loadHost(options) {
  const root = options.root;
  const manifest = (name) => JSON.parse(fs.readFileSync(path.join(root, 'node_modules', name, 'package.json'), 'utf8'));
  const load = (name) => import(pathToFileURL(path.join(root, 'node_modules', name, manifest(name).main)).href);
  const [tools, cordis, skills, appBoot] = await Promise.all(['@deepseek-ai/dsh-tools', '@deepseek-ai/cordis', '@deepseek-ai/dsh-skill', '@deepseek-ai/dsh-app-boot'].map(load));
  return { tools, cordis, skills, appBoot };
}
