// Local mock interaction checks only. This is not an authentication/security test.
// Run after integration: node --experimental-vm-modules tests/login-demo.cjs
// External review: NOVA_TEST_PROJECT=/absolute/checkout node --experimental-vm-modules <this-file>
// The readable, explicitly public text alternative supplies each fake challenge.
// jsdom does not verify real browser layout, tab navigation, CSP enforcement or AT output.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const project = process.env.NOVA_TEST_PROJECT || path.resolve(__dirname, '..');
const { JSDOM, VirtualConsole } = require(require.resolve('jsdom', { paths: [project] }));
const html = fs.readFileSync(path.join(project, 'dist/login.html'), 'utf8');
const script = fs.readFileSync(path.join(project, 'dist/js/login.js'), 'utf8');
const css = ['dist/login.css', 'dist/login-preview.css']
  .map((file) => fs.readFileSync(path.join(project, file), 'utf8')).join('\n');
const tests = [];
const test = (name, run, options = {}) => tests.push({ name, run, options });
const originalURL = 'https://nova-preview.test/login.html';

async function createDemo(options = {}) {
  const errors = [], network = [], storageWrites = [], timerHistory = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (error) => errors.push(error.message));
  const dom = new JSDOM(html, { url: originalURL, runScripts: 'outside-only', virtualConsole });
  const w = dom.window, d = w.document;
  const q = (selector) => {
    const element = d.querySelector(selector);
    assert.ok(element, `Missing demo element: ${selector}`);
    return element;
  };
  let now = 1700000000000, timerID = 0, randomSequence = 0;
  const timers = new Map();
  w.Date.now = () => now;
  w.setTimeout = (callback, delay = 0, ...args) => {
    const id = ++timerID, entry = { id, callback: () => callback(...args), at: now + Number(delay), delay: Number(delay) };
    timers.set(id, entry);
    timerHistory.push(entry);
    return id;
  };
  w.clearTimeout = (id) => timers.delete(id);
  const advance = (ms) => {
    const end = now + ms;
    let iterations = 0;
    while (true) {
      const next = [...timers.values()].filter((entry) => entry.at <= end)
        .sort((a, b) => a.at - b.at || a.id - b.id)[0];
      if (!next) break;
      assert.ok(++iterations < 100, 'Timer loop must terminate');
      timers.delete(next.id);
      now = next.at;
      next.callback();
    }
    now = end;
  };
  Object.defineProperty(w.crypto, 'getRandomValues', { configurable: true, value: (values) => {
    randomSequence++;
    values.forEach((_, index) => { values[index] = randomSequence * 5 + index; });
    return values;
  } });
  const mediaListeners = new Set();
  const system = {
    media: '(prefers-color-scheme: dark)', matches: Boolean(options.systemDark),
    addEventListener: (type, handler) => { if (type === 'change') mediaListeners.add(handler); },
    removeEventListener: (type, handler) => { if (type === 'change') mediaListeners.delete(handler); },
  };
  w.matchMedia = () => system;
  const systemDark = (value) => {
    system.matches = value;
    mediaListeners.forEach((handler) => handler({ matches: value, media: system.media }));
  };
  if (options.savedSettings !== undefined) w.localStorage.setItem('nova-settings', options.savedSettings);
  if (options.savedTheme !== undefined) w.localStorage.setItem('nova-theme', options.savedTheme);
  const realGetItem = w.Storage.prototype.getItem;
  const realSetItem = w.Storage.prototype.setItem;
  w.Storage.prototype.getItem = function (key) {
    if (options.storageUnavailable) throw new w.DOMException('Storage disabled', 'SecurityError');
    return realGetItem.call(this, key);
  };
  w.Storage.prototype.setItem = function (key, value) {
    storageWrites.push({ store: this === w.localStorage ? 'local' : 'session', key, value: String(value) });
    if (options.storageUnavailable) throw new w.DOMException('Storage disabled', 'SecurityError');
    return realSetItem.call(this, key, value);
  };
  const forbidNetwork = (kind) => (...args) => {
    network.push({ kind, args });
    throw new Error(`Static demo attempted ${kind}`);
  };
  w.fetch = forbidNetwork('fetch');
  w.XMLHttpRequest = function () { network.push({ kind: 'XMLHttpRequest' }); throw new Error('No XHR allowed'); };
  w.WebSocket = function () { network.push({ kind: 'WebSocket' }); throw new Error('No websocket allowed'); };
  w.EventSource = function () { network.push({ kind: 'EventSource' }); throw new Error('No event stream allowed'); };
  w.navigator.sendBeacon = forbidNetwork('sendBeacon');
  w.open = forbidNetwork('window.open');
  w.HTMLFormElement.prototype.submit = forbidNetwork('native form submit');
  w.HTMLFormElement.prototype.requestSubmit = forbidNetwork('native form requestSubmit');
  w.addEventListener('error', (event) => errors.push(event.error?.message || event.message));
  w.addEventListener('unhandledrejection', (event) => errors.push(String(event.reason)));
  const module = new vm.SourceTextModule(script, {
    context: dom.getInternalVMContext(), identifier: path.join(project, 'dist/js/login.js'),
  });
  w.HTMLImageElement.prototype.decode = async function () {};
  w.eval(fs.readFileSync(path.join(project, 'dist/vendor/nova-slider-captcha/slider.js'), 'utf8'));
  await module.link(async (specifier) => {
    assert.ok(['./palette.js', './login-slider-demo.js', './branding.js'].includes(specifier), 'Only local presentation helpers');
    const dependency = new vm.SourceTextModule(fs.readFileSync(path.join(project, 'dist/js', specifier), 'utf8'), { context: dom.getInternalVMContext() });
    await dependency.link(() => { throw new Error('Unexpected nested dependency'); });
    return dependency;
  });
  await module.evaluate();

  const click = (selector) => q(selector).click();
  const input = (selector, value) => {
    q(selector).value = value;
    q(selector).dispatchEvent(new w.Event('input', { bubbles: true }));
  };
  const change = (selector, value) => {
    if (typeof value === 'boolean') q(selector).checked = value;
    else q(selector).value = value;
    q(selector).dispatchEvent(new w.Event('change', { bubbles: true }));
  };
  const code = () => {
    if (q('#captcha-text').hidden) click('#captcha-alternative');
    assert.equal(q('#captcha-text').hidden, false, 'Read only the visible demo alternative');
    const value = q('#captcha-text strong').textContent.trim();
    assert.match(value, /^[A-HJ-NP-Z2-9]{5,8}$/);
    return value;
  };
  const answer = () => { const value = code(); input('#demo-captcha', value); return value; };
  const submit = () => {
    const event = new w.SubmitEvent('submit', { bubbles: true, cancelable: true, submitter: q('#login-submit') });
    q('#demo-login-form').dispatchEvent(event);
    assert.equal(event.defaultPrevented, true, 'Every submit must prevent native navigation');
  };
  if (options.policy !== 'progressive') change('#captcha-policy', 'always');
  const noSuccess = () => {
    assert.equal(q('#login-success').hidden, true);
    assert.equal(q('#demo-login-form').hidden, false);
  };
  const idle = () => {
    assert.equal(q('#login-submit').disabled, false);
    assert.equal(q('#demo-login-form').getAttribute('aria-busy'), 'false');
    ['username', 'password', 'captcha'].forEach((field) => assert.equal(q('#demo-' + field).readOnly, false));
  };
  const pendingCallback = () => {
    const entry = timerHistory.filter((timer) => timer.delay === 350).at(-1);
    assert.ok(entry, 'Demo request timer should be scheduled');
    return entry.callback;
  };
  const safe = () => {
    assert.deepEqual(errors, [], 'No uncaught JavaScript errors');
    assert.deepEqual(network, [], 'No network/auth/native submission attempts');
    assert.equal(w.location.href, originalURL, 'The fake login must not navigate or append credentials');
    assert.equal(d.cookie, '', 'The fake login must not create a cookie/session');
    assert.equal(w.sessionStorage.length, 0, 'No credentials or session data stored');
    for (const entry of storageWrites) {
      assert.equal(entry.store, 'local');
      assert.equal(entry.key, 'nova-theme', 'Theme is the only allowed persisted data');
      assert.ok(['light', 'dark', 'auto'].includes(entry.value));
    }
    for (let i = 0; i < w.localStorage.length; i++) assert.ok(['nova-theme','nova-settings'].includes(w.localStorage.key(i)));
  };
  return { w, d, q, click, input, change, code, answer, submit, noSuccess, idle, advance,
    timerHistory, pendingCallback, systemDark, storageWrites, safe, close: () => dom.window.close() };
}


