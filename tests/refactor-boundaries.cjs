// Public UI regressions for the static prototype's shared collection refactor.
const path = require('node:path');
const project = process.env.NOVA_TEST_PROJECT || path.resolve(__dirname, '..');
const { createApp } = require(path.join(project, 'tests/dom-runtime.cjs'));
const assert = require('node:assert/strict');

let passed = 0;
const processRejections = [];
const captureRejection = (reason) => processRejections.push(reason);
process.on('unhandledRejection', captureRejection);

const wait = (ms = 25) => new Promise((resolve) => setTimeout(resolve, ms));
const check = (description, test) => {
  test();
  passed += 1;
  console.log('PASS', description);
};

async function session(description, run, options = {}) {
  const app = await createApp(options);
  const { w, d } = app;
  const errors = [];
  const rejectionStart = processRejections.length;
  w.addEventListener('error', (event) => errors.push(event.error || event.message));
  w.addEventListener('unhandledrejection', (event) => errors.push(event.reason));
  const q = (selector) => d.querySelector(selector);
  const all = (selector) => [...d.querySelectorAll(selector)];
  const requireElement = (selector) => {
    const element = q(selector);
    assert.ok(element, `Missing UI element: ${selector}`);
    return element;
  };
  const click = (selector) => requireElement(selector).click();
  const input = (selector, value) => {
    const element = requireElement(selector);
    element.value = value;
    element.dispatchEvent(new w.Event('input', { bubbles: true }));
  };
  const change = (selector, value) => {
    const element = requireElement(selector);
    if (typeof value === 'boolean') element.checked = value;
    else element.value = value;
    element.dispatchEvent(new w.Event('change', { bubbles: true }));
  };
  const route = async (value) => {
    w.location.hash = value;
    await wait();
  };
  try {
    await run({ w, d, q, all, click, input, change, route });
    await wait();
    check(`${description}: no uncaught errors or unhandled rejections`, () => {
      assert.deepEqual(errors, []);
      assert.deepEqual(processRejections.slice(rejectionStart), []);
    });
  } finally {
    app.close();
  }
}

const lists = [
  {
    name: 'users',
    table: '.users-full-table',
    mobile: '.mobile-user-cards',
    checkbox: '.row-check',
    selectAll: '#select-all',
    mobileAll: '#mobile-select-all',
    pageAttribute: 'data-page',
    search: '#user-search',
    pageSize: 10,
    count: 24,
    storage: 'nova-users',
    statusFilter: '#status-filter',
    activeStatus: '正常',
    targetStatus: '已停用',
    originalStatus: '正常',
    confirm: '[data-action="confirm-disable"]',
    beginBulk: ({ click }) => click('[data-action="bulk-disable"]'),
  },
  {
    name: 'catalog',
    table: '.catalog-table-wrap',
    mobile: '.catalog-mobile-cards',
    checkbox: '.catalog-check',
    selectAll: '#catalog-all',
    mobileAll: '#catalog-mobile-all',
    pageAttribute: 'data-catalog-page',
    search: '#catalog-search',
    pageSize: 10,
    count: 24,
    storage: 'nova-catalog',
    statusFilter: '#catalog-status',
    activeStatus: '已发布',
    targetStatus: '归档',
    originalStatus: '已发布',
    confirm: '[data-catalog="confirm-batch"]',
    beginBulk: ({ click, change }) => {
      change('#catalog-bulk', '归档');
      click('[data-catalog="apply-batch"]');
    },
  },
  {
    name: 'news',
    table: '.news-table-wrap',
    mobile: '.mobile-news-cards',
    checkbox: '.news-check',
    selectAll: '#news-all',
    mobileAll: '#news-mobile-all',
    pageAttribute: 'data-news-page',
    search: '#news-search',
    pageSize: 10,
    count: 24,
    storage: 'nova-news',
    statusFilter: '#news-status',
    activeStatus: '已发布',
    targetStatus: '归档',
    originalStatus: '已发布',
    confirm: '[data-news="confirm"]',
    beginBulk: ({ click }) => click('[data-news="archive"]'),
  },
];

