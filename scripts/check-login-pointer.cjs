// Existing Playwright CLI required. Only the public synthetic preview is exercised.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const cli = process.argv[2] || 'playwright-cli';
const url = process.argv[3] || 'http://127.0.0.1:4173/login.html';
const session = `nova-pointer-check-${process.pid}`;
fs.mkdirSync(path.join(root, 'output/playwright/captcha-pointer-20261030'), {recursive:true});
const run = args => execFileSync(cli, [`-s=${session}`, ...args], {cwd:root, stdio:'inherit'});
let opened = false;
try {
  run(['open', url]); opened = true;
  run(['run-code', fs.readFileSync(path.join(root, 'tests/login-pointer.browser.js'), 'utf8')]);
} finally {
  if (opened) run(['close']);
}