test('focused login keeps required controls visible and auxiliary scenarios closed', ({ q, d }) => {
  assert.equal(d.querySelectorAll('form').length, 1);
  assert.equal(d.querySelectorAll('form input[required]').length, 3);
  assert.equal(q('.login-demo-tools').open, false);
  assert.equal(q('.login-demo-notice').closest('details'), null);
  assert.equal(q('#demo-login-title').textContent, '登录');
  assert.equal(q('#login-submit').textContent, '登录');
  assert.equal(d.querySelector('.nova-login-brand'), null);
  for (const id of ['demo-username','demo-password','demo-captcha','login-submit','login-feedback','captcha-error','captcha-announcement']) {
    assert.equal(q('#' + id).closest('details'), null, id + ' must remain outside collapsed help');
  }
  assert.ok(q('.login-demo-tools').contains(q('#expire-captcha')));
  assert.ok(q('.login-demo-tools').contains(q('#fail-login')));
});

test('expiry becomes visible only when needed and refresh restores the compact state', ({ q, click }) => {
  assert.equal(q('#captcha-expiry').classList.contains('login-visually-hidden'), true);
  click('#expire-captcha');
  assert.equal(q('#captcha-expiry').classList.contains('login-visually-hidden'), false);
  click('#refresh-captcha');
  assert.equal(q('#captcha-expiry').classList.contains('login-visually-hidden'), true);
  assert.equal(q('#login-submit').textContent, '登录');
});

