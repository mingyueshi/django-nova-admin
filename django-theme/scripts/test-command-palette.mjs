/* DOM contracts only. Real dialog layout/focus is verified separately in a browser. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const {JSDOM, VirtualConsole} = createRequire(import.meta.url)('jsdom');
const source = readFileSync(new URL('../src/nova_admin/static/nova_admin/command-palette.js', import.meta.url), 'utf8');
const row = (href, name) => `<tr><th scope="row">${href ? `<a href="${href}"><span class="nova-nav-model-label">${name}</span><span>9999</span></a>` : `<span class="nova-nav-model-label">${name}</span>`}</th><td><a href="/warehouse/catalog/draft/add/">Add</a></td></tr>`;
function setup(options = {}) {
  const errors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', error => errors.push(error));
  const dom = new JSDOM(`<!doctype html><body class="${options.native ? '' : 'nova-admin'}"><button id="outside">Outside</button><input id="editing"><textarea></textarea><div contenteditable="true" tabindex="0">Editor</div><select><option>Choice</option></select><div role="textbox" tabindex="0">Rich text</div>
    <nav class="nova-navigation"><a class="nova-nav-home" href="${options.home || '/warehouse/'}">Site overview ↗</a><input id="nav-filter" value="unchanged"><section data-nova-favorites hidden>Saved favorite</section><details class="nova-nav-group"><summary><span>商品示例 R&amp;D</span><span>99</span></summary><table><tbody>${options.rows ?? row('/warehouse/catalog/product/', '商品 Products') + row('/warehouse/catalog/category/', '分类 Categories') + row(null, 'Draft only')}</tbody></table></details></nav>
    <button type="button" data-nova-command-open hidden><kbd data-nova-command-shortcut></kbd>Search navigation</button><dialog id="nova-command-palette" hidden data-count-message="Results: {count}"><button type="button" data-nova-command-close>Close</button><input data-nova-command-query><p data-nova-command-status></p><ul data-nova-command-results></ul><p data-nova-command-empty hidden>Empty</p></dialog>`, {url: 'https://example.invalid/warehouse/', runScripts: 'outside-only', virtualConsole});
  const w = dom.window, d = w.document;
  for (const name of ['localStorage', 'sessionStorage']) Object.defineProperty(w, name, {get() { throw Error('Command palette must not access storage'); }});
  for (const name of ['fetch', 'XMLHttpRequest']) w[name] = () => { throw Error('Command palette must not request data'); };
  if (options.platform) Object.defineProperty(w.navigator, 'platform', {value: options.platform});
  if (options.dialog !== false) {
    w.HTMLDialogElement.prototype.showModal = function () {
      if (options.throwDialog) throw Error('Unavailable dialog');
      this.setAttribute('open', '');
    };
    w.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); if (!options.queuedClose) this.dispatchEvent(new w.Event('close')); };
  }
  if (options.noNav) d.querySelector('nav').remove();
  if (options.noMarkup) d.querySelector('dialog').remove();
  w.eval(source);
  const dialog = d.querySelector('dialog'), query = d.querySelector('[data-nova-command-query]'), trigger = d.querySelector('[data-nova-command-open]');
  return {w, d, dialog, query, trigger, errors,
    open() { trigger.focus(); trigger.click(); },
    links() { return [...d.querySelectorAll('[data-nova-command-results] a')]; },
    search(value) { query.value = value; query.dispatchEvent(new w.Event('input', {bubbles: true})); },
    key(target, key, more = {}) { const event = new w.KeyboardEvent('keydown', {key, bubbles: true, cancelable: true, ...more}); target.dispatchEvent(event); return event; },
    finish() { assert.deepEqual(errors, []); w.close(); },
  };
}
let count = 0;
function test(name, body) { try { body(); count++; } catch (e) { e.message = `Command palette: ${name}: ${e.message}`; throw e; } }
test('only permitted list anchors and site home', () => {
  const r = setup(); r.open(); assert.deepEqual(r.links().map(a => a.pathname), ['/warehouse/', '/warehouse/catalog/product/', '/warehouse/catalog/category/']);
  assert.ok(!r.dialog.textContent.includes('Draft only')); assert.ok(!r.dialog.textContent.includes('9999')); r.finish();
});
test('search app names and model names with all tokens', () => {
  const r = setup(); r.open(); r.search('R&D PRODUCTS'); assert.equal(r.links().length, 1); assert.match(r.links()[0].textContent, /商品 Products/);
  r.search('示例 分类'); assert.equal(r.links().length, 1); r.search('ＰＲＯＤＵＣＴＳ'); assert.equal(r.links().length, 1); r.finish();
});
test('empty results keep input and keyboard usable', () => {
  const r = setup(); r.open(); r.search('none'); assert.equal(r.links().length, 0); assert.equal(r.d.querySelector('[data-nova-command-empty]').hidden, false);
  r.key(r.query, 'ArrowDown'); r.key(r.query, 'ArrowUp'); r.key(r.query, 'Enter'); assert.equal(r.d.activeElement, r.query);
  assert.equal(r.d.querySelector('[data-nova-command-status]').textContent, 'Results: 0'); r.finish();
});
test('text content never becomes markup', () => {
  const r = setup(); r.d.querySelector('.nova-nav-model-label').textContent = '<img src=x onerror=alert(1)>'.repeat(20); r.open();
  r.search('<img'); assert.equal(r.links().length, 1); assert.equal(r.dialog.querySelector('img'), null); r.finish();
});
test('dangerous external and other site URLs are rejected', () => {
  const unsafe = ['javascript:alert(1)', 'data:text/plain,x', 'https://evil.invalid/warehouse/a/', '//example.invalid/warehouse/a/', '/review/catalog/product/', '/warehouse-other/product/', '/warehouse/%2e%2e/review/', '/warehouse/a%2fb%2f%2f/', '/warehouse/%5c/evil/', '/warehouse/a/?token=1', '/warehouse/a/#x', '/warehouse/%ZZ/', 'https://user:pass@example.invalid/warehouse/a/'];
  const r = setup({rows: unsafe.map(href => row(href, 'Unsafe')).join('') + row('/warehouse/catalog/product/', 'Allowed')}); r.open();
  assert.deepEqual(r.links().map(a => a.pathname), ['/warehouse/', '/warehouse/catalog/product/']); r.finish();
});
test('invalid site home leaves entry hidden', () => {
  for (const home of ['https://evil.invalid/', '/warehouse?query=x', 'javascript:void(0)', '/warehouse']) { const r = setup({home}); assert.equal(r.trigger.hidden, true); r.finish(); }
});
test('same origin site URL accepted and duplicates removed', () => {
  const r = setup({rows: row('/warehouse/catalog/product/', 'First') + row('https://example.invalid/warehouse/catalog/product/', 'Duplicate')}); r.open();
  assert.equal(r.links().length, 2); assert.match(r.links()[1].textContent, /First/); r.finish();
});
test('home-only staff has usable navigation', () => { const r = setup({rows: ''}); r.open(); assert.equal(r.links().length, 1); r.finish(); });
test('no dialog support leaves original navigation usable', () => {
  const r = setup({dialog: false}); assert.equal(r.trigger.hidden, true); assert.equal(r.d.querySelector('#nav-filter').disabled, false);
  assert.equal(r.key(r.d.body, 'k', {ctrlKey: true}).defaultPrevented, false); r.finish();
});
test('native missing navigation and missing markup stay inert', () => {
  for (const options of [{native: true}, {noNav: true}, {noMarkup: true}]) { const r = setup(options); assert.equal(r.trigger.hidden, true); r.finish(); }
});
test('showModal failure hides entry and restores fallback', () => {
  const r = setup({throwDialog: true}); r.open(); assert.equal(r.trigger.hidden, true); assert.equal(r.dialog.hidden, true);
  assert.equal(r.key(r.d.body, 'k', {ctrlKey: true}).defaultPrevented, false); r.finish();
});
test('explicit entry focuses input and Escape restores opener', () => {
  const r = setup(); r.open(); assert.equal(r.d.activeElement, r.query); r.key(r.query, 'Escape');
  assert.equal(r.dialog.open, false); assert.equal(r.dialog.hidden, true); assert.equal(r.d.activeElement, r.trigger); assert.equal(r.links().length, 0); r.finish();
});
test('Ctrl and Command shortcuts return to their actual opener', () => {
  for (const modifier of ['ctrlKey', 'metaKey']) { const r = setup({platform: modifier === 'metaKey' ? 'MacIntel' : 'Linux'}); const outside = r.d.getElementById('outside'); outside.focus();
    assert.equal(r.key(outside, 'k', {[modifier]: true}).defaultPrevented, true); assert.equal(r.dialog.open, true); r.key(r.query, 'Escape'); assert.equal(r.d.activeElement, outside); r.finish(); }
});
test('editing shortcuts and modifier variants are not intercepted', () => {
  const r = setup(); for (const el of r.d.querySelectorAll('input,textarea,select,[contenteditable],[role="textbox"]')) { el.focus(); assert.equal(r.key(el, 'k', {ctrlKey: true}).defaultPrevented, false); }
  for (const more of [{ctrlKey: true, altKey: true}, {metaKey: true, shiftKey: true}, {}]) assert.equal(r.key(r.d.body, 'k', more).defaultPrevented, false);
  r.d.designMode = 'on'; assert.equal(r.key(r.d.body, 'k', {ctrlKey: true}).defaultPrevented, false); assert.equal(r.dialog.open, false); r.finish();
});
test('IME never opens or activates or closes', () => {
  const r = setup(); assert.equal(r.key(r.d.body, 'k', {ctrlKey: true, isComposing: true}).defaultPrevented, false); r.open(); let activated = 0;
  r.dialog.addEventListener('click', e => { if (e.target.closest('a')) { e.preventDefault(); activated++; } });
  r.query.dispatchEvent(new r.w.CompositionEvent('compositionstart')); r.search('商品'); r.key(r.query, 'Enter'); r.key(r.query, 'Escape');
  assert.equal(activated, 0); assert.equal(r.dialog.open, true); r.query.dispatchEvent(new r.w.CompositionEvent('compositionend')); assert.equal(r.links().length, 2);
  r.key(r.query, 'Enter', {keyCode: 229}); assert.equal(activated, 0); r.finish();
});
test('arrows select links and Up returns to query', () => {
  const r = setup(); r.open(); r.key(r.query, 'ArrowDown'); assert.equal(r.d.activeElement, r.links()[0]);
  r.key(r.d.activeElement, 'ArrowDown'); assert.equal(r.d.activeElement, r.links()[1]); r.key(r.d.activeElement, 'ArrowUp'); assert.equal(r.d.activeElement, r.links()[0]);
  r.key(r.d.activeElement, 'ArrowUp'); assert.equal(r.d.activeElement, r.query); r.key(r.query, 'ArrowUp'); assert.equal(r.d.activeElement, r.links().at(-1)); r.finish();
});
test('Enter from query activates selected destination', () => {
  const r = setup(); r.open(); r.search('Products'); let href;
  r.dialog.addEventListener('click', e => { if (e.target.closest('a')) { e.preventDefault(); href = e.target.closest('a').href; } });
  r.key(r.query, 'Enter'); assert.equal(href, 'https://example.invalid/warehouse/catalog/product/'); r.finish();
});
test('Tab and Shift Tab constrain focus including empty state', () => {
  const r = setup(); r.open(); const close = r.d.querySelector('[data-nova-command-close]'); close.focus(); r.key(close, 'Tab', {shiftKey: true}); assert.equal(r.d.activeElement, r.links()[0]);
  r.key(r.d.activeElement, 'Tab'); assert.equal(r.d.activeElement, close); r.search('none'); r.query.focus(); r.key(r.query, 'Tab'); assert.equal(r.d.activeElement, close);
  r.key(close, 'Tab', {shiftKey: true}); assert.equal(r.d.activeElement, r.query); r.finish();
});
test('close control and cancel restore focus', () => {
  const r = setup(); r.open(); r.d.querySelector('[data-nova-command-close]').click(); assert.equal(r.d.activeElement, r.trigger);
  r.open(); r.dialog.dispatchEvent(new r.w.Event('cancel', {cancelable: true})); assert.equal(r.dialog.open, false); assert.equal(r.d.activeElement, r.trigger); r.finish();
});
test('fresh DOM is read on every open without menu cache', () => {
  const r = setup(); r.open(); r.key(r.query, 'Escape'); r.d.querySelector('tbody tr').remove(); r.open();
  assert.equal(r.links().some(a => a.pathname.includes('product')), false); assert.equal(r.query.value, ''); r.finish();
});
test('destination removed before activation cannot navigate', () => {
  const r = setup(); r.open(); r.search('Products'); r.d.querySelector('tbody tr').remove(); const link = r.links()[0];
  assert.equal(link.dispatchEvent(new r.w.MouseEvent('click', {bubbles: true, cancelable: true})), false); assert.equal(r.links().length, 0); assert.equal(r.d.activeElement, r.query); r.finish();
});
test('sidebar filters favorites and expansion state are unchanged', () => {
  const r = setup(); const nav = r.d.querySelector('nav'); const before = nav.outerHTML; r.open(); r.search('Products'); r.key(r.query, 'Escape'); assert.equal(nav.outerHTML, before); r.finish();
});
test('pagehide clears ephemeral menu and query', () => {
  const r = setup(); r.open(); r.search('Products'); r.w.dispatchEvent(new r.w.Event('pagehide')); assert.equal(r.dialog.open, false); assert.equal(r.query.value, ''); assert.equal(r.links().length, 0); r.finish();
});
test('reinitializing the script never duplicates handlers', () => {
  const r = setup(); r.w.eval(source); r.open(); assert.equal(r.links().length, 3); r.search('Products'); assert.equal(r.links().length, 1); r.finish();
});
test('queued native close from a previous opening never hides the next modal', () => {
  const r = setup({queuedClose: true}); r.open(); r.search('Products'); r.key(r.query, 'Escape');
  assert.equal(r.dialog.hidden, true); assert.equal(r.d.activeElement, r.trigger); r.open();
  r.dialog.dispatchEvent(new r.w.Event('close'));
  assert.equal(r.dialog.open, true); assert.equal(r.dialog.hidden, false); assert.equal(r.links().length, 3); assert.equal(r.d.activeElement, r.query);
  r.dialog.close(); r.trigger.click(); r.dialog.dispatchEvent(new r.w.Event('close'));
  assert.equal(r.dialog.open, true); assert.equal(r.dialog.hidden, false); assert.equal(r.d.activeElement, r.query);
  r.key(r.query, 'Escape'); assert.equal(r.d.activeElement, r.trigger); r.finish();
});
console.log(`${count} command palette DOM scenarios passed.`);
