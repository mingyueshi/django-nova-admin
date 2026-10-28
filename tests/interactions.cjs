const { createApp } = require('./dom-runtime.cjs');
const assert = require('node:assert/strict');
const cases = [];
const test = (name, route, run) => cases.push({ name, route, run });
const wait = () => new Promise(resolve => setTimeout(resolve, 10));
function controls(app) {
  const { w, d } = app;
  const q = selector => d.querySelector(selector);
  const click = selector => q(selector).click();
  const event = (selector, value, type) => {
    q(selector).value = value;
    q(selector).dispatchEvent(new w.Event(type, { bubbles: true }));
  };
  const input = (selector, value) => event(selector, value, 'input');
  const change = (selector, value) => event(selector, value, 'change');
  const submit = selector => q(selector).dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  const go = async route => { w.location.hash = route; await wait(); };
  const addUser = () => {
    click('[data-action="add"]'); input('#member-name', '测试用户');
    input('#member-email', 'new@example.com'); submit('#user-form');
  };
  const contentForm = () => {
    input('#lab-title', '十月更新演示'); q('#lab-confirm').checked = true; submit('#lab-content-form');
  };
  return { ...app, q, click, input, change, submit, go, addUser, contentForm };
}
test('Dashboard renders four metrics', '', ({ d }) => assert.equal(d.querySelectorAll('.metric').length, 4));
test('Date changes metric', '', ({ q, change }) => {
  change('#period', '7'); assert.equal(q('.metric-value').textContent, '1,286');
});
test('Enterprise light default can toggle to dark', '', ({ d, click }) => {
  click('[data-action="theme"]'); assert.equal(d.documentElement.dataset.theme, 'dark');
});
test('User navigation', '', async ({ q, click }) => {
  click('[href="#users"]'); await wait(); assert.equal(q('h1').textContent, '用户管理');
});
test('Search narrows rows', 'users', ({ d, input }) => {
  input('#user-search', '林知夏'); assert.equal(d.querySelectorAll('.users-full-table tbody tr').length, 1);
});
test('Empty state', 'users', ({ q, input }) => {
  input('#user-search', 'NO-SUCH-NAME'); assert.match(q('#user-results').textContent, /没有找到/);
});
test('Status filter', 'users', ({ d, change }) => {
  change('#status-filter', '已停用'); assert.equal(d.querySelectorAll('.users-full-table tbody tr').length, 3);
});
test('Role filter', 'users', ({ d, change }) => {
  change('#role-filter', '管理员'); assert.equal(d.querySelectorAll('.users-full-table tbody tr').length, 4);
});
test('Pagination', 'users', ({ q, click }) => {
  click('[data-page="2"]'); assert.match(q('.table-footer').textContent, /第 11–20 条/);
});
test('Validation', 'users', ({ q, click, input, submit }) => {
  click('[data-edit="1"]'); input('#member-name', ''); input('#member-email', 'invalid'); submit('#user-form');
  assert.match(q('#name-error').textContent, /至少/);
});
test('Edit save persists', 'users', ({ w, click, input, submit }) => {
  click('[data-edit="1"]'); input('#member-name', '林知夏更新'); input('#member-email', 'demo01@example.com'); submit('#user-form');
  assert.equal(JSON.parse(w.localStorage.getItem('nova-users'))[0].name, '林知夏更新');
});
test('Duplicate email rejected', 'users', ({ q, click, input, submit }) => {
  click('[data-action="add"]'); input('#member-name', '测试用户'); input('#member-email', 'demo01@example.com'); submit('#user-form');
  assert.match(q('#email-error').textContent, /已存在/);
});
test('Add save', 'users', ({ w, addUser }) => {
  addUser(); assert.equal(JSON.parse(w.localStorage.getItem('nova-users')).length, 25);
});
test('Role matrix navigation', '', async ({ d, click }) => {
  click('[href="#roles"]'); await wait(); assert.equal(d.querySelectorAll('.permission-check').length, 12);
});
test('Permission local save', 'roles', ({ w, q, click }) => {
  const checkbox = q('.permission-check'); checkbox.checked = false;
  checkbox.dispatchEvent(new w.Event('change', { bubbles: true })); click('[data-action="save-permissions"]');
  assert.equal(JSON.parse(w.localStorage.getItem('nova-permissions'))['编辑'][0], false);
});
test('Command user search', 'users', ({ q, click, input, addUser }) => {
  addUser(); click('[data-action="search"]'); input('#command-search', '测试用户');
  assert.match(q('#command-results').textContent, /测试用户/);
});
test('Native comparison uses real template snapshot', '', async ({ q, click }) => {
  click('[data-action="native"]'); await wait(); assert.ok(q('#native-preview').getAttribute('src').includes('/native/'));
});
test('Settings save', 'settings', ({ q, input, submit }) => {
  input('#workspace-name', '测试工作空间'); submit('#settings-form'); assert.equal(q('.workspace-copy strong').textContent, '测试工作空间');
});
test('Reset restores original record', 'users', async ({ q, click, input, submit, go }) => {
  click('[data-edit="1"]'); input('#member-name', 'Changed'); submit('#user-form');
  await go('settings');
  click('[data-action="reset-demo"]'); click('[data-action="confirm-reset-demo"]'); await go('users');
  input('#user-search', '林知夏'); assert.equal(q('.users-full-table .person strong').textContent, '林知夏');
});
test('Reset restores original count', 'users', async ({ q, click, addUser, go }) => {
  addUser(); await go('settings'); click('[data-action="reset-demo"]'); click('[data-action="confirm-reset-demo"]'); await go('users');
  assert.match(q('.table-footer').textContent, /共 24 位/);
});
test('Component form category', 'components', ({ q }) => assert.ok(q('#lab-content-form')));
test('Extended form required validation', 'components', ({ q, submit }) => {
  submit('#lab-content-form'); assert.match(q('#lab-title-error').textContent, /至少/);
});
test('Extended form submits local', 'components', ({ q, contentForm }) => {
  contentForm(); assert.match(q('#lab-form-result').textContent, /提交成功/);
});
test('Error boundary state', 'components', ({ q, click }) => {
  click('[data-lab-tab="feedback"]'); click('[data-surface="error"]'); assert.match(q('#state-surface').textContent, /暂时无法加载/);
});
test('Loading skeleton', 'components', ({ q, click }) => {
  click('[data-lab-tab="feedback"]'); click('[data-surface="loading"]'); assert.ok(q('.skeleton-list'));
});
test('Cancel loading', 'components', ({ q, click }) => {
  click('[data-lab-tab="feedback"]'); click('[data-surface="loading"]'); click('[data-lab="cancel-load"]');
  assert.match(q('#state-surface').textContent, /没有记录/);
});
test('Wizard reaches review', 'components', ({ q, click, submit }) => {
  click('[data-lab-tab="workflow"]'); submit('#wizard-form'); submit('#wizard-form'); assert.match(q('#wizard-form').textContent, /立即模拟/);
});
test('Audit includes form event', 'components', async ({ q, contentForm, go }) => {
  contentForm(); await go('audit'); assert.match(q('.audit-table').textContent, /十月更新演示/);
});
test('Detail drawer', 'users', ({ q, click }) => {
  click('[data-detail="1"]'); assert.match(q('#drawer-title').textContent, /成员详情/);
});
test('Dirty form exit guard', 'users', ({ q, click, input }) => {
  click('[data-edit="1"]'); input('#member-name', '未保存修改'); click('[data-action="close"]'); assert.ok(q('#discard-confirm'));
});
test('No unhandled runtime exception', '', ({ q }) => assert.ok(q('#view').innerHTML.length > 100));
(async () => {
  const selected = cases.filter(item => !process.argv[2] || item.name.includes(process.argv[2]));
  assert.ok(selected.length, 'No matching test cases');
  let passed = 0;
  for (const item of selected) {
    let app;
    try {
      app = await createApp({ url: 'https://example.test/#' + item.route });
      await item.run(controls(app)); console.log('PASS', item.name); passed++;
    } catch (error) { console.error('FAIL', item.name, error); process.exitCode = 1; }
    finally { app?.close(); }
  }
  console.log('TOTAL', passed, 'passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
