// Test the selected exact Node/npm pair without changing the dependency lock.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const options = {};
for (let i = 0; i < args.length; i += 2) {
  if (!['--node', '--npm', '--logs', '--sidebars'].includes(args[i]) || !args[i + 1] || options[args[i]]) throw Error('Expected --node, --npm, --logs, --sidebars');
  options[args[i]] = args[i + 1];
}
if (Object.keys(options).length !== 4) throw Error('Four explicit arguments required');
const selected = JSON.parse(fs.readFileSync(path.join(root, 'ci/matrix.json'))).node.find(row => row.node === options['--node'] && row.npm === options['--npm']);
if (!selected || process.version !== 'v' + selected.node) throw Error('Unexpected Node runtime');
const logs = path.resolve(options['--logs']);
if (logs === root || logs.startsWith(root + path.sep)) throw Error('Logs must be outside checkout');
fs.mkdirSync(logs, { recursive: false });
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toLowerCase().startsWith('npm_config_') && !['NODE_OPTIONS', 'NODE_PATH', 'NOVA_TEST_PROJECT'].includes(key)));
env.PATH = path.dirname(process.execPath) + path.delimiter + process.env.PATH;
env.NPM_CONFIG_USERCONFIG = path.join(logs, 'empty-npmrc');
env.NPM_CONFIG_GLOBALCONFIG = path.join(logs, 'empty-global-npmrc');
env.NPM_CONFIG_CACHE = path.join(logs, 'npm-cache');
env.NPM_CONFIG_ENGINE_STRICT = 'true';
fs.writeFileSync(env.NPM_CONFIG_USERCONFIG, '');
fs.writeFileSync(env.NPM_CONFIG_GLOBALCONFIG, '');
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex');
const before = Object.fromEntries(['package.json', 'package-lock.json'].map(file => [file, sha(file)]));
const steps = [];
function run(name, command, values) {
  const out = fs.openSync(path.join(logs, name + '.log'), 'w');
  let result;
  try { result = spawnSync(command, values, { cwd: root, env, stdio: ['ignore', out, out], timeout: 300000 }); }
  finally { fs.closeSync(out); }
  steps.push({ name, exitCode: result.status, signal: result.signal, error: result.error?.message });
  fs.writeFileSync(path.join(logs, 'steps.json'), JSON.stringify(steps, null, 2));
  if (result.status !== 0 || result.error || result.signal) throw Error(`${name} failed; inspect ${logs}`);
  return fs.readFileSync(path.join(logs, name + '.log'), 'utf8');
}
const versionLines = run('npm-version', 'npm', ['--version']).trim().split(/\r?\n/).filter(line => /^\d+\.\d+\.\d+$/.test(line));
if (versionLines.length !== 1) throw Error('Expected one unambiguous npm version');
const npmVersion = versionLines[0];
if (npmVersion !== selected.npm) throw Error('Bundled npm differs from matrix');
fs.writeFileSync(path.join(logs, 'runtime.json'), JSON.stringify({ node: process.version, npm: npmVersion, platform: process.platform, arch: process.arch, execPath: process.execPath }, null, 2));
run('install', 'npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund', '--registry=https://registry.npmjs.org']);
const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json')));
for (const [file, metadata] of Object.entries(lock.packages)) {
  if (!file) continue;
  const actual = JSON.parse(fs.readFileSync(path.join(root, file, 'package.json')));
  if (actual.version !== metadata.version) throw Error(`Installed version differs: ${file}`);
}
const tree = run('dependency-tree', 'npm', ['ls', '--all', '--json']);
// npm may emit proxy warnings on stderr; retain them in the log, keep JSON separate.
const jsonStart = tree.indexOf('{');
fs.writeFileSync(path.join(logs, 'dependency-tree.json'), JSON.stringify(JSON.parse(tree.slice(jsonStart)), null, 2));
run('frontend', 'npm', ['test']);
const sidebars = path.resolve(options['--sidebars']);
const versions = Object.keys(JSON.parse(fs.readFileSync(path.join(root, 'ci/matrix.json'))).django_wheels);
run('navigation', process.execPath, ['django-theme/scripts/test-navigation.mjs', ...versions.map(version => path.join(sidebars, `django-${version}.js`))]);
run('enhancements', process.execPath, ['django-theme/scripts/test-enhancements.mjs']);
run('captcha', process.execPath, ['django-theme/scripts/test-captcha.mjs']);
run('captcha-dialog', process.execPath, ['--test', 'django-theme/scripts/test-captcha-dialog.mjs']);
for (const [file, hash] of Object.entries(before)) if (sha(file) !== hash) throw Error(`Dependency input changed: ${file}`);
fs.writeFileSync(path.join(logs, 'inputs.json'), JSON.stringify(before, null, 2));
console.log(`PASS Node ${selected.node} / npm ${selected.npm}; lock unchanged`);