async function testCrossPageSelection(spec) {
  await session(`${spec.name} selection`, async ({ q, all, click, input, change, route }) => {
    await route(spec.name);
    const firstId = q(`${spec.table} ${spec.checkbox}`).value;
    const chosen = `${spec.checkbox}[value="${firstId}"]`;
    change(`${spec.table} ${chosen}`, true);
    check(`${spec.name}: one selection synchronizes both layouts and partial select-all`, () => {
      assert.equal(q(`${spec.table} ${chosen}`).checked, true);
      assert.equal(q(`${spec.mobile} ${chosen}`).checked, true);
      assert.equal(q(spec.selectAll).indeterminate, true);
      assert.equal(q(spec.mobileAll).indeterminate, true);
    });

    click(`[${spec.pageAttribute}="2"]`);
    const pageTwoCount = Math.min(spec.pageSize, spec.count - spec.pageSize);
    change(spec.mobileAll, true);
    check(`${spec.name}: page-two select-all adds to the previous page's selection`, () => {
      assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, pageTwoCount);
      assert.equal(all(`${spec.mobile} ${spec.checkbox}:checked`).length, pageTwoCount);
      assert.match(q('.bulk-bar').textContent, new RegExp(`已选 ${pageTwoCount + 1}`));
      assert.match(q('.bulk-bar').textContent, /其他页 1/);
      assert.equal(q(spec.selectAll).checked, true);
      assert.equal(q(spec.selectAll).indeterminate, false);
    });

    change(spec.selectAll, false);
    check(`${spec.name}: deselect-all removes only the current page`, () => {
      assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, 0);
      assert.match(q('.bulk-bar').textContent, /已选 1/);
      assert.match(q('.bulk-bar').textContent, /其他页 1/);
      assert.equal(q(spec.mobileAll).checked, false);
    });
    click(`[${spec.pageAttribute}="1"]`);
    check(`${spec.name}: the original off-page selection survives returning`, () => {
      assert.equal(q(`${spec.table} ${chosen}`).checked, true);
      assert.equal(q(`${spec.mobile} ${chosen}`).checked, true);
    });
    input(spec.search, 'NO-SUCH-RECORD-REFRACTOR-TEST');
    check(`${spec.name}: changing the search clears selection and reaches an empty first page`, () => {
      assert.equal(q('.bulk-bar'), null);
      assert.equal(q(`${spec.table} tbody tr`), null);
      assert.ok(q('.empty-state'));
      assert.equal(q('.pagination [aria-current]').textContent.trim(), '1');
    });
  });
}

async function testBulkFailure(spec) {
  await session(`${spec.name} bulk persistence`, async (ui) => {
    const { w, q, click, change, route } = ui;
    await route(spec.name);
    const chosenId = q(`${spec.table} ${spec.checkbox}`).value;
    const rowSelector = `${spec.table} ${spec.checkbox}[value="${chosenId}"]`;
    const previousRowText = q(rowSelector).closest('tr').textContent;
    const unaffectedId = q(`${spec.table} tbody tr:nth-child(2) ${spec.checkbox}`).value;
    const unaffectedStatus = q(`${spec.table} tbody tr:nth-child(2)`).children[3].textContent;
    change(rowSelector, true);
    spec.beginBulk(ui);
    const previousStorage = w.localStorage.getItem(spec.storage);
    const previousAudit = w.localStorage.getItem('nova-audit');
    const originalSetItem = w.Storage.prototype.setItem;
    try {
      w.Storage.prototype.setItem = function () { throw new Error('Storage unavailable'); };
      click(spec.confirm);
      check(`${spec.name}: failed bulk storage preserves the confirmation, selection, rows and audit`, () => {
        assert.ok(q(spec.confirm));
        assert.ok(q('#storage-warning'));
        assert.equal(q(rowSelector).checked, true);
        assert.equal(q(rowSelector).closest('tr').textContent, previousRowText);
        assert.equal(w.localStorage.getItem(spec.storage), previousStorage);
        assert.equal(w.localStorage.getItem('nova-audit'), previousAudit);
      });
    } finally {
      w.Storage.prototype.setItem = originalSetItem;
    }

    click('#overlay-root [data-action="close"]');
    await route('overview');
    await route(spec.name);
    check(`${spec.name}: re-render after failure reads the original in-memory record`, () => {
      assert.equal(q(rowSelector).closest('tr').textContent, previousRowText);
      assert.equal(q(rowSelector).checked, true);
    });
    spec.beginBulk(ui);
    click(spec.confirm);
    check(`${spec.name}: retry commits only the selected record and clears selection`, () => {
      const saved = JSON.parse(w.localStorage.getItem(spec.storage));
      assert.equal(saved.length, spec.count);
      assert.equal(saved.find((row) => row.id === Number(chosenId)).status, spec.targetStatus);
      assert.equal(saved.find((row) => row.id === Number(unaffectedId)).status, unaffectedStatus);
      assert.match(q(rowSelector).closest('tr').textContent, new RegExp(spec.targetStatus));
      assert.equal(q('.bulk-bar'), null);
      assert.equal(q(spec.confirm), null);
      assert.equal(q('#storage-warning'), null);
    });
  });
}

