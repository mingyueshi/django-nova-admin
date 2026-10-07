import { createCollection } from './collection.js';
import { pagination, submitPageJump } from './pagination.js';
import { searchShortcut } from './presentation.js';
import { initMedia, thumbnail, imageSpec, restoreMedia } from './media.js';
import { initNews, renderNews, resetNews, syncNewsSelection } from './news.js';
import { enhanceControls } from './controls.js';
import {
  initNativeSamples,
  renderNativeSamples,
  selectNativeComparison,
} from './native-samples.js';
import {
  readNavigationPreferences,
  saveNavigationPreference,
  navigationPreferenceKey,
  flattenedNavigation,
  renderNavigation,
  renderBreadcrumb,
} from './navigation.js';
import {
  initCatalog,
  renderCatalog,
  catalogDirty,
  discardCatalogDraft,
  catalogRouteLabel,
  resetCatalog,
  syncCatalogSelection,
} from './catalog.js';
import { icon } from './icons.js';
import {
  renderComponentLab,
  renderAudit,
  initScenarios,
  addAuditEvent,
  resetAudit,
} from './scenarios.js';
import { initialUsers, initialPermissions, metricSets } from './data.js';
const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) =>
  String(s ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
const read = (k, f) => {
  try {
    const v = JSON.parse(localStorage.getItem(k));
    if (v === null) return f;
    if (
      k === 'nova-users' &&
      (!Array.isArray(v) ||
        !v.every(
          (u) =>
            u &&
            Number.isFinite(u.id) &&
            typeof u.name === 'string' &&
            typeof u.email === 'string' &&
            ['管理员', '编辑', '只读成员'].includes(u.role) &&
            ['正常', '待激活', '已停用'].includes(u.status),
        ))
    )
      return f;
    if (
      k === 'nova-permissions' &&
      !Object.keys(initialPermissions).every(
        (r) =>
          Array.isArray(v[r]) && v[r].length === 12 && v[r].every((x) => typeof x === 'boolean'),
      )
    )
      return f;
    if (
      k === 'nova-settings' &&
      (!v || typeof v.workspace !== 'string' || typeof v.animations !== 'boolean')
    )
      return f;
    return v;
  } catch {
    return f;
  }
};
const nav = flattenedNavigation();
const routeView = (route) => route.split('/')[0].split('?')[0];
const validRoute = (route) =>
  [
    'overview',
    'users',
    'roles',
    'audit',
    'components',
    'settings',
    'catalog',
    'native-samples',
    'login-preview',
    'news',
  ].includes(routeView(route));
const initialRoute = validRoute(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
let storageFailed = false;
const save = (k, v) => {
  try {
    localStorage.setItem(k, JSON.stringify(v));
    storageFailed = false;
    document.querySelector('#storage-warning')?.remove();
    return true;
  } catch {
    storageFailed = true;
    showStorageWarning();
    toast('保存失败：浏览器存储不可用，更改尚未保存', 'error');
    return false;
  }
};
function showStorageWarning() {
  if (!document.querySelector('#storage-warning'))
    document
      .querySelector('#main')
      ?.insertAdjacentHTML(
        'afterbegin',
        '<div id="storage-warning" class="storage-warning" role="alert">本地存储不可用。当前输入仍保留，请允许浏览器存储后再次保存；刷新可能丢失未保存内容。</div>',
      );
}

const state = {
  view: routeView(initialRoute),
  route: initialRoute,
  users: read('nova-users', structuredClone(initialUsers)),
  permissions: read('nova-permissions', structuredClone(initialPermissions)),
  period: 30,
  chart: '新增用户',
  selectedRole: '编辑',
  native: false,
  mobile: false,
  settings: read('nova-settings', { workspace: 'NOVA 工作空间', animations: true, compact: false }),
};
const userCollection = createCollection({
  getRecords: () => state.users,
  pageSize: 10,
  sort: 'desc',
  pageBeforeSort: true,
  filters: {
    search: { default: '', param: 'q', parse: (value) => (value || '').slice(0, 100) },
    status: {
      default: '全部状态',
      parse: (value) => (['正常', '待激活', '已停用'].includes(value) ? value : '全部状态'),
    },
    role: {
      default: '全部角色',
      parse: (value) => (['管理员', '编辑', '只读成员'].includes(value) ? value : '全部角色'),
    },
  },
  matches: (user, list) =>
    (user.name + user.email + user.team).toLowerCase().includes(list.search.toLowerCase()) &&
    (list.status === '全部状态' || user.status === list.status) &&
    (list.role === '全部角色' || user.role === list.role),
  compare: (a, b, list) =>
    list.sort === 'desc' ? b.joined.localeCompare(a.joined) : a.joined.localeCompare(b.joined),
});
const userList = userCollection.state;
let lastFocus = null,
  toastTimer,
  unsavedRole = false,
  permissionDraft = null,
  pendingRole = null,
  pendingNavigation = null,
  mainFormDirty = false;
const navOpened = readNavigationPreferences();
let navPersistenceFailed = false;
const restoreNavigationMenu = () => {
  if (navPersistenceFailed) return;
  const latest = readNavigationPreferences(navOpened);
  if (latest === navOpened) return;
  for (const key of Object.keys(navOpened)) delete navOpened[key];
  Object.assign(navOpened, latest);
  // Do not rerender forms or dialogs when another tab changes only navigation.
  document.querySelectorAll('[data-nav-group]').forEach((button) => {
    const key = button.dataset.navGroup;
    const open = navOpened[key] === true;
    button.setAttribute('aria-expanded', String(open));
    document.getElementById('nav-group-' + key).hidden = !open;
  });
};
window.addEventListener('pageshow', (event) => {
  if (event.persisted) restoreNavigationMenu();
});
window.addEventListener('storage', (event) => {
  if (event.key === navigationPreferenceKey() || event.key === null) restoreNavigationMenu();
});
let overlayStack = [];
let appearanceMode = 'light';
try {
  const saved = localStorage.getItem('nova-theme');
  if (['light', 'dark', 'auto'].includes(saved)) appearanceMode = saved;
} catch {}
const appearanceMedia = window.matchMedia?.('(prefers-color-scheme: dark)');
function applyAppearance(mode, persist = false) {
  if (!['light', 'dark', 'auto'].includes(mode)) mode = 'light';
  appearanceMode = mode;
  const resolved = mode === 'auto' ? (appearanceMedia?.matches ? 'dark' : 'light') : mode;
  document.documentElement.dataset.themeMode = mode;
  document.documentElement.dataset.theme = resolved;
  if (persist) {
    try {
      localStorage.setItem('nova-theme', mode);
    } catch {
      toast('主题已在当前页应用，浏览器未能保存偏好', 'error');
    }
  }
  $$('.topbar [data-action=theme]').forEach((b) => {
    b.innerHTML = icon(resolved === 'dark' ? 'sun' : 'moon');
    b.setAttribute('aria-label', resolved === 'dark' ? '切换浅色主题' : '切换深色主题');
  });
  const select = $('#appearance-mode');
  if (select) select.value = mode;
}
appearanceMedia?.addEventListener?.('change', () => {
  if (appearanceMode === 'auto') applyAppearance('auto');
});
applyAppearance(appearanceMode);

const roleDescription = {
  '管理员': '管理全部资源与组织配置',
  '编辑': '维护内容与日常业务数据',
  '只读成员': '查看信息，不进行数据修改',
};
function button(text, action, cls = '', ico = '') {
  return `<button type="button" class="btn ${cls}" data-action="${action}">${ico ? icon(ico) : ''}${text}</button>`;
}
function pill(status) {
  return `<span class="pill dot status-${status === '正常' ? 'normal' : status === '待激活' ? 'pending' : 'disabled'}">${status}</span>`;
}
function person(u) {
  return `<div class="person">${thumbnail(imageSpec('avatar', u.id, u.name))}<div><strong>${esc(u.name)}</strong><small>${esc(u.email)}</small></div></div>`;
}
function layout() {
  $('#app').innerHTML =
    `<div class="shell ${state.mobile ? 'mobile-open' : ''}"><button class="mobile-backdrop" data-action="close-nav" aria-label="关闭导航"></button><aside class="sidebar"><a class="brand" href="#overview" aria-label="NOVA 管理首页"><span class="brand-mark">N</span><span class="brand-name">NOVA</span></a><button class="workspace-select" data-action="workspace"><span class="workspace-icon">${icon('layers')}</span><span class="workspace-copy"><strong>${esc(state.settings.workspace)}</strong></span>${icon('down')}</button><div class="section-label">工作空间</div><nav class="nav-list" aria-label="主导航">${renderNavigation(state, icon, esc, navOpened)}</nav><div class="sidebar-bottom"><div class="sidebar-integration"><span class="integration-mark">${icon('terminal')}</span><div><strong>Django Admin</strong><button data-action="docs">集成与原生恢复说明 ${icon('arrow')}</button></div></div><button class="nav-item" data-action="native">${icon('history')}<span>原生恢复对照</span></button><div class="user-profile"><span class="avatar peach">演</span><div><p>演示管理员</p><small>本地演示 · 无真实账户</small></div></div></div></aside><div class="main-area">${state.native ? '<div class="preview-banner">当前为原生外观模拟。真实 Django 恢复方式见集成说明。</div>' : ''}<header class="topbar"><div class="breadcrumb"><button class="icon-button mobile-menu" data-action="mobile" aria-label="打开导航">${icon('menu')}</button>${renderBreadcrumb(state, icon, esc, state.view === 'catalog' ? catalogRouteLabel(state.route) : '')}</div><div class="topbar-actions"><span class="prototype">交互原型 · 模拟数据</span><button class="global-search" data-action="search" aria-label="搜索页面或用户（${searchShortcut().spoken}）" aria-keyshortcuts="${searchShortcut().keys}"><span>${icon('search')}</span><span>搜索页面或用户</span><kbd aria-hidden="true">${searchShortcut().label}</kbd>${window.innerWidth < 701 ? icon('search') : ''}</button><button class="icon-button" data-action="theme" aria-label="${document.documentElement.dataset.theme === 'dark' ? '切换浅色主题' : '切换深色主题'}">${icon(document.documentElement.dataset.theme === 'dark' ? 'sun' : 'moon')}</button><button class="icon-button unread" data-action="notifications" aria-label="查看演示通知">${icon('bell')}</button><span class="topbar-divider"></span><span class="avatar peach">演</span></div></header><main id="main" class="content" tabindex="-1"><div id="view"></div><footer class="footer"><span class="footer-left"><i class="live-dot"></i>NOVA ADMIN <span>·</span> 设计预览 v1.8.0</span><span class="footer-right">所有数据为本地模拟 <span>·</span> <a href="./responsive.html" target="_blank" rel="noopener">多尺寸预览 ↗</a> <span>·</span> <a href="#" data-action="docs">Django 集成说明</a></span></footer></main></div></div>`;
  document.body.classList.toggle('native', state.native);
  document.body.classList.toggle('reduced-motion', !state.settings.animations);
  renderView();
  if (storageFailed) showStorageWarning();
}
function intro(title, subtitle, actions, cls = '') {
  return `<div class="page-intro ${cls}"><div><h1>${title}</h1><p>${subtitle}</p></div><div class="page-actions">${actions}</div></div>`;
}
function renderView() {
  const view = {
    overview: overview,
    users: usersView,
    roles: rolesView,
    components: componentsView,
    audit: auditView,
    settings: settingsView,
    catalog: () => renderCatalog(state.route),
    news: () => renderNews(state.route),
    'native-samples': nativeSamplesView,
    'login-preview': loginPreviewView,
  }[state.view];
  $('#view').innerHTML = `<div class="view-animate">${view()}</div>`;
  const h = $('#view h1');
  if (h) h.setAttribute('tabindex', '-1');
  enhanceControls();
  if (state.view === 'users') syncUserSelection();
  if (state.view === 'catalog') syncCatalogSelection();
  if (state.view === 'news') syncNewsSelection();
  const crumb = $('.breadcrumb-trail');
  if (crumb)
    crumb.outerHTML = renderBreadcrumb(
      state,
      icon,
      esc,
      state.view === 'catalog' ? catalogRouteLabel(state.route) : '',
    );
}
function overview() {
  let m = metricSets[state.period],
    chartVals =
      state.chart === '新增用户'
        ? [49, 77, 57, 93, 69, 100, 89, 150, 124, 136, 171, 161, 188]
        : [65, 86, 70, 89, 110, 126, 109, 137, 125, 162, 159, 190, 175];
  return (
    intro(
      '工作概览',
      '欢迎回来，开始今天的工作吧。',
      `<select id="period" class="date-select" aria-label="概览时间范围">${[7, 30, 90].map((n) => `<option value="${n}" ${n === state.period ? 'selected' : ''}>最近 ${n} 天</option>`).join('')}</select>${button('导出报告', 'report', '', 'download')}`,
    ) +
    `<section class="metrics" aria-label="关键指标">${[
      ['总用户数', m[0].toLocaleString(), '+12.8%', 'users'],
      ['新增用户', m[1].toLocaleString(), '+18.6%', 'bolt'],
      ['账户活跃率', m[2], '+2.4%', 'activity'],
      ['操作记录', m[3].toLocaleString(), '+8.2%', 'layers'],
    ]
      .map(
        ([n, v, c, i], k) =>
          `<article class="metric"><div class="metric-top"><span>${n}</span><span class="metric-icon">${icon(i)}</span></div><div class="metric-value">${v}${k === 2 ? '<small>%</small>' : ''}</div><div class="metric-foot"><span class="positive">${icon('trend')}${c}</span><span>较上一周期</span></div><svg class="spark" viewBox="0 0 90 34" aria-hidden="true"><path d="M1 28L10 24L19 27L27 18L36 21L44 10L53 15L61 7L70 11L80 3L90 6" fill="none" stroke="${['var(--accent)', 'var(--mint)', 'var(--blue)', 'var(--peach)'][k]}" stroke-width="1.5"/></svg></article>`,
      )
      .join(
        '',
      )}</section><div class="dashboard-middle"><section class="panel"><div class="panel-head"><div><h2>用户增长趋势</h2><p>每一次增长，都值得被看见</p></div><div class="segmented" aria-label="图表指标">${['新增用户', '活跃用户'].map((n) => `<button data-chart="${n}" class="${state.chart === n ? 'active' : ''}" aria-pressed="${state.chart === n}">${n}</button>`).join('')}</div></div><div class="chart-summary"><strong>${(state.chart === '新增用户' ? m[1] : Math.round(m[0] * 0.71)).toLocaleString()}</strong><span class="positive">${icon('trend')}18.6%</span><div class="legend"><span><i></i>本期</span><span><i class="secondary"></i>上期</span></div></div><div class="chart-wrap"><svg role="img" aria-label="${state.chart}趋势示意图，本期整体上升" viewBox="0 0 660 213" preserveAspectRatio="none"><defs><linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="var(--accent)" stop-opacity=".2"/><stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>${[20, 63, 106, 149, 192].map((y, i) => `<line class="chart-grid" x1="38" y1="${y}" x2="644" y2="${y}"/><text class="chart-text" x="4" y="${y + 4}">${[200, 150, 100, 50, 0][i]}</text>`).join('')}<path d="M38 166C70 167 65 145 87 150S127 180 138 150 174 152 188 138 219 166 238 133 263 148 289 133 320 153 338 124 375 147 390 117 428 129 440 113 471 139 491 108 520 120 542 96 566 113 590 94 620 102 644 78" fill="none" stroke="var(--mint)" stroke-width="2" stroke-dasharray="4 5" opacity=".7"/>${chartPaths(chartVals)}${[38, 139, 240, 341, 442, 543, 644].map((x, i) => `<text class="chart-text" x="${x}" y="211" text-anchor="${i === 0 ? 'start' : i === 6 ? 'end' : 'middle'}">${state.period === 7 ? ['09/24', '09/25', '09/26', '09/27', '09/28', '09/29', '09/30'][i] : state.period === 90 ? ['07/01', '07/16', '08/01', '08/16', '09/01', '09/16', '09/30'][i] : ['09/01', '09/05', '09/10', '09/15', '09/20', '09/25', '09/30'][i]}</text>`).join('')}</svg><div class="chart-axis-y" aria-hidden="true">${[20, 63, 106, 149, 192].map((y, i) => `<span style="top:${(y / 213) * 100}%">${[200, 150, 100, 50, 0][i]}</span>`).join('')}</div><div class="chart-axis-x" aria-hidden="true">${(state.period === 7 ? ['09/24', '09/25', '09/26', '09/27', '09/28', '09/29', '09/30'] : state.period === 90 ? ['07/01', '07/16', '08/01', '08/16', '09/01', '09/16', '09/30'] : ['09/01', '09/05', '09/10', '09/15', '09/20', '09/25', '09/30']).map((d) => `<span>${d}</span>`).join('')}</div><div class="chart-tooltip"><small>本期中段 · 示例观测点</small><span>${state.chart}<strong>${chartVals[7]}</strong></span></div></div><div class="chart-caption">${icon('circle')}趋势与指标均为示例，用于预览不同时间范围</div></section><section class="panel progress-panel"><div class="panel-head"><h2>运行概况</h2><span class="pill dot status-normal">演示环境</span></div><div class="ring-wrap"><svg viewBox="0 0 140 140" aria-hidden="true"><circle cx="70" cy="70" r="58" fill="none" stroke="var(--line)" stroke-width="8"/><circle cx="70" cy="70" r="58" fill="none" stroke="var(--accent)" stroke-width="8" stroke-linecap="round" stroke-dasharray="345 365"/></svg><div class="ring-center"><strong>99.9<small style="font-size:15px">%</small></strong><span>可用性示例</span></div></div><div class="health-list"><div class="health-row"><span>应用服务</span><span class="health-value"><i></i>正常</span></div><div class="health-row"><span>平均响应</span><span>124<span class="muted">ms</span></span></div><div class="health-row"><span>上次同步</span><span class="muted">演示快照</span></div></div></section></div><section class="panel table-panel overview-table"><div class="panel-head"><div class="table-title"><h2>最近加入的用户</h2><span class="count-badge">${state.users.length} 位</span></div><a class="btn subtle" href="#users">查看全部 ${icon('arrow')}</a></div><div class="table-scroll">${table(state.users.slice(0, 4), false)}</div><div class="table-footer"><span>展示 4 条演示记录</span><span>更新时间 · 2026.09.30</span></div></section>`
  );
}
function chartPaths(v) {
  const p = v.map((n, i) => [38 + i * 50.5, 192 - n * 0.84]);
  let d = `M${p[0][0]} ${p[0][1]}`;
  for (let i = 1; i < p.length; i++) {
    let [x, y] = p[i],
      [a, b] = p[i - 1];
    d += ` C${a + 23} ${b} ${x - 23} ${y} ${x} ${y}`;
  }
  return `<path d="${d} L644 192 L38 192 Z" fill="url(#chartGradient)"/><path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2.5"/><line x1="391.5" x2="391.5" y1="${p[7][1]}" y2="192" stroke="var(--accent)" stroke-dasharray="3 4" opacity=".5"/><circle class="chart-spot" cx="391.5" cy="${p[7][1]}" r="4.5"/>`;
}
function filteredUsers() {
  return userCollection.filtered();
}
function table(rows, full = true) {
  return `<table><thead><tr>${full ? '<th class="check-cell"><input class="checkbox" type="checkbox" id="select-all" aria-label="选择当前页全部用户" ' + (rows.length && rows.every((u) => userList.selected.has(u.id)) ? 'checked' : '') + '></th>' : ''}<th>用户</th><th>角色</th><th>状态</th>${full ? '<th>所属团队</th>' : ''}<th>${full ? `<button class="sort-btn" data-action="sort">加入时间 ${icon('down')}</button>` : '加入时间'}</th><th style="text-align:right">操作</th></tr></thead><tbody>${rows.map((u) => `<tr>${full ? `<td class="check-cell"><input type="checkbox" class="checkbox row-check" value="${u.id}" aria-label="选择${esc(u.name)}" ${userList.selected.has(u.id) ? 'checked' : ''}></td>` : ''}<td>${person(u)}</td><td><span class="pill ${u.role === '管理员' ? 'role-admin' : ''}">${u.role}</span></td><td>${pill(u.status)}</td>${full ? `<td class="muted">${u.team}</td>` : ''}<td class="muted">${u.joined}</td><td style="text-align:right"><button class="icon-button" data-detail="${u.id}" aria-label="查看${esc(u.name)}详情">${icon('book')}</button><button class="icon-button" data-edit="${u.id}" aria-label="编辑${esc(u.name)}">${icon('edit')}</button></td></tr>`).join('')}</tbody></table>`;
}
function syncUserRoute(push = false) {
  if (state.view !== 'users') return;
  state.route = 'users' + userCollection.queryString();
  const method = push && location.hash !== '#' + state.route ? 'pushState' : 'replaceState';
  history[method](null, '', '#' + state.route);
}
function restoreUserRoute() {
  userCollection.restore(state.route);
}
function usersView() {
  restoreUserRoute();
  return (
    intro(
      '用户管理',
      '管理成员、角色与访问状态，让协作井然有序。',
      button('导出 CSV', 'export', '', 'download') + button('添加用户', 'add', 'primary', 'plus'),
      'users-intro',
    ) +
    `<section class="panel table-panel"><div class="user-toolbar"><div class="search-input">${icon('search')}<input id="user-search" placeholder="搜索姓名、邮箱或团队…" aria-label="搜索用户" value="${esc(userList.search)}"></div><select id="status-filter" aria-label="按状态筛选">${['全部状态', '正常', '待激活', '已停用'].map((n) => `<option ${userList.status === n ? 'selected' : ''}>${n}</option>`).join('')}</select><select id="role-filter" aria-label="按角色筛选">${['全部角色', '管理员', '编辑', '只读成员'].map((n) => `<option ${userList.role === n ? 'selected' : ''}>${n}</option>`).join('')}</select><span class="spacer"></span>${button('重置', 'reset-filters', 'subtle', 'filter')}</div><div id="user-results">${userResults()}</div></section>`
  );
}
function userResults() {
  const { all, pages, rows } = userCollection.pageItems();
  syncUserRoute();
  return `<div class="mobile-table-actions"><label><input type="checkbox" id="mobile-select-all" class="checkbox" aria-label="选择当前页全部用户" ${rows.length && rows.every((u) => userList.selected.has(u.id)) ? 'checked' : ''} ${rows.length ? '' : 'disabled'}>本页全选</label><button class="btn subtle" data-action="sort">加入时间 ${userList.sort === 'desc' ? '↓' : '↑'}</button></div>${userList.selected.size ? `<div class="bulk-bar">已选 ${userList.selected.size} 位用户 · 本页 ${rows.filter((u) => userList.selected.has(u.id)).length} 位 / 其他页 ${userList.selected.size - rows.filter((u) => userList.selected.has(u.id)).length} 位 ${button('停用所选', 'bulk-disable')}${button('取消选择', 'clear-selection', 'subtle')}</div>` : ''}${rows.length ? `<div class="table-scroll users-full-table">${table(rows)}</div><div class="mobile-user-cards">${rows.map((u) => `<article class="user-card"><div class="user-card-top"><input type="checkbox" class="checkbox row-check" value="${u.id}" aria-label="选择${esc(u.name)}" ${userList.selected.has(u.id) ? 'checked' : ''}>${person(u)}<button class="icon-button" data-detail="${u.id}" aria-label="查看${esc(u.name)}详情">${icon('book')}</button><button class="icon-button" data-edit="${u.id}" aria-label="编辑${esc(u.name)}">${icon('edit')}</button></div><div class="user-card-bottom"><span class="pill ${u.role === '管理员' ? 'role-admin' : ''}">${u.role}</span>${pill(u.status)}<span class="spacer"></span>${u.team}</div></article>`).join('')}</div>` : `<div class="empty-state">${icon('search')}<h3>没有找到符合条件的用户</h3><p>试试其他关键词，或清除筛选条件</p>${button('清除筛选', 'reset-filters', 'subtle')}</div>`}${pagination(userCollection, 'users', 'data-page', '用户', '位用户')}`;
}
function syncUserSelection() {
  const { indeterminate } = userCollection.pageItems();
  for (const checkbox of $$('#select-all,#mobile-select-all'))
    checkbox.indeterminate = indeterminate;
}
function renderUsers(focusId) {
  syncUserRoute();
  if ($('#user-results')) $('#user-results').innerHTML = userResults();
  syncUserSelection();
  if (focusId) {
    const candidates = $$(`.row-check[value="${focusId}"]`);
    (candidates.find((x) => x.getClientRects().length) || candidates[0])?.focus();
  }
}
function rolesView() {
  let p =
    permissionDraft || (permissionDraft = structuredClone(state.permissions[state.selectedRole]));
  return (
    intro(
      '角色与权限',
      '清晰的职责边界，让每个人专注于自己的工作。',
      button('重置演示配置', 'reset-permissions', '', 'history'),
    ) +
    `<div class="notice">${icon('shield')}<span>这里仅演示权限配置界面，不提供安全控制。接入后须由 Django 在服务端校验真实权限。</span></div><div class="role-layout"><div class="role-cards">${Object.keys(
      initialPermissions,
    )
      .map(
        (r) =>
          `<button class="role-card ${state.selectedRole === r ? 'active' : ''}" data-role="${r}" aria-pressed="${state.selectedRole === r}"><span class="role-icon">${icon(r === '管理员' ? 'shield' : r === '编辑' ? 'edit' : 'book')}</span><strong>${r}</strong><p>${roleDescription[r]}</p><small>${state.users.filter((u) => u.role === r).length} 位演示成员</small></button>`,
      )
      .join(
        '',
      )}</div><section class="panel"><div class="panel-head" style="padding-bottom:20px"><div><h2>${state.selectedRole}的权限</h2><p>按资源配置操作范围</p></div><span class="pill role-admin">演示配置</span></div><div class="table-scroll"><table class="permission-table"><thead><tr><th>资源</th>${['查看', '新增', '修改', '删除'].map((t) => `<th>${t}</th>`).join('')}</tr></thead><tbody>${[
      ['用户与成员', 'auth.User'],
      ['内容与记录', 'content.Record'],
      ['系统配置', 'system.Settings'],
    ]
      .map(
        ([r, c], i) =>
          `<tr><td><strong>${r}</strong><small>${c}</small></td>${[0, 1, 2, 3].map((j) => `<td><input class="checkbox permission-check" type="checkbox" data-index="${i * 4 + j}" ${p[i * 4 + j] ? 'checked' : ''} aria-label="${r}：${['查看', '新增', '修改', '删除'][j]}"></td>`).join('')}</tr>`,
      )
      .join(
        '',
      )}</tbody></table></div><div class="permission-footer"><span id="permission-status">${unsavedRole ? '有未保存的修改' : '更改仅保存在当前浏览器'}</span>${button('保存配置', 'save-permissions', 'primary', 'check')}</div></section></div>`
  );
}
function componentsView() {
  return (
    intro(
      '组件预览',
      '覆盖常见后台场景，让每一步都有清楚的状态和反馈。',
      button('查看设计说明', 'docs', '', 'book'),
    ) + renderComponentLab()
  );
}
function auditView() {
  return (
    intro(
      '操作日志',
      '变化有迹可循，问题有据可查。',
      button('查看用户', 'notification-users', '', 'users'),
    ) + renderAudit()
  );
}
function nativeSamplesView() {
  return renderNativeSamples();
}
function settingsView() {
  return (
    intro('系统设置', '在熟悉的工作方式里，留一点自己的偏好。', '') +
    `<div class="settings-layout"><form class="panel" id="settings-form"><div class="panel-head"><h2>工作空间</h2><span class="pill">仅本地保存</span></div><div class="settings-body"><div class="field"><label for="workspace-name">工作空间名称</label><input id="workspace-name" name="workspace" required maxlength="24" value="${esc(state.settings.workspace)}"><small>展示在侧边栏；不修改任何真实组织信息</small></div><button class="toggle" type="button" role="switch" id="motion-toggle" aria-checked="${state.settings.animations}" data-action="motion-toggle"><span>界面动效<small>支持系统“减少动态效果”偏好</small></span><span class="toggle-track"></span></button></div><div class="settings-footer"><button class="btn primary" type="submit">${icon('check')}保存偏好</button></div></form><section class="panel"><div class="panel-head"><h2>主题与恢复</h2></div><div class="settings-body"><p class="muted" style="font-size:12px;margin-bottom:18px">NOVA 是可关闭的外观增强。站内提供真实原生模板的只读对照；实际 Django 项目通过主题开关恢复原生样式。</p><div class="field"><label for="appearance-mode">外观偏好</label><select id="appearance-mode">${[
      ['light', '企业浅色'],
      ['dark', '深色'],
      ['auto', '跟随系统'],
    ]
      .map(
        ([value, label]) =>
          `<option value="${value}" ${appearanceMode === value ? 'selected' : ''}>${label}</option>`,
      )
      .join(
        '',
      )}</select><small>立即应用；首次访问默认浅色，保留你已保存的选择</small></div><div style="display:flex;gap:10px;flex-wrap:wrap">${button('切换深浅主题', 'theme', '', 'sun')}${button('查看原生模板对照', 'native', '', 'history')}${button('集成与恢复说明', 'docs', 'subtle', 'book')}</div></div></section><section class="panel"><div class="panel-head"><h2>重置演示数据</h2></div><div class="settings-body"><p class="muted" style="font-size:12px;margin-bottom:18px">清除当前浏览器里的用户、角色及偏好修改，恢复最初的演示内容。</p>${button('恢复演示初始状态', 'reset-demo', 'danger', 'history')}</div></section></div>`
  );
}
function hasUnsavedChanges() {
  return (
    $('#user-form')?.dataset.dirty === 'true' || unsavedRole || mainFormDirty || catalogDirty()
  );
}
function cleanCurrentDrafts() {
  unsavedRole = false;
  permissionDraft = null;
  mainFormDirty = false;
  discardCatalogDraft();
  const f = $('#user-form');
  if (f) f.dataset.dirty = 'false';
}
function applyRoute(route) {
  state.route = route;
  state.view = routeView(route);
  state.mobile = false;
  closeOverlay(true);
  layout();
  window.scrollTo({ top: 0 });
  $('#view h1')?.focus({ preventScroll: true });
  document.title = (nav.find((n) => n[0] === state.view)?.[2] || '控制台') + ' · NOVA Admin';
}
function navigate(route) {
  if (!validRoute(route)) return;
  if (state.route === route) {
    state.mobile = false;
    document.querySelector('.shell')?.classList.remove('mobile-open');
    if (state.view === 'catalog') {
      renderView();
      $('#view h1')?.focus({ preventScroll: true });
    }
    return;
  }
  if (hasUnsavedChanges()) {
    pendingNavigation = route;
    if ($('#user-form')?.dataset.dirty === 'true') {
      showDiscard();
      return;
    }
    confirmDialog(
      '离开前，有未保存的更改',
      '继续编辑可保留输入。放弃后将前往你选择的页面。',
      'confirm-leave',
      '放弃并离开',
    );
    return;
  }
  location.hash = route;
}
window.addEventListener('hashchange', () => {
  const route = location.hash.slice(1);
  if (!validRoute(route)) return;
  if (hasUnsavedChanges() && route !== state.route) {
    history.replaceState(null, '', '#' + state.route);
    navigate(route);
    return;
  }
  applyRoute(route);
});
window.addEventListener('beforeunload', (e) => {
  if (hasUnsavedChanges()) {
    e.preventDefault();
    e.returnValue = '';
  }
});
// Intercept only app routes; external links and native form anchors stay native.
document.addEventListener(
  'click',
  (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const route = a.getAttribute('href').slice(1);
    if (validRoute(route)) {
      e.preventDefault();
      navigate(route);
    }
  },
  true,
);
function toast(text, type = 'success') {
  clearTimeout(toastTimer);
  $('#toast-root').innerHTML =
    `<div class="toast toast-${type}" role="status">${icon(type === 'error' ? 'close' : type === 'info' ? 'circle' : 'check')}${esc(text)}</div>`;
  toastTimer = setTimeout(() => ($('#toast-root').innerHTML = ''), 3500);
}
function focusOverlay() {
  const root = $('#overlay-root');
  const focus =
    $(
      '[autofocus],input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled])',
      root,
    ) || $('button:not([disabled]),a[href]', root);
  focus?.focus();
}
function openOverlay(html, modal = false) {
  if ($('#user-form')?.dataset.dirty === 'true') {
    showDiscard();
    return false;
  }
  const root = $('#overlay-root');
  if (root.firstElementChild)
    overlayStack.push({ node: root.firstElementChild, lastFocus, opener: document.activeElement });
  lastFocus = document.activeElement;
  root.innerHTML = `<div class="overlay ${modal ? 'modal-overlay' : ''}" data-overlay="true">${html}</div>`;
  document.body.style.overflow = 'hidden';
  $('#app').inert = true;
  setTimeout(focusOverlay, 0);
  return true;
}
function showDiscard() {
  if (!$('#discard-confirm'))
    $('.drawer')?.insertAdjacentHTML(
      'beforeend',
      `<div id="discard-confirm" class="discard-confirm" role="alert">有未保存的修改，要放弃吗？<div>${button('继续编辑', 'keep-editing')}${button('放弃修改', 'discard-editing', 'danger')}</div></div>`,
    );
  $('#discard-confirm [data-action="keep-editing"]')?.focus();
}
function closeOverlay(force = false) {
  const root = $('#overlay-root');
  if (!root.children.length) return true;
  if (!force && $('#user-form')?.dataset.dirty === 'true') {
    showDiscard();
    return false;
  }
  if (!force) pendingNavigation = null;
  if (!force && overlayStack.length) {
    const parent = overlayStack.pop();
    root.replaceChildren(parent.node);
    restoreMedia(parent.node);
    lastFocus = parent.lastFocus;
    parent.opener?.focus();
    return true;
  }
  overlayStack = [];
  root.innerHTML = '';
  document.body.style.overflow = '';
  $('#app').inert = false;
  if (lastFocus?.isConnected) lastFocus.focus();
  else $('#view h1')?.focus({ preventScroll: true });
  return true;
}
function confirmDialog(title, content, action, label = '确认') {
  openOverlay(
    `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-icon">${icon('circle')}</div><h2 id="modal-title">${title}</h2><p>${content}</p><div class="modal-actions">${button('取消', 'close')}${button(label, action, 'primary')}</div></section>`,
    true,
  );
}
function openUser(id) {
  let u = state.users.find((u) => u.id === id) || {
    name: '',
    email: '',
    role: '编辑',
    status: '正常',
    team: '产品设计',
    color: 'violet',
  };
  openOverlay(
    `<section class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title"><div class="drawer-header"><div><h2 id="drawer-title">${id ? '编辑用户' : '添加用户'}</h2><p>本地演示资料，不会创建真实账户</p></div><button class="icon-button" data-action="close" aria-label="关闭表单">${icon('close')}</button></div><form id="user-form" data-id="${id || ''}" style="display:contents" novalidate><div class="drawer-content"><div class="form-avatar">${thumbnail(imageSpec('avatar', u.id, u.name || '新成员'))}<div><p>${id ? esc(u.name) : '新的协作，从这里开始'}</p><small>完善基本资料，分配合适的角色</small></div></div><div class="field"><label for="member-name">姓名 <span style="color:var(--danger)">*</span></label><input name="name" id="member-name" aria-describedby="name-error" value="${esc(u.name)}" placeholder="请输入姓名" maxlength="24" autocomplete="off"><small class="error" id="name-error"></small></div><div class="field"><label for="member-email">邮箱 <span style="color:var(--danger)">*</span></label><input name="email" id="member-email" aria-describedby="email-error" value="${esc(u.email)}" type="email" placeholder="name@example.com" autocomplete="off"><small class="error" id="email-error"></small></div><div class="field-row"><div class="field"><label for="member-role">角色</label><select name="role" id="member-role">${Object.keys(
      initialPermissions,
    )
      .map((r) => `<option ${u.role === r ? 'selected' : ''}>${r}</option>`)
      .join(
        '',
      )}</select></div><div class="field"><label for="member-status">状态</label><select name="status" id="member-status">${['正常', '待激活', '已停用'].map((r) => `<option ${u.status === r ? 'selected' : ''}>${r}</option>`).join('')}</select></div></div><div class="field"><label for="member-team">所属团队</label><select name="team" id="member-team">${['产品设计', '研发中心', '内容运营', '客户服务'].map((r) => `<option ${u.team === r ? 'selected' : ''}>${r}</option>`).join('')}</select></div><div class="notice" style="font-size:11px">${icon('shield')}角色与状态仅在预览中生效，不授予任何真实访问权限。</div></div><div class="drawer-footer">${button('取消', 'close')}<button type="submit" class="btn primary">${icon('check')}${id ? '保存修改' : '创建演示用户'}</button></div></form></section>`,
  );
}
function docs() {
  openOverlay(
    `<section class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title"><div class="drawer-header"><div><h2 id="drawer-title">增强外观，保留原生</h2></div><button class="icon-button" data-action="close" aria-label="关闭说明">${icon('close')}</button></div><div class="drawer-content docs-content"><div class="notice">${icon('circle')}当前网站是静态交互原型，所有数据为模拟数据。</div><h3>01 / 设计预览</h3><p>这里展示统一的管理界面方向：仪表盘、列表、筛选、表单抽屉、角色矩阵与深浅主题。数据只保存在当前浏览器，不连接 Django。</p><h3>02 / Django 原生主题</h3><p>真实主题应用以模板继承、样式与权限过滤的导航增强 Django 原生页面，不替换 ModelAdmin、认证、权限、表单、搜索、列表过滤和批量动作。</p><p>已在Linux x86-64标准CPython中完成以下7组核心与可选验证码的源码及wheel验证，包括关联字段、Inline、校验错误、权限、批量动作、分页和原生恢复：</p><ul><li>Python 3.11.17：Django 5.2.17</li><li>Python 3.12.15：Django 5.2.17 / 6.0.8 / 6.1.1</li><li>Python 3.13.16：Django 6.1.1</li><li>Python 3.14.8：Django 5.2.17 / 6.1.1</li></ul><p>这7组不等于所有交叉组合；其它系统、补丁和第三方插件仍需项目级验证。Python 3.10已EOL，仅保留历史安装门槛。静态原型中的数据与图表仍为演示。</p><h3>03 / Node 开发工具链</h3><ul><li>Node 22.23.3 · npm 10.9.9：维护 LTS</li><li>Node 24.21.0 · npm 11.19.0：主推荐 LTS</li><li>Node 26.10.0 · npm 11.19.1：Current 已测，非长期承诺</li></ul><p>三组均在Linux x64使用原锁文件独立安装，格式、语法、540项前端交互与97项主题JS检查通过。此范围针对开发工具；静态预览和Django主题运行不需要Node服务。Node 18/20已EOL，不列为维护推荐。其它补丁和系统尚未验证。</p><h3>04 / 随时恢复</h3><ul><li>在主题骨架中，通过受 CSRF 保护的偏好表单，按当前会话关闭增强样式</li><li>需要完全恢复时，移除主题应用配置，Django 自带模板继续生效</li><li>“原生恢复对照”展示 Django 6.1.1 原生模板的只读快照；真实项目中通过主题开关恢复</li></ul><h3>05 / 可复用的边界</h3><p>视觉使用 CSS 变量组织颜色和间距，预览数据与界面逻辑分文件维护。真实接入时仍需服务端权限验证、CSRF 防护、审计及项目级测试。</p><h3>06 / CI/CD 接入</h3><p>已准备 GitHub Actions 配置：PR 快速检查、手动完整兼容矩阵、wheel 与静态产物校验。候选交付默认关闭，需维护者配置审批后手动触发。</p><p>目前仅完成本地流程验证，尚未接入 GitHub 仓库或生产发布。接入步骤见源码中的 CI_CD.md。</p><p><a href="./extensions.html" target="_blank" rel="noopener">品牌配置、收藏导航与扩展接入指南 ↗</a></p><h3>官方参考</h3><p><a href="https://docs.djangoproject.com/en/6.1/ref/contrib/admin/#overriding-admin-templates" target="_blank" rel="noopener">Django · 覆盖与扩展管理模板 ↗</a></p><p style="margin-top:25px">这份预览用于确认视觉和交互方向。集成范围与已验证版本以随源码提供的 README 为准。</p></div><div class="drawer-footer">${button('明白了', 'close', 'primary')}</div></section>`,
  );
}
function commandSearch() {
  openOverlay(
    `<section class="modal command-modal" role="dialog" aria-modal="true" aria-label="搜索页面或用户（${searchShortcut().spoken}）" aria-keyshortcuts="${searchShortcut().keys}"><div class="command-input">${icon('search')}<input id="command-search" placeholder="搜索页面、姓名或邮箱…" aria-label="搜索页面或用户（${searchShortcut().spoken}）" aria-keyshortcuts="${searchShortcut().keys}"><button class="icon-button" data-action="close" aria-label="关闭搜索">${icon('close')}</button></div><div class="command-results" id="command-results">${commandResults('')}</div><div class="command-hint">选择结果前往 · Esc 关闭</div></section>`,
    true,
  );
}
function commandResults(q) {
  let result = nav
    .filter((n) => n[2].includes(q))
    .map(
      ([id, i, n]) =>
        `<button class="command-item" data-nav="${id}">${icon(i)}${n}<small>页面</small></button>`,
    );
  if (q)
    result.push(
      ...state.users
        .filter((u) => (u.name + u.email).toLowerCase().includes(q.toLowerCase()))
        .slice(0, 5)
        .map(
          (u) =>
            `<button class="command-item" data-edit="${u.id}">${icon('users')}${esc(u.name)}<small>${esc(u.email)}</small></button>`,
        ),
    );
  return result.join('') || '<div class="empty-state" style="padding:25px">没有匹配结果</div>';
}
function exportCsv(report = false) {
  let rows = report
    ? [
        ['NOVA 概览报告（模拟数据）'],
        ['周期', `最近 ${state.period} 天`],
        ['总用户数', '新增用户', '活跃率', '操作记录'],
        metricSets[state.period],
      ]
    : [
        ['姓名', '邮箱', '角色', '状态', '团队', '加入时间'],
        ...filteredUsers().map((u) => [u.name, u.email, u.role, u.status, u.team, u.joined]),
      ];
  let csv =
    '\uFEFF' +
    rows
      .map((r) =>
        r
          .map(
            (v) =>
              '"' +
              String(v)
                .replace(/^[=+@-]/, "'$&")
                .replaceAll('"', '""') +
              '"',
          )
          .join(','),
      )
      .join('\r\n');
  let a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  a.download = report ? 'nova-demo-report.csv' : 'nova-demo-users.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  toast(report ? '模拟概览报告已导出' : '当前筛选结果已导出');
}
const actions = {
  'discard-permissions': () => {
    unsavedRole = false;
    permissionDraft = null;
    state.selectedRole = pendingRole;
    pendingRole = null;
    closeOverlay(true);
    renderView();
  },
  'confirm-leave': () => {
    const target = pendingNavigation;
    pendingNavigation = null;
    cleanCurrentDrafts();
    closeOverlay(true);
    if (target) location.hash = target;
  },
  'keep-editing': () => {
    pendingNavigation = null;
    $('#discard-confirm')?.remove();
    $('#user-form input')?.focus();
  },
  'discard-editing': () => {
    const target = pendingNavigation;
    pendingNavigation = null;
    closeOverlay(true);
    if (target) {
      cleanCurrentDrafts();
      location.hash = target;
    }
  },
  theme: () =>
    applyAppearance(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', true),
  mobile: () => {
    state.mobile = true;
    $('.shell')?.classList.add('mobile-open');
    document.body.style.overflow = 'hidden';
    $('.sidebar a')?.focus();
  },
  'close-nav': () => {
    state.mobile = false;
    $('.shell')?.classList.remove('mobile-open');
    document.body.style.overflow = '';
    $('.mobile-menu')?.focus();
  },
  native: () => {
    selectNativeComparison(state.view, state.route);
    navigate('native-samples');
  },
  docs,
  search: commandSearch,
  close: closeOverlay,
  workspace: () => {
    navigate('settings');
    toast('工作空间名称可在此修改');
  },
  add: () => openUser(),
  export: () => exportCsv(),
  report: () => exportCsv(true),
  'reset-filters': () => {
    userCollection.resetFilters();
    syncUserRoute();
    renderView();
  },
  sort: () => {
    userList.sort = userList.sort === 'desc' ? 'asc' : 'desc';
    renderUsers();
    toast(userList.sort === 'desc' ? '加入时间：从新到旧' : '加入时间：从旧到新');
  },
  'clear-selection': () => {
    userList.selected.clear();
    renderUsers();
  },
  'bulk-disable': () =>
    confirmDialog(
      '停用所选演示用户？',
      `将停用：${state.users
        .filter((u) => userList.selected.has(u.id))
        .map((u) => esc(u.name))
        .join('、')}。共 ${userList.selected.size} 位；只影响当前浏览器，可通过编辑恢复。`,
      'confirm-disable',
      '停用所选',
    ),
  'confirm-disable': () => {
    const next = state.users.map((u) =>
      userList.selected.has(u.id) ? { ...u, status: '已停用' } : u,
    );
    if (!save('nova-users', next)) return;
    state.users = next;
    addAuditEvent('批量停用', `${userList.selected.size} 位演示用户`);
    userList.selected.clear();
    closeOverlay();
    renderUsers();
    toast('所选演示用户已停用');
  },
  'save-permissions': () => {
    const next = { ...state.permissions, [state.selectedRole]: structuredClone(permissionDraft) };
    if (!save('nova-permissions', next)) return;
    state.permissions = next;
    addAuditEvent('保存权限配置', state.selectedRole);
    unsavedRole = false;
    $('#permission-status').textContent = '已保存在当前浏览器';
    toast('演示权限配置已保存');
  },
  'reset-permissions': () =>
    confirmDialog(
      '恢复初始权限示例？',
      '将重置三个演示角色的本地权限矩阵。不会影响真实系统。',
      'confirm-reset-permissions',
      '恢复初始配置',
    ),
  'confirm-reset-permissions': () => {
    const next = structuredClone(initialPermissions);
    if (!save('nova-permissions', next)) return;
    state.permissions = next;
    permissionDraft = null;
    unsavedRole = false;
    closeOverlay();
    renderView();
    toast('已恢复初始权限示例');
  },
  'sample-success': () => toast('操作成功，反馈保持清晰'),
  'sample-toast': () => toast('这是一个轻量提示示例'),
  'sample-modal': () =>
    confirmDialog(
      '保存这次更改？',
      '这是确认弹窗的交互示例，不会修改真实记录。',
      'sample-confirm',
      '确认保存',
    ),
  'sample-confirm': () => {
    closeOverlay();
    toast('确认流程已完成');
  },
  notifications: () =>
    openOverlay(
      `<section class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title"><div class="drawer-header"><div><h2 id="drawer-title">工作动态</h2><p>示例通知，不连接实时服务</p></div><button class="icon-button" data-action="close" aria-label="关闭通知">${icon('close')}</button></div><div class="drawer-content">${[
        ['mint', 'check', '数据备份完成', '演示环境的例行备份已完成', '10 分钟前'],
        ['violet', 'users', '3 位成员加入工作空间', '查看新成员的角色与访问范围', '36 分钟前'],
        ['blue', 'shield', '角色配置已更新', '编辑角色获得内容修改权限', '2 小时前'],
      ]
        .map(
          ([c, i, t, d, time]) =>
            `<div class="activity-item"><span class="avatar ${c}">${icon(i)}</span><div><p>${t}</p><small>${d}</small><p class="muted" style="font-size:10px;margin-top:9px">${time} · 模拟</p></div></div>`,
        )
        .join(
          '',
        )}</div><div class="drawer-footer">${button('查看用户', 'notification-users', 'primary')}</div></section>`,
    ),
  'notification-users': () => {
    closeOverlay();
    navigate('users');
  },
  'reset-demo': () =>
    confirmDialog(
      '恢复演示初始状态？',
      '将清除当前浏览器中的演示修改。下载过的文件不会受到影响。',
      'confirm-reset-demo',
      '恢复初始状态',
    ),
  'confirm-reset-demo': () => {
    try {
      for (const key of [
        'nova-users',
        'nova-permissions',
        'nova-settings',
        'nova-catalog',
        'nova-audit',
        'nova-news',
      ])
        localStorage.removeItem(key);
    } catch {
      storageFailed = true;
      showStorageWarning();
      toast('无法清除本地存储，尚未重置', 'error');
      return;
    }
    resetCatalog();
    resetNews();
    mainFormDirty = false;
    resetAudit();
    unsavedRole = false;
    permissionDraft = null;
    state.users = structuredClone(initialUsers);
    state.permissions = structuredClone(initialPermissions);
    state.settings = { workspace: 'NOVA 工作空间', animations: true, compact: false };
    ['nova-users', 'nova-permissions', 'nova-settings'].forEach((k) => {
      try {
        localStorage.removeItem(k);
      } catch {}
    });
    userCollection.resetFilters({ resetPageSize: true });
    state.route = state.view;
    history.replaceState(null, '', '#' + state.route);
    closeOverlay();
    layout();
    toast('演示数据已重置');
  },
};
document.addEventListener('click', (e) => {
  const group = e.target.closest('[data-nav-group]');
  if (group) {
    const key = group.dataset.navGroup,
      open = group.getAttribute('aria-expanded') !== 'true';
    group.setAttribute('aria-expanded', open);
    document.getElementById('nav-group-' + key).hidden = !open;
    navPersistenceFailed = !saveNavigationPreference(navOpened, key, open);
    return;
  }
  let a = e.target.closest('[data-action]');
  if (a) {
    e.preventDefault();
    let key = a.dataset.action;
    if (key === 'sample-toggle' || key === 'motion-toggle') {
      a.setAttribute('aria-checked', a.getAttribute('aria-checked') !== 'true');
      if (key === 'motion-toggle') mainFormDirty = true;
      return;
    }
    actions[key]?.();
    return;
  }
  let edit = e.target.closest('[data-edit]');
  if (edit) {
    openUser(Number(edit.dataset.edit));
    return;
  }
  let page = e.target.closest('[data-page]');
  if (page && !page.disabled) {
    userCollection.setPage(page.dataset.page);
    syncUserRoute(true);
    renderUsers();
    $(`.pagination [data-page="${userList.page}"]`)?.focus();
    return;
  }
  let role = e.target.closest('[data-role]');
  if (role) {
    if (unsavedRole) {
      pendingRole = role.dataset.role;
      confirmDialog(
        '放弃未保存的权限修改？',
        '当前角色的修改尚未保存。放弃后再切换角色。',
        'discard-permissions',
        '放弃并切换',
      );
      return;
    }
    state.selectedRole = role.dataset.role;
    permissionDraft = null;
    renderView();
    return;
  }
  let chart = e.target.closest('[data-chart]');
  if (chart) {
    state.chart = chart.dataset.chart;
    renderView();
    return;
  }
  let n = e.target.closest('[data-nav]');
  if (n) {
    closeOverlay();
    navigate(n.dataset.nav);
    return;
  }
  if (e.target.dataset.overlay) closeOverlay();
});
document.addEventListener('input', (e) => {
  let form = e.target.closest('#user-form');
  if (form) form.dataset.dirty = 'true';
  if (e.target.closest('#settings-form,#lab-content-form,#wizard-form')) mainFormDirty = true;
  if (e.target.id === 'user-search') {
    userCollection.setFilter('search', e.target.value);
    renderUsers();
  }
  if (e.target.id === 'command-search')
    $('#command-results').innerHTML = commandResults(e.target.value);
});
document.addEventListener('change', (e) => {
  if (e.target.dataset.pageSize === 'users') {
    if (userCollection.setPageSize(e.target.value)) {
      syncUserRoute(true);
      renderUsers();
      $('#users-page-size')?.focus();
    }
    return;
  }
  if (e.target.id === 'appearance-mode') applyAppearance(e.target.value, true);
  let form = e.target.closest('#user-form');
  if (form) form.dataset.dirty = 'true';
  if (e.target.closest('#settings-form,#lab-content-form,#wizard-form')) mainFormDirty = true;
  if (e.target.id === 'period') {
    state.period = Number(e.target.value);
    renderView();
  }
  if (e.target.id === 'status-filter' || e.target.id === 'role-filter') {
    userCollection.setFilter(e.target.id === 'status-filter' ? 'status' : 'role', e.target.value);
    renderUsers();
  }
  if (e.target.classList.contains('row-check')) {
    let id = Number(e.target.value);
    userCollection.select(id, e.target.checked);
    renderUsers(id);
  }
  if (e.target.id === 'select-all' || e.target.id === 'mobile-select-all') {
    const focusId = e.target.id;
    userCollection.selectPage(e.target.checked);
    renderUsers();
    document.getElementById(focusId)?.focus();
  }
  if (e.target.classList.contains('permission-check')) {
    permissionDraft[Number(e.target.dataset.index)] = e.target.checked;
    unsavedRole =
      JSON.stringify(permissionDraft) !== JSON.stringify(state.permissions[state.selectedRole]);
    $('#permission-status').textContent = unsavedRole ? '有未保存的修改' : '更改仅保存在当前浏览器';
  }
});
document.addEventListener('submit', (e) => {
  if (
    submitPageJump(e, userCollection, 'users', (focus) => {
      syncUserRoute(true);
      renderUsers();
      $(focus)?.focus();
    })
  )
    return;
  e.preventDefault();
  if (e.target.id === 'user-form') {
    let f = new FormData(e.target),
      id = Number(e.target.dataset.id),
      name = f.get('name').trim(),
      email = f.get('email').trim(),
      valid = true;
    $('#name-error').textContent = '';
    $('#email-error').textContent = '';
    if (name.length < 2) {
      $('#name-error').textContent = '请输入至少 2 个字符的姓名';
      $('#member-name').setAttribute('aria-invalid', 'true');
      valid = false;
    } else $('#member-name').removeAttribute('aria-invalid');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      $('#email-error').textContent = '请输入有效的邮箱地址';
      $('#member-email').setAttribute('aria-invalid', 'true');
      valid = false;
    } else if (
      state.users.some((u) => u.id !== id && u.email.toLowerCase() === email.toLowerCase())
    ) {
      $('#email-error').textContent = '该邮箱已存在于演示用户中';
      $('#member-email').setAttribute('aria-invalid', 'true');
      valid = false;
    } else $('#member-email').removeAttribute('aria-invalid');
    if (!valid) {
      $('.error:not(:empty)')?.previousElementSibling?.focus();
      return;
    }
    let data = { name, email, role: f.get('role'), status: f.get('status'), team: f.get('team') };
    const next = structuredClone(state.users);
    if (id)
      Object.assign(
        next.find((u) => u.id === id),
        data,
      );
    else
      next.unshift({
        ...data,
        id: Math.max(...next.map((u) => u.id), 0) + 1,
        color: 'violet',
        joined: new Date().toISOString().slice(0, 10),
      });
    if (!save('nova-users', next)) return;
    state.users = next;
    addAuditEvent(id ? '修改用户' : '新增用户', name);
    closeOverlay(true);
    layout();
    toast(id ? '用户资料已更新' : '演示用户已创建');
  }
  if (e.target.id === 'sample-form') {
    let valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test($('#sample-email').value);
    $('#sample-error').textContent = valid ? '格式正确，不会发送邮件' : '请输入有效的邮箱地址';
    $('#sample-error').className = valid ? '' : 'error';
    $('#sample-email').setAttribute('aria-invalid', !valid);
    if (valid) toast('邮箱格式验证通过');
  }
  if (e.target.id === 'settings-form') {
    let name = $('#workspace-name').value.trim();
    if (!name) {
      $('#workspace-name').focus();
      return;
    }
    const next = {
      ...state.settings,
      workspace: name,
      animations: $('#motion-toggle').getAttribute('aria-checked') === 'true',
    };
    if (!save('nova-settings', next)) return;
    state.settings = next;
    mainFormDirty = false;
    layout();
    toast('工作空间偏好已保存');
  }
});
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    commandSearch();
  }
  if (e.key === 'Escape') {
    closeOverlay();
    if (state.mobile) actions['close-nav']();
  }
  if (e.key === 'Tab' && state.mobile && !$('#overlay-root').children.length) {
    const items = $$('a[href],button:not([disabled])', $('.sidebar')).filter(
      (x) => x.getClientRects().length,
    );
    const first = items[0],
      last = items.at(-1);
    if (
      first &&
      ((e.shiftKey && document.activeElement === first) ||
        (!e.shiftKey && document.activeElement === last))
    ) {
      e.preventDefault();
      (e.shiftKey ? last : first).focus();
    }
  }
  if (e.key === 'Tab' && $('#overlay-root').children.length) {
    let nodes = $$(
        'button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]',
        $('#overlay-root'),
      ).filter((x) => x.getClientRects().length),
      first = nodes[0],
      last = nodes.at(-1);
    if (!first) return;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
});
// Route changes remain owned by the application. Consumers receive capabilities,
// never the mutable state object; catalog list refreshes cannot replace an editor URL.
function listRouting(view, preserveEditor = false) {
  return Object.freeze({
    current: () => state.route,
    navigate,
    replaceListRoute(route, { push = false } = {}) {
      if (state.view !== view || (preserveEditor && state.route.startsWith(view + '/'))) return;
      state.route = route;
      const method = push && location.hash !== '#' + route ? 'pushState' : 'replaceState';
      history[method](null, '', '#' + route);
    },
  });
}
initScenarios({
  ui: Object.freeze({ icon, esc, button, toast, openOverlay, renderView, person, confirmDialog }),
  getView: () => state.view,
  getUsers: (limit) => structuredClone(state.users.slice(0, limit)),
  getUser: (id) =>
    structuredClone(id === undefined ? state.users[0] : state.users.find((user) => user.id === id)),
  navigate,
  markClean: () => {
    mainFormDirty = false;
  },
});
initCatalog({
  ui: Object.freeze({ icon, esc, intro, toast, openOverlay, closeOverlay, renderView }),
  routing: listRouting('catalog', true),
  saveRecords: (records) => save('nova-catalog', records),
  recordAudit: addAuditEvent,
});
initNativeSamples({ icon, intro });
initMedia({ icon, openOverlay, closeOverlay });
initNews({
  ui: Object.freeze({ icon, esc, intro, toast, renderView, openOverlay, closeOverlay }),
  routing: Object.freeze({ replaceListRoute: listRouting('news').replaceListRoute }),
  saveRecords: (records) => save('nova-news', records),
  recordAudit: addAuditEvent,
});
layout();

function loginPreviewView() {
  return (
    intro(
      '登录页预览',
      '图形验证码与完整登录状态，可独立打开体验。',
      '<a class="btn primary" href="./login.html" target="_blank" rel="noopener">独立打开登录页 ↗</a>',
    ) +
    '<div class="notice">此页仅为本地交互演示，不接收真实账户。Django 可选接入在服务端校验，详见源码说明。</div><iframe class="login-preview-frame" title="登录界面交互演示" src="./login.html" sandbox="allow-scripts allow-same-origin allow-forms"></iframe>'
  );
}
