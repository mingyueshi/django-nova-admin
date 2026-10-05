import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {JSDOM} = require('jsdom');
const script = readFileSync(new URL('../src/nova_admin/static/nova_admin/enhancements.js', import.meta.url), 'utf8');
let count = 0;
function run(label, {body = 'nova-admin', attrs = '', help = '', fallback = 'Search records…'} = {}, check) {
    const dom = new JSDOM(`<body class="${body}"><script data-nova-search-placeholder="${fallback}"></script><form id="changelist-search" method="get"><label for="searchbar">Search</label><input id="searchbar" name="q" value="kept" aria-describedby="searchbar_helptext" ${attrs}><div id="searchbar_helptext">${help}</div></form></body>`, {runScripts:'outside-only'});
    try {dom.window.eval(script); check(dom.window.document); count++; console.log('PASS', label);} finally {dom.window.close();}
}
run('ModelAdmin help becomes a placeholder without replacing visible help', {help:'Search SKU or title'}, d => {assert.equal(d.querySelector('input').placeholder,'Search SKU or title'); assert.equal(d.querySelector('#searchbar_helptext').textContent,'Search SKU or title');});
run('Localized fallback works', {fallback:'搜索记录…'}, d => assert.equal(d.querySelector('input').placeholder,'搜索记录…'));
run('Existing placeholder is preserved', {attrs:'placeholder="Custom search"'}, d => assert.equal(d.querySelector('input').placeholder,'Custom search'));
run('Explicit empty placeholder is preserved', {attrs:'placeholder=""'}, d => assert.equal(d.querySelector('input').placeholder,''));
run('Native mode is untouched', {body:''}, d => assert.equal(d.querySelector('input').hasAttribute('placeholder'),false));
run('Disabled input is untouched', {attrs:'disabled'}, d => assert.equal(d.querySelector('input').hasAttribute('placeholder'),false));
run('Readonly input is untouched', {attrs:'readonly'}, d => assert.equal(d.querySelector('input').hasAttribute('placeholder'),false));
run('Form values and label semantics are unchanged', {}, d => {assert.equal(d.querySelector('input').value,'kept');assert.equal(d.querySelector('input').name,'q');assert.equal(d.querySelector('form').method,'get');assert.equal(d.querySelector('label').htmlFor,'searchbar');assert.equal(d.querySelector('input').getAttribute('aria-describedby'),'searchbar_helptext');});
console.log(`TOTAL ${count} search enhancement tests passed`);
