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


function changelist({structure = 'external', body = 'nova-admin', filter = true, table = true, toolbar = true,
    evaluate = true, saved = null, storageFails = false, writeFails = false,
    resizeObserver = true, rtl = false, resultId = '', viewport = 320, width = 1000} = {}) {
    const filterHtml = filter ? `<${structure === 'internal' ? 'search' : 'nav'} id="changelist-filter"><h2>Filters</h2><a href="?q=kept&status=active">Active</a><form id="filter-choice" method="get"><input name="status" value="active"></form></${structure === 'internal' ? 'search' : 'nav'}>` : '';
    const search = '<form id="changelist-search" method="get"><label for="searchbar">Search</label><input id="searchbar" name="q" value="kept"><input type="hidden" name="category" value="2"></form>';
    const form = `<form id="changelist-form" method="post"><input name="csrfmiddlewaretoken" value="synthetic"><select name="action"><option value="publish">Publish</option></select>${table ? `<div class="results" ${resultId ? `id="${resultId}"` : ''} style="direction:${rtl ? 'rtl' : 'ltr'}"><table><tbody><tr><td><input type="checkbox" name="_selected_action" value="3" checked></td><td>Record</td></tr></tbody></table></div>` : ''}<button type="submit" name="_save">Save</button></form>`;
    const searchMarkup = toolbar ? `<div id="toolbar">${search}</div>` : search;
    const inner = structure === 'internal'
        ? `<div class="changelist-form-container">${filterHtml}<div>${searchMarkup}${form}</div></div>`
        : `<div class="changelist-form-container">${searchMarkup}${form}</div>${filterHtml}`;
    const dom = new JSDOM(`<body class="${body}"><script data-nova-search-placeholder="Search records…" data-nova-show-filters="显示过滤器" data-nova-hide-filters="隐藏过滤器" data-nova-scroll-table="横向滚动表格" data-nova-scroll-left="向左滚动表格" data-nova-scroll-right="向右滚动表格"></script><div id="changelist" class="module filtered">${inner}</div></body>`, {runScripts:'outside-only', url:'https://admin.example.test/admin/catalog/product/?q=kept'});
    const {window: w} = dom;
    const d = w.document;
    const sizes = {viewport, width, collapsedViewport: viewport};
    const viewportSize = () => d.querySelector('#changelist').classList.contains('nova-filters-collapsed') ? sizes.collapsedViewport : sizes.viewport;
    Object.defineProperty(w.HTMLElement.prototype, 'clientWidth', {configurable:true, get() {
        if (this.classList.contains('results')) return viewportSize();
        return 0;
    }});
    Object.defineProperty(w.HTMLElement.prototype, 'scrollWidth', {configurable:true, get() {
        if (this.classList.contains('results') || this.tagName === 'TABLE') return Math.max(sizes.width, viewportSize());
        return this.clientWidth;
    }});
    const results = d.querySelector('.results');
    if (results) {
        let offset = 0;
        const clamp = value => rtl ? Math.max(-Math.max(0, sizes.width - viewportSize()), Math.min(0, value)) : Math.max(0, Math.min(Math.max(0, sizes.width - viewportSize()), value));
        Object.defineProperty(results, 'scrollLeft', {configurable:true, get() {return clamp(offset);}, set(value) {offset = clamp(value);}});
    }
    const observations = [];
    if (resizeObserver) w.ResizeObserver = class {
        constructor(callback) {this.callback = callback; observations.push(this); this.elements = [];}
        observe(element) {this.elements.push(element);}
    };
    else w.ResizeObserver = undefined;
    const storageKey = 'nova.changelist.filters:/admin/catalog/product/';
    if (saved !== null) w.sessionStorage.setItem(storageKey, saved);
    if (storageFails) Object.defineProperty(w, 'sessionStorage', {get() {throw Error('Storage denied');}});
    else if (writeFails) w.Storage.prototype.setItem = () => {throw Error('Quota exceeded');};
    const before = d.body.innerHTML;
    if (evaluate) w.eval(script);
    return {w, d, sizes, results, observations, storageKey, before, close: () => w.close()};
}
function checkList(label, options, check) {
    const fixture = changelist(options);
    try {check(fixture); count++; console.log('PASS', label);} finally {fixture.close();}
}
const query = (fixture, selector) => fixture.d.querySelector(selector);
const contents = (w, form) => Array.from(new w.FormData(form));

