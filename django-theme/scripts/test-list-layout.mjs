import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const source = readFileSync(new URL('../src/nova_admin/static/nova_admin/list-layout.js', import.meta.url), 'utf8');
for (const withActions of [true, false]) {
    const dom = new JSDOM(`<form id="changelist-form"><div class="results"><table id="result_list">
        <thead><tr>${withActions ? '<th class="action-checkbox-column"></th>' : ''}
        <th><div class="text"><a href="?o=1">Name</a></div></th><th><div class="text">Count</div></th></tr></thead>
        <tbody><tr><td colspan="${withActions ? 3 : 2}">Error</td></tr>
        <tr>${withActions ? '<td class="action-checkbox"></td>' : ''}<th>Name</th><td><input name="count"></td></tr></tbody>
        </table></div></form>`, {runScripts: 'dangerously', url: 'https://example.test/admin/'});
    const {window} = dom;
    const doc = window.document;
    const table = doc.querySelector('table');
    Object.defineProperty(table.parentElement, 'clientWidth', {value: 400});
    window.HTMLTableCellElement.prototype.getClientRects = () => [{width: 100}];
    window.HTMLTableCellElement.prototype.getBoundingClientRect = function () {
        return {width: table.classList.contains('nova-sized') ? parseFloat(this.style.getPropertyValue('--nova-column-width')) : 100};
    };
    const stock = doc.querySelector('input');
    stock.value = 'unsaved';
    const script = doc.createElement('script');
    Object.assign(script.dataset, {resize: 'Resize', help: 'Use arrow keys'});
    script.textContent = source;
    doc.body.append(script);
    assert.equal(table.querySelectorAll('.nova-pinned').length, 2);
    assert.equal(table.querySelector('tbody .nova-pinned').textContent, 'Name');
    assert.equal(table.querySelector('[colspan]').classList.contains('nova-pinned'), false);
    const handle = table.querySelector('.nova-pinned [role=separator]');
    const press = key => handle.dispatchEvent(new window.KeyboardEvent('keydown', {key, bubbles: true}));
    press('ArrowRight');
    assert.equal(handle.getAttribute('aria-valuenow'), '116');
    assert.equal(table.querySelector('.nova-pinned a').getAttribute('href'), '?o=1');
    press('Home');
    assert.equal(table.classList.contains('nova-sized'), false);
    assert.equal(doc.querySelector('input'), stock);
    assert.equal(stock.value, 'unsaved');
    window.close();
}
console.log('PASS Resizing and pinning the business column with and without actions preserves sort links, edits and error rows');