async function testFilteredBulkPageClamp(spec) {
  await session(`${spec.name} filtered bulk page clamp`, async (ui) => {
    const { w, q, all, click, change, route } = ui;
    await route(spec.name);
    if (spec.name === 'catalog') {
      // Keep editor-save coverage independent from bulk publishing by preparing
      // every unpublished record through its real editor, across all three pages.
      const unpublishedIds = [];
      for (const page of [1, 2, 3]) {
        click(`[${spec.pageAttribute}="${page}"]`);
        unpublishedIds.push(...all(`${spec.table} tbody tr`)
          .filter((row) => row.children[3].textContent !== '已发布')
          .map((row) => Number(row.querySelector(spec.checkbox).value)));
      }
      for (const id of unpublishedIds) {
        await route(`catalog/edit/${id}`);
        change('#product-status', '已发布');
        q('#catalog-form').dispatchEvent(new w.SubmitEvent('submit', {
          bubbles: true,
          cancelable: true,
          submitter: q('[data-save-mode="list"]'),
        }));
        await wait();
      }
      check('Catalog editor saves prepare all records for the published filter', () => {
        const records = JSON.parse(w.localStorage.getItem(spec.storage));
        assert.equal(records.length, spec.count);
        assert.equal(records.every((record) => record.status === '已发布'), true);
      });
    } else if (spec.name === 'news') {
      for (const page of [1, 2, 3]) {
        click(`[${spec.pageAttribute}="${page}"]`);
        change(spec.selectAll, true);
      }
      click('[data-news="publish"]');
      click(spec.confirm);
      check(`${spec.name}: cross-page publish prepares all records through the UI`, () => {
        const records = JSON.parse(w.localStorage.getItem(spec.storage));
        assert.equal(records.length, spec.count);
        assert.equal(records.every((record) => record.status === '已发布'), true);
        assert.equal(q('.bulk-bar'), null);
      });
    }

    change(spec.statusFilter, spec.activeStatus);
    const originalCount = Number(q('.table-footer').textContent.match(/共 (\d+)/)[1]);
    const lastPage = Math.ceil(originalCount / spec.pageSize);
    assert.ok(lastPage > 1, `${spec.name} fixture must span multiple filtered pages`);
    click(`[${spec.pageAttribute}="${lastPage}"]`);
    const chosenIds = all(`${spec.table} ${spec.checkbox}`).map((box) => Number(box.value));
    change(spec.selectAll, true);
    const remainingCount = originalCount - chosenIds.length;
    const expectedPage = Math.max(1, Math.ceil(remainingCount / spec.pageSize));
    check(`${spec.name}: the active filter's last page is selected before bulk mutation`, () => {
      assert.equal(q('.pagination [aria-current]').textContent.trim(), String(lastPage));
      assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, chosenIds.length);
      assert.equal(new URLSearchParams(w.location.hash.split('?')[1]).get('status'), spec.activeStatus);
    });
    spec.beginBulk(ui);
    click(spec.confirm);

    check(`${spec.name}: bulk status removes matching rows and clamps page and URL together`, () => {
      const params = new URLSearchParams(w.location.hash.split('?')[1]);
      assert.equal(q(spec.statusFilter).value, spec.activeStatus);
      assert.equal(params.get('status'), spec.activeStatus);
      assert.equal(params.get('page'), expectedPage > 1 ? String(expectedPage) : null);
      assert.equal(q('.pagination [aria-current]').textContent.trim(), String(expectedPage));
      assert.equal(Number(q('.table-footer').textContent.match(/共 (\d+)/)[1]), remainingCount);
      assert.equal(all(`${spec.table} tbody tr`).length, spec.pageSize);
      assert.equal(q('.bulk-bar'), null);
      assert.equal(all(`${spec.table} ${spec.checkbox}:checked`).length, 0);
      assert.equal(q(spec.selectAll).checked, false);
      assert.equal(q(spec.selectAll).indeterminate, false);
      assert.equal(q(spec.confirm), null);
    });
    check(`${spec.name}: filtered bulk save updates only selected targets and retains other matches`, () => {
      const records = JSON.parse(w.localStorage.getItem(spec.storage));
      assert.equal(records.length, spec.count);
      for (const id of chosenIds) {
        assert.equal(records.find((record) => record.id === id).status, spec.targetStatus);
        assert.equal(q(`${spec.table} ${spec.checkbox}[value="${id}"]`), null);
      }
      assert.equal(records.filter((record) => record.status === spec.activeStatus).length, remainingCount);
      assert.equal(records.find((record) => record.id === (spec.name === 'users' ? 1 : spec.name === 'catalog' ? 101 : 201)).status, spec.activeStatus);
    });
  });
}

