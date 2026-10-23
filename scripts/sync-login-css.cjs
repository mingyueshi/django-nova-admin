#!/usr/bin/env node
// The theme owns this stylesheet; the static preview consumes an exact copy.
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');

const root = path.resolve(__dirname, '..');
const source = 'django-theme/src/nova_admin/static/nova_admin/login.css';
const target = 'dist/login.css';
const args = process.argv.slice(2);
if (args.length > 1 || (args.length === 1 && args[0] !== '--check')) {
  console.error('Usage: node scripts/sync-login-css.cjs [--check]');
  process.exit(2);
}
const check = args[0] === '--check';
try {
  const expected = fs.readFileSync(path.join(root, source));
  let actual = null;
  try {
    actual = fs.readFileSync(path.join(root, target));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const drift = actual === null || !expected.equals(actual);
  if (drift && !check) {
    fs.mkdirSync(path.dirname(path.join(root, target)), { recursive: true });
    fs.writeFileSync(path.join(root, target), expected);
    actual = expected;
  }
  const hash = bytes => bytes === null ? null : createHash('sha256').update(bytes).digest('hex');
  console.log(JSON.stringify({
    status: check && drift ? 'drift' : 'passed',
    mode: check ? 'check' : 'sync',
    source, target, updated: !check && drift,
    source_sha256: hash(expected), target_sha256: hash(actual),
  }));
  if (check && drift) {
    console.error('Shared login CSS differs. Edit the theme source, then run npm run sync:login-css.');
    process.exitCode = 1;
  }
} catch (error) {
  console.error('Cannot synchronize shared login CSS: ' + error.message);
  process.exitCode = 1;
}