test('public mock entry has local assets, no auth endpoint, CSP and visible disclosure', ({ q, d }) => {
  assert.match(q('.login-demo-notice').textContent, /虚构账号/);
  assert.match(q('.login-demo-notice').textContent, /不要输入真实密码/);
  assert.match(q('.login-demo-tools').textContent, /不提供防机器人保护/);
  assert.equal(q('#demo-username').value, 'demo_admin');
  assert.equal(q('#demo-password').value, 'NovaPreview123');
  assert.equal(q('#demo-login-form').getAttribute('autocomplete'), 'off');
  assert.equal(q('#demo-login-form').hasAttribute('action'), false);
  const csp = q('meta[http-equiv="Content-Security-Policy"]').content;
  assert.match(csp, /(?:^|;)\s*connect-src 'none'(?:;|$)/);
  assert.match(csp, /(?:^|;)\s*form-action 'none'(?:;|$)/);
  assert.deepEqual([...d.querySelectorAll('script')].map((node) => [node.type, node.getAttribute('src')]), [['', './js/preferences-init.js'], ['', './vendor/nova-slider-captcha/slider.js'], ['module', './js/login.js']]);
  for (const element of d.querySelectorAll('[src],link[href]')) {
    const value = element.getAttribute('src') || element.getAttribute('href');
    assert.ok(value.startsWith('./'), `Only same-directory assets expected: ${value}`);
    assert.ok(fs.existsSync(path.resolve(project, 'dist', value)), `Missing asset: ${value}`);
  }
});

