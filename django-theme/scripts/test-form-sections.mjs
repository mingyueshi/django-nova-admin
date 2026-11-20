import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const source = readFileSync(new URL('../src/nova_admin/static/nova_admin/form-sections.js', import.meta.url), 'utf8');
function changeForm({scope = 'account-and-site', model = 'catalog.product', stored = {}, error = false, blocked = false} = {}) {
    const invalid = error ? '<ul class="errorlist"><li>Invalid</li></ul>' : '';
    const dom = new JSDOM(`<body class="change-form"><div id="content-main"><form>
        <fieldset class="module"><h2 class="fieldset-heading" id="main">Main</h2><input name="other"></fieldset>
        <fieldset class="module collapse"><details><summary><h2 class="fieldset-heading" id="stock">Stock</h2></summary>
            <div class="form-row field-count">${invalid}<input name="count" ${error ? 'aria-invalid="true"' : ''}></div>
        </details></fieldset></form></div></body>`, {runScripts: 'dangerously', url: 'https://example.test/admin/'});
    const {window} = dom;
    const doc = window.document;
    window.HTMLElement.prototype.getClientRects = () => [{width: 30, height: 20}];
    for (const [key, value] of Object.entries(stored)) window.sessionStorage.setItem(key, value);
    if (blocked) Object.defineProperty(window, 'sessionStorage', {get() { throw Error('Blocked'); }});
    const script = doc.createElement('script');
    Object.assign(script.dataset, {scope, model, sections: 'Form sections'});
    script.textContent = source;
    doc.body.append(script);
    return {window, doc, details: doc.querySelector('details')};
}

const first = changeForm();
const input = first.doc.querySelector('[name=count]');
input.value = 'dirty';
first.doc.querySelector('nav a[href="#stock"]').click();
assert.equal(first.details.open, true);
assert.equal(first.doc.activeElement.id, 'stock');
assert.equal(first.doc.querySelector('[name=count]'), input);
assert.equal(input.value, 'dirty');
// Exercise an immediate navigation, before the browser's queued toggle event.
first.window.dispatchEvent(new first.window.Event('pagehide'));
const stored = {...first.window.sessionStorage};
assert.deepEqual(Object.values(stored), ['1']);
first.window.close();

for (const [options, open] of [[{}, true], [{scope: 'another-account-or-site'}, false],
    [{model: 'catalog.other'}, false], [{blocked: true}, false]]) {
    const form = changeForm({...options, stored});
    assert.equal(form.details.open, open);
    assert.equal(form.doc.querySelectorAll('nav a').length, 2);
    form.window.close();
}

const closed = Object.fromEntries(Object.keys(stored).map(key => [key, '0']));
const invalid = changeForm({error: true, stored: closed});
invalid.window.dispatchEvent(new invalid.window.Event('load'));
assert.equal(invalid.details.open, true);
assert.equal(invalid.doc.activeElement.name, 'count');
invalid.window.dispatchEvent(new invalid.window.Event('pagehide'));
assert.deepEqual({...invalid.window.sessionStorage}, closed);
invalid.window.close();
console.log('PASS Form anchors, immediate navigation, isolated fold preferences, unavailable storage and validation focus');