for (const structure of ['external', 'internal']) {
    checkList(`${structure}: filter toggle is an independent localized button`, {structure}, f => {
        const toggle = query(f, '.nova-filter-toggle');
        assert.equal(toggle.type, 'button');
        assert.equal(toggle.closest('form'), null);
        assert.equal(toggle.parentElement.parentElement.id, 'toolbar');
        assert.equal(toggle.parentElement.previousElementSibling.id, 'changelist-search');
        assert.equal(toggle.getAttribute('aria-controls'), 'changelist-filter');
        assert.equal(toggle.getAttribute('aria-expanded'), 'true');
        assert.equal(toggle.textContent, '隐藏过滤器');
        toggle.focus();
        toggle.click();
        assert.equal(query(f, '#changelist-filter').hidden, true);
        assert.equal(query(f, '#changelist').classList.contains('nova-filters-collapsed'), true);
        assert.equal(toggle.getAttribute('aria-expanded'), 'false');
        assert.equal(toggle.textContent, '显示过滤器');
        toggle.click();
        assert.equal(query(f, '#changelist-filter').hidden, false);
        assert.equal(toggle.getAttribute('aria-expanded'), 'true');
        assert.equal(f.d.activeElement, toggle);
    });
    checkList(`${structure}: collapsing does not move controls or change GET/POST payloads`, {structure, evaluate:false}, f => {
        const controls = Array.from(f.d.querySelectorAll('form input, form select'));
        const parents = controls.map(control => control.parentNode);
        const forms = Array.from(f.d.querySelectorAll('form'));
        const payloads = forms.map(form => contents(f.w, form));
        const link = query(f, '#changelist-filter a');
        const destination = link.href;
        f.w.eval(script);
        query(f, '.nova-filter-toggle').click();
        query(f, '.nova-filter-toggle').click();
        assert.deepEqual(controls.map(control => control.parentNode), parents);
        assert.deepEqual(forms.map(form => contents(f.w, form)), payloads);
        assert.equal(query(f, '#changelist-search').method, 'get');
        assert.equal(query(f, '#changelist-form').method, 'post');
        assert.equal(link.href, destination);
        assert.equal(f.w.location.search, '?q=kept');
    });
}
checkList('No JavaScript leaves the original filter visible', {evaluate:false}, f => {
    assert.equal(query(f, '#changelist-filter').hidden, false);
    assert.equal(query(f, '.nova-filter-toggle'), null);
    assert.equal(query(f, '.nova-results-scroll-tools'), null);
});
checkList('Native mode receives no list enhancement or DOM mutation', {body:''}, f => {
    assert.equal(f.d.body.innerHTML, f.before);
});
checkList('Pages without filters still receive horizontal scrolling', {filter:false}, f => {
    assert.equal(query(f, '.nova-filter-toggle'), null);
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, false);
});
checkList('Pages without search toolbar or results keep a standalone filter control', {table:false, toolbar:false}, f => {
    assert.equal(query(f, '.nova-changelist-controls').nextElementSibling, query(f, '#changelist'));
    assert.equal(query(f, '.nova-results-scroll-tools'), null);
    query(f, '.nova-filter-toggle').click();
    assert.equal(query(f, '#changelist-filter').hidden, true);
});
checkList('Collapsing while focus is in the filter returns focus to its toggle', {}, f => {
    query(f, '#filter-choice input').focus();
    query(f, '.nova-filter-toggle').click();
    assert.equal(f.d.activeElement, query(f, '.nova-filter-toggle'));
    query(f, '.nova-filter-toggle').click();
    assert.equal(f.d.activeElement, query(f, '.nova-filter-toggle'));
});
checkList('Saved state is restored and reopening updates only this model path', {saved:'1'}, f => {
    const otherKey = 'nova.changelist.filters:/admin/catalog/tag/';
    f.w.sessionStorage.setItem(otherKey, '1');
    assert.equal(query(f, '#changelist-filter').hidden, true);
    assert.equal(query(f, '.nova-filter-toggle').getAttribute('aria-expanded'), 'false');
    query(f, '.nova-filter-toggle').click();
    assert.equal(f.w.sessionStorage.getItem(f.storageKey), '0');
    assert.equal(f.w.sessionStorage.getItem(otherKey), '1');
});
checkList('Invalid stored filter state leaves the default visible', {saved:'invalid'}, f => {
    assert.equal(query(f, '#changelist-filter').hidden, false);
});
for (const options of [{storageFails:true}, {writeFails:true}]) {
    checkList(`Storage ${options.storageFails ? 'access' : 'write'} failure does not break filter controls`, options, f => {
        query(f, '.nova-filter-toggle').click();
        assert.equal(query(f, '#changelist-filter').hidden, true);
        query(f, '.nova-filter-toggle').click();
        assert.equal(query(f, '#changelist-filter').hidden, false);
    });
}
checkList('Overflow toolbar has a named native range slider and independent arrow buttons', {resultId:'existing-results'}, f => {
    const tools = query(f, '.nova-results-scroll-tools');
    const bar = query(f, '.nova-results-scrollbar');
    assert.equal(tools.nextElementSibling, f.results);
    assert.equal(tools.hidden, false);
    assert.equal(bar.tabIndex, 0);
    assert.equal(bar.tagName, 'INPUT');
    assert.equal(bar.type, 'range');
    assert.equal(bar.hasAttribute('role'), false);
    assert.equal(bar.hasAttribute('name'), false);
    assert.equal(bar.min, '0');
    assert.equal(bar.step, '1');
    assert.equal(bar.valueAsNumber, 0);
    assert.equal(bar.getAttribute('aria-label'), '横向滚动表格');
    assert.equal(bar.getAttribute('aria-controls'), 'existing-results');
    assert.equal(query(f, '.nova-results-scroll-left').type, 'button');
    assert.equal(query(f, '.nova-results-scroll-right').type, 'button');
    assert.equal(query(f, '.nova-results-scroll-left').getAttribute('aria-label'), '向左滚动表格');
    assert.equal(query(f, '.nova-results-scroll-right').getAttribute('aria-label'), '向右滚动表格');
    assert.equal(Number(bar.max), f.results.scrollWidth - f.results.clientWidth);
    const payload = contents(f.w, query(f, '#changelist-form'));
    assert.deepEqual(payload.map(([name]) => name), ['csrfmiddlewaretoken', 'action', '_selected_action']);
});
checkList('Tables that initially fit keep the extra toolbar hidden', {width:240}, f => {
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, true);
    assert.equal(f.results.scrollLeft, 0);
    assert.equal(f.results.hasAttribute('tabindex'), false);
});
checkList('Arrow clicks scroll to both ends without submitting the form', {}, f => {
    let submissions = 0;
    query(f, '#changelist-form').addEventListener('submit', event => {submissions++; event.preventDefault();});
    const left = query(f, '.nova-results-scroll-left');
    const right = query(f, '.nova-results-scroll-right');
    assert.equal(left.disabled, true);
    assert.equal(right.disabled, false);
    right.click();
    assert.equal(f.results.scrollLeft, 240);
    right.click(); right.click();
    assert.equal(f.results.scrollLeft, 680);
    assert.equal(right.disabled, true);
    left.click(); left.click(); left.click();
    assert.equal(f.results.scrollLeft, 0);
    assert.equal(left.disabled, true);
    assert.equal(submissions, 0);
});
checkList('Slider input and committed change synchronize the original results', {}, f => {
    const bar = query(f, '.nova-results-scrollbar');
    bar.value = '300';
    bar.dispatchEvent(new f.w.Event('input', {bubbles:true}));
    assert.equal(f.results.scrollLeft, 300);
    bar.value = bar.max;
    bar.dispatchEvent(new f.w.Event('change', {bubbles:true}));
    assert.equal(f.results.scrollLeft, 680);
    assert.equal(query(f, '.nova-results-scroll-right').disabled, true);
});
checkList('Touch or native scrolling in results synchronizes the slider position', {}, f => {
    f.results.scrollLeft = 420;
    f.results.dispatchEvent(new f.w.Event('scroll'));
    assert.equal(query(f, '.nova-results-scrollbar').valueAsNumber, 420);
});
checkList('Keyboard arrows and Home/End scroll while unrelated shortcuts stay native', {}, f => {
    const bar = query(f, '.nova-results-scrollbar');
    bar.focus();
    for (const [key, expected] of [['ArrowRight',40], ['End',680], ['ArrowLeft',640], ['Home',0]]) {
        const event = new f.w.KeyboardEvent('keydown', {key, cancelable:true, bubbles:true});
        bar.dispatchEvent(event);
        assert.equal(event.defaultPrevented, true);
        assert.equal(f.results.scrollLeft, expected);
        assert.equal(bar.valueAsNumber, expected);
    }
    for (const options of [{key:'Escape'}, {key:'ArrowRight', ctrlKey:true}]) {
        const event = new f.w.KeyboardEvent('keydown', {...options, cancelable:true});
        bar.dispatchEvent(event);
        assert.equal(event.defaultPrevented, false);
        assert.equal(f.results.scrollLeft, 0);
    }
});
checkList('ResizeObserver tracks viewport/table changes and handles focus when overflow disappears', {}, f => {
    const observer = f.observations[0];
    const bar = query(f, '.nova-results-scrollbar');
    assert.deepEqual(observer.elements, [f.results, f.results.querySelector('table')]);
    bar.focus();
    f.sizes.viewport = 1200;
    observer.callback();
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, true);
    assert.equal(f.d.activeElement, f.results);
    f.sizes.width = 1800;
    observer.callback();
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, false);
    assert.equal(Number(bar.max), 600);
    assert.equal(bar.disabled, false);
    bar.value = '600';
    bar.dispatchEvent(new f.w.Event('input'));
    assert.equal(f.results.scrollLeft, 600);
});
checkList('Window resize updates overflow when ResizeObserver is unavailable', {resizeObserver:false}, f => {
    f.sizes.width = 300;
    f.w.dispatchEvent(new f.w.Event('resize'));
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, true);
    f.sizes.width = 1400;
    f.w.dispatchEvent(new f.w.Event('resize'));
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, false);
});
checkList('Collapsing/reopening the filter recalculates a widened content viewport', {}, f => {
    f.sizes.width = 700;
    f.sizes.collapsedViewport = 900;
    query(f, '.nova-filter-toggle').click();
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, true);
    query(f, '.nova-filter-toggle').click();
    assert.equal(query(f, '.nova-results-scroll-tools').hidden, false);
    const bar = query(f, '.nova-results-scrollbar');
    assert.equal(Number(bar.max), 380);
});
checkList('RTL physical arrows and keyboard endpoints synchronize negative offsets', {rtl:true}, f => {
    const left = query(f, '.nova-results-scroll-left');
    const right = query(f, '.nova-results-scroll-right');
    const bar = query(f, '.nova-results-scrollbar');
    assert.equal(bar.dir, 'rtl');
    assert.equal(right.disabled, true);
    left.click();
    assert.equal(f.results.scrollLeft, -240);
    assert.equal(bar.valueAsNumber, 240);
    bar.value = '360';
    bar.dispatchEvent(new f.w.Event('input'));
    assert.equal(f.results.scrollLeft, -360);
    bar.dispatchEvent(new f.w.KeyboardEvent('keydown', {key:'End', cancelable:true}));
    assert.equal(f.results.scrollLeft, -680);
    assert.equal(bar.valueAsNumber, 680);
    assert.equal(left.disabled, true);
    right.click();
    assert.equal(f.results.scrollLeft, -440);
    bar.dispatchEvent(new f.w.KeyboardEvent('keydown', {key:'Home', cancelable:true}));
    assert.equal(f.results.scrollLeft, 0);
});
checkList('Repeated script loading does not duplicate controls or click handlers', {}, f => {
    f.w.eval(script);
    assert.equal(f.d.querySelectorAll('.nova-filter-toggle').length, 1);
    assert.equal(f.d.querySelectorAll('.nova-results-scroll-tools').length, 1);
    query(f, '.nova-results-scroll-right').click();
    assert.equal(f.results.scrollLeft, 240);
});
console.log(`TOTAL ${count} changelist enhancement tests passed`);
