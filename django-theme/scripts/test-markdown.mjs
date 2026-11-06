import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {JSDOM} = require('jsdom');
const source = readFileSync(new URL('../src/nova_admin/static/nova_admin/markdown.js', import.meta.url), 'utf8');
const labels = {toolbar:'Markdown formatting', bold:'Bold', italic:'Italic', code:'Inline code', link:'Link', heading:'Heading', list:'Bulleted list', quote:'Blockquote'};
let count = 0;
function check(label, run) { run(); count++; console.log('PASS', label); }
function setup({body = 'nova-admin', popup = false, markup = '', omitLabels = false} = {}) {
    const config = omitLabels ? '' : `<script type="application/json" id="nova-md-labels">${JSON.stringify(labels)}</script>`;
    const dom = new JSDOM(`<body class="${body}${popup ? ' popup' : ''}">${config}${markup}</body>`, {runScripts:'outside-only', url:'https://admin.example.test/admin/'});
    dom.window.eval(source);
    return {w: dom.window, d: dom.window.document};
}
const marked = (extra = '') => `<form><div class="form-row"><textarea id="body" data-nova-markdown ${extra}>Line one</textarea></div><textarea id="plain"></textarea></form>`;
const toolbar = d => d.querySelector('.nova-md-toolbar');

check('marked textarea gains a labelled toolbar with seven insert buttons', () => {
    const {d} = setup({markup: marked()});
    const bar = toolbar(d);
    assert.ok(bar);
    assert.equal(bar.getAttribute('role'), 'toolbar');
    assert.equal(bar.getAttribute('aria-label'), 'Markdown formatting');
    assert.equal(bar.previousElementSibling, null);
    assert.equal(d.querySelector('#body').previousElementSibling, bar);
    assert.equal(bar.querySelectorAll('button').length, 7);
    assert.equal(d.querySelector('.nova-md-bold').getAttribute('aria-label'), 'Bold');
    assert.equal(d.querySelector('.nova-md-bold').type, 'button');
});
check('unmarked textareas stay untouched', () => {
    const {d} = setup({markup: marked()});
    assert.equal(d.querySelector('#plain').closest('.nova-md-field'), null);
    assert.equal(d.querySelectorAll('.nova-md-toolbar').length, 1);
    assert.equal(d.querySelectorAll('.nova-md-toolbar .nova-md-button').length, 7);
});
check('popups and non-admin bodies never enhance', () => {
    for (const options of [{popup: true, markup: marked()}, {body: '', markup: marked()}, {omitLabels: true, markup: marked()}]) {
        const {d} = setup(options);
        assert.equal(toolbar(d), null);
    }
});
check('bold wraps the current selection and keeps it selected', () => {
    const {d, w} = setup({markup: marked()});
    const area = d.querySelector('#body');
    area.setSelectionRange(0, 9);
    d.querySelector('.nova-md-bold').click();
    assert.equal(area.value, '**Line one**');
    assert.deepEqual([area.selectionStart, area.selectionEnd], [2, 10]);
    assert.equal(d.activeElement, area);
});
check('empty selections insert a placeholder and select it', () => {
    const {d} = setup({markup: marked()});
    const area = d.querySelector('#body');
    area.setSelectionRange(9, 9);
    d.querySelector('.nova-md-italic').click();
    assert.equal(area.value, 'Line one*text*');
    assert.deepEqual([area.selectionStart, area.selectionEnd], [9, 13]);
});
check('prefix actions insert at the cursor without swallowing text', () => {
    const {d} = setup({markup: marked()});
    const area = d.querySelector('#body');
    area.setSelectionRange(9, 9);
    d.querySelector('.nova-md-heading').click();
    assert.equal(area.value, 'Line one## ');
    d.querySelector('#plain');
    d.querySelector('.nova-md-list').click();
    assert.equal(area.value, 'Line one## - ');
});
check('code and link actions wrap their placeholder for hosts', () => {
    const {d} = setup({markup: marked()});
    const area = d.querySelector('#body');
    area.setSelectionRange(0, 0);
    d.querySelector('.nova-md-code').click();
    assert.equal(area.value, '`code`Line one');
    area.setSelectionRange(area.value.length, area.value.length);
    d.querySelector('.nova-md-link').click();
    assert.equal(area.value, '`code`Line one[label](https://)');
});
check('block quote and repeated runs stay idempotent', () => {
    const {d, w} = setup({markup: marked()});
    d.querySelector('.nova-md-quote').click();
    w.eval(source);
    assert.equal(d.querySelectorAll('.nova-md-toolbar').length, 1);
    const area = d.querySelector('#body');
    assert.equal(area.value, '> Line one');
});
check('disabled and readonly textareas are never modified', () => {
    const {d} = setup({markup: marked('disabled') + '<textarea id="ro" data-nova-markdown readonly></textarea>'});
    assert.equal(toolbar(d), null);
    assert.equal(d.querySelector('#ro').dataset.novaMdReady, undefined);
});
check('inserted content fires a bubbling input event for host listeners', () => {
    const {d} = setup({markup: marked()});
    let fired = 0;
    d.querySelector('form').addEventListener('input', () => fired++);
    d.querySelector('.nova-md-bold').click();
    assert.equal(fired, 1);
});
console.log(`${count} markdown DOM scenarios passed.`);
