/* Real DOM regressions, including the installed Django sidebar script.
   Requires jsdom (npm install --no-save jsdom, or set NODE_PATH).
   Usage: node scripts/test-navigation.mjs [path/to/nav_sidebar.js ...]
   Without paths, PYTHON (default python3) selects the installed Django.
   This is DOM/behavior coverage, not browser-layout or full accessibility QA. */
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const {JSDOM, VirtualConsole} = require('jsdom');
const source = readFileSync(new URL('../src/nova_admin/static/nova_admin/navigation.js', import.meta.url), 'utf8');
const paths = process.argv.slice(2);
if (!paths.length) paths.push(execFileSync(process.env.PYTHON || 'python3', ['-c',
  'from pathlib import Path; import django; print(Path(django.__file__).parent / "contrib/admin/static/admin/js/nav_sidebar.js")',
], {encoding: 'utf8'}).trim());
const scope = 'a'.repeat(64);
const otherScope = 'b'.repeat(64);
const stateKey = value => 'nova.admin.navigation.v2.' + value;
const filterKey = value => 'nova.admin.navigation.v1.' + value;
const nativeFilterKey = 'django.admin.navSidebarFilterValue';
const delay = () => new Promise(resolve => setTimeout(resolve, 0));
class MemoryStorage {
  constructor(entries = []) { this.data = new Map(entries); this.failRead = false; this.failWrite = false; }
  getItem(key) { if (this.failRead) throw Error('Storage disabled'); return this.data.get(key) ?? null; }
  setItem(key, value) { if (this.failWrite) throw Error('Quota exceeded'); this.data.set(key, String(value)); }
  removeItem(key) { this.data.delete(key); }
}
function markup({grouped = true, active = '', limited = false, native = false, namespace = scope, extensions = false, noModels = false} = {}) {
  const modelKey = id => (['product', 'category', 'draft'].includes(id) ? 'catalog.' : 'auth.') + id;
  const row = (id, title, {linked = true} = {}) => `<tr data-nova-nav-model="${id}" data-nova-model-key="${modelKey(id)}" class="model-${id} ${active === id ? 'current-model' : ''}"><th scope="row">${linked ? `<a href="/admin/${id}/" ${active === id ? 'aria-current="page"' : ''}><span class="nova-nav-model-label">${title}</span>${extensions ? '<span class="nova-nav-badge">83421</span>' : ''}</a>` : `<span>${title}</span>`}</th><td>${extensions && linked ? `<button type="button" data-nova-favorite="${modelKey(id)}" aria-label="Favorite ${title}" aria-pressed="false" hidden><span aria-hidden="true">☆</span></button>` : ''}<a class="nova-nav-add" href="/admin/${id}/add/" aria-label="Add ${title}">+</a></td></tr>`;
  const app = (id, title, rows, open) => `<details class="nova-nav-group" data-nova-nav-app="${id}" ${open ? 'open' : ''}><summary><span>${title}</span><span aria-hidden="true" class="nova-nav-count">99</span></summary><table><caption>${title}</caption><tbody>${rows}</tbody></table></details>`;
  const section = (title, apps, open) => `<details class="nova-nav-section" ${open ? 'open' : ''}><summary class="nova-nav-section-title"><span>${title}</span></summary><div class="nova-nav-section-apps">${apps}</div></details>`;
  const catalog = app('catalog', '商品示例', row('product', '商品') + (limited ? '' : row('category', '商品分类') + row('draft', 'Drafts', {linked: false})), false);
  const auth = app('auth', 'Authentication and Authorization', row('user', 'Users') + row('group', 'Groups') + row('research', 'R&amp;D'), true);
  const shortcut = (id, title, favorite = false) => `<li data-nova-shortcut-model="${modelKey(id)}" ${favorite ? 'data-nova-favorite-shortcut hidden' : ''}><a href="/admin/${id}/">${title}</a></li>`;
  const shortcuts = extensions && !noModels ? `<section class="nova-nav-shortcuts" data-nova-common-models><h2>Common models</h2><ul>${shortcut('product', '商品')}</ul></section><section class="nova-nav-shortcuts" data-nova-favorites hidden><h2>Favorites</h2><ul>${shortcut('product', '商品', true)}${limited ? '' : shortcut('category', '商品分类', true) + shortcut('user', 'Users', true) + shortcut('group', 'Groups', true) + shortcut('research', 'R&amp;D', true)}</ul></section>` : '';
  const navigationModels = noModels ? '' : grouped ? section('业务管理', catalog, false) + (limited ? '' : section('系统管理', auth, true)) : catalog + (limited ? '' : auth);
  return `<!doctype html><html><body class="${native ? '' : 'nova-admin'}"><div class="main" id="main">${native ? '' : '<button id="nova-mobile-nav-toggle" type="button" aria-controls="nav-sidebar" aria-expanded="false" hidden>Navigation</button>'}<button id="toggle-nav-sidebar" aria-label="Toggle navigation"></button><nav id="nav-sidebar" ${native ? '' : `class="nova-navigation" data-nova-nav-scope="${namespace}"${extensions ? ' data-nova-favorites-enabled="true"' : ''}`}><label for="nav-filter">Filter navigation items</label><input type="search" id="nav-filter" maxlength="200" aria-label="Filter navigation items">${shortcuts}${navigationModels}</nav></div></body></html>`;
}
let count = 0;
for (const path of paths) {
  const upstream = readFileSync(path, 'utf8');
  const windows = [];
  function setup(options = {}) {
    const local = options.local || new MemoryStorage();
    const session = options.session || new MemoryStorage();
    const errors = [];
    const virtualConsole = new VirtualConsole();
    virtualConsole.on('jsdomError', error => errors.push(error));
    const dom = new JSDOM(options.html ?? markup(options), {
      url: options.url || 'https://example.invalid/admin/', runScripts: 'outside-only', virtualConsole,
    });
    const {window} = dom;
    windows.push(window);
    const viewport = new window.EventTarget();
    viewport.matches = Boolean(options.mobile);
    if (!options.noMatchMedia) window.matchMedia = query => {
      assert.equal(query, '(max-width: 767px)');
      return viewport;
    };
    for (const [name, storage] of [['localStorage', local], ['sessionStorage', session]]) {
      Object.defineProperty(window, name, {get() {
        if (options.denyStorage) throw new window.DOMException('Storage disabled', 'SecurityError');
        return storage;
      }});
    }
    let upstreamError;
    if (options.runUpstream !== false) {
      try { window.eval(upstream); } catch (error) { upstreamError = error; }
    }
    const originalFilter = window.document.querySelector('#nav-filter');
    if (options.focus) {
      originalFilter.focus();
      originalFilter.setSelectionRange(...options.focus);
    }
    window.eval(source);
    const filter = window.document.querySelector('#nav-filter');
    const apps = [...window.document.querySelectorAll('.nova-nav-group')];
    const sections = [...window.document.querySelectorAll('.nova-nav-section')];
    return {window, filter, originalFilter, apps, sections, local, session, errors, upstreamError,
      resize(mobile) {
        viewport.matches = mobile;
        viewport.dispatchEvent(new window.Event('change'));
      },
      fire(type, value, key = '') {
        filter.value = value;
        filter.dispatchEvent(new window.KeyboardEvent(type, {bubbles: true, key}));
      },
      rows() { return [...window.document.querySelectorAll('tbody > tr')]; },
      visible() { return this.rows().filter(row => !row.hidden && row.style.display !== 'none').map(row => row.dataset.novaNavModel); },
      state() { return JSON.parse(local.getItem(stateKey(options.namespace || scope))); },
    };
  }
  async function test(name, body) {
    try { await body(); count++; } catch (error) { error.message = `${path}: ${name}: ${error.message}`; throw error; }
    finally { while (windows.length) windows.pop().close(); }
  }
  await test('absent markup and filter are harmless', () => {
    for (const html of ['<body></body>', '<body class="nova-admin"><nav class="nova-navigation"></nav></body>']) {
      const result = setup({html, runUpstream: false});
      assert.equal(result.errors.length, 0);
    }
  });
  await test('all previous two/three-level reveal/restore and case checks', async () => {
    for (const grouped of [false, true]) {
      const result = setup({grouped});
      assert.equal(result.apps[0].open, false);
      result.fire('input', '商品');
      assert.equal(result.apps[0].open, true);
      assert.equal(result.apps[0].hidden, false);
      assert.equal(result.apps[1].hidden, true);
      if (grouped) { assert.equal(result.sections[0].open, true); assert.equal(result.sections[1].hidden, true); }
      result.fire('keyup', '');
      await delay();
      assert.deepEqual(result.apps.map(app => app.open), [false, false]);
      assert.ok(result.apps.every(app => !app.hidden));
      if (grouped) assert.deepEqual(result.sections.map(section => section.open), [false, false]);
      result.fire('change', 'USERS');
      assert.deepEqual(result.visible(), ['user']);
      result.fire('input', 'unmatched');
      assert.ok(result.apps.every(app => app.hidden));
      assert.ok(result.sections.every(section => section.hidden));
      assert.equal(result.filter.classList.contains('no-results'), true);
      result.fire('keyup', '');
      assert.ok(result.apps.every(app => !app.hidden));
      assert.equal(result.filter.classList.contains('no-results'), false);
      assert.equal(result.upstreamError, undefined);
      assert.equal(result.errors.length, 0);
    }
  });
  await test('group/app/model matching includes unlinked labels and literal text', () => {
    const result = setup();
    result.fire('input', '系统管理');
    assert.deepEqual(result.visible(), ['user', 'group', 'research']);
    assert.equal(result.filter.classList.contains('no-results'), false);
    result.fire('change', ' AUTHENTICATION ');
    assert.deepEqual(result.visible(), ['user', 'group', 'research']);
    result.fire('keyup', 'Drafts');
    assert.deepEqual(result.visible(), ['draft']);
    result.fire('input', 'r&d');
    assert.deepEqual(result.visible(), ['research']);
    result.fire('input', '99');
    assert.deepEqual(result.visible(), []); // Decorative counts are not app names.
    result.fire('input', '   ');
    assert.equal(result.visible().length, 6);
  });
  await test('native and Nova do not compete or share query state', () => {
    const session = new MemoryStorage([[nativeFilterKey, 'Users']]);
    const result = setup({session});
    assert.notEqual(result.filter, result.originalFilter);
    assert.equal(result.window.document.querySelectorAll('#nav-filter').length, 1);
    assert.equal(result.filter.value, '');
    assert.equal(result.visible().length, 6);
    result.fire('input', '业务管理');
    assert.deepEqual(result.visible(), ['product', 'category', 'draft']);
    assert.equal(session.getItem(nativeFilterKey), 'users');
    assert.equal(result.filter.classList.contains('no-results'), false);
    result.window.document.querySelector('#toggle-nav-sidebar').click();
    assert.equal(result.local.getItem('django.admin.navSidebarIsOpen'), 'false');
    assert.equal(result.window.document.querySelector('#nav-sidebar').getAttribute('aria-expanded'), 'false');
    assert.equal(result.upstreamError, undefined);
    assert.equal(result.errors.length, 0);
  });
  await test('stored query and pre-search collapse survive a page visit', async () => {
    const result = setup();
    result.apps[1].querySelector('summary').click();
    result.apps[1].querySelector('summary').click();
    await delay();
    assert.equal(result.apps[1].open, false);
    result.fire('input', 'Users');
    assert.equal(result.apps[1].open, true);
    await delay();
    const reload = setup({local: result.local, session: result.session, url: 'https://example.invalid/admin/product/?p=2'});
    assert.equal(reload.filter.value, 'Users');
    assert.deepEqual(reload.visible(), ['user']);
    reload.fire('keyup', 'Users', 'Escape');
    await delay();
    assert.equal(reload.filter.value, '');
    assert.deepEqual(reload.apps.map(app => app.open), [false, false]);
    assert.deepEqual(reload.sections.map(section => section.open), [false, false]);
  });
  await test('manual collapse during search never replaces pre-search state', async () => {
    const result = setup();
    result.fire('input', '系统管理');
    result.apps[1].querySelector('summary').click();
    await delay();
    assert.equal(result.apps[1].open, false);
    result.fire('keyup', '系统管理', 'ArrowLeft');
    assert.equal(result.apps[1].open, false);
    result.fire('input', '');
    await delay();
    assert.equal(result.apps[1].open, false);
    assert.deepEqual(result.sections.map(section => section.open), [false, false]);
  });
  await test('first visit and active route never expand untouched ancestors', () => {
    const result = setup({active: 'product'});
    assert.deepEqual(result.apps.map(item => item.open), [false, false]);
    assert.deepEqual(result.sections.map(item => item.open), [false, false]);
    assert.deepEqual(result.state().nodes, []);
    const different = setup({active: 'category', local: result.local, session: result.session});
    assert.equal(different.apps[0].open, false);
    assert.equal(different.sections[0].open, false);
    assert.equal(different.window.document.querySelector('[aria-current="page"]').textContent, '商品分类');
  });
  await test('manual open and close survive routes and reloads with independent levels', () => {
    const result = setup({active: 'product'});
    result.sections[0].querySelector('summary').click();
    result.apps[0].querySelector('summary').click();
    // No timeout: the user's choice is persisted before a navigation can unload.
    assert.equal(result.state().nodes.length, 2);
    const reload = setup({active: 'category', local: result.local});
    assert.equal(reload.apps[0].open, true);
    assert.equal(reload.sections[0].open, true);
    assert.equal(reload.apps[1].open, false);
    reload.sections[0].querySelector('summary').click();
    const closedParent = setup({active: 'user', local: result.local});
    assert.equal(closedParent.apps[0].open, true);
    assert.equal(closedParent.sections[0].open, false);
    closedParent.sections[0].querySelector('summary').click();
    assert.equal(closedParent.apps[0].open, true);
    closedParent.apps[0].querySelector('summary').click();
    const closedChild = setup({active: 'product', local: result.local});
    assert.equal(closedChild.apps[0].open, false);
    assert.equal(closedChild.sections[0].open, true);
  });
  await test('legacy automatic choices are ignored without deleting unrelated preferences', () => {
    const legacy = JSON.stringify({version: 1, active: 'legacy', nodes: [['a:0000000000000000', true]]});
    const local = new MemoryStorage([[filterKey(scope), legacy], ['nova-theme', 'dark'], ['django.admin.navSidebarIsOpen', 'false']]);
    const result = setup({local, active: 'product'});
    assert.ok([...result.apps, ...result.sections].every(item => !item.open));
    assert.equal(local.getItem(filterKey(scope)), legacy);
    assert.equal(local.getItem('nova-theme'), 'dark');
    assert.equal(local.getItem('django.admin.navSidebarIsOpen'), 'false');
  });
  await test('explicit group keys survive labels and visible membership changes', () => {
    const html = markup().replace('class="nova-nav-section"', 'class="nova-nav-section" data-nova-nav-section="business"');
    const result = setup({html});
    result.sections[0].querySelector('summary').click();
    const changed = html.replace('业务管理', 'Business').replace('data-nova-nav-app="catalog"', 'data-nova-nav-app="renamed"');
    const reload = setup({html: changed, local: result.local});
    assert.equal(reload.sections[0].open, true);
    assert.equal(reload.apps[0].open, false);
  });
  await test('queued programmatic toggles and repeated initialization never invent choices', async () => {
    const result = setup();
    result.apps[0].open = true;
    await delay();
    assert.deepEqual(result.state().nodes, []);
    result.apps[0].open = false;
    result.window.eval(source);
    result.apps[0].querySelector('summary').click();
    result.apps[0].querySelector('summary').click();
    result.apps[0].querySelector('summary').click();
    assert.equal(result.apps[0].open, true);
    assert.equal(result.state().nodes.length, 1);
    assert.equal(setup({local: result.local}).apps[0].open, true);
  });
  await test('Back cache and other-tab storage changes refresh only disclosure preferences', () => {
    const first = setup();
    first.sections[0].querySelector('summary').click();
    first.apps[0].querySelector('summary').click();
    const next = setup({local: first.local});
    next.apps[0].querySelector('summary').click();
    next.sections[1].querySelector('summary').click();
    first.window.dispatchEvent(new first.window.PageTransitionEvent('pageshow', {persisted: true}));
    assert.equal(first.apps[0].open, false);
    assert.deepEqual(first.sections.map(item => item.open), [true, true]);
    first.fire('input', '商品');
    next.sections[0].querySelector('summary').click();
    first.window.dispatchEvent(new first.window.StorageEvent('storage', {key: stateKey(scope)}));
    assert.equal(first.sections[0].open, true); // Search stays temporarily expanded.
    first.fire('input', '');
    assert.equal(first.sections[0].open, false);
    assert.equal(first.apps[0].open, false);
    assert.equal(first.sections[1].open, true);
    first.local.removeItem(stateKey(scope));
    first.window.dispatchEvent(new first.window.StorageEvent('storage', {key: null}));
    assert.ok([...first.sections, ...first.apps].every(item => !item.open));
  });
  await test('Back cache with blocked storage preserves usable in-page choices', () => {
    const result = setup();
    result.apps[0].querySelector('summary').click();
    result.local.failRead = true;
    result.window.dispatchEvent(new result.window.PageTransitionEvent('pageshow', {persisted: true}));
    assert.equal(result.apps[0].open, true);
    result.apps[0].querySelector('summary').click();
    assert.equal(result.apps[0].open, false);
  });
  await test('failed writes cannot revert local choices on Back or storage events', () => {
    const result = setup();
    result.local.failWrite = true;
    result.apps[0].querySelector('summary').click();
    result.window.dispatchEvent(new result.window.PageTransitionEvent('pageshow', {persisted: true}));
    result.window.dispatchEvent(new result.window.StorageEvent('storage', {key: stateKey(scope)}));
    assert.equal(result.apps[0].open, true);
    result.local.failWrite = false;
    result.apps[0].querySelector('summary').click();
    assert.equal(result.apps[0].open, false);
    assert.equal(setup({local: result.local}).apps[0].open, false);
  });
  await test('site/user scopes are isolated', async () => {
    const result = setup();
    result.apps[1].querySelector('summary').click();
    await delay();
    result.fire('input', 'Users');
    const other = setup({namespace: otherScope, local: result.local, session: result.session});
    assert.equal(other.filter.value, '');
    assert.equal(other.apps[1].open, false);
    assert.equal(JSON.parse(result.session.getItem(filterKey(scope))).query, 'Users');
  });
  await test('permission changes prune stale state and cannot create cached links', () => {
    const result = setup();
    result.apps[1].querySelector('summary').click();
    result.sections[1].querySelector('summary').click();
    result.fire('input', 'Users');
    const previous = result.state();
    const limited = setup({limited: true, local: result.local, session: result.session});
    assert.equal(limited.filter.value, '');
    assert.deepEqual(limited.visible(), ['product']);
    assert.equal(limited.apps.length, 1);
    assert.equal(limited.sections.length, 1);
    assert.ok(limited.state().nodes.length < previous.nodes.length);
    assert.equal(limited.window.document.querySelector('a[href="/admin/user/"]'), null);
    const stored = limited.local.getItem(stateKey(scope));
    for (const forbidden of ['业务管理', '系统管理', '商品', '/admin/', 'catalog', 'product', 'auth']) assert.equal(stored.includes(forbidden), false);
  });
  await test('bad JSON, oversized and malformed stored schemas are ignored', () => {
    for (const bad of ['{', 'null', '[]', 'x'.repeat(17000), JSON.stringify({version: 9, nodes: []}),
      JSON.stringify({version: 2, nodes: [['__proto__', false], ['a:' + 'c'.repeat(16), 'false']], active: {}}),
      JSON.stringify({version: 2, nodes: Array.from({length: 201}, () => ['a:' + 'c'.repeat(16), false])}),
    ]) {
      const result = setup({local: new MemoryStorage([[stateKey(scope), bad]]), session: new MemoryStorage([[stateKey(scope), bad]])});
      assert.equal(result.filter.value, '');
      assert.deepEqual(result.apps.map(app => app.open), [false, false]);
      assert.equal(result.errors.length, 0);
      assert.equal(result.state().version, 2);
    }
  });
  await test('storage failures never disable Nova filtering or native summaries', async () => {
    for (const mode of ['read', 'write', 'getter']) {
      const local = new MemoryStorage();
      const session = new MemoryStorage();
      for (const storage of [local, session]) { storage.failRead = mode === 'read'; storage.failWrite = mode === 'write'; }
      const result = setup({local, session, denyStorage: mode === 'getter'});
      // Django itself has unguarded storage access; Nova does not copy that failure.
      if (mode !== 'write') assert.ok(result.upstreamError);
      result.fire('input', '系统管理');
      assert.deepEqual(result.visible(), ['user', 'group', 'research']);
      result.fire('input', '');
      result.apps[0].querySelector('summary').click();
      await delay();
      assert.equal(result.apps[0].open, true);
      assert.equal(result.errors.length, 0);
    }
  });
  await test('read-denied but writable storage never loses preexisting navigation or favorite choices', () => {
    const first = setup({extensions: true});
    first.apps[1].querySelector('summary').click();
    first.window.document.querySelector('[data-nova-favorite="auth.user"]').click();
    first.fire('input', 'Users');
    const localBefore = new Map(first.local.data);
    const sessionBefore = new Map(first.session.data);
    first.local.failRead = first.session.failRead = true;
    const denied = setup({extensions: true, local: first.local, session: first.session});
    denied.apps[0].querySelector('summary').click();
    denied.window.document.querySelector('[data-nova-favorite="catalog.product"]').click();
    denied.fire('input', '商品');
    assert.equal(denied.apps[0].open, true);
    assert.deepEqual(denied.local.data, localBefore);
    assert.deepEqual(denied.session.data, sessionBefore);
    denied.local.failRead = denied.session.failRead = false;
    denied.fire('input', '');
    denied.apps[0].querySelector('summary').click();
    assert.deepEqual(denied.local.data, localBefore); // This page stays memory-only.
    const reload = setup({extensions: true, local: first.local, session: first.session});
    reload.fire('input', '');
    assert.equal(reload.apps[1].open, true);
    assert.equal(reload.apps[0].open, false);
    assert.equal(reload.window.document.querySelector('[data-nova-favorite="auth.user"]').getAttribute('aria-pressed'), 'true');
  });
  await test('query and collapse storage remain bounded', () => {
    const result = setup();
    result.fire('input', 'a'.repeat(1000));
    assert.equal(result.filter.value.length, 200);
    assert.equal(JSON.parse(result.session.getItem(filterKey(scope))).query.length, 200);
    const group = '<details class="nova-nav-group" open data-nova-nav-app="APP"><summary><span>App</span></summary><table><tbody><tr data-nova-nav-model="model"><th scope="row"><a href="/m/">Model</a></th></tr></tbody></table></details>';
    const many = setup({html: `<body class="nova-admin"><nav class="nova-navigation" data-nova-nav-scope="${scope}"><input type="search" id="nav-filter">${Array.from({length: 250}, (_, index) => group.replace('APP', String(index))).join('')}</nav></body>`, runUpstream: false});
    assert.deepEqual(many.state().nodes, []);
    many.apps.forEach(app => app.querySelector('summary').click());
    assert.equal(many.state().nodes.length, 200);
    const noScope = setup({namespace: ''});
    noScope.fire('input', 'Users');
    assert.equal([...noScope.local.data.keys()].some(key => key.startsWith('nova.')), false);
  });
  await test('focus, selection, accessible name, Escape and idempotent initialization', () => {
    const session = new MemoryStorage();
    const first = setup({session});
    first.fire('input', 'Users');
    session.setItem(nativeFilterKey, 'Users');
    const result = setup({session, focus: [1, 3]});
    // Scoped value is restored before focus/selection are restored.
    assert.equal(result.window.document.activeElement, result.filter);
    assert.equal(result.filter.getAttribute('aria-label'), 'Filter navigation items');
    assert.equal(result.filter.labels.length, 1);
    assert.equal(result.filter.value, 'Users');
    assert.deepEqual([result.filter.selectionStart, result.filter.selectionEnd], [1, 3]);
    // Set focus selection on the live input and ensure later searches retain focus.
    result.filter.setSelectionRange(1, 3);
    result.fire('input', 'Users');
    assert.equal(result.window.document.activeElement, result.filter);
    const live = result.filter;
    result.window.eval(source);
    assert.equal(result.window.document.querySelector('#nav-filter'), live);
    result.fire('keyup', 'Users', 'Escape');
    assert.equal(result.filter.value, '');
    assert.equal(result.window.document.activeElement, live);
    assert.equal(result.errors.length, 0);
  });
  await test('native-mode filter and sidebar remain fully owned by Django', () => {
    const result = setup({native: true});
    assert.equal(result.filter, result.originalFilter);
    result.fire('input', 'Users');
    assert.deepEqual(result.visible(), ['draft', 'user']); // Original Django filters anchors only.
    assert.equal(result.session.getItem(nativeFilterKey), 'users');
    assert.equal([...result.local.data.keys()].some(key => key.startsWith('nova.')), false);
    assert.equal(result.upstreamError, undefined);
    assert.equal(result.errors.length, 0);
  });
  await test('mobile disclosure preserves desktop open and closed preferences', () => {
    for (const desktopOpen of [false, true]) {
      const local = new MemoryStorage([['django.admin.navSidebarIsOpen', String(desktopOpen)]]);
      const result = setup({mobile: true, local});
      const document = result.window.document;
      const toggle = document.getElementById('nova-mobile-nav-toggle');
      const nav = document.getElementById('nav-sidebar');
      const main = document.getElementById('main');
      assert.equal(toggle.hidden, false);
      assert.equal(toggle.getAttribute('aria-controls'), nav.id);
      assert.equal(toggle.getAttribute('aria-expanded'), 'false');
      assert.equal(nav.hidden, true);
      toggle.click();
      assert.equal(nav.hidden, false);
      assert.equal(toggle.getAttribute('aria-expanded'), 'true');
      assert.equal(main.classList.contains('shifted'), desktopOpen);
      assert.equal(local.getItem('django.admin.navSidebarIsOpen'), String(desktopOpen));
      nav.querySelector('summary').focus();
      nav.querySelector('summary').dispatchEvent(new result.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
      assert.equal(nav.hidden, true);
      assert.equal(toggle.getAttribute('aria-expanded'), 'false');
      assert.equal(document.activeElement, toggle);
      assert.equal(document.querySelector('[inert]'), null);
      result.resize(false);
      assert.equal(nav.hidden, false);
      assert.equal(toggle.hidden, true);
      assert.equal(nav.getAttribute('aria-expanded'), String(desktopOpen));
      assert.equal(document.activeElement, document.getElementById('toggle-nav-sidebar'));
      assert.equal(main.classList.contains('shifted'), desktopOpen);
      assert.equal(result.errors.length, 0);
    }
  });
  await test('first Escape clears the mobile filter, next Escape closes and returns focus', () => {
    const result = setup({mobile: true});
    const document = result.window.document;
    const toggle = document.getElementById('nova-mobile-nav-toggle');
    const nav = document.getElementById('nav-sidebar');
    toggle.click();
    result.filter.focus();
    result.fire('input', 'Users');
    const escape = () => result.filter.dispatchEvent(new result.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
    escape();
    assert.equal(nav.hidden, false);
    result.fire('keyup', 'Users', 'Escape');
    assert.equal(result.filter.value, '');
    assert.equal(nav.hidden, false);
    assert.equal(document.activeElement, result.filter);
    escape();
    assert.equal(nav.hidden, true);
    assert.equal(document.activeElement, toggle);
    toggle.click();
    assert.equal(nav.hidden, false);
    assert.deepEqual(result.visible(), ['product', 'category', 'draft', 'user', 'group', 'research']);
  });
  await test('responsive transition preserves navigation focus or recovers a visible control', () => {
    const result = setup();
    const document = result.window.document;
    const nav = document.getElementById('nav-sidebar');
    const mobileToggle = document.getElementById('nova-mobile-nav-toggle');
    const desktopToggle = document.getElementById('toggle-nav-sidebar');
    result.filter.focus();
    result.resize(true);
    assert.equal(nav.hidden, false);
    assert.equal(document.activeElement, result.filter);
    result.resize(false);
    assert.equal(document.activeElement, result.filter);
    desktopToggle.click(); // Desktop preference changes only through Django.
    assert.equal(nav.getAttribute('aria-expanded'), 'false');
    desktopToggle.focus();
    result.resize(true);
    assert.equal(document.activeElement, mobileToggle);
    result.filter.focus();
    result.resize(false);
    assert.equal(document.activeElement, desktopToggle);
    assert.equal(nav.getAttribute('aria-expanded'), 'false');
    assert.equal(nav.hidden, false);
    assert.equal(result.local.getItem('django.admin.navSidebarIsOpen'), 'false');
  });
  await test('mobile disclosure tolerates denied storage and repeated initialization', () => {
    const result = setup({mobile: true, denyStorage: true});
    const document = result.window.document;
    const toggle = document.getElementById('nova-mobile-nav-toggle');
    const nav = document.getElementById('nav-sidebar');
    result.window.eval(source);
    toggle.click();
    assert.equal(nav.hidden, false);
    toggle.click();
    assert.equal(nav.hidden, true);
    assert.equal(document.activeElement, toggle);
    result.resize(false);
    assert.equal(nav.hidden, false);
    assert.equal(nav.hasAttribute('aria-expanded'), false);
    assert.equal(result.errors.length, 0);
  });
  await test('missing matchMedia retains the progressive markup fallback', () => {
    const result = setup({noMatchMedia: true});
    assert.equal(result.window.document.getElementById('nova-mobile-nav-toggle').hidden, true);
    assert.equal(result.window.document.getElementById('nav-sidebar').hidden, false);
    result.fire('input', 'Users');
    assert.deepEqual(result.visible(), ['user']);
    assert.equal(result.errors.length, 0);
  });
  await test('favorites toggle with native button semantics, persist, and keep focus', () => {
    const result = setup({extensions: true});
    const document = result.window.document;
    const button = document.querySelector('[data-nova-favorite="auth.user"]');
    const favorites = document.querySelector('[data-nova-favorites]');
    assert.equal(button.hidden, false);
    assert.equal(favorites.hidden, true);
    button.focus();
    button.click();
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.equal(document.activeElement, button);
    assert.equal(favorites.hidden, false);
    assert.equal(favorites.querySelector('[data-nova-shortcut-model="auth.user"]').hidden, false);
    assert.equal(favorites.querySelector('[data-nova-shortcut-model="catalog.product"]').hidden, true);
    const saved = result.local.getItem('nova.admin.favorites.v1.' + scope);
    for (const forbidden of ['auth', 'user', 'Users', '/admin/', 'catalog']) assert.equal(saved.includes(forbidden), false);
    assert.equal(JSON.parse(saved).models.length, 1);
    const reload = setup({extensions: true, local: result.local});
    const restored = reload.window.document.querySelector('[data-nova-favorite="auth.user"]');
    assert.equal(restored.getAttribute('aria-pressed'), 'true');
    restored.click();
    assert.equal(restored.getAttribute('aria-pressed'), 'false');
    assert.equal(reload.window.document.querySelector('[data-nova-favorites]').hidden, true);
  });
  await test('favorites isolate opaque user/site scopes and prune revoked models', () => {
    const result = setup({extensions: true});
    result.window.document.querySelector('[data-nova-favorite="auth.user"]').click();
    const other = setup({extensions: true, namespace: otherScope, local: result.local});
    assert.equal(other.window.document.querySelector('[data-nova-favorites]').hidden, true);
    const limited = setup({extensions: true, limited: true, local: result.local});
    assert.equal(limited.window.document.querySelector('[data-nova-favorites]').hidden, true);
    assert.equal(limited.window.document.querySelector('a[href="/admin/user/"]'), null);
    assert.deepEqual(JSON.parse(limited.local.getItem('nova.admin.favorites.v1.' + scope)).models, []);
  });
  await test('losing every list permission clears enabled favorites before permission returns', () => {
    const result = setup({extensions: true});
    result.window.document.querySelector('[data-nova-favorite="auth.user"]').click();
    const key = 'nova.admin.favorites.v1.' + scope;
    assert.equal(JSON.parse(result.local.getItem(key)).models.length, 1);
    const empty = setup({extensions: true, noModels: true, local: result.local});
    assert.equal(empty.window.document.querySelectorAll('[data-nova-favorite]').length, 0);
    assert.deepEqual(JSON.parse(empty.local.getItem(key)).models, []);
    const restored = setup({extensions: true, local: result.local});
    assert.equal(restored.window.document.querySelector('[data-nova-favorite="auth.user"]').getAttribute('aria-pressed'), 'false');
    assert.equal(restored.window.document.querySelector('[data-nova-favorites]').hidden, true);
  });
  await test('a disabled favorites feature preserves saved choices even on an empty page', () => {
    const result = setup({extensions: true});
    result.window.document.querySelector('[data-nova-favorite="auth.user"]').click();
    const key = 'nova.admin.favorites.v1.' + scope;
    const saved = result.local.getItem(key);
    setup({extensions: false, noModels: true, local: result.local});
    assert.equal(result.local.getItem(key), saved);
    const restored = setup({extensions: true, local: result.local});
    assert.equal(restored.window.document.querySelector('[data-nova-favorite="auth.user"]').getAttribute('aria-pressed'), 'true');
  });
  await test('filtering honors common/favorite links and excludes badge text', () => {
    const result = setup({extensions: true});
    const document = result.window.document;
    document.querySelector('[data-nova-favorite="auth.user"]').click();
    result.fire('input', 'Users');
    assert.equal(document.querySelector('[data-nova-common-models]').hidden, true);
    assert.equal(document.querySelector('[data-nova-favorites]').hidden, false);
    result.fire('input', '83421');
    assert.deepEqual(result.visible(), []);
    assert.equal(document.querySelector('[data-nova-favorites]').hidden, true);
    result.fire('input', '业务管理');
    assert.equal(document.querySelector('[data-nova-common-models]').hidden, false);
    assert.equal(document.querySelector('[data-nova-favorites]').hidden, true);
    result.fire('input', '');
    assert.equal(document.querySelector('[data-nova-favorites]').hidden, false);
  });
  await test('malformed or oversized favorite data cannot create a link or selection', () => {
    for (const bad of ['{', 'null', JSON.stringify({version: 1, models: ['auth.user', '<img src=x>', 'a'.repeat(16)]}),
      JSON.stringify({version: 1, models: Array(51).fill('a'.repeat(16))}), 'x'.repeat(2200),
    ]) {
      const result = setup({extensions: true, local: new MemoryStorage([['nova.admin.favorites.v1.' + scope, bad]])});
      assert.equal(result.window.document.querySelector('[data-nova-favorites]').hidden, true);
      assert.equal(result.window.document.querySelector('img'), null);
      assert.equal(result.errors.length, 0);
    }
  });
  await test('favorite storage failures remain usable in-page and missing scope stays private', () => {
    const result = setup({extensions: true, denyStorage: true});
    const button = result.window.document.querySelector('[data-nova-favorite="catalog.product"]');
    button.click();
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.equal(result.window.document.querySelector('[data-nova-favorites]').hidden, false);
    const noScope = setup({extensions: true, namespace: ''});
    assert.ok([...noScope.window.document.querySelectorAll('[data-nova-favorite]')].every(item => item.hidden));
    assert.equal([...noScope.local.data.keys()].some(key => key.startsWith('nova.admin.favorites.')), false);
    assert.equal(noScope.window.document.querySelector('[data-nova-common-models]').hidden, false);
  });
  console.log(`Navigation DOM: passed with ${path}`);
}
console.log(`${count} navigation DOM scenarios passed (${paths.length} Django script versions).`);
