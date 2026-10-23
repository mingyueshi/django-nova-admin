const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { JSDOM } = require('jsdom');
const { createApp } = require('./dom-runtime.cjs');
const root = path.join(__dirname, '../dist');
const keys = ['default', 'teal', 'indigo', 'violet', 'terracotta', 'graphite', 'midnight', 'forest', 'amber', 'ocean', 'slate', 'plum', 'coffee', 'glacier', 'rose', 'olive', 'ink'];
let count = 0;
function check(name, run) { run(); console.log('PASS', name); count++; }
const wait = () => new Promise(resolve => setTimeout(resolve, 10));
async function login(storage = {}, fail = false) {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'login.html'), 'utf8'), { url: 'https://example.test/login.html', runScripts: 'outside-only' });
  const w = dom.window;
  w.matchMedia = () => ({ matches: false, addEventListener() {} });
  for (const [key, value] of Object.entries(storage)) w.localStorage.setItem(key, value);
  if (fail) w.Storage.prototype.getItem = () => { throw new Error('Denied'); };
  w.eval(fs.readFileSync(path.join(root, 'js/preferences-init.js'), 'utf8'));
  w.eval(fs.readFileSync(path.join(root, 'vendor/nova-slider-captcha/slider.js'), 'utf8'));
  const context = dom.getInternalVMContext();
  const module = new vm.SourceTextModule(fs.readFileSync(path.join(root, 'js/login.js'), 'utf8'), { context });
  await module.link(async spec => {
    assert.ok(['./palette.js', './login-slider-demo.js'].includes(spec));
    const helper = new vm.SourceTextModule(fs.readFileSync(path.join(root, 'js', spec), 'utf8'), { context });
    await helper.link(() => { throw new Error('Unexpected import'); });
    return helper;
  });
  await module.evaluate();
  return { w, d: w.document, close: () => w.close() };
}
(async () => {
  for (const key of keys) {
    const app = await createApp({ storage: { 'nova-palette': key, 'nova-theme': 'auto' }, systemDark: true });
    check(`${key}: independently restores auto/dark and palette`, () => {
      assert.equal(app.d.documentElement.dataset.palette, key);
      assert.equal(app.d.documentElement.dataset.theme, 'dark');
      assert.equal(app.w.localStorage.getItem('nova-theme'), 'auto');
    });
    app.setSystemDark(false);
    check(`${key}: system changes keep palette`, () => {
      assert.equal(app.d.documentElement.dataset.palette, key);
      assert.equal(app.d.documentElement.dataset.theme, 'light');
    });
    const cross = await login({ 'nova-palette': key, 'nova-theme': 'auto' });
    check(`${key}: login restores same independent preference`, () => {
      assert.equal(cross.d.documentElement.dataset.palette, key);
      assert.equal(cross.d.querySelector('#login-palette').value, key);
    });
    cross.close(); app.close();
  }
  const app = await createApp({ url: 'https://example.test/#settings', storage: { 'nova-palette': 'bad-value', 'nova-theme': 'dark', 'other-business': 'keep' } });
  check('invalid stored palette falls back without deleting theme or data', () => {
    assert.equal(app.d.documentElement.dataset.palette, 'default');
    assert.equal(app.w.localStorage.getItem('nova-theme'), 'dark');
    assert.equal(app.w.localStorage.getItem('other-business'), 'keep');
  });
  check('gallery presents 16 named preset buttons outside the workspace form', () => {
    const cards = [...app.d.querySelectorAll('[data-palette-card]')];
    assert.deepEqual(cards.map(card => card.dataset.paletteCard), keys.slice(1));
    assert.ok(cards.every(card => card.type === 'button' && card.closest('form') === null));
    assert.equal(app.d.querySelector('[data-palette-current]').getAttribute('role'), 'status');
  });
  for (const key of keys.slice(1)) {
    const card = app.d.querySelector(`[data-palette-card="${key}"]`);
    card.focus(); card.querySelector('.palette-mini').click();
    check(`${key}: card applies and persists without losing focus or appearance`, () => {
      assert.equal(app.d.documentElement.dataset.palette, key);
      assert.equal(app.d.querySelector('#palette-mode').value, key);
      assert.equal(app.w.localStorage.getItem('nova-palette'), key);
      assert.equal(app.w.localStorage.getItem('nova-theme'), 'dark');
      assert.equal(app.d.querySelectorAll('[data-palette-card][aria-pressed="true"]').length, 1);
      assert.equal(card.getAttribute('aria-pressed'), 'true');
      assert.equal(card.querySelector('.palette-card-state').textContent, '使用中');
      assert.equal(app.d.activeElement, card);
    });
  }
  app.d.querySelector('[data-palette-default]').click();
  check('default restoration clears active cards and preserves independent data', () => {
    assert.equal(app.d.querySelectorAll('[data-palette-card][aria-pressed="true"]').length, 0);
    assert.equal(app.d.querySelector('#palette-mode').value, 'default');
    assert.match(app.d.querySelector('[data-palette-current]').textContent, /默认配色.*深色/);
    assert.equal(app.w.localStorage.getItem('other-business'), 'keep');
  });
  for (const key of [...keys, ...keys].reverse()) {
    const select = app.d.querySelector('#palette-mode'); select.value = key;
    select.dispatchEvent(new app.w.Event('change', { bubbles: true }));
    check(`repeated selection ${key}`, () => {
      assert.equal(app.d.documentElement.dataset.palette, key);
      assert.equal(app.w.localStorage.getItem('nova-palette'), key);
      assert.equal(app.w.localStorage.getItem('nova-theme'), 'dark');
    });
  }
  app.d.querySelector('[data-action="native"]').click(); await wait();
  const nativeChange = (id, value) => { const el = app.d.querySelector(id); el.value = value; el.dispatchEvent(new app.w.Event('change', { bubbles: true })); };
  nativeChange('#native-look', 'auto'); nativeChange('#native-density', 'compact'); nativeChange('#native-page', 'changeform');
  for (const key of keys.slice(1)) {
    nativeChange('#native-palette', key);
    check(`${key}: comparison selects safe supported representative`, () => {
      assert.ok(app.d.querySelector('#native-preview').getAttribute('src').endsWith(`/palette-${key}-light/index.html`));
      assert.equal(app.d.querySelector('#native-density').disabled, true);
      assert.equal(app.d.querySelector('#native-page option[value="changeform"]').disabled, true);
      assert.equal(app.d.querySelector('#native-look option[value="auto"]').disabled, true);
    });
    nativeChange('#native-look', 'dark'); nativeChange('#native-page', 'login');
    check(`${key}: representative login dark path exists`, () => {
      const relative = app.d.querySelector('#native-preview').getAttribute('src').replace(/^\.\//, '');
      assert.ok(fs.existsSync(path.join(root, relative)));
    });
    nativeChange('#native-palette', 'default');
    check(`${key}: default comparison restores prior mode/density/page`, () => {
      assert.ok(app.d.querySelector('#native-preview').getAttribute('src').endsWith('/compact-auto/changeform.html'));
      assert.equal(app.d.querySelector('#native-density').value, 'compact');
      assert.equal(app.d.querySelector('#native-look').value, 'auto');
    });
  }
  app.d.querySelector('[href="#settings"]').click(); await wait();
  check('native sample round trip retains selected palette', () => assert.equal(app.d.querySelector('#palette-mode').value, 'default'));
  app.w.dispatchEvent(new app.w.StorageEvent('storage', { key: 'nova-palette', newValue: 'violet', storageArea: app.w.localStorage }));
  check('another tab palette event updates control without writing theme', () => {
    assert.equal(app.d.documentElement.dataset.palette, 'violet');
    assert.equal(app.d.querySelector('#palette-mode').value, 'violet');
    assert.equal(app.w.localStorage.getItem('nova-theme'), 'dark');
    assert.equal(app.d.querySelector('[data-palette-card="violet"]').getAttribute('aria-pressed'), 'true');
  });
  app.w.dispatchEvent(new app.w.StorageEvent('storage', { key: 'unrelated', newValue: 'teal' }));
  check('unrelated storage events leave palette alone', () => assert.equal(app.d.documentElement.dataset.palette, 'violet'));
  app.w.dispatchEvent(new app.w.StorageEvent('storage', { key: 'nova-palette', newValue: 'untrusted' }));
  check('invalid cross-tab values return to default', () => assert.equal(app.d.documentElement.dataset.palette, 'default'));
  app.w.dispatchEvent(new app.w.StorageEvent('storage', { key: 'nova-palette', newValue: 'indigo' }));
  app.w.dispatchEvent(new app.w.StorageEvent('storage', { key: null, storageArea: app.w.localStorage }));
  check('same-origin storage clear restores palette default without writes', () => assert.equal(app.d.documentElement.dataset.palette, 'default'));

  app.w.Storage.prototype.setItem = () => { throw new Error('Quota'); };
  const select = app.d.querySelector('#palette-mode'); select.value = 'teal'; select.dispatchEvent(new app.w.Event('change', { bubbles: true }));
  check('storage failure applies current-page palette and explains persistence', () => {
    assert.equal(app.d.documentElement.dataset.palette, 'teal');
    assert.match(app.d.querySelector('#toast-root').textContent, /浏览器未能保存偏好/);
  });
  app.d.querySelector('[data-palette-card="ink"]').click();
  check('card selection remains usable when preference storage fails', () => {
    assert.equal(app.d.documentElement.dataset.palette, 'ink');
    assert.equal(app.d.querySelector('[data-palette-card="ink"]').getAttribute('aria-pressed'), 'true');
    assert.match(app.d.querySelector('#toast-root').textContent, /浏览器未能保存偏好/);
  }); app.close();
  const blocked = await login({}, true);
  check('unavailable storage login safely restores default', () => assert.equal(blocked.d.documentElement.dataset.palette, 'default'));
  blocked.w.Storage.prototype.setItem = () => { throw new Error('Quota'); };
  const loginSelect = blocked.d.querySelector('#login-palette'); loginSelect.value = 'terracotta'; loginSelect.dispatchEvent(new blocked.w.Event('change', { bubbles: true }));
  check('login storage failure retains usable palette and status', () => {
    assert.equal(blocked.d.documentElement.dataset.palette, 'terracotta');
    assert.match(blocked.d.querySelector('#palette-status').textContent, /未能保存/);
  }); blocked.close();
  const css = fs.readFileSync(path.join(root, 'presets.css'), 'utf8');
  for (const mode of ['light', 'dark']) {
    check(`${mode}: palette roles match login base specificity`, () => {
      assert.ok(css.includes(`:root[data-theme="${mode}"]:where([data-palette]:not([data-palette="default"]))`));
    });
  }
  for (const file of ['index.html', 'login.html']) {
    const html = fs.readFileSync(path.join(root, file), 'utf8');
    check(`${file}: CSP-compatible preference bootstrap precedes stylesheet`, () => {
      assert.ok(html.indexOf('preferences-init.js') < html.indexOf('rel="stylesheet"'));
      assert.equal((html.match(/presets.css/g) || []).length, 1);
    });
  }
  console.log('TOTAL', count, 'palette checks passed');
})().catch(error => { console.error(error); process.exit(1); });
