const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const script = 'scripts/sync-login-css.cjs';
const source = 'django-theme/src/nova_admin/static/nova_admin/login.css';
const target = 'dist/login.css';
const run = (directory, ...args) => spawnSync(process.execPath, [path.join(directory, script), ...args], { encoding: 'utf8', cwd: os.tmpdir() });
const state = file => {
  const stat = fs.statSync(file, { bigint: true });
  return { bytes: fs.readFileSync(file), mtime: stat.mtimeNs, ctime: stat.ctimeNs };
};
let count = 0;
const test = (name, body) => { body(); count++; console.log('PASS', name); };
function fixture(body) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'nova-login-css-'));
  try {
    for (const file of [source, target, script]) fs.mkdirSync(path.dirname(path.join(directory, file)), { recursive: true });
    fs.copyFileSync(path.join(root, script), path.join(directory, script));
    const bytes = Buffer.from('/* 品牌 CSS: preserve CRLF and final newline */\r\nbody { border-radius: var(--radius); }\r\n');
    fs.writeFileSync(path.join(directory, source), bytes);
    fs.writeFileSync(path.join(directory, target), bytes);
    body(directory);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
}
test('shared login CSS matches the theme byte for byte and repository check writes nothing', () => {
  const beforeSource = state(path.join(root, source)), beforeTarget = state(path.join(root, target));
  const result = run(root, '--check');
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(beforeSource.bytes, beforeTarget.bytes);
  assert.deepEqual(state(path.join(root, source)), beforeSource);
  assert.deepEqual(state(path.join(root, target)), beforeTarget);
});
test('injected target drift is detected with nonzero exit and both fixture files unchanged', () => fixture(directory => {
  fs.appendFileSync(path.join(directory, target), '/* temporary drift */\n');
  const beforeSource = state(path.join(directory, source)), beforeTarget = state(path.join(directory, target));
  const result = run(directory, '--check');
  assert.equal(result.status, 1);
  assert.equal(JSON.parse(result.stdout).status, 'drift');
  assert.match(result.stderr, /npm run sync:login-css/);
  assert.deepEqual(state(path.join(directory, source)), beforeSource);
  assert.deepEqual(state(path.join(directory, target)), beforeTarget);
}));
test('explicit sync restores exact source bytes and an already synchronized file is not rewritten', () => fixture(directory => {
  fs.appendFileSync(path.join(directory, target), '/* drift */');
  const original = state(path.join(directory, source));
  let result = run(directory);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).updated, true);
  assert.deepEqual(fs.readFileSync(path.join(directory, target)), original.bytes);
  assert.deepEqual(state(path.join(directory, source)), original);
  const synchronized = state(path.join(directory, target));
  result = run(directory);
  assert.equal(result.status, 0);
  assert.equal(JSON.parse(result.stdout).updated, false);
  assert.deepEqual(state(path.join(directory, target)), synchronized);
}));
test('check detects a missing target without creating it or altering the source', () => fixture(directory => {
  fs.unlinkSync(path.join(directory, target));
  const original = state(path.join(directory, source));
  const result = run(directory, '--check');
  assert.equal(result.status, 1);
  assert.equal(JSON.parse(result.stdout).target_sha256, null);
  assert.equal(fs.existsSync(path.join(directory, target)), false);
  assert.deepEqual(state(path.join(directory, source)), original);
}));
console.log('TOTAL', count, 'shared login CSS checks passed');
