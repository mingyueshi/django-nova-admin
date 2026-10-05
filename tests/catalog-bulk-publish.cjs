// Regression for the formerly malformed catalog publish <option>, including
// two draft records selected across the new 10-row page boundary.
const assert = require('node:assert/strict');
const path = require('node:path');
const project = process.env.NOVA_TEST_PROJECT || path.resolve(__dirname, '..');
const { createApp } = require(path.join(project, 'tests/dom-runtime.cjs'));
let passed = 0;
const rejections = [];
const captureRejection = (reason) => rejections.push(reason);
process.on('unhandledRejection', captureRejection);
const wait = () => new Promise((resolve) => setTimeout(resolve, 25));
const check = (description, test) => {
  test();
  passed += 1;
  console.log('PASS', description);
};

async function main() {
  const { w, d, close } = await createApp();
  const errors = [];
  w.addEventListener('error', (event) => errors.push(event.error || event.message));
  w.addEventListener('unhandledrejection', (event) => errors.push(event.reason));
  const q = (selector) => d.querySelector(selector);
  const change = (selector, value) => {
    const element = q(selector);
    assert.ok(element, `Missing UI element: ${selector}`);
    if (typeof value === 'boolean') element.checked = value;
    else element.value = value;
    element.dispatchEvent(new w.Event('change', { bubbles: true }));
  };
  try {
    w.location.hash = 'catalog';
    await wait();
    const firstTitle = q('.catalog-table .catalog-check[value="102"]').closest('tr').querySelector('.object-link').textContent;
    change('.catalog-table .catalog-check[value="102"]', true);
    q('[data-catalog-page="2"]').click();
    const secondTitle = q('.catalog-table .catalog-check[value="112"]').closest('tr').querySelector('.object-link').textContent;
    change('.catalog-table .catalog-check[value="112"]', true);

    check('Catalog bulk publish is a real selectable option with the correct label', () => {
      const publish = q('#catalog-bulk option[value="已发布"]');
      assert.ok(publish, 'The catalog bulk select must contain an option with value 已发布');
      assert.equal(publish.textContent, '发布所选');
    });
    change('#catalog-bulk', '已发布');
    check('Selecting publish retains its value before execution', () => {
      assert.equal(q('#catalog-bulk').value, '已发布');
      assert.equal(q('#catalog-bulk').selectedOptions[0].textContent, '发布所选');
    });
    q('[data-catalog="apply-batch"]').click();
    check('Publish confirmation identifies exactly the two selected cross-page records', () => {
      assert.ok(q('[data-catalog="confirm-batch"]'));
      assert.match(q('#batch-title').textContent, /发布 2 条/);
      assert.equal(d.querySelectorAll('.batch-preview li').length, 2);
      assert.ok(q('.batch-preview').textContent.includes(firstTitle));
      assert.ok(q('.batch-preview').textContent.includes(secondTitle));
    });
    check('Opening publish confirmation does not mutate persisted records', () => {
      assert.equal(w.localStorage.getItem('nova-catalog'), null);
      assert.match(q('.catalog-table .catalog-check[value="112"]').closest('tr').textContent, /草稿/);
    });
    q('[data-catalog="confirm-batch"]').click();
    check('Confirming publish persists only the selected status changes', () => {
      const records = JSON.parse(w.localStorage.getItem('nova-catalog'));
      assert.equal(records.length, 24);
      assert.equal(records.find((record) => record.id === 102).status, '已发布');
      assert.equal(records.find((record) => record.id === 112).status, '已发布');
      assert.equal(records.find((record) => record.id === 105).status, '草稿');
      assert.equal(records.find((record) => record.id === 107).status, '草稿');
      assert.equal(records.find((record) => record.id === 104).status, '归档');
      assert.equal(records.find((record) => record.id === 101).status, '已发布');
      assert.equal(records.find((record) => record.id === 103).status, '已发布');
      assert.equal(records.find((record) => record.id === 106).status, '已发布');
    });
    check('Publish success updates the visible row and clears selection and confirmation', () => {
      const row = q('.catalog-table .catalog-check[value="112"]');
      assert.match(row.closest('tr').textContent, /已发布/);
      assert.equal(row.checked, false);
      assert.equal(q('.bulk-bar'), null);
      assert.equal(q('[data-catalog="confirm-batch"]'), null);
      assert.equal(q('#catalog-all').checked, false);
      assert.equal(q('#catalog-all').indeterminate, false);
    });
    await wait();
    check('Catalog bulk publish has no uncaught errors or unhandled rejections', () => {
      assert.deepEqual(errors, []);
      assert.deepEqual(rejections, []);
    });
    console.log('TOTAL', passed, 'catalog bulk publish checks passed (Node/jsdom)');
  } finally {
    close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
}).finally(() => {
  process.removeListener('unhandledRejection', captureRejection);
});
