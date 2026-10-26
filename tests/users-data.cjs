// Synthetic local records only. DOM checks do not replace browser acceptance.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { JSDOM } = require('jsdom');
const { createApp } = require('./dom-runtime.cjs');
let passed = 0, failed = 0;
const base = { id: 901, name: 'Review User', email: 'review@example.test', role: '编辑', status: '正常', team: '研发中心', joined: '2026-10-26' };
const literal = { ...base, name: '<b>名</b>&"\'', email: '<i>m</i>&@ex.test' };
const wait = () => new Promise(resolve => setTimeout(resolve, 15));
async function test(name, run) {
  try { await run(); passed++; console.log('PASS', name); }
  catch (error) { failed++; console.error('FAIL', name, error.stack); }
}
async function session(records, route, run, options = {}) {
  const raw = options.raw ?? JSON.stringify(records), errors = [];
  let window;
  try {
    const app = await createApp({ url: 'https://example.test/#' + route, storage: { 'nova-users': raw }, beforeLoad(w) { window = w; w.addEventListener('error', event => errors.push(event.error)); } });
    const { w, d } = app, q = selector => d.querySelector(selector), all = selector => [...d.querySelectorAll(selector)];
    const click = selector => { assert.ok(q(selector), 'Missing ' + selector); q(selector).click(); };
    const input = (selector, value) => { q(selector).value = value; q(selector).dispatchEvent(new w.Event('input', { bubbles: true })); };
    const change = (selector, value) => { q(selector).value = value; q(selector).dispatchEvent(new w.Event('change', { bubbles: true })); };
    const submit = () => q('#user-form').dispatchEvent(new w.SubmitEvent('submit', { bubbles: true, cancelable: true }));
    await run({ w, d, q, all, click, input, change, submit, raw, route: async value => { w.location.hash = value; await wait(); } });
    assert.deepEqual(errors, [], 'No uncaught user-data exception');
  } finally { window?.close(); }
}
async function fallback(records, options) {
  await session(records, 'users', ({ w, q, all, raw }) => {
    assert.equal(all('.users-full-table tbody tr').length, 10);
    assert.match(q('#user-results').textContent, /共 24 位用户/);
    assert.equal(all('[data-review-injection]').length, 0);
    assert.equal(w.localStorage.getItem('nova-users'), raw, 'Reading must not rewrite saved data');
  }, options);
}
(async () => {
  await test('Malformed JSON falls back without rewriting storage', () => fallback(null, { raw: '{bad' }));
  await test('A non-array storage value falls back without rewriting storage', () => fallback({ users: [base] }));
  await test('Null array entries fall back without crashing', () => fallback([null]));
  for (const [label, patch] of [
    ['numeric name', { name: 42 }], ['short name', { name: 'A' }], ['oversized name', { name: '长'.repeat(25) }],
    ['numeric email', { email: 42 }], ['invalid email', { email: 'invalid' }], ['email with a trailing newline', { email: 'review@example.test\n' }],
    ['unknown role', { role: '<b data-review-injection="role">marker</b>' }],
    ['unknown status', { status: '<b data-review-injection="status">marker</b>' }],
    ['missing team', { team: undefined }], ['numeric team', { team: 42 }], ['unknown team', { team: '外部团队' }],
    ['HTML team', { team: '<b data-review-injection="team">marker</b>' }],
    ['missing date', { joined: undefined }], ['numeric date', { joined: 42 }], ['null date', { joined: null }],
    ['HTML date', { joined: '<b data-review-injection="date">marker</b>' }],
    ['unpadded date', { joined: '2026-1-2' }], ['date with a trailing newline', { joined: '2026-10-26\n' }], ['non-leap February 29', { joined: '2026-02-29' }],
    ['century non-leap date', { joined: '1900-02-29' }], ['February 30', { joined: '2024-02-30' }],
    ['April 31', { joined: '2026-04-31' }], ['month zero', { joined: '2026-00-01' }],
    ['month thirteen', { joined: '2026-13-01' }], ['day zero', { joined: '2026-01-00' }],
    ['year zero', { joined: '0000-01-01' }], ['five-digit year', { joined: '10000-01-01' }],
    ['fractional ID', { id: 1.5 }], ['negative ID', { id: -1 }], ['unsafe ID', { id: Number.MAX_SAFE_INTEGER + 1 }],
  ]) await test('Storage rejects ' + label, () => fallback([{ ...base, ...patch }]));
  await test('Two numeric dates cannot crash collection sorting', () => fallback([{ ...base, joined: 42 }, { ...base, id: 902, email: 'second@example.test', joined: 43 }]));
  await test('Duplicate IDs cannot create ambiguous editor targets', () => fallback([base, { ...base, email: 'other@example.test' }]));
  await test('Case-insensitive duplicate emails follow form uniqueness rules', () => fallback([base, { ...base, id: 902, email: 'REVIEW@example.test' }]));
  const valid = [
    { ...base, id: 901, team: '产品设计', role: '管理员', joined: '0001-01-01' },
    { ...base, id: 902, email: 'two@example.test', status: '待激活', joined: '2000-02-29' },
    { ...base, id: 903, email: 'three@example.test', team: '内容运营', role: '只读成员', status: '已停用', joined: '2024-02-29' },
    { ...base, id: 904, email: 'four@example.test', team: '客户服务', joined: '9999-12-31' },
  ];
  await test('All supported teams, roles, statuses and valid calendar boundaries load', () => session(valid, 'users', ({ w, all, raw }) => {
    assert.equal(all('.users-full-table tbody tr').length, 4);
    assert.deepEqual(all('.users-full-table tbody [data-edit]').map(el => +el.dataset.edit), [904, 903, 902, 901]);
    assert.equal(w.localStorage.getItem('nova-users'), raw);
  }));
  await test('Validated dates still sort ascending and descending', () => session(valid, 'users', ({ all, click }) => {
    click('.users-full-table [data-action="sort"]');
    assert.deepEqual(all('.users-full-table tbody [data-edit]').map(el => +el.dataset.edit), [901, 902, 903, 904]);
    click('.users-full-table [data-action="sort"]');
    assert.deepEqual(all('.users-full-table tbody [data-edit]').map(el => +el.dataset.edit), [904, 903, 902, 901]);
  }));
  await test('Team search and role/status filters still use validated records', () => session(valid, 'users', ({ all, input, click, change }) => {
    input('#user-search', '研发中心'); assert.equal(all('.users-full-table tbody tr').length, 1);
    click('[data-action="reset-filters"]'); change('#role-filter', '只读成员'); assert.equal(all('.users-full-table tbody tr').length, 1);
    click('[data-action="reset-filters"]'); change('#status-filter', '待激活'); assert.equal(all('.users-full-table tbody tr').length, 1);
  }));
  await test('Desktop rows and mobile cards display literal name and email', () => session([literal], 'users', ({ q, all }) => {
    for (const parent of ['.users-full-table', '.mobile-user-cards']) {
      assert.equal(q(parent + ' .person strong').textContent, literal.name);
      assert.equal(q(parent + ' .person small').textContent, literal.email);
      assert.equal(all(parent + ' b, ' + parent + ' i').length, 0);
    }
  }));
  await test('Member detail and timeline display literal text and validated metadata', () => session([literal], 'users', ({ q, all, click }) => {
    click('[data-detail="901"]');
    assert.equal(q('.detail-profile .person strong').textContent, literal.name);
    assert.equal(q('.detail-profile .person small').textContent, literal.email);
    assert.deepEqual(all('.detail-list dd').map(el => el.textContent), ['NOVA-0901', base.team, base.role, base.joined, literal.email]);
    assert.equal(q('.timeline div:nth-child(2) p').textContent, base.role + ' · ' + base.team);
    assert.equal(all('.drawer b, .drawer i[data-review-injection]').length, 0);
  }));
  await test('Overview recent users display literal text and valid dates', () => session([literal], 'overview', ({ q }) => {
    assert.equal(q('.overview-table .person strong').textContent, literal.name);
    assert.equal(q('.overview-table .person small').textContent, literal.email);
    assert.ok(q('.overview-table').textContent.includes(base.joined));
  }));
  await test('Command results keep literal names and emails when opening an editor', () => session([literal], 'users', ({ q, click, input }) => {
    click('[data-action="search"]'); input('#command-search', '名');
    assert.ok(q('#command-results').textContent.includes(literal.name));
    assert.equal(q('#command-results small').textContent, literal.email);
    click('#command-results [data-edit="901"]');
    assert.equal(q('#member-name').value, literal.name); assert.equal(q('#member-email').value, literal.email);
  }));
  await test('Component profile, avatar and density table keep literal user text', () => session([literal], 'components', ({ q, all, click }) => {
    click('[data-lab-tab="data"]');
    assert.equal(q('.profile-showcase h3').textContent, literal.name);
    assert.equal(q('.profile-showcase p').textContent, literal.email);
    assert.equal(q('.profile-showcase .avatar').textContent, literal.name.slice(-2));
    assert.equal(q('#density-table .person strong').textContent, literal.name);
    assert.equal(all('.profile-showcase b, .profile-showcase i, #density-table b, #density-table i').length, 0);
    click('[data-detail="901"]'); assert.equal(q('.detail-profile .person strong').textContent, literal.name);
  }));
  for (const view of ['overview', 'users', 'roles', 'components']) await test('Empty users remain empty in ' + view, () => session([], view, ({ w, q, all, click, raw }) => {
    if (view === 'components') {
      click('[data-lab-tab="data"]'); assert.match(q('.lab-grid').textContent, /暂无成员/);
      assert.equal(q('.profile-showcase'), null); assert.equal(q('[data-detail]'), null); assert.equal(q('[data-edit]'), null);
      assert.equal(all('#density-table tbody tr').length, 0);
    } else if (view === 'users') assert.match(q('#user-results').textContent, /没有找到/);
    else if (view === 'overview') assert.equal(all('.overview-table tbody tr').length, 0);
    else assert.ok(all('.role-card small').every(el => el.textContent.includes('0 位')));
    assert.equal(w.localStorage.getItem('nova-users'), raw);
  }));
  await test('Empty component profile offers creation and survives refresh', async () => {
    let saved;
    await session([], 'components', ({ w, q, click, input, submit }) => {
      click('[data-lab-tab="data"]'); click('.lab-grid [data-action="add"]');
      input('#member-name', '空表新增'); input('#member-email', 'first@example.test'); submit();
      saved = w.localStorage.getItem('nova-users'); assert.equal(JSON.parse(saved).length, 1);
      assert.equal(q('.profile-showcase h3').textContent, '空表新增');
    });
    await session(null, 'components', ({ q, click }) => { click('[data-lab-tab="data"]'); assert.equal(q('.profile-showcase h3').textContent, '空表新增'); }, { raw: saved });
  });
  for (const [field, value] of [['role', '未知角色'], ['status', '未知状态'], ['team', '<b>未知团队</b>']]) {
    await test('Submitting a forged ' + field + ' option is rejected and retained for correction', () => session([base], 'users', ({ w, q, d, click, change, submit, raw }) => {
      click('[data-edit="901"]');
      const option = d.createElement('option'); option.value = value; option.textContent = value; q('#member-' + field).append(option);
      change('#member-' + field, value); submit();
      assert.equal(w.localStorage.getItem('nova-users'), raw); assert.ok(q('#user-form'));
      assert.equal(q('#member-' + field).getAttribute('aria-invalid'), 'true');
      assert.ok(q('#' + field + '-error').textContent); assert.equal(d.activeElement.id, 'member-' + field);
    }));
  }
  await test('Programmatic overlong names follow the same storage and form limit', () => session([base], 'users', ({ w, q, click, input, submit, raw }) => {
    click('[data-edit="901"]'); input('#member-name', '长'.repeat(25)); submit();
    assert.equal(w.localStorage.getItem('nova-users'), raw); assert.ok(q('#name-error').textContent); assert.equal(q('#member-name').value.length, 25);
  }));
  await test('Editing preserves the valid joined date and literal text across refresh', async () => {
    let saved;
    await session([base], 'users', ({ w, q, click, input, change, submit }) => {
      click('[data-edit="901"]'); input('#member-name', literal.name); input('#member-email', literal.email);
      change('#member-team', '内容运营'); change('#member-role', '只读成员'); change('#member-status', '待激活'); submit();
      saved = w.localStorage.getItem('nova-users'); const result = JSON.parse(saved)[0];
      assert.equal(result.joined, base.joined); assert.equal(result.name, literal.name); assert.equal(result.email, literal.email); assert.equal(result.team, '内容运营');
      assert.equal(q('.users-full-table .person strong').textContent, literal.name);
    });
    await session(null, 'components', ({ q, click }) => { click('[data-lab-tab="data"]'); assert.equal(q('.profile-showcase h3').textContent, literal.name); assert.equal(q('.profile-showcase p').textContent, literal.email); }, { raw: saved });
  });
  await test('Creation trims text, saves supported fields and restores after refresh', async () => {
    let saved;
    await session([], 'users', ({ w, click, input, change, submit }) => {
      click('[data-action="add"]'); input('#member-name', '  A<&  '); input('#member-email', '  new@example.test  ');
      change('#member-team', '客户服务'); change('#member-role', '管理员'); change('#member-status', '已停用'); submit();
      saved = w.localStorage.getItem('nova-users'); const result = JSON.parse(saved)[0];
      assert.equal(result.name, 'A<&'); assert.equal(result.email, 'new@example.test'); assert.equal(result.team, '客户服务');
      assert.match(result.joined, /^\d{4}-\d{2}-\d{2}$/); assert.ok(Number.isSafeInteger(result.id));
    });
    await session(null, 'users', ({ q }) => assert.equal(q('.users-full-table .person strong').textContent, 'A<&'), { raw: saved });
  });
  await test('Normal form creation keeps an HTML-shaped name literal through all user surfaces and refresh', async () => {
    const name = '<b id=probe>甲</b>'; let saved;
    await session([], 'users', async ({ w, d, q, click, input, submit, route }) => {
      click('[data-action="add"]'); input('#member-name', name); input('#member-email', 'user-review@example.test'); submit();
      saved = w.localStorage.getItem('nova-users'); assert.equal(JSON.parse(saved)[0].name, name);
      assert.equal(q('.users-full-table .person strong').textContent, name); assert.equal(q('.mobile-user-cards .person strong').textContent, name);
      click('[data-detail="1"]'); assert.equal(q('.detail-profile .person strong').textContent, name); click('[data-action="close"]');
      click('[data-edit="1"]'); assert.equal(q('#member-name').value, name); click('[data-action="close"]');
      await route('overview'); assert.equal(q('.overview-table .person strong').textContent, name);
      await route('components'); click('[data-lab-tab="data"]'); assert.equal(q('.profile-showcase h3').textContent, name); assert.equal(d.querySelector('#probe'), null);
    });
    await session(null, 'components', ({ d, q, click }) => { click('[data-lab-tab="data"]'); assert.equal(q('.profile-showcase h3').textContent, name); assert.equal(d.querySelector('#probe'), null); }, { raw: saved });
  });
  await test('Creation cannot round an exhausted safe member ID into corrupt storage', () => session([{ ...base, id: Number.MAX_SAFE_INTEGER }], 'users', ({ w, q, click, input, submit, raw }) => {
    click('[data-action="add"]'); input('#member-name', '编号边界'); input('#member-email', 'limit@example.test'); submit();
    assert.equal(w.localStorage.getItem('nova-users'), raw); assert.match(q('#user-form-error').textContent, /编号/); assert.equal(q('#member-name').value, '编号边界');
  }));
  await test('Scenario renderers escape metadata at their public data boundary', async () => {
    const dom = new JSDOM('<main id="view"></main><div id="drawer"></div>', { url: 'https://example.test/', runScripts: 'outside-only' });
    const { window: w } = dom, d = w.document; w.structuredClone = structuredClone;
    try {
      const module = new vm.SourceTextModule(fs.readFileSync(path.join(__dirname, '../dist/js/scenarios.js'), 'utf8'), { context: dom.getInternalVMContext() });
      await module.link(() => { throw new Error('Unexpected scenario import'); }); await module.evaluate();
      const user = { ...literal, ...Object.fromEntries(['role', 'status', 'team', 'joined'].map(field => [field, '<b data-probe="' + field + '">' + field + '</b>'])) };
      const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
      const renderView = () => { d.querySelector('#view').innerHTML = module.namespace.renderComponentLab(); };
      module.namespace.initScenarios({ ui: { icon: () => '', esc, person: u => '<strong>' + esc(u.name) + '</strong>', renderView, openOverlay: html => { d.querySelector('#drawer').innerHTML = html; } }, getUser: () => user, getUsers: () => [user] });
      renderView(); d.querySelector('[data-lab-tab="data"]').click();
      assert.equal(d.querySelector('.profile-showcase .pill').textContent, user.role);
      assert.equal(d.querySelector('#density-table td:nth-child(2)').textContent, user.role);
      d.querySelector('[data-detail]').click();
      for (const field of ['role', 'status', 'team', 'joined']) assert.ok(d.querySelector('#drawer').textContent.includes(user[field]));
      assert.equal(d.querySelectorAll('[data-probe]').length, 0);
    } finally { w.close(); }
  });
  await test('Duplicate email validation remains case insensitive', () => session([base], 'users', ({ w, q, click, input, submit, raw }) => {
    click('[data-action="add"]'); input('#member-name', '重复邮箱'); input('#member-email', 'REVIEW@example.test'); submit();
    assert.match(q('#email-error').textContent, /已存在/); assert.equal(w.localStorage.getItem('nova-users'), raw);
  }));
  await test('Failed persistence retains the editor and original stored records', () => session([base], 'users', ({ w, q, click, input, submit, raw }) => {
    click('[data-edit="901"]'); input('#member-name', '保留修改');
    w.Storage.prototype.setItem = () => { throw new Error('quota'); }; submit();
    assert.equal(w.localStorage.getItem('nova-users'), raw); assert.equal(q('#member-name').value, '保留修改'); assert.equal(q('#user-form').dataset.dirty, 'true');
  }));
  await test('Validated user CSV retains literal text, quoting and formula protection', () => session([{ ...literal, name: '=1+1' }], 'users', ({ w, click }) => {
    let csv, filename;
    w.Blob = class { constructor(parts) { csv = parts.join(''); } };
    w.URL.createObjectURL = () => 'blob:users-data'; w.URL.revokeObjectURL = () => {};
    w.HTMLAnchorElement.prototype.click = function () { filename = this.download; };
    click('[data-action="export"]');
    assert.equal(filename, 'nova-demo-users.csv'); assert.ok(csv.startsWith('\uFEFF'));
    assert.ok(csv.includes('"\'=1+1"')); assert.ok(csv.includes('"' + literal.email + '"'));
    assert.ok(csv.includes('"研发中心","2026-10-26"')); assert.ok(!csv.includes('&lt;'));
  }));
  await test('Bulk status updates still persist validated records and literal confirmation text', () => session([literal], 'users', ({ w, q, click }) => {
    q('.users-full-table .row-check').checked = true; q('.users-full-table .row-check').dispatchEvent(new w.Event('change', { bubbles: true }));
    click('[data-action="bulk-disable"]'); assert.ok(q('.modal').textContent.includes(literal.name));
    click('[data-action="confirm-disable"]'); const result = JSON.parse(w.localStorage.getItem('nova-users'))[0];
    assert.equal(result.status, '已停用'); assert.equal(result.joined, base.joined); assert.equal(result.name, literal.name);
  }));
  if (failed) { console.error('FAILED', failed, 'user data scenarios;', passed, 'passed'); process.exitCode = 1; }
  else console.log('TOTAL', passed, 'user data checks passed (Node/jsdom)');
})().catch(error => { console.error(error); process.exitCode = 1; });
