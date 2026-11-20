import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const source = readFileSync(new URL('../src/nova_admin/static/nova_admin/action-selection.js', import.meta.url), 'utf8');
const key = 'nova.admin.action-selection.v1';
function list(values, {stored, scope = 'same-filter', limit = '1000', blocked = false} = {}) {
    const rows = values.map(value => `<tr><td><input class="action-select" type="checkbox" name="_selected_action" value="${value}"></td></tr>`);
    const dom = new JSDOM(`<form id="changelist-form"><div class="actions">
        <select name="action"><option value="publish">Publish</option></select><input class="select-across" name="select_across" value="0">
        <button name="index" value="0">Run</button><span class="action-counter"></span><span class="question"><a href="#">All matches</a></span>
        </div><table id="result_list"><thead><tr><th><input type="checkbox" id="action-toggle"></th></tr></thead>
        <tbody>${rows.join('')}</tbody></table><input name="form-0-id" value="${values[0]}"><input type="submit" name="_save"></form>`,
        {url: 'https://example.test/admin/', runScripts: 'dangerously'});
    const w = dom.window;
    const d = w.document;
    const form = d.querySelector('form');
    w.FormDataEvent = w.Event; // jsdom has FormData but doesn't dispatch the browser's formdata event.
    if (stored) w.sessionStorage.setItem(key, stored);
    if (blocked) Object.defineProperty(w, 'sessionStorage', {get() { throw Error('Storage denied'); }});
    const script = d.createElement('script');
    Object.assign(script.dataset, {scope, maxFields: limit, manual: '{page}/{total}', all: 'All matches',
        clear: 'Clear', limit: 'Reduce selection', unavailable: 'This page only'});
    script.textContent = source;
    d.body.append(script);
    function check(index, checked = true) {
        const box = form.querySelectorAll('.action-select')[index];
        box.checked = checked;
        box.dispatchEvent(new w.Event('change', {bubbles: true}));
    }
    function submit(name, cancelAfterSerialization = false) {
        const button = form.elements.namedItem(name);
        const event = new w.SubmitEvent('submit', {submitter: button, cancelable: true});
        form.dispatchEvent(event);
        if (event.defaultPrevented) return null;
        const data = new w.FormData(form, button);
        const serialization = new w.Event('formdata');
        serialization.formData = data;
        form.dispatchEvent(serialization);
        if (cancelAfterSerialization) event.preventDefault();
        w.dispatchEvent(new w.Event('pagehide'));
        return data;
    }
    return {w, d, check, submit, count: () => d.querySelector('.action-counter').textContent,
        state: () => w.sessionStorage.getItem(key), close: () => w.close()};
}

const first = list(['uuid-A', 'uuid-B']);
first.check(0);
const second = list(['uuid-C', 'uuid-D'], {stored: first.state()});
second.check(1);
assert.equal(second.count(), '1/2');
const selected = second.state();
const third = list(['uuid-E'], {stored: selected});
assert.equal(third.count(), '0/2');
const save = third.submit('_save');
assert.deepEqual(save.getAll('_selected_action'), []);
assert.deepEqual(save.getAll('form-0-id'), ['uuid-E']);
assert.equal(third.state(), selected);
third.submit('index', true);
assert.equal(third.state(), selected);
const run = third.submit('index');
assert.deepEqual(run.getAll('_selected_action'), ['uuid-A', 'uuid-D']);
assert.deepEqual(run.getAll('select_across'), ['0']);
assert.equal(third.state(), null);
[first, second, third].forEach(page => page.close());

const limited = list(['uuid-E'], {stored: selected, limit: '4'});
assert.equal(limited.submit('index'), null);
assert.equal(limited.state(), selected);
assert.equal(limited.d.querySelector('[role=status]').textContent, 'Reduce selection');
limited.close();

const other = list(['uuid-A'], {scope: 'another-filter', stored: selected});
assert.equal(other.count(), '0/0');
assert.equal(other.state(), null);
other.check(0);
assert.equal(other.d.querySelector('.select-across').value, '0');
assert.equal(other.count(), '1/1');
// Django sets the hidden input when its explicit "all matches" link is clicked.
other.d.querySelector('.question a').addEventListener('click', event => {
    event.preventDefault();
    other.d.querySelector('.select-across').value = '1';
});
other.d.querySelector('.question a').click();
assert.equal(other.count(), 'All matches');
const all = list(['uuid-E', 'uuid-F'], {scope: 'another-filter', stored: other.state()});
assert.equal(all.d.querySelectorAll('.action-select:checked').length, 2);
all.check(0, false);
assert.equal(all.count(), '1/1');
assert.deepEqual(all.submit('index').getAll('_selected_action'), ['uuid-F']);
other.close();
all.close();

const unavailable = list(['uuid-A'], {blocked: true});
assert.equal(unavailable.d.querySelector('[role=status]').textContent, 'This page only');
assert.equal(unavailable.d.querySelectorAll('.actions button').length, 1);
unavailable.close();
console.log('PASS Cross-page manual IDs, native all matches, page-local saves, scope changes, cancellation and field limits');
