import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const script = readFileSync(new URL('../src/nova_admin/static/nova_admin/columns.js', import.meta.url), 'utf8');

export async function testColumns() {
    const option = (key, index, visible) => `<li data-default-index="${index}">
        <input type="hidden" name="order" value="${key}">
        <input type="checkbox" name="visible" value="${key}" ${visible ? 'checked' : ''}>
        <button data-move="-1" type="button">↑</button><button data-move="1" type="button">↓</button></li>`;
    const dom = new JSDOM(`<details class="nova-columns" hidden><form method="post" data-saved="Saved" data-error="Failed">
        <ol>${option('stock', 1, true)}${option('sku', 0, false)}</ol>
        <button value="save"></button><button value="reset"></button><span role="status"></span></form></details>
        <form id="business"><table id="result_list"><thead><tr><th>Name</th><th class="column-sku">SKU</th>
        <th>Featured</th><th class="column-stock">Stock</th></tr></thead><tbody>
        <tr><td colspan="4">Validation error</td></tr>
        <tr><th>Name</th><td class="field-sku">X</td><td><input name="featured"></td><td class="field-stock">10</td></tr>
        </tbody></table></form>`, {runScripts: 'outside-only', url: 'https://test.invalid/list/?o=2'});
    const w = dom.window;
    const d = w.document;
    const featured = d.querySelector('[name=featured]');
    featured.value = 'unsaved';
    const requests = [];
    let ok = false;
    w.fetch = async (url, init) => {
        requests.push({url, fields: Array.from(init.body)});
        return {ok, json: async () => ({saved: true})};
    };
    const headings = () => Array.from(d.querySelectorAll('thead th'), cell => cell.textContent);
    const submit = async action => {
        d.querySelector(`button[value="${action}"]`).click();
        await new Promise(resolve => w.setTimeout(resolve, 0));
    };
    const scenarios = [
        ['Restore ordering without disturbing editable fields or error rows', () => {
            w.eval(script);
            assert.deepEqual(headings(), ['Name', 'Stock', 'Featured', 'SKU']);
            assert.ok(d.querySelector('.column-sku').hasAttribute('data-nova-column-hidden'));
            assert.equal(d.querySelectorAll('tbody tr')[1].cells[1].textContent, '10');
            assert.equal(d.querySelector('td[colspan]').textContent, 'Validation error');
            assert.equal(featured.form.id, 'business');
            assert.equal(requests.length, 0);
        }],
        ['A failed reset preserves the applied column layout', async () => {
            await submit('reset');
            assert.equal(d.querySelector('[role=status]').textContent, 'Failed');
            assert.deepEqual(headings(), ['Name', 'Stock', 'Featured', 'SKU']);
            assert.ok(d.querySelector('.field-sku').hasAttribute('data-nova-column-hidden'));
        }],
        ['A successful retry restores defaults without posting business fields', async () => {
            ok = true;
            await submit('reset');
            assert.equal(d.querySelector('[role=status]').textContent, 'Saved');
            assert.deepEqual(headings(), ['Name', 'SKU', 'Featured', 'Stock']);
            assert.equal(d.querySelectorAll('[data-nova-column-hidden]').length, 0);
            assert.equal(featured.value, 'unsaved');
            assert.equal(requests[1].url, 'https://test.invalid/list/?o=2');
            assert.ok(requests.every(({fields}) => fields.every(([name]) => name !== 'featured')));
        }],
    ];
    try {
        for (const [name, check] of scenarios) {
            await check();
            console.log('PASS', name);
        }
        return scenarios.length;
    } finally {
        w.close();
    }
}