async function main() {
  await session('List sort and search', async ({ w, q, all, click, input, route }) => {
    await route('users?page=2');
    click('[data-action="sort"]');
    check('User sorting preserves page two and writes ascending order into the URL', () => {
      assert.equal(q('.pagination [aria-current]').textContent, '2');
      assert.equal(new URLSearchParams(w.location.hash.split('?')[1]).get('sort'), 'asc');
      const dates = all('.users-full-table tbody tr').map((row) => row.children[5].textContent);
      assert.deepEqual(dates, [...dates].sort());
    });
    click('[data-action="reset-filters"]');
    check('User filter reset returns to page one while retaining sort', () => {
      assert.equal(q('.pagination [aria-current]').textContent, '1');
      assert.equal(w.location.hash, '#users?sort=asc');
    });
    input('#user-search', 'DEMO01@EXAMPLE.COM');
    check('User search matches email without case sensitivity', () => {
      assert.equal(all('.users-full-table tbody tr').length, 1);
      assert.equal(q('.users-full-table .row-check').value, '1');
    });
    await route('catalog');
    input('#catalog-search', 'nova-kb-01');
    check('Catalog search matches SKU without case sensitivity', () => {
      assert.equal(all('.catalog-table tbody tr').length, 1);
      assert.equal(q('.catalog-table .catalog-check').value, '101');
    });
    await route('news?page=2');
    click('[data-news="sort"]');
    check('News sorting returns to page one and shows the earliest publication', () => {
      assert.equal(q('.pagination [aria-current]').textContent, '1');
      assert.equal(q('.news-table .news-check').value, '224');
      assert.equal(w.location.hash, '#news?sort=asc');
    });
    input('#news-search', '秋日');
    click('[data-news="reset"]');
    check('News filter reset retains ascending sort', () => {
      assert.equal(q('#news-search').value, '');
      assert.equal(q('.news-table .news-check').value, '224');
      assert.equal(w.location.hash, '#news?sort=asc');
    });
  });

  await session('News search case', async ({ all, input, route }) => {
    await route('news');
    input('#news-search', 'editorial');
    check('News title search remains case-sensitive', () => {
      assert.equal(all('.news-table tbody tr').length, 0);
    });
    input('#news-search', 'Editorial');
    check('News title search matches the original case', () => {
      assert.equal(all('.news-table tbody tr').length, 1);
    });
    input('#news-search', 'Author');
    check('News search also matches its author', () => {
      assert.equal(all('.news-table tbody tr').length, 1);
    });
  }, {
    storage: {
      'nova-news': JSON.stringify([{
        id: 201,
        title: 'Editorial Example',
        category: '设计观察',
        author: 'Example Author',
        status: '已发布',
        date: '2026-10-01',
        views: 10,
        summary: 'A persisted record used to exercise case-sensitive title and author search.',
      }]),
    },
  });

  await session('Scenario member snapshots', async ({ w, q, all, click, input, route }) => {
    await route('components');
    click('[data-lab-tab="data"]');
    check('Component data tab renders its profile and three member density rows', () => {
      assert.equal(q('.profile-showcase h3').textContent, '林知夏');
      assert.equal(all('#density-table tbody tr').length, 3);
      assert.equal(q('#density-table tbody tr:first-child .person strong').textContent, '林知夏');
    });
    click('.profile-showcase + .mini-stats + .lab-form-actions [data-edit="1"]');
    input('#member-name', '资料卡更新成员');
    q('#user-form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    check('Saving a member refreshes the component profile and density records', () => {
      assert.equal(q('.profile-showcase h3').textContent, '资料卡更新成员');
      assert.equal(q('#density-table tbody tr:first-child .person strong').textContent, '资料卡更新成员');
    });

    await route('users');
    click('[data-edit="2"]');
    input('#member-name', '指定编号更新成员');
    q('#user-form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    click('[data-detail="2"]');
    check('Member details retrieve the latest saved record by its selected ID', () => {
      assert.equal(q('.detail-profile .person strong').textContent, '指定编号更新成员');
      assert.match(q('.detail-list').textContent, /NOVA-0002/);
    });
    click('#overlay-root [data-action="close"]');
    await route('components');
    check('Reopening component data reads the updated member collection', () => {
      assert.equal(q('#density-table tbody tr:nth-child(2) .person strong').textContent, '指定编号更新成员');
      assert.equal(q('.profile-showcase h3').textContent, '资料卡更新成员');
    });

    await route('settings');
    click('[data-action="reset-demo"]');
    click('[data-action="confirm-reset-demo"]');
    await route('components');
    check('Demo reset refreshes the profile and density snapshots from original records', () => {
      assert.equal(q('.profile-showcase h3').textContent, '林知夏');
      assert.equal(q('#density-table tbody tr:first-child .person strong').textContent, '林知夏');
      assert.equal(q('#density-table tbody tr:nth-child(2) .person strong').textContent, '陈屿');
    });
    await route('users');
    click('[data-detail="2"]');
    check('Member details retrieve the reset record rather than a previous snapshot', () => {
      assert.equal(q('.detail-profile .person strong').textContent, '陈屿');
      assert.match(q('.detail-list').textContent, /NOVA-0002/);
    });
  });

  for (const spec of lists) await testCrossPageSelection(spec);
  for (const spec of lists) await testBulkFailure(spec);
  for (const spec of lists) await testFilteredBulkPageClamp(spec);

  await session('Catalog reset race', async ({ w, q, click, route }) => {
    await route('catalog');
    click('.catalog-table [data-feature-toggle="101"]');
    check('A pending catalog toggle continues displaying its original value', () => {
      assert.equal(q('[data-feature-toggle="101"]').getAttribute('aria-busy'), 'true');
      assert.equal(q('[data-feature-toggle="101"]').getAttribute('aria-checked'), 'true');
    });
    await route('settings');
    click('[data-action="reset-demo"]');
    click('[data-action="confirm-reset-demo"]');
    await wait(500);
    await route('catalog');
    check('Reset invalidates the pending catalog write and its audit event', () => {
      assert.equal(q('[data-feature-toggle="101"]').getAttribute('aria-checked'), 'true');
      assert.equal(q('[data-feature-toggle="101"]').getAttribute('aria-busy'), null);
      assert.equal(w.localStorage.getItem('nova-catalog'), null);
      assert.equal(w.localStorage.getItem('nova-audit'), null);
    });
  });

  await session('Concurrent catalog updates', async ({ w, q, click, change, route }) => {
    await route('catalog');
    click('.catalog-table [data-feature-toggle="101"]');
    click('.catalog-table [data-feature-toggle="102"]');
    change('.catalog-table .catalog-check[value="101"]', true);
    change('#catalog-bulk', '归档');
    click('[data-catalog="apply-batch"]');
    click('[data-catalog="confirm-batch"]');
    check('A bulk update can complete while independent featured toggles are pending', () => {
      assert.equal(JSON.parse(w.localStorage.getItem('nova-catalog')).find((row) => row.id === 101).status, '归档');
      assert.equal(q('[data-feature-toggle="101"]').getAttribute('aria-busy'), 'true');
      assert.equal(q('[data-feature-toggle="102"]').getAttribute('aria-busy'), 'true');
    });
    await wait(500);
    check('Delayed toggles preserve each other and the intervening bulk status update', () => {
      const rows = JSON.parse(w.localStorage.getItem('nova-catalog'));
      assert.equal(rows.find((row) => row.id === 101).featured, false);
      assert.equal(rows.find((row) => row.id === 101).status, '归档');
      assert.equal(rows.find((row) => row.id === 102).featured, true);
      assert.equal(rows.find((row) => row.id === 102).status, '草稿');
      assert.equal(rows.find((row) => row.id === 103).featured, false);
      assert.equal(q('[data-feature-toggle="101"]').getAttribute('aria-checked'), 'false');
      assert.equal(q('[data-feature-toggle="102"]').getAttribute('aria-checked'), 'true');
      assert.equal(q('[data-feature-toggle="101"]').getAttribute('aria-busy'), null);
      const audit = JSON.parse(w.localStorage.getItem('nova-audit'));
      assert.equal(audit.filter((entry) => entry.type === '更新精选状态').length, 2);
      assert.equal(audit.filter((entry) => entry.type === '商品批量更新').length, 1);
    });
  });

  console.log('TOTAL', passed, 'refactor boundary checks passed (Node/jsdom)');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
}).finally(() => {
  process.removeListener('unhandledRejection', captureRejection);
});