test('form, alternative and outcome expose labels, described errors and focus targets', ({ q, d, click }) => {
  for (const name of ['username', 'password', 'captcha']) {
    const field = q('#demo-' + name);
    assert.ok(d.querySelector(`label[for="${field.id}"]`));
    assert.equal(field.required, true);
    for (const id of field.getAttribute('aria-describedby').split(/\s+/)) assert.ok(d.getElementById(id));
  }
  assert.equal(q('#captcha-graphic').getAttribute('role'), 'img');
  assert.ok(q('#captcha-graphic').getAttribute('aria-label'));
  assert.equal(q('#captcha-announcement').getAttribute('aria-live'), 'polite');
  assert.equal(q('#login-feedback').getAttribute('role'), 'alert');
  assert.equal(q('#login-feedback').tabIndex, -1);
  assert.equal(q('#login-success-title').tabIndex, -1);
  assert.equal(q('#demo-login-title').tabIndex, -1);
  assert.equal(q('.login-skip').getAttribute('href'), '#demo-login-title');
  for (const id of ['password-visible', 'refresh-captcha', 'captcha-alternative', 'expire-captcha', 'login-again']) {
    assert.equal(q('#' + id).type, 'button');
    assert.ok(q('#' + id).tabIndex >= 0, `${id} must be natively keyboard-focusable`);
  }
  q('#refresh-captcha').focus();
  assert.equal(d.activeElement, q('#refresh-captcha'));
  click('#refresh-captcha');
  assert.equal(d.activeElement, q('#demo-captcha'));
  assert.match(css, /:focus-visible/);
  assert.match(css, /\.login-skip:focus/);
  assert.match(css, /\[hidden\]\s*\{\s*display\s*:\s*none\s*!important/);
});

test('text inputs explicitly match the shared login field styling selectors', ({ q }) => {
  assert.equal(q('#demo-username').getAttribute('type'), 'text');
  assert.equal(q('#demo-captcha').getAttribute('type'), 'text');
  assert.equal(q('#demo-password').getAttribute('type'), 'password');
  assert.match(css, /input\[type=text\]/);
});

test('text alternative toggles visibly and announces its demo scope', ({ q, click, code }) => {
  assert.equal(q('#captcha-text').hidden, true);
  assert.equal(q('#captcha-graphic').hidden, false);
  const value = code();
  assert.equal(q('#captcha-graphic').hidden, true);
  assert.equal(q('#captcha-alternative').getAttribute('aria-expanded'), 'true');
  assert.equal(q('#captcha-alternative').getAttribute('aria-controls'), 'captcha-text');
  assert.match(q('#captcha-announcement').textContent, /文字验证/);
  click('#captcha-alternative');
  assert.equal(q('#captcha-text').hidden, true);
  assert.equal(q('#captcha-graphic').hidden, false);
  assert.equal(q('#captcha-alternative').getAttribute('aria-expanded'), 'false');
  assert.equal(code(), value, 'Switching presentation must preserve the current challenge');
});

test('refresh changes challenge, clears answer/error, retains alternative, focuses input', ({ q, d, click, code, input, submit }) => {
  const previous = code();
  input('#demo-captcha', 'WRNG');
  submit();
  assert.equal(q('#demo-captcha').getAttribute('aria-invalid'), 'true');
  input('#demo-captcha', 'OLD');
  click('#refresh-captcha');
  assert.notEqual(code(), previous);
  assert.equal(q('#demo-captcha').value, '');
  assert.equal(q('#captcha-error').textContent, '');
  assert.equal(q('#demo-captcha').hasAttribute('aria-invalid'), false);
  assert.equal(q('#captcha-text').hidden, false);
  assert.equal(d.activeElement, q('#demo-captcha'));
  assert.match(q('#captcha-announcement').textContent, /已更新/);
});

for (const name of ['username', 'password', 'captcha']) {
  test(`missing ${name} blocks success and focuses its described error`, (ui) => {
    ui.answer();
    ui.input('#demo-' + name, '');
    ui.submit();
    ui.advance(1000);
    ui.noSuccess();
    assert.equal(ui.q('#demo-' + name).getAttribute('aria-invalid'), 'true');
    assert.ok(ui.q('#' + name + '-error').textContent);
    assert.equal(ui.d.activeElement, ui.q('#demo-' + name));
    ui.idle();
  });
}

test('all missing fields report errors and focus the first', (ui) => {
  ['username', 'password', 'captcha'].forEach((name) => ui.input('#demo-' + name, ''));
  ui.submit();
  ui.advance(1000);
  ui.noSuccess();
  ['username', 'password', 'captcha'].forEach((name) => assert.equal(ui.q('#demo-' + name).getAttribute('aria-invalid'), 'true'));
  assert.equal(ui.d.activeElement, ui.q('#demo-username'));
});

test('wrong challenge never authenticates and invalidates its prior answer', (ui) => {
  const previous = ui.code();
  ui.input('#demo-captcha', '!!!!');
  ui.submit();
  ui.advance(1000);
  ui.noSuccess();
  assert.equal(ui.q('#demo-captcha').value, '');
  assert.notEqual(ui.code(), previous);
  assert.match(ui.q('#captcha-error').textContent, /不正确/);
  assert.equal(ui.d.activeElement, ui.q('#demo-captcha'));
});

test('manual expiry blocks submission, announces error and refresh permits retry', (ui) => {
  ui.answer();
  ui.click('#expire-captcha');
  ui.submit();
  ui.advance(1000);
  ui.noSuccess();
  assert.match(ui.q('#captcha-error').textContent, /过期/);
  assert.match(ui.q('#captcha-expiry').textContent, /过期/);
  assert.equal(ui.d.activeElement, ui.q('#demo-captcha'));
  ui.click('#refresh-captcha');
  ui.answer();
  ui.submit();
  ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
});

test('naturally expired challenge blocks submission before the UI timer fires', (ui) => {
  ui.answer();
  ui.advance(120000);
  ui.submit();
  ui.advance(1000);
  ui.noSuccess();
  assert.match(ui.q('#captcha-error').textContent, /过期/);
  ui.idle();
});

test('natural expiry during a pending request invalidates the eventual success', (ui) => {
  ui.answer();
  ui.advance(119800);
  ui.submit();
  ui.advance(351);
  ui.noSuccess();
  ui.idle();
  assert.match(ui.q('#captcha-announcement').textContent, /过期/);
});

for (const [name, value] of [['username', 'someone_else'], ['password', 'incorrect-password'], ['password', 'NovaPreview123 ']]) {
  test(`non-demo ${name} ${JSON.stringify(value)} is rejected and allows corrected retry`, (ui) => {
    ui.input('#demo-' + name, value);
    const previous = ui.answer();
    ui.submit();
    ui.advance(350);
    ui.noSuccess();
    ui.idle();
    assert.match(ui.q('#login-feedback').textContent, /用户名或密码不正确/);
    assert.equal(ui.d.activeElement, ui.q('#login-feedback'));
    assert.notEqual(ui.code(), previous);
    assert.equal(ui.q('#demo-captcha').value, '');
    ui.input('#demo-' + name, name === 'username' ? 'demo_admin' : 'NovaPreview123');
    ui.answer();
    ui.submit();
    ui.advance(350);
    assert.equal(ui.q('#login-success').hidden, false);
  });
}

test('only fake credentials plus readable challenge reach one success on repeated submit', async (ui) => {
  const transitions = [];
  const observer = new ui.w.MutationObserver((records) => transitions.push(...records));
  observer.observe(ui.q('#login-success'), { attributes: true, attributeFilter: ['hidden'] });
  ui.input('#demo-username', ' demo_admin ');
  ui.input('#demo-captcha', ' ' + ui.code().toLowerCase() + ' ');
  ui.submit();
  ui.submit();
  ui.submit();
  assert.equal(ui.q('#demo-login-form').getAttribute('aria-busy'), 'true');
  assert.equal(ui.q('#login-submit').disabled, true);
  ['username', 'password', 'captcha'].forEach((name) => assert.equal(ui.q('#demo-' + name).readOnly, true));
  assert.equal(ui.timerHistory.filter((timer) => timer.delay === 350).length, 1);
  ui.advance(349);
  ui.noSuccess();
  ui.advance(1);
  await Promise.resolve();
  assert.equal(ui.q('#login-success').hidden, false);
  assert.equal(ui.q('#demo-login-form').hidden, true);
  assert.equal(ui.d.activeElement, ui.q('#login-success-title'));
  ['username', 'password', 'captcha'].forEach((name) => assert.equal(ui.q('#demo-' + name).value, ''));
  assert.match(ui.q('#login-success').textContent, /没有建立真实登录会话/);
  assert.equal(transitions.length, 1, 'Exactly one visible success transition');
  observer.disconnect();
});

test('simulated request failure is one-shot and retry succeeds with a fresh challenge', (ui) => {
  ui.change('#fail-login', true);
  const previous = ui.answer();
  ui.submit();
  assert.equal(ui.q('#fail-login').checked, false);
  ui.advance(350);
  ui.noSuccess();
  ui.idle();
  assert.match(ui.q('#login-feedback').textContent, /请求失败（模拟）/);
  assert.equal(ui.q('#login-feedback').hidden, false);
  assert.equal(ui.d.activeElement, ui.q('#login-feedback'));
  assert.notEqual(ui.code(), previous);
  ui.answer();
  ui.submit();
  assert.equal(ui.q('#login-feedback').hidden, true);
  ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
});

for (const action of ['refresh-captcha', 'expire-captcha']) {
  test(`${action} during pending request defeats its stale callback and supports retry`, (ui) => {
    ui.answer();
    ui.submit();
    const stale = ui.pendingCallback();
    ui.advance(100);
    ui.click('#' + action);
    ui.noSuccess();
    ui.idle();
    stale(); // Simulate a callback already queued by the browser before clearTimeout.
    ui.advance(500);
    ui.noSuccess();
    if (action === 'expire-captcha') ui.click('#refresh-captcha');
    ui.answer();
    ui.submit();
    stale(); // A cancelled earlier generation must not cancel or complete the new attempt.
    assert.equal(ui.q('#login-submit').disabled, true);
    ui.advance(350);
    assert.equal(ui.q('#login-success').hidden, false);
  });
}

test('pagehide clears password and invalidates pending callback', (ui) => {
  ui.answer();
  ui.submit();
  const stale = ui.pendingCallback();
  ui.w.dispatchEvent(new ui.w.Event('pagehide'));
  assert.equal(ui.q('#demo-password').value, '');
  stale();
  ui.advance(200000);
  ui.noSuccess();
  ui.idle();
});

test('password visibility preserves value, announces state, and resets after success', (ui) => {
  ui.click('#password-visible');
  assert.equal(ui.q('#demo-password').type, 'text');
  assert.equal(ui.q('#demo-password').value, 'NovaPreview123');
  assert.equal(ui.q('#password-visible').getAttribute('aria-pressed'), 'true');
  assert.match(ui.q('#password-visible').getAttribute('aria-label'), /隐藏/);
  ui.click('#password-visible');
  assert.equal(ui.q('#demo-password').type, 'password');
  assert.equal(ui.q('#password-visible').getAttribute('aria-pressed'), 'false');
  assert.match(ui.q('#password-visible').getAttribute('aria-label'), /显示/);
  ui.click('#password-visible');
  ui.answer();
  ui.submit();
  ui.advance(350);
  assert.equal(ui.q('#demo-password').value, '');
  ui.click('#login-again');
  ui.noSuccess();
  ui.idle();
  assert.equal(ui.q('#demo-password').type, 'password');
  assert.equal(ui.q('#demo-password').value, 'NovaPreview123');
  assert.equal(ui.q('#password-visible').getAttribute('aria-pressed'), 'false');
  assert.equal(ui.q('#demo-captcha').value, '');
  assert.equal(ui.d.activeElement, ui.q('#demo-username'));
});

test('default theme is light and initialization does not persist anything', (ui) => {
  assert.equal(ui.d.documentElement.dataset.theme, 'light');
  assert.equal(ui.d.documentElement.dataset.themeMode, 'light');
  assert.equal(ui.q('#login-appearance').value, 'light');
  assert.deepEqual(ui.storageWrites, []);
});

test('saved dark preference loads and ignores system updates', (ui) => {
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  assert.equal(ui.q('#login-appearance').value, 'dark');
  ui.systemDark(true);
  ui.systemDark(false);
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  assert.deepEqual(ui.storageWrites, []);
}, { savedTheme: 'dark' });

test('manual preference stores only its mode and stays stable across system changes', (ui) => {
  ui.change('#login-appearance', 'dark');
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  assert.equal(ui.w.localStorage.getItem('nova-theme'), 'dark');
  ui.systemDark(true);
  ui.systemDark(false);
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  ui.change('#login-appearance', 'light');
  assert.equal(ui.d.documentElement.dataset.theme, 'light');
  assert.equal(ui.w.localStorage.getItem('nova-theme'), 'light');
});

test('saved auto preference follows system changes without rewriting stored mode', (ui) => {
  assert.equal(ui.d.documentElement.dataset.themeMode, 'auto');
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  assert.equal(ui.q('#login-appearance').value, 'auto');
  ui.systemDark(false);
  assert.equal(ui.d.documentElement.dataset.theme, 'light');
  assert.equal(ui.w.localStorage.getItem('nova-theme'), 'auto');
  ui.systemDark(true);
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  assert.deepEqual(ui.storageWrites, []);
}, { savedTheme: 'auto', systemDark: true });

test('selecting auto persists auto and changing to manual stops system following', (ui) => {
  ui.change('#login-appearance', 'auto');
  assert.equal(ui.w.localStorage.getItem('nova-theme'), 'auto');
  ui.systemDark(true);
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  ui.change('#login-appearance', 'light');
  ui.systemDark(false);
  ui.systemDark(true);
  assert.equal(ui.d.documentElement.dataset.theme, 'light');
  assert.equal(ui.w.localStorage.getItem('nova-theme'), 'light');
});

test('invalid stored appearance safely falls back to light', (ui) => {
  assert.equal(ui.d.documentElement.dataset.theme, 'light');
  assert.equal(ui.q('#login-appearance').value, 'light');
  assert.deepEqual(ui.storageWrites, []);
}, { savedTheme: 'unexpected-value' });

test('unavailable storage never prevents theme changes or fake login', (ui) => {
  ui.change('#login-appearance', 'dark');
  assert.equal(ui.d.documentElement.dataset.theme, 'dark');
  ui.answer();
  ui.submit();
  ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
}, { storageUnavailable: true });


for (const length of [5, 6, 8]) {
  test(`image supports ${length} characters without input truncation`, (ui) => {
    ui.change('#captcha-length', String(length));
    assert.equal(ui.code().length, length);
    assert.equal(ui.q('#demo-captcha').hasAttribute('maxlength'), false);
    ui.answer(); ui.submit(); ui.advance(350);
    assert.equal(ui.q('#login-success').hidden, false);
  });
}

test('progressive default has no challenge and permits a normal demo login', (ui) => {
  assert.equal(ui.q('#image-captcha-section').hidden, true);
  assert.equal(ui.q('#demo-captcha').disabled, true);
  assert.equal(ui.q('#demo-captcha').required, false);
  ui.submit(); ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
}, { policy: 'progressive' });

test('two failures escalate immediately and hidden input cannot bypass required challenge', (ui) => {
  ui.input('#demo-password', 'wrong');
  ui.submit(); ui.advance(350);
  assert.equal(ui.q('#image-captcha-section').hidden, true);
  ui.submit(); ui.advance(350);
  assert.equal(ui.q('#image-captcha-section').hidden, false);
  ui.input('#demo-password', 'NovaPreview123');
  ui.submit(); ui.advance(350); ui.noSuccess();
  assert.match(ui.q('#captcha-error').textContent, /请输入/);
  ui.answer(); ui.submit(); ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
  ui.click('#login-again');
  assert.equal(ui.q('#image-captcha-section').hidden, true);
}, { policy: 'progressive' });

test('trusted anomaly simulation escalates either provider; reset clears local risk', (ui) => {
  ui.click('#trigger-risk');
  assert.equal(ui.q('#image-captcha-section').hidden, false);
  ui.click('#reset-risk');
  assert.equal(ui.q('#image-captcha-section').hidden, true);
  ui.change('#captcha-provider', 'slider'); ui.click('#trigger-risk');
  assert.equal(ui.q('#slider-captcha-section').hidden, false);
  assert.ok(ui.q('nova-slider-demo'));
  ui.click('#reset-risk');
  assert.equal(ui.d.querySelector('nova-slider-demo'), null);
}, { policy: 'progressive' });

const settleSlider = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
async function solveSlider(ui) {
  await settleSlider();
  const slider = ui.q('nova-slider-demo');
  assert.equal(slider.state, 'ready');
  slider.move(slider.demoPuzzle.x); // Public synthetic answer; not a security test.
  slider.range.dispatchEvent(new ui.w.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  await settleSlider();
  assert.equal(slider.state, 'success');
  return slider;
}

test('original slider component keyboard solve and one-time demo consumption', async (ui) => {
  ui.change('#captcha-provider', 'slider');
  ui.submit(); ui.noSuccess();
  assert.match(ui.q('#slider-error').textContent, /请先完成/);
  const slider = await solveSlider(ui);
  assert.equal(ui.d.querySelectorAll('[name="nova_slider_token"]').length, 1);
  ui.submit(); ui.submit(); ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
  assert.equal(slider.consumeDemoToken(), false);
  assert.equal(slider.live, false);
});

test('slider proof expiry, refresh and wrong password require a fresh solution', async (ui) => {
  ui.change('#captcha-provider', 'slider');
  await solveSlider(ui); ui.advance(60001);
  ui.submit(); ui.noSuccess();
  await ui.q('nova-slider-demo').refresh();
  await solveSlider(ui);
  ui.input('#demo-password', 'wrong'); ui.submit(); ui.advance(350);
  ui.noSuccess(); await settleSlider();
  assert.equal(ui.q('nova-slider-demo').getToken(), '');
  ui.input('#demo-password', 'NovaPreview123');
  ui.submit(); ui.noSuccess();
  await solveSlider(ui); ui.submit(); ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
});

test('provider change cancels a pending attempt and disconnects old slider', async (ui) => {
  ui.change('#captcha-provider', 'slider');
  const slider = await solveSlider(ui);
  ui.submit(); const stale = ui.pendingCallback();
  ui.change('#captcha-provider', 'image'); stale(); ui.advance(350);
  ui.noSuccess();
  assert.equal(slider.live, false);
  assert.equal(slider.getToken(), '');
  ui.answer(); ui.submit(); ui.advance(350);
  assert.equal(ui.q('#login-success').hidden, false);
});

test('vendored slider bytes match the declared MIT source manifest', () => {
  const crypto = require('node:crypto');
  const base = path.join(project, 'dist/vendor/nova-slider-captcha');
  const manifest = JSON.parse(fs.readFileSync(path.join(base, 'manifest.json')));
  assert.equal(manifest.version, '0.2.0');
  assert.equal(manifest.license, 'MIT');
  for (const [name, digest] of Object.entries(manifest.files))
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(base, name))).digest('hex'), digest);
});

