// Shared pagination contract exercised through each public list UI.
// Browser layout is covered separately; jsdom verifies route/state/DOM behavior.
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const project = process.env.NOVA_TEST_PROJECT || path.resolve(__dirname, '..');
const { createApp } = require(path.join(project, 'tests/dom-runtime.cjs'));
const wait = (ms = 25) => new Promise(resolve => setTimeout(resolve, ms));
let passed = 0;
const rejections = [];
const captureRejection = reason => rejections.push(reason);
process.on('unhandledRejection', captureRejection);
const check = (description, run) => { run(); passed++; console.log('PASS', description); };
const specs = [
  { name: 'users', table: '.users-full-table', mobile: '.mobile-user-cards', checkbox: '.row-check', all: '#select-all', mobileAll: '#mobile-select-all', page: 'data-page', search: '#user-search', filter: '#status-filter', active: '正常', reset: '[data-action="reset-filters"]', storage: 'nova-users', target: '已停用', start: ui => ui.click('[data-action="bulk-disable"]'), confirm: '[data-action="confirm-disable"]' },
  { name: 'catalog', table: '.catalog-table', mobile: '.catalog-mobile-cards', checkbox: '.catalog-check', all: '#catalog-all', mobileAll: '#catalog-mobile-all', page: 'data-catalog-page', search: '#catalog-search', filter: '#catalog-status', active: '已发布', reset: '[data-catalog="reset-filters"]', storage: 'nova-catalog', target: '归档', start: ui => { ui.change('#catalog-bulk', '归档'); ui.click('[data-catalog="apply-batch"]'); }, confirm: '[data-catalog="confirm-batch"]' },
  { name: 'news', table: '.news-table', mobile: '.mobile-news-cards', checkbox: '.news-check', all: '#news-all', mobileAll: '#news-mobile-all', page: 'data-news-page', search: '#news-search', filter: '#news-status', active: '已发布', reset: '[data-news="reset"]', storage: 'nova-news', target: '归档', start: ui => ui.click('[data-news="archive"]'), confirm: '[data-news="confirm"]' },
];
async function session(spec, label, run, options = {}) {
  const app = await createApp({ url: `https://example.test/#${spec.name}`, ...options });
  const { w, d } = app, errors = [], start = rejections.length;
  w.addEventListener('error', event => errors.push(event.error || event.message));
  w.addEventListener('unhandledrejection', event => errors.push(event.reason));
  const q = selector => d.querySelector(selector), all = selector => [...d.querySelectorAll(selector)];
  const requireElement = selector => { const element = q(selector); assert.ok(element, `Missing ${selector}`); return element; };
  const change = (selector, value) => { const element = requireElement(selector); if (typeof value === 'boolean') element.checked = value; else element.value = value; element.dispatchEvent(new w.Event('change', { bubbles: true })); };
  const input = (selector, value) => { const element = requireElement(selector); element.value = value; element.dispatchEvent(new w.Event('input', { bubbles: true })); };
  const click = selector => requireElement(selector).click();
  const route = async value => { w.location.hash = value; await wait(); };
  const traverse = async direction => {
    const changed = new Promise(resolve => w.addEventListener('hashchange', resolve, { once: true }));
    w.history[direction]();
    await Promise.race([changed, wait(1000).then(() => { throw new Error(`History ${direction} did not change hash`); })]);
    await wait();
  };
  const jump = value => { requireElement(`#${spec.name}-page-input`).value = value; requireElement(`[data-page-jump="${spec.name}"]`).dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true })); };
  const page = () => q('.pagination [aria-current="page"]').textContent.trim();
  const rowIds = () => all(`${spec.table} ${spec.checkbox}`).map(box => Number(box.value));
  const params = () => new URLSearchParams(w.location.hash.split('?')[1]);
  try {
    await run({ ...app, q, all, click, change, input, route, traverse, jump, page, rowIds, params });
    await wait();
    check(`${spec.name} ${label}: no runtime errors`, () => { assert.deepEqual(errors, []); assert.deepEqual(rejections.slice(start), []); });
  } finally { app.close(); }
}
async function controls(spec) {
  await session(spec, 'controls', async ui => {
    const { w, d, q, all, click, change, jump, page, rowIds, params } = ui;
    const size = `#${spec.name}-page-size`;
    check(`${spec.name}: defaults to 10 rows with exactly the four allowed sizes`, () => {
      assert.equal(q(size).value, '10'); assert.equal(rowIds().length, 10);
      assert.deepEqual(all(`${size} option`).map(option => option.value), ['10', '20', '50', '100']);
      assert.equal(all('.pagination [aria-current="page"]').length, 1);
      assert.equal(q('.pagination button:first-child').disabled, true);
      assert.equal(q('.pagination button:last-child').disabled, false);
      assert.match(q('.collection-total').textContent, /共 24 .*第 1–10 条/);
      assert.equal(q(`#${spec.name}-page-input`).disabled, false);
    });
    const initialHistory = w.history.length;
    click(`[${spec.page}="3"]`);
    check(`${spec.name}: last page shows the remaining four records with coherent navigation`, () => {
      assert.equal(page(), '3'); assert.equal(rowIds().length, 4); assert.equal(params().get('page'), '3');
      assert.equal(q('.pagination button:last-child').disabled, true); assert.equal(q('.pagination button:first-child').disabled, false);
      assert.match(q('.collection-total').textContent, /第 21–24 条/); assert.equal(w.history.length, initialHistory + 1);
    });
    for (const invalid of ['', '0', '-1', '1.5', '1e2', 'Infinity', 'NaN', 'abc', '9007199254740992', '2x']) {
      const url = w.location.href, history = w.history.length, ids = rowIds();
      jump(invalid);
      check(`${spec.name}: invalid jump ${JSON.stringify(invalid)} keeps the route, records and accessible error`, () => {
        assert.equal(w.location.href, url); assert.equal(w.history.length, history); assert.deepEqual(rowIds(), ids);
        assert.equal(q(`#${spec.name}-page-input`).getAttribute('aria-invalid'), 'true');
        assert.match(q(`#${spec.name}-page-error`).textContent, /正整数/); assert.equal(d.activeElement.id, `${spec.name}-page-input`);
      });
    }
    jump(' 0002 ');
    check(`${spec.name}: correcting a jump normalizes its value and clears the error`, () => {
      assert.equal(page(), '2'); assert.equal(params().get('page'), '2'); assert.equal(q(`#${spec.name}-page-input`).value, '2');
      assert.equal(q(`#${spec.name}-page-input`).getAttribute('aria-invalid'), null); assert.equal(q(`#${spec.name}-page-error`).textContent, '');
      assert.equal(d.activeElement.id, `${spec.name}-page-input`);
    });
    jump('9007199254740991');
    check(`${spec.name}: a safe oversized jump clamps to the last page in both DOM and URL`, () => { assert.equal(page(), '3'); assert.equal(params().get('page'), '3'); assert.equal(q(`#${spec.name}-page-input`).value, '3'); });
    change(size, '20');
    check(`${spec.name}: changing size resets to page one, updates the URL and restores focus`, () => {
      assert.equal(page(), '1'); assert.equal(rowIds().length, 20); assert.equal(params().get('per_page'), '20'); assert.equal(params().get('page'), null);
      assert.equal(d.activeElement.id, `${spec.name}-page-size`); assert.match(q('.collection-total').textContent, /第 1–20 条/);
    });
    click(`[${spec.page}="2"]`);
    check(`${spec.name}: 20-row pagination yields an accurate last-page range`, () => { assert.equal(rowIds().length, 4); assert.match(q('.collection-total').textContent, /第 21–24 条/); });
    for (const value of ['50', '100']) {
      change(size, value);
      check(`${spec.name}: ${value}-row size renders all records with one disabled-boundary page`, () => {
        assert.equal(page(), '1'); assert.equal(rowIds().length, 24); assert.equal(params().get('per_page'), value);
        assert.equal(q('.pagination button:first-child').disabled, true); assert.equal(q('.pagination button:last-child').disabled, true);
        assert.equal(q(`#${spec.name}-page-input`).disabled, true); assert.equal(q('.page-jump button').disabled, true);
      });
    }
    change(size, '10');
    check(`${spec.name}: returning to the default size removes per_page from the URL`, () => { assert.equal(rowIds().length, 10); assert.equal(w.location.hash, `#${spec.name}`); });
  });
}
async function routeValidation(spec) {
  await session(spec, 'URL normalization', async ({ w, q, all, route, page, rowIds, params }) => {
    for (const value of ['', '0', '-2', '1.5', '1e2', 'NaN', 'Infinity', 'oops', '9007199254740992', ' 2 ']) {
      await route(`${spec.name}?page=${encodeURIComponent(value)}&per_page=20`);
      check(`${spec.name}: malformed URL page ${JSON.stringify(value)} becomes canonical page one`, () => {
        assert.equal(page(), '1'); assert.equal(rowIds().length, 20); assert.equal(params().get('page'), null); assert.equal(params().get('per_page'), '20');
      });
    }
    for (const value of ['', '0', '-10', '6', '11', '101', '20.0', '1e2', 'oops', '9007199254740992']) {
      await route(`${spec.name}?per_page=${encodeURIComponent(value)}&page=2`);
      check(`${spec.name}: unsupported URL size ${JSON.stringify(value)} uses the default without losing valid page`, () => {
        assert.equal(q(`#${spec.name}-page-size`).value, '10'); assert.equal(rowIds().length, 10); assert.equal(page(), '2');
        assert.equal(params().get('per_page'), null); assert.equal(params().get('page'), '2');
      });
    }
    for (const [size, expectedPage, count] of [[10, 3, 4], [20, 2, 4], [50, 1, 24], [100, 1, 24]]) {
      await route(`${spec.name}?page=999&per_page=${size}`);
      check(`${spec.name}: allowed URL size ${size} determines correct clamping`, () => { assert.equal(page(), String(expectedPage)); assert.equal(rowIds().length, count); assert.equal(params().get('page'), expectedPage > 1 ? String(expectedPage) : null); assert.equal(q(`#${spec.name}-page-size`).value, String(size)); });
    }
    await route(`${spec.name}?page=0002&per_page=0020`);
    check(`${spec.name}: valid zero-padded URL integers canonicalize`, () => { assert.equal(params().get('page'), '2'); assert.equal(params().get('per_page'), '20'); assert.equal(rowIds().length, 4); });
    await route(`${spec.name}?q=NO-MATCH-PAGINATION&status=INVALID&category=INVALID&role=INVALID&page=999&per_page=50`);
    check(`${spec.name}: empty filtered data clamps to page one and removes unsupported filters`, () => {
      assert.equal(page(), '1'); assert.equal(rowIds().length, 0); assert.equal(q('.empty-state') !== null, true);
      assert.match(q('.collection-total').textContent, /共 0 /); assert.equal(params().get('page'), null); assert.equal(params().get('per_page'), '50');
      for (const key of ['status', 'category', 'role']) assert.equal(params().get(key), null);
      assert.equal(q(`#${spec.name}-page-input`).disabled, true); if (spec.name === 'catalog') assert.equal(q(spec.mobileAll), null); else assert.equal(q(spec.mobileAll).disabled, true);
      assert.equal(all('.pagination [aria-current="page"]').length, 1);
    });
  });
}
async function historyAndFilters(spec) {
  await session(spec, 'history and filters', async ui => {
    const { w, q, click, change, input, traverse, page, rowIds, params } = ui;
    const size = `#${spec.name}-page-size`;
    const firstIds = rowIds(), startHistory = w.history.length;
    click(`[${spec.page}="2"]`); const secondIds = rowIds();
    click(`[${spec.page}="3"]`); const thirdIds = rowIds();
    check(`${spec.name}: page clicks add one history entry each`, () => { assert.equal(w.history.length, startHistory + 2); assert.notDeepEqual(firstIds, secondIds); assert.notDeepEqual(secondIds, thirdIds); });
    click(`.pagination [aria-current="page"]`);
    check(`${spec.name}: selecting the current page does not create duplicate history`, () => assert.equal(w.history.length, startHistory + 2));
    await traverse('back'); check(`${spec.name}: Back restores page two and its exact records`, () => { assert.equal(page(), '2'); assert.deepEqual(rowIds(), secondIds); });
    await traverse('back'); check(`${spec.name}: a second Back restores the first page`, () => { assert.equal(page(), '1'); assert.deepEqual(rowIds(), firstIds); });
    await traverse('forward'); await traverse('forward');
    check(`${spec.name}: Forward restores the last page`, () => { assert.equal(page(), '3'); assert.deepEqual(rowIds(), thirdIds); });
    const beforeSize = w.history.length;
    change(size, '20'); const twentyIds = rowIds();
    check(`${spec.name}: size changes create one history entry`, () => assert.equal(w.history.length, beforeSize + 1));
    await traverse('back'); check(`${spec.name}: Back restores the previous size and page`, () => { assert.equal(q(size).value, '10'); assert.equal(page(), '3'); assert.deepEqual(rowIds(), thirdIds); });
    await traverse('forward'); check(`${spec.name}: Forward restores size 20 and its first page`, () => { assert.equal(q(size).value, '20'); assert.equal(page(), '1'); assert.deepEqual(rowIds(), twentyIds); });
    click(`[${spec.page}="2"]`);
    change(`${spec.table} ${spec.checkbox}`, true);
    const beforeFilter = w.history.length;
    change(spec.filter, spec.active);
    check(`${spec.name}: filtering replaces history, clears cross-page selection and retains page size`, () => { assert.equal(page(), '1'); assert.equal(params().get('per_page'), '20'); assert.equal(params().get('status'), spec.active); assert.equal(q('.bulk-bar'), null); assert.equal(w.history.length, beforeFilter); });
    input(spec.search, 'NO-MATCH-PAGINATION');
    click(spec.reset);
    check(`${spec.name}: filter reset retains the chosen size and clears filters without adding history`, () => {
      assert.equal(page(), '1'); assert.equal(rowIds().length, 20); assert.equal(q(spec.search).value, ''); assert.equal(params().get('status'), null); assert.equal(params().get('q'), null);
      assert.equal(q(size).value, '20'); assert.equal(w.history.length, beforeFilter);
    });
    click(`[${spec.page}="2"]`);
    const url = w.location.href, ids = rowIds();
    const reloaded = await createApp({ url });
    try {
      check(`${spec.name}: a fresh load restores page and size from the shared URL`, () => {
        assert.equal(reloaded.w.location.href, url); assert.equal(reloaded.d.querySelector(size).value, '20');
        assert.equal(reloaded.d.querySelector('.pagination [aria-current="page"]').textContent, '2');
        assert.deepEqual([...reloaded.d.querySelectorAll(`${spec.table} ${spec.checkbox}`)].map(box => Number(box.value)), ids);
      });
    } finally { reloaded.close(); }
  });
}
async function selectionAndBulk(spec) {
  await session(spec, 'resized bulk', async ui => {
    const { w, q, all, click, change, page, rowIds, params } = ui;
    const size = `#${spec.name}-page-size`;
    change(size, '100');
    const originals = new Map(all(`${spec.table} tbody tr`).map(row => [Number(row.querySelector(spec.checkbox).value), row.children[3].textContent]));
    const names = spec.name === 'users' ? new Map(all(`${spec.table} tbody tr`).map(row => [Number(row.querySelector(spec.checkbox).value), row.querySelector('.person strong').textContent])) : null;
    change(size, '10');
    const first = rowIds()[0]; change(`${spec.table} ${spec.checkbox}[value="${first}"]`, true);
    click(`[${spec.page}="3"]`); const lastPage = rowIds(), last = lastPage[0]; change(`${spec.mobile} ${spec.checkbox}[value="${last}"]`, true);
    change(size, '20');
    check(`${spec.name}: resize preserves visible and off-page selection and synchronized partial controls`, () => {
      assert.equal(page(), '1'); assert.equal(q(`${spec.table} ${spec.checkbox}[value="${first}"]`).checked, true); assert.equal(q(`${spec.mobile} ${spec.checkbox}[value="${first}"]`).checked, true);
      assert.match(q('.bulk-bar').textContent, /已选 2/); assert.match(q('.bulk-bar').textContent, /其他页 1/); assert.equal(q(spec.all).indeterminate, true); assert.equal(q(spec.mobileAll).indeterminate, true);
    });
    change(spec.mobileAll, true);
    check(`${spec.name}: select-all after resizing selects the current 20 plus the off-page record`, () => { assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, 20); assert.match(q('.bulk-bar').textContent, /已选 21/); assert.equal(q(spec.all).checked, true); assert.equal(q(spec.all).indeterminate, false); });
    change(spec.all, false);
    check(`${spec.name}: deselect-all after resizing preserves only the off-page record`, () => { assert.match(q('.bulk-bar').textContent, /已选 1/); assert.match(q('.bulk-bar').textContent, /其他页 1/); assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, 0); });
    change(`${spec.table} ${spec.checkbox}[value="${first}"]`, true);
    click(`[${spec.page}="2"]`);
    check(`${spec.name}: returning to the resized last page retains exactly its selected record`, () => { assert.deepEqual(rowIds(), lastPage); assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, 1); assert.equal(q(`${spec.table} ${spec.checkbox}[value="${last}"]`).checked, true); assert.equal(q(spec.all).indeterminate, true); });
    spec.start(ui);
    check(`${spec.name}: resized cross-page bulk preview lists exactly the two selected records`, () => { if (spec.name === 'users') { assert.match(q('#overlay-root').textContent, /共 2 位/); assert.ok(q('#overlay-root').textContent.includes(names.get(first))); assert.ok(q('#overlay-root').textContent.includes(names.get(last))); } else assert.equal(all('.batch-preview li').length, 2); assert.ok(q(spec.confirm)); });
    const storageBefore = w.localStorage.getItem(spec.storage), auditBefore = w.localStorage.getItem('nova-audit'), routeBefore = w.location.href;
    const originalSet = w.Storage.prototype.setItem;
    try {
      w.Storage.prototype.setItem = () => { throw new Error('Storage unavailable'); };
      click(spec.confirm);
      check(`${spec.name}: failed resized bulk save retains route, selection, confirmation and persisted data`, () => {
        assert.equal(w.location.href, routeBefore); assert.equal(w.localStorage.getItem(spec.storage), storageBefore); assert.equal(w.localStorage.getItem('nova-audit'), auditBefore);
        assert.ok(q(spec.confirm)); assert.ok(q('#storage-warning')); assert.match(q('.bulk-bar').textContent, /已选 2/); assert.equal(q(`${spec.table} ${spec.checkbox}[value="${last}"]`).checked, true);
        assert.equal(q(`${spec.table} ${spec.checkbox}[value="${last}"]`).closest('tr').children[3].textContent, originals.get(last));
      });
    } finally { w.Storage.prototype.setItem = originalSet; }
    click(spec.confirm);
    check(`${spec.name}: retry changes only selected records and retains pagination size`, () => {
      const records = JSON.parse(w.localStorage.getItem(spec.storage)); assert.equal(records.length, 24);
      for (const record of records) assert.equal(record.status, [first, last].includes(record.id) ? spec.target : originals.get(record.id), `Unexpected status for ${record.id}`);
      assert.equal(q('.bulk-bar'), null); assert.equal(q(spec.confirm), null); assert.equal(q('#storage-warning'), null); assert.equal(q(spec.all).indeterminate, false);
      assert.equal(page(), '2'); assert.equal(params().get('per_page'), '20');
    });
    const stored = Object.fromEntries(Array.from({ length: w.localStorage.length }, (_, index) => { const key = w.localStorage.key(index); return [key, w.localStorage.getItem(key)]; }));
    const reloaded = await createApp({ url: w.location.href, storage: stored });
    try {
      check(`${spec.name}: reload retains committed status and route while clearing transient selection`, () => {
        const row = reloaded.d.querySelector(`${spec.table} ${spec.checkbox}[value="${last}"]`);
        assert.equal(row.closest('tr').children[3].textContent, spec.target); assert.equal(row.checked, false); assert.equal(reloaded.d.querySelector('.bulk-bar'), null);
        assert.equal(reloaded.d.querySelector(size).value, '20'); assert.equal(reloaded.d.querySelector('.pagination [aria-current="page"]').textContent, '2');
      });
    } finally { reloaded.close(); }
  });
}
async function selectionHistory(spec) {
  await session(spec, 'selection history', async ({ w, q, click, change, route, traverse, rowIds }) => {
    const first = rowIds()[0];
    change(`${spec.table} ${spec.checkbox}[value="${first}"]`, true);
    click(`[${spec.page}="2"]`);
    await traverse('back');
    check(`${spec.name}: Back restores selected rows and both indeterminate select-all controls`, () => {
      assert.equal(q(`${spec.table} ${spec.checkbox}[value="${first}"]`).checked, true);
      assert.equal(q(spec.all).indeterminate, true); assert.equal(q(spec.mobileAll).indeterminate, true);
      assert.equal(q(spec.all).checked, false); assert.equal(q(spec.mobileAll).checked, false);
    });
    await traverse('forward');
    check(`${spec.name}: Forward to an unselected page clears partial header state while keeping off-page selection`, () => {
      assert.equal(q(spec.all).indeterminate, false); assert.equal(q(spec.mobileAll).indeterminate, false);
      assert.match(q('.bulk-bar').textContent, /其他页 1/);
    });
    await traverse('back');
    change(spec.all, true);
    change(`#${spec.name}-page-size`, '20');
    await traverse('back');
    check(`${spec.name}: Back to the smaller fully selected page restores checked headers`, () => {
      assert.equal(q(spec.all).checked, true); assert.equal(q(spec.mobileAll).checked, true);
      assert.equal(q(spec.all).indeterminate, false); assert.equal(q(spec.mobileAll).indeterminate, false);
    });
    await traverse('forward');
    check(`${spec.name}: Forward to the larger partially selected page restores mixed headers`, () => {
      assert.equal(q(spec.all).checked, false); assert.equal(q(spec.mobileAll).checked, false);
      assert.equal(q(spec.all).indeterminate, true); assert.equal(q(spec.mobileAll).indeterminate, true);
    });
    const listRoute = w.location.hash.slice(1);
    await route('overview'); await route(listRoute);
    check(`${spec.name}: returning from another screen restores mixed selection controls`, () => {
      assert.equal(q(spec.all).indeterminate, true); assert.equal(q(spec.mobileAll).indeterminate, true);
      assert.match(q('.bulk-bar').textContent, /已选 10/);
    });
  });
}
async function resizedFilteredClamp(spec) {
  // Obtain valid records via the public save workflow, then set up a fully matching fixture.
  await session(spec, 'resized filtered setup', async ui => {
    ui.change(`${spec.table} ${spec.checkbox}`, true); spec.start(ui); ui.click(spec.confirm);
    const records = JSON.parse(ui.w.localStorage.getItem(spec.storage)).map(record => ({ ...record, status: spec.active }));
    await session(spec, 'resized filtered clamp', async scoped => {
      const { w, q, all, click, change, page, rowIds, params } = scoped;
      const chosen = rowIds(); change(spec.all, true); spec.start(scoped); click(spec.confirm);
      check(`${spec.name}: filtered 20-row last-page mutation clamps to the previous full page`, () => {
        assert.equal(chosen.length, 4); assert.equal(page(), '1'); assert.equal(rowIds().length, 20);
        assert.equal(params().get('page'), null); assert.equal(params().get('per_page'), '20'); assert.equal(params().get('status'), spec.active);
        assert.match(q('.collection-total').textContent, /共 20 .*第 1–20 条/); assert.equal(q('.bulk-bar'), null);
        const saved = JSON.parse(w.localStorage.getItem(spec.storage));
        for (const record of saved) assert.equal(record.status, chosen.includes(record.id) ? spec.target : spec.active);
      });
      change(spec.all, true); spec.start(scoped); click(spec.confirm);
      check(`${spec.name}: removing all remaining filter matches shows a valid empty first page`, () => {
        assert.equal(page(), '1'); assert.equal(rowIds().length, 0); assert.ok(q('.empty-state'));
        assert.match(q('.collection-total').textContent, /共 0 /); assert.equal(q('.bulk-bar'), null);
        assert.equal(q('.pagination button:first-child').disabled, true); assert.equal(q('.pagination button:last-child').disabled, true);
        assert.equal(q(`#${spec.name}-page-input`).disabled, true); assert.equal(params().get('per_page'), '20'); assert.equal(params().get('status'), spec.active);
        assert.equal(JSON.parse(w.localStorage.getItem(spec.storage)).every(record => record.status === spec.target), true);
      });
      click(spec.reset);
      check(`${spec.name}: reset after empty filtered bulk exposes all saved records with the chosen size`, () => {
        assert.equal(rowIds().length, 20); assert.equal(q(`#${spec.name}-page-size`).value, '20'); assert.equal(page(), '1');
        assert.equal(params().get('status'), null); assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, 0);
      });
    }, { url: `https://example.test/#${spec.name}?status=${encodeURIComponent(spec.active)}&per_page=20&page=2`, storage: { [spec.storage]: JSON.stringify(records) } });
  });
}
async function legacyStorage(spec) {
  await session(spec, 'persisted subsets', async ({ w, q, change }) => {
    // Generate valid records through an actual save, then emulate an older saved dataset.
    change(`${spec.table} ${spec.checkbox}`, true);
    spec.start({ click: selector => q(selector).click(), change }); q(spec.confirm).click();
    const records = JSON.parse(w.localStorage.getItem(spec.storage)).slice(0, spec.name === 'news' ? 8 : spec.name === 'catalog' ? 7 : 6);
    records[0].status = spec.target;
    const subset = await createApp({ url: `https://example.test/#${spec.name}?per_page=20&page=9`, storage: { [spec.storage]: JSON.stringify(records) } });
    try {
      check(`${spec.name}: existing smaller saved datasets are preserved rather than padded with seed rows`, () => {
        assert.equal(subset.d.querySelectorAll(`${spec.table} tbody tr`).length, records.length); assert.equal(subset.d.querySelector('.pagination [aria-current="page"]').textContent, '1');
        assert.equal(subset.w.location.hash, `#${spec.name}?per_page=20`); assert.equal(subset.d.querySelector(`${spec.table} tbody tr`).children[3].textContent, spec.target);
        assert.deepEqual(JSON.parse(subset.w.localStorage.getItem(spec.storage)), records);
      });
    } finally { subset.close(); }
  });
}
async function collectionContract() {
  const { createCollection } = await import(pathToFileURL(path.join(project, 'dist/js/collection.js')).href);
  const { pagination } = await import(pathToFileURL(path.join(project, 'dist/js/pagination.js')).href);
  let records = Array.from({ length: 1001 }, (_, index) => ({ id: index + 1, category: index % 2 }));
  const collection = createCollection({ getRecords: () => records, filters: { query: { default: '' } }, matches: (record, state) => !state.query || String(record.id).includes(state.query) });
  check('Collection rejects an unsupported default page size', () => assert.throws(() => createCollection({ getRecords: () => [], filters: {}, matches: () => true, pageSize: 6 }), RangeError));
  collection.setPage(50);
  check('Long collection exposes bounded numbered controls with ellipses and current-page accessibility', () => {
    const html = pagination(collection, 'test', 'data-test-page', '测试');
    assert.equal((html.match(/<button/g) || []).length, 8); // 5 numbered, previous, next, jump.
    assert.equal((html.match(/pagination-gap/g) || []).length, 2); assert.equal((html.match(/aria-current="page"/g) || []).length, 1);
    assert.match(html, /第 491–500 条/); assert.match(html, /data-test-page="101"/);
  });
  collection.selectPage(true); collection.setPageSize('20');
  check('Collection resize retains selected IDs and resets page', () => { assert.equal(collection.state.selected.size, 10); assert.equal(collection.state.page, 1); assert.equal(collection.pageSize, 20); });
  records = records.slice(0, 23); collection.setPage(99);
  check('Collection page clamp derives from the current dataset after mutation', () => { assert.equal(collection.state.page, 2); assert.equal(collection.pageItems().rows.length, 3); });
  collection.setPageSize(100); collection.setFilter('query', 'missing');
  check('Empty collection retains one navigable state and clears selection on filtering', () => { const items = collection.pageItems(); assert.equal(items.pages, 1); assert.equal(items.rows.length, 0); assert.equal(collection.state.selected.size, 0); });
  collection.resetFilters();
  check('Reset clears filters while retaining the deliberate page size', () => { assert.equal(collection.state.query, ''); assert.equal(collection.pageSize, 100); assert.equal(collection.state.page, 1); });
  collection.resetFilters({ resetPageSize: true });
  check('Explicit full reset restores the default page size', () => { assert.equal(collection.pageSize, 10); assert.equal(collection.state.page, 1); });
}
async function globalReset() {
  await session(specs[0], 'global reset', async ({ w, q, click, change, route }) => {
    for (const spec of specs) {
      await route(spec.name);
      change(`#${spec.name}-page-size`, '20');
      click(`[${spec.page}="2"]`);
      change(`${spec.table} ${spec.checkbox}`, true);
    }
    await route('settings');
    click('[data-action="reset-demo"]');
    click('[data-action="confirm-reset-demo"]');
    for (const spec of specs) {
      await route(spec.name);
      check(`${spec.name}: global reset restores 10-row first page and clears selection`, () => {
        assert.equal(q(`#${spec.name}-page-size`).value, '10');
        assert.equal(q('.pagination [aria-current="page"]').textContent, '1');
        assert.equal(q('.bulk-bar'), null);
        assert.equal(w.location.hash, `#${spec.name}`);
        assert.equal(w.localStorage.getItem(spec.storage), null);
      });
    }
  });
}
async function main() {
  await collectionContract();
  await globalReset();
  for (const spec of specs) {
    await controls(spec); await routeValidation(spec); await historyAndFilters(spec); await selectionAndBulk(spec); await legacyStorage(spec); await resizedFilteredClamp(spec); await selectionHistory(spec);
  }
  console.log('TOTAL', passed, 'pagination checks passed (Node/jsdom)');
}
main().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => process.removeListener('unhandledRejection', captureRejection));
