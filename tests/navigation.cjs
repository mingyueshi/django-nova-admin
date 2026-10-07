const assert = require('node:assert/strict');
const { createApp } = require('./dom-runtime.cjs');
const key = 'nova.preview.navigation.v2./';
const wait = () => new Promise(resolve => setTimeout(resolve, 25));
let passed = 0;
const open = (app, name) => app.d.querySelector(`[data-nav-group="${name}"]`).getAttribute('aria-expanded') === 'true';
const click = (app, name) => app.d.querySelector(`[data-nav-group="${name}"]`).click();
const saved = app => JSON.parse(app.w.localStorage.getItem(key));
const snapshot = app => Object.fromEntries(Object.keys(app.w.localStorage).map(k => [k, app.w.localStorage.getItem(k)]));
const allClosed = app => {
  for (const name of ['business', 'organization', 'system', 'developer']) {
    assert.equal(open(app, name), false, name);
    assert.equal(app.d.getElementById('nav-group-' + name).hidden, true, name);
  }
};
async function test(name, run) {
  const apps = [];
  const setup = async options => { const app = await createApp(options); apps.push(app); return app; };
  try { await run(setup); passed++; console.log('PASS', name); }
  finally { apps.forEach(app => app.close()); }
}
(async () => {
  await test('all levels default closed on overview and direct active route', async setup => {
    for (const url of ['https://example.test/', 'https://example.test/#users']) {
      const app = await setup({ url });
      allClosed(app);
      assert.equal(saved(app), null);
      assert.ok(app.d.querySelector('.nav-item[aria-current="page"]'));
    }
  });
  await test('only touched nodes persist immediately and restore on navigation/reload', async setup => {
    const app = await setup();
    click(app, 'business');
    click(app, 'organization');
    assert.deepEqual(saved(app), { version: 2, nodes: { business: true, organization: true } });
    app.w.location.hash = 'users'; await wait();
    assert.equal(open(app, 'business'), true);
    assert.equal(open(app, 'organization'), true);
    assert.equal(open(app, 'system'), false);
    const reload = await setup({ url: 'https://example.test/#users', storage: snapshot(app) });
    assert.equal(open(reload, 'business'), true);
    assert.equal(open(reload, 'organization'), true);
    assert.equal(open(reload, 'developer'), false);
  });
  await test('closing either level does not overwrite independent child choice', async setup => {
    const app = await setup(); click(app, 'business'); click(app, 'organization'); click(app, 'business');
    app.w.location.hash = 'catalog'; await wait();
    assert.equal(open(app, 'business'), false); assert.equal(open(app, 'organization'), true);
    click(app, 'business'); assert.equal(open(app, 'organization'), true);
    click(app, 'organization'); app.w.location.hash = 'users'; await wait();
    assert.equal(open(app, 'organization'), false);
    const reload = await setup({ url: 'https://example.test/#users', storage: snapshot(app) });
    assert.equal(open(reload, 'business'), true); assert.equal(open(reload, 'organization'), false);
  });
  await test('route search, Back/Forward and theme changes never reopen menus', async setup => {
    const app = await setup();
    app.d.querySelector('[data-action="search"]').click();
    const field = app.d.querySelector('#command-search'); field.value = '用户';
    field.dispatchEvent(new app.w.Event('input', { bubbles: true }));
    app.d.querySelector('[data-nav="users"]').click(); await wait();
    allClosed(app);
    app.w.location.hash = 'settings'; await wait(); allClosed(app);
    app.w.history.back(); await wait(); allClosed(app);
    app.w.history.forward(); await wait(); allClosed(app);
    app.d.querySelector('[data-action="theme"]').click(); allClosed(app);
    assert.equal(saved(app), null);
  });
  await test('legacy automatic state is ignored and unrelated preferences are preserved', async setup => {
    const old = JSON.stringify({ business: true, organization: true, system: true });
    const app = await setup({ storage: { 'nova-nav-open': old, 'nova-theme': 'dark', 'django.admin.navSidebarIsOpen': 'false' } });
    allClosed(app); click(app, 'business');
    assert.equal(app.w.localStorage.getItem('nova-nav-open'), old);
    assert.equal(app.w.localStorage.getItem('nova-theme'), 'dark');
    assert.equal(app.w.localStorage.getItem('django.admin.navSidebarIsOpen'), 'false');
  });
  await test('schema validation rejects malformed and nonboolean states', async setup => {
    for (const raw of ['{', 'null', '[]', 'x'.repeat(4001), JSON.stringify({ version: 1, nodes: { business: true } }), JSON.stringify({ version: 2, nodes: { business: 'true', organization: 1, __proto__: true } })]) {
      allClosed(await setup({ storage: { [key]: raw } }));
    }
    const app = await setup({ storage: { [key]: JSON.stringify({ version: 2, nodes: { business: true, foreign: true } }) } });
    assert.equal(open(app, 'business'), true); click(app, 'system');
    assert.deepEqual(saved(app).nodes, { business: true, system: true });
  });
  await test('same project paths share choices; different installation paths are isolated', async setup => {
    const app = await setup({ url: 'https://example.test/a/#users' }); click(app, 'business');
    const store = snapshot(app);
    const same = await setup({ url: 'https://example.test/a/index.html#users', storage: store });
    assert.equal(open(same, 'business'), true);
    allClosed(await setup({ url: 'https://example.test/b/#users', storage: store }));
  });
  await test('storage getter/read/write failures retain usable in-page choices', async setup => {
    for (const mode of ['getter', 'read', 'write']) {
      const app = await setup({ beforeLoad(w) {
        if (mode === 'getter') Object.defineProperty(w, 'localStorage', { get() { throw Error('disabled'); } });
        else w.Storage.prototype[mode === 'read' ? 'getItem' : 'setItem'] = function () { throw Error('blocked'); };
      } });
      allClosed(app); click(app, 'business'); click(app, 'organization');
      app.w.location.hash = 'users'; await wait();
      assert.equal(open(app, 'business'), true); assert.equal(open(app, 'organization'), true);
      click(app, 'business'); assert.equal(open(app, 'business'), false);
    }
  });
  await test('Back cache and cross-tab events update navigation without replacing unsaved forms', async setup => {
    const app = await setup({ url: 'https://example.test/#catalog/add' });
    const field = app.d.querySelector('#product-title');
    field.value = 'unsaved navigation regression';
    field.dispatchEvent(new app.w.Event('input', { bubbles: true }));
    app.w.localStorage.setItem(key, JSON.stringify({ version: 2, nodes: { business: true } }));
    app.w.dispatchEvent(new app.w.StorageEvent('storage', { key }));
    assert.equal(open(app, 'business'), true);
    assert.equal(app.d.querySelector('#product-title'), field);
    assert.equal(field.value, 'unsaved navigation regression');
    app.w.localStorage.setItem(key, JSON.stringify({ version: 2, nodes: { system: true } }));
    app.w.dispatchEvent(new app.w.PageTransitionEvent('pageshow', { persisted: true }));
    assert.equal(open(app, 'business'), false); assert.equal(open(app, 'system'), true);
    app.w.localStorage.removeItem(key);
    app.w.dispatchEvent(new app.w.StorageEvent('storage', { key: null }));
    allClosed(app); assert.equal(app.d.querySelector('#product-title'), field);
  });
  await test('Back cache keeps in-memory state if storage later becomes unavailable', async setup => {
    const app = await setup(); click(app, 'business');
    app.w.Storage.prototype.getItem = function () { throw Error('blocked later'); };
    app.w.dispatchEvent(new app.w.PageTransitionEvent('pageshow', { persisted: true }));
    assert.equal(open(app, 'business'), true);
    click(app, 'business'); assert.equal(open(app, 'business'), false);
  });
  await test('repeated activations preserve aria controls and synchronous final state', async setup => {
    const app = await setup();
    const button = app.d.querySelector('[data-nav-group="business"]'); button.focus();
    for (let index = 0; index < 7; index++) button.click();
    assert.equal(app.d.activeElement, button);
    assert.equal(app.d.getElementById(button.getAttribute('aria-controls')).hidden, false);
    assert.equal(saved(app).nodes.business, true);
    const reload = await setup({ storage: snapshot(app) }); assert.equal(open(reload, 'business'), true);
  });
  await test('failed writes preserve local choices after cache restore and storage events', async setup => {
    const app = await setup();
    const set = app.w.Storage.prototype.setItem;
    app.w.Storage.prototype.setItem = function () { throw Error('quota'); };
    click(app, 'business');
    app.w.dispatchEvent(new app.w.PageTransitionEvent('pageshow', { persisted: true }));
    app.w.dispatchEvent(new app.w.StorageEvent('storage', { key }));
    assert.equal(open(app, 'business'), true);
    app.w.Storage.prototype.setItem = set;
    click(app, 'business'); assert.equal(saved(app).nodes.business, false);
  });
  await test('mobile disclosure exposes one controlled sidebar and synchronized expanded state', async setup => {
    const app = await setup();
    const button = app.d.querySelector('.mobile-menu');
    const sidebar = app.d.getElementById(button.getAttribute('aria-controls'));
    assert.equal(button.type, 'button');
    assert.ok(sidebar.classList.contains('sidebar'));
    assert.equal(app.d.querySelectorAll('#' + sidebar.id).length, 1);
    assert.equal(button.getAttribute('aria-expanded'), 'false');
    assert.equal(button.getAttribute('aria-label'), '打开导航');
    button.focus(); button.click();
    assert.equal(button.getAttribute('aria-expanded'), 'true');
    assert.equal(button.getAttribute('aria-label'), '关闭导航');
    assert.equal(app.d.querySelector('.shell').classList.contains('mobile-open'), true);
    assert.equal(app.d.body.style.overflow, 'hidden');
    assert.equal(app.d.activeElement, sidebar.querySelector('a'));
    app.d.dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert.equal(button.getAttribute('aria-expanded'), 'false');
    assert.equal(app.d.activeElement, button);
    assert.equal(app.d.body.style.overflow, '');
  });
  await test('mobile repeated activation and backdrop close restore state and keyboard focus', async setup => {
    const app = await setup(); const button = app.d.querySelector('.mobile-menu');
    for (let iteration = 0; iteration < 3; iteration++) {
      button.click(); assert.equal(button.getAttribute('aria-expanded'), 'true');
      button.click(); assert.equal(button.getAttribute('aria-expanded'), 'false');
      assert.equal(app.d.activeElement, button);
    }
    button.click(); app.d.querySelector('[data-action="close-nav"]').click();
    assert.equal(button.getAttribute('aria-expanded'), 'false');
    assert.equal(app.d.querySelector('.shell').classList.contains('mobile-open'), false);
    assert.equal(app.d.activeElement, button); assert.equal(app.d.body.style.overflow, '');
  });
  await test('mobile Tab boundaries remain contained and Escape returns to its trigger', async setup => {
    const app = await setup(); const button = app.d.querySelector('.mobile-menu');
    const sidebar = app.d.querySelector('.sidebar');
    const first = sidebar.querySelector('a');
    const last = sidebar.querySelector('[data-action="native"]');
    // jsdom has no layout; supply only the two visible focus boundaries.
    first.getClientRects = last.getClientRects = () => [{ width: 10, height: 10 }];
    button.click();
    const backward = new app.w.KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
    first.dispatchEvent(backward); assert.equal(backward.defaultPrevented, true); assert.equal(app.d.activeElement, last);
    const forward = new app.w.KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    last.dispatchEvent(forward); assert.equal(forward.defaultPrevented, true); assert.equal(app.d.activeElement, first);
    first.dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert.equal(app.d.activeElement, button); assert.equal(button.getAttribute('aria-expanded'), 'false');
  });
  await test('mobile same-route and new-route navigation release scrolling and retain disclosure choices', async setup => {
    const app = await setup(); let button = app.d.querySelector('.mobile-menu');
    button.click(); app.d.querySelector('.brand').click();
    assert.equal(button.getAttribute('aria-expanded'), 'false'); assert.equal(app.d.body.style.overflow, '');
    assert.equal(app.d.activeElement, button);
    button.click(); click(app, 'business'); click(app, 'organization');
    app.d.querySelector('.nav-list a[href="#users"]').click(); await wait();
    button = app.d.querySelector('.mobile-menu');
    assert.equal(button.getAttribute('aria-expanded'), 'false');
    assert.equal(button.getAttribute('aria-controls'), 'nova-preview-sidebar');
    assert.equal(app.d.body.style.overflow, ''); assert.equal(app.d.activeElement, app.d.querySelector('#view h1'));
    assert.equal(open(app, 'business'), true); assert.equal(open(app, 'organization'), true);
    const reload = await setup({ url: 'https://example.test/#users', storage: snapshot(app) });
    assert.equal(reload.d.querySelector('.mobile-menu').getAttribute('aria-expanded'), 'false');
    assert.equal(open(reload, 'business'), true); assert.equal(open(reload, 'organization'), true);
  });
  await test('mobile disclosure retains matching state when history restores the page', async setup => {
    const app = await setup(); const button = app.d.querySelector('.mobile-menu');
    button.click();
    app.w.dispatchEvent(new app.w.PageTransitionEvent('pageshow', { persisted: true }));
    assert.equal(button.getAttribute('aria-expanded'), 'true');
    assert.equal(app.d.querySelector('.shell').classList.contains('mobile-open'), true);
    app.d.dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert.equal(button.getAttribute('aria-expanded'), 'false'); assert.equal(app.d.activeElement, button);
  });
  await test('closing a sidebar dialog preserves the still-open mobile disclosure and scroll lock', async setup => {
    const app = await setup(); const button = app.d.querySelector('.mobile-menu');
    button.click();
    const trigger = app.d.querySelector('.sidebar [data-action="docs"]'); trigger.focus(); trigger.click();
    await wait(); assert.ok(app.d.querySelector('#overlay-root .drawer'));
    app.d.querySelector('#overlay-root [data-action="close"]').click();
    assert.equal(app.d.querySelector('#overlay-root').children.length, 0);
    assert.equal(button.getAttribute('aria-expanded'), 'true');
    assert.equal(app.d.querySelector('.shell').classList.contains('mobile-open'), true);
    assert.equal(app.d.body.style.overflow, 'hidden'); assert.equal(app.d.activeElement, trigger);
    trigger.dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert.equal(button.getAttribute('aria-expanded'), 'false'); assert.equal(app.d.body.style.overflow, '');
    assert.equal(app.d.activeElement, button);
  });
  await test('layout replacement restores open mobile ARIA and connected sidebar focus', async setup => {
    const app = await setup({ url: 'https://example.test/#settings' });
    const previous = app.d.querySelector('.mobile-menu'); previous.click();
    // Exercise the existing layout redraw without relying on a private app API.
    app.d.querySelector('#settings-form').dispatchEvent(new app.w.Event('submit', { bubbles: true, cancelable: true }));
    const button = app.d.querySelector('.mobile-menu');
    assert.notEqual(button, previous); assert.equal(button.getAttribute('aria-expanded'), 'true');
    assert.equal(app.d.getElementById(button.getAttribute('aria-controls')), app.d.querySelector('.sidebar'));
    assert.equal(app.d.querySelector('.shell').classList.contains('mobile-open'), true);
    assert.equal(app.d.body.style.overflow, 'hidden');
    assert.equal(app.d.activeElement, app.d.querySelector('.sidebar a'));
    app.d.dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert.equal(button.getAttribute('aria-expanded'), 'false'); assert.equal(app.d.activeElement, button);
  });
  await test('saving a command-search editor returns to the still-open mobile sidebar', async setup => {
    const app = await setup(); app.d.querySelector('.mobile-menu').click();
    app.d.dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true, cancelable: true }));
    const search = app.d.querySelector('#command-search'); search.value = '林知夏';
    search.dispatchEvent(new app.w.Event('input', { bubbles: true }));
    app.d.querySelector('.command-results [data-edit="1"]').click(); await wait();
    app.d.querySelector('#user-form').dispatchEvent(new app.w.Event('submit', { bubbles: true, cancelable: true }));
    const button = app.d.querySelector('.mobile-menu');
    assert.equal(app.d.querySelector('#overlay-root').children.length, 0);
    assert.equal(button.getAttribute('aria-expanded'), 'true');
    assert.equal(app.d.querySelector('.shell').classList.contains('mobile-open'), true);
    assert.equal(app.d.body.style.overflow, 'hidden'); assert.equal(app.d.activeElement, app.d.querySelector('.sidebar a'));
    app.d.dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert.equal(app.d.activeElement, button); assert.equal(button.getAttribute('aria-expanded'), 'false');
  });
  await test('read-denied but writable storage preserves unread choices through clicks until reload', async setup => {
    const previous = JSON.stringify({ version: 2, nodes: { system: true, developer: true } });
    let originalGet;
    const app = await setup({ storage: { [key]: previous }, beforeLoad(w) {
      originalGet = w.Storage.prototype.getItem;
      w.Storage.prototype.getItem = function () { throw Error('read denied'); };
    } });
    click(app, 'business'); assert.equal(open(app, 'business'), true);
    assert.equal(originalGet.call(app.w.localStorage, key), previous);
    app.w.Storage.prototype.getItem = originalGet;
    click(app, 'organization');
    assert.equal(app.w.localStorage.getItem(key), previous);
    const reload = await setup({ storage: { [key]: previous } });
    assert.equal(open(reload, 'system'), true); assert.equal(open(reload, 'developer'), true);
    assert.equal(open(reload, 'business'), false);
  });
  console.log(`TOTAL ${passed} preview navigation scenarios passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