test('login and decorative initial read the same configured name as the dashboard', (ui) => {
  assert.equal(ui.q('[data-brand-name]').textContent,'星河后台');
  for(const badge of ui.d.querySelectorAll('[data-brand-initial]')) assert.equal(badge.textContent,'星');
  assert.equal(ui.d.title,'登录页预览 · 星河后台');
}, {savedSettings:JSON.stringify({brandName:'星河后台',workspace:'Example',animations:true})});

test('cross-tab brand update preserves entered credentials and current CAPTCHA', (ui) => {
  const code=ui.answer();ui.input('#demo-username','unfinished-user');
  // Populate shared storage without recording a user-originated demo write.
  const next=JSON.stringify({brandName:'Atlas Admin',workspace:'Example',animations:true});
  ui.w.localStorage.setItem('nova-settings',next);
  ui.storageWrites.pop();
  ui.w.dispatchEvent(new ui.w.StorageEvent('storage',{key:'nova-settings',newValue:next}));
  assert.equal(ui.q('[data-brand-name]').textContent,'Atlas Admin');
  assert.equal(ui.q('[data-brand-initial]').textContent,'A');
  assert.equal(ui.q('#demo-username').value,'unfinished-user');
  assert.equal(ui.q('#demo-captcha').value,code);
});

test('malformed stored identity falls back without writing storage', (ui) => {
  assert.equal(ui.q('[data-brand-name]').textContent,'NOVA');
  assert.equal(ui.q('[data-brand-initial]').textContent,'N');
  assert.deepEqual(ui.storageWrites,[]);
  const partial = JSON.stringify({brandName:'Partial invalid settings'});
  ui.w.localStorage.setItem('nova-settings',partial);
  ui.storageWrites.pop();
  ui.w.dispatchEvent(new ui.w.StorageEvent('storage',{key:'nova-settings',newValue:partial}));
  assert.equal(ui.q('[data-brand-name]').textContent,'NOVA');
  assert.deepEqual(ui.storageWrites,[]);
}, {savedSettings:'invalid-json'});

async function main() {
  assert.equal(typeof vm.SourceTextModule, 'function', 'Use node --experimental-vm-modules');
  let passed = 0, failed = 0;
  for (const { name, run, options } of tests) {
    let ui;
    try {
      ui = await createDemo(options);
      await run(ui);
      ui.safe();
      console.log('PASS', name);
      passed++;
    } catch (error) {
      console.error('FAIL', name, '\n' + error.stack);
      failed++;
    } finally {
      ui?.close();
    }
  }
  console.log(`TOTAL ${passed} passed, ${failed} failed (Node/jsdom static login demo)`);
  if (failed) process.exitCode = 1;
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
