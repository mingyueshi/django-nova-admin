import { icon } from './icons.js';
import { chartProviders, chartExampleCsv } from './chart-lab-data.js';
import { loadChartLibrary, chartTheme } from './chart-lab.js';
import {
  analysisScenarios,
  analysisSnapshot,
  analysisExport,
  analysisValue,
} from './analysis-lab-data.js';
import { analysisOptions } from './analysis-lab-options.js';
let api,
  charts = {},
  observer = null,
  generation = 0,
  scheduler = null,
  pending = null,
  snapshot = null,
  updating = false,
  deadline = 0;
const state = {
  scenario: 'sales',
  metric: 'revenue',
  days: 30,
  path: [],
  selected: null,
  range: null,
  sample: 'normal',
  revision: 0,
  page: 1,
  interval: 5,
  auto: false,
  busy: false,
  failNext: false,
  error: '',
  lastSuccess: null,
};
const esc = (value) => api.esc(value);
const number = (value) =>
  new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value);
const current = () => analysisScenarios.find((s) => s.id === state.scenario);
const active = () => api.getView() === 'analysis';
function time(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(value);
}
function getSnapshot() {
  snapshot = analysisSnapshot(state);
  state.path = snapshot.path;
  state.selected = snapshot.selected;
  return snapshot;
}
function kpis(s) {
  const t = s.totals;
  const entries =
    s.scenario.id === 'sales'
      ? [
          ['支付金额', t.revenue / 100, '元'],
          ['支付订单', t.orders, '笔'],
          ['客单价', t.orders ? t.revenue / 100 / t.orders : null, '元'],
          ['退款金额', t.refunds / 100, '元'],
        ]
      : s.scenario.id === 'growth'
        ? [
            ['访问会话', t.visits, '次'],
            ['注册会话', t.signups, '次'],
            ['付费会话', t.paid, '次'],
            ['访问付费率', t.visits ? (t.paid / t.visits) * 100 : null, '%'],
          ]
        : [
            ['请求量', t.requests, '次'],
            ['错误请求', t.errors, '次'],
            ['错误率', t.requests ? (t.errors / t.requests) * 100 : null, '%'],
            ['平均响应', t.requests ? t.latency : null, 'ms'],
          ];
  return entries
    .map(
      ([label, value, unit]) =>
        `<div class="panel al-kpi"><span>${label}</span><strong>${value === null ? '—' : number(value)}<small>${unit}</small></strong><p>当前下钻与联动范围</p></div>`,
    )
    .join('');
}
function scopeMarkup(s) {
  return `<nav aria-label="分析下钻路径" class="al-breadcrumb"><button type="button" data-al-depth="0"${!s.path.length ? ' aria-current="location"' : ''}>全部${s.scenario.id === 'sales' ? '区域' : s.scenario.id === 'growth' ? '渠道' : '服务'}</button>${s.path.map((p, i) => `<span aria-hidden="true">/</span><button type="button" data-al-depth="${i + 1}"${i === s.path.length - 1 ? ' aria-current="location"' : ''}>${esc(p.value)}</button>`).join('')}</nav><div class="al-chips">${s.selected ? `<button type="button" data-al-clear-selection aria-label="清除${esc(s.selected)}联动">${esc(s.dimension.label)}：${esc(s.selected)} ×</button>` : '<span>全部分组</span>'}${s.range ? `<button type="button" data-al-clear-range aria-label="清除自选时间">${esc(s.range.join(' 至 '))} ×</button>` : `<span>${esc(s.periods[0])} 至 ${esc(s.periods.at(-1))}</span>`}</div>`;
}
function groupsMarkup(s) {
  return `<div class="al-panel-head"><div><h2>${s.dimension ? esc(s.dimension.label) + '明细与下钻' : '已到最深明细层'}</h2><p>点击联动查看单组；下钻后展开下一层。</p></div><button type="button" class="btn subtle" data-al-up${!s.path.length ? ' disabled' : ''}>返回上层</button></div>${s.dimension ? `<div class="table-scroll" tabindex="0" role="region" aria-label="分组联动和下钻"><table><thead><tr><th>${esc(s.dimension.label)}</th><th>${esc(s.metric.label)}（${esc(s.metric.unit)}）</th><th>操作</th></tr></thead><tbody>${s.groups.map((g) => `<tr${s.selected === g.key ? ' class="al-selected"' : ''}><th scope="row">${esc(g.key)}</th><td>${number(g.value)}</td><td><div class="al-row-actions"><button type="button" data-al-select="${esc(g.key)}" aria-pressed="${s.selected === g.key}" aria-label="联动${esc(g.key)}">${s.selected === g.key ? '已联动' : '联动'}</button><button type="button" data-al-drill="${esc(g.key)}" aria-label="下钻${esc(g.key)}">下钻 →</button></div></td></tr>`).join('') || '<tr><td colspan="3">当前范围没有分组数据</td></tr>'}</tbody></table></div>` : `<p class="al-leaf">${esc(s.path.map((p) => p.value).join(' / '))}<br>已展开到${esc(s.scenario.detail)}，在下方查看与导出完整范围。</p>`}`;
}
function detailsMarkup(s) {
  const pages = Math.max(1, Math.ceil(s.details.length / 20));
  state.page = Math.min(Math.max(1, state.page), pages);
  return `<div class="al-panel-head"><div><h2>${esc(s.scenario.detail)}</h2><p>${s.details.length} 行模拟明细 · 与指标、联动范围及 CSV 同源</p></div><button type="button" class="btn" data-al-export>${icon('download')}导出当前范围</button></div><div class="table-scroll" tabindex="0" role="region" aria-label="分析数据明细，可横向滚动"><table><thead><tr>${s.columns.map((v) => `<th>${esc(v)}</th>`).join('')}</tr></thead><tbody>${
    s.details
      .slice((state.page - 1) * 20, state.page * 20)
      .map(
        (row) =>
          `<tr>${row.map((v) => `<td>${esc(typeof v === 'number' ? number(v) : v)}</td>`).join('')}</tr>`,
      )
      .join('') ||
    `<tr><td colspan="${s.columns.length}">当前范围没有数据，请清除联动或调整时间。</td></tr>`
  }</tbody></table></div><div class="al-pagination"><span>第 ${state.page} / ${pages} 页 · 每页 20 行</span><button type="button" class="btn subtle" data-al-page="-1"${state.page === 1 ? ' disabled' : ''}>上一页</button><button type="button" class="btn subtle" data-al-page="1"${state.page === pages ? ' disabled' : ''}>下一页</button></div>`;
}
const usage = `// 1. 统一查询状态，图表、指标、表格和导出共享一个快照。
import { analysisSnapshot } from './js/analysis-lab-data.js';
import { analysisOptions } from './js/analysis-lab-options.js';
const query = { scenario: 'sales', metric: 'revenue', days: 30,
  path: [], selected: null, range: null, revision: 0 };
function update() {
  const snapshot = analysisSnapshot(query); // 本地模拟数据
  const options = analysisOptions(snapshot, theme);
  trend.setOption(options.trend, {notMerge: true, silent: true});
  rank.setOption(options.rank, {notMerge: true, silent: true});
  composition.setOption(options.composition, {notMerge: true});
  // 指标用 snapshot.totals，明细用 snapshot.details。
}
// 2. 图表点击联动；下钻按钮把本层维度加入 path。
rank.on('click', ({data}) => {
  query.selected = query.selected === data.groupKey ? null : data.groupKey;
  update();
});
function drill(key, value) {
  query.path.push({key, value}); query.selected = null; update();
}
// 3. 轮询必须等待本次请求结束；保留最后成功快照。
// 实际页面还处理 visibilitychange、失败、筛选、取消与路由卸载。
let stopped = false, controller, timer;
async function refresh() {
  controller = new AbortController();
  try {
    // 宿主实现只读、带权限的 JSON 接口；本演示没有该接口。
    const response = await fetch('/your-app/analytics/', {
      signal: controller.signal, headers: {Accept: 'application/json'}
    });
    if (!response.ok) throw new Error('刷新失败');
    const next = await response.json();
    if (!stopped) applyValidatedSnapshot(next); // 先校验结构与口径
  } catch (error) {
    if (error.name !== 'AbortError') showErrorAndKeepLastSnapshot(error);
  } finally {
    if (!stopped) timer = setTimeout(refresh, 5000);
  }
}
function stop() { stopped = true; clearTimeout(timer); controller?.abort(); }
// 页面隐藏/离开：stop(); 图表卸载：chart.dispose();
// 恢复时重新创建刷新任务；不得复用已终止的 AbortController。`;
export function renderAnalysisLab() {
  const s = getSnapshot();
  return `<div class="analysis-lab">${api.intro('联动分析工作台', '从全局趋势到具体明细，沿着问题继续探索。', `<a href="#analytics" class="btn">统计分析</a><a href="#charts" class="btn">开源图表库</a><span class="pill">ECharts · 本地模拟数据</span>`)}<div class="al-scenarios" role="group" aria-label="联动分析场景">${analysisScenarios.map((item) => `<button type="button" class="panel" data-al-scenario="${item.id}" aria-pressed="${state.scenario === item.id}">${icon(item.icon)}<span><strong>${item.title}</strong><small>${item.dimensions.map((d) => d.label).join(' → ')} → 明细</small></span></button>`).join('')}</div><section class="panel al-toolbar" aria-label="联动分析筛选"><label>分析指标<select id="al-metric" aria-label="联动分析指标">${s.scenario.metrics.map((m) => `<option value="${m.id}"${m.id === state.metric ? ' selected' : ''}>${m.label}（${m.unit}）</option>`).join('')}</select></label>${state.scenario === 'ops' ? '<span class="al-window-note">最近 60 分钟<br>每次成功刷新推进 1 分钟</span>' : `<label>时间窗口<select id="al-days" aria-label="联动时间窗口">${[7, 30, 90].map((d) => `<option value="${d}"${d === state.days ? ' selected' : ''}>最近 ${d} 天</option>`).join('')}</select></label>`}<label>数据示例<select id="al-sample" aria-label="联动数据示例"><option value="normal"${state.sample === 'normal' ? ' selected' : ''}>正常数据</option><option value="zero"${state.sample === 'zero' ? ' selected' : ''}>全零数据</option><option value="empty"${state.sample === 'empty' ? ' selected' : ''}>无数据</option></select></label><button type="button" class="btn subtle" data-al-reset>${icon('history')}重置分析</button></section><section class="panel al-refresh" aria-label="模拟实时刷新"><div><strong><i id="al-live-dot"></i>模拟实时刷新</strong><p id="al-refresh-status" role="status"></p></div><div class="al-refresh-actions"><label>刷新间隔<select id="al-interval" aria-label="刷新间隔">${[3, 5, 10].map((n) => `<option value="${n}"${n === state.interval ? ' selected' : ''}>${n} 秒</option>`).join('')}</select></label><button type="button" class="btn primary" data-al-auto aria-pressed="${state.auto}">开始自动刷新</button><button type="button" class="btn" data-al-refresh>立即刷新</button><button type="button" class="btn subtle" data-al-fail aria-pressed="${state.failNext}">模拟一次失败</button></div></section><div class="al-kpis" id="al-kpis">${kpis(s)}</div><section class="panel al-scope" id="al-scope" aria-label="当前分析范围">${scopeMarkup(s)}</section><div class="al-grid"><section class="panel al-chart-panel"><div class="al-panel-head"><div><h2>联动趋势</h2><p>拖动底部滑块选择时间，或点击折线上的时间点。</p></div><span class="pill" id="al-metric-label">${esc(s.metric.label)}</span></div><div id="al-trend" class="al-chart" tabindex="0" role="img" aria-label="联动趋势图，时间区间也可通过下方控件选择"></div><div class="al-range" id="al-range"></div><p class="al-note">趋势保留完整窗口以便调整时间；指标、排行、构成和明细使用选中区间。虚线为本层合计。</p></section><section class="panel al-chart-panel"><div class="al-panel-head"><div><h2 id="al-rank-title">${esc(s.dimension?.label || '明细')}排行</h2><p>单击柱形联动；双击下钻，也可使用下方按钮。</p></div><button type="button" class="btn subtle" data-al-clear-selection>清除联动</button></div><div id="al-rank" class="al-chart" tabindex="0" role="img" aria-label="分组排行，可在分组明细表用键盘联动与下钻"></div><p id="al-selection-note" class="al-note" role="status"></p></section></div><div class="al-insights"><section class="panel al-chart-panel"><div class="al-panel-head"><div><h2 id="al-composition-title">${compositionTitle()}</h2><p>跟随当前下钻、分组与时间范围。</p></div></div><div id="al-composition" class="al-chart al-composition" tabindex="0" role="img" aria-label="当前范围的构成图，精确数值见下方"></div><div id="al-composition-values" class="al-composition-values"></div></section><section class="panel al-groups" id="al-groups">${groupsMarkup(s)}</section></div><section class="panel al-details" id="al-details">${detailsMarkup(s)}</section><p class="al-feedback" id="al-feedback" role="status">正在按需加载本地 ECharts…</p><details class="panel al-usage"><summary>数据口径与接入用法</summary><p>经营收入为独立模拟订单；支付金额为订单已发生的支付，包含后续退款订单；退款金额单列，未从支付金额扣减。用户转化为每日渠道队列，付费会话属于注册会话。服务监控为每分钟接口聚合，平均响应按请求数加权，错误率 = 错误请求 ÷ 总请求。分母为零时显示“—”。</p><p>刷新在本地异步生成下一版样本，不访问实时接口。失败保留上次成功快照并暂停自动刷新；标签隐藏时暂停，返回后继续；离开工作台会停止刷新。手动选择的时间区间固定，清除后跟随最新窗口。导出包含当前范围全部明细，不受分页影响。</p><p>下面展示事件、统一查询与宿主接口接入结构；其中宿主接口和校验函数需要在项目中实现。图表事件与动态更新使用 ECharts 原生 API。</p><pre><code>${esc(usage)}</code></pre><a href="https://echarts.apache.org/handbook/en/concepts/event/" target="_blank" rel="noopener">ECharts 事件文档 ↗</a><a href="https://echarts.apache.org/handbook/en/how-to/data/dynamic-data/" target="_blank" rel="noopener">动态数据文档 ↗</a></details></div>`;
}
function compositionTitle() {
  return state.scenario === 'sales'
    ? '渠道支付构成'
    : state.scenario === 'growth'
      ? '访问到付费漏斗'
      : '请求成功与错误';
}
function rangeMarkup(s) {
  const format = (p) => (state.scenario === 'ops' ? p.slice(11) : p);
  const options = (selected) =>
    [...new Set([...(selected && !s.periods.includes(selected) ? [selected] : []), ...s.periods])]
      .map(
        (p) =>
          `<option value="${esc(p)}"${p === selected ? ' selected' : ''}>${esc(format(p))}</option>`,
      )
      .join('');
  return `<label>开始<select id="al-start" aria-label="联动区间开始">${options(s.range?.[0] || s.periods[0])}</select></label><label>结束<select id="al-end" aria-label="联动区间结束">${options(s.range?.[1] || s.periods.at(-1))}</select></label><button type="button" class="btn subtle" data-al-clear-range>完整窗口</button>`;
}
function paint(focus) {
  if (!active() || !document.querySelector('.analysis-lab')) return;
  const previous = document.activeElement;
  const focusKey = previous?.closest('.analysis-lab')
    ? {
        id: previous.id,
        label: previous.getAttribute('aria-label'),
        data: Object.entries(previous.dataset).filter(([key]) => key.startsWith('al')),
      }
    : null;
  const s = getSnapshot();
  const replace = (id, html) => {
    document.getElementById(id).innerHTML = html;
  };
  replace('al-kpis', kpis(s));
  replace('al-scope', scopeMarkup(s));
  replace('al-groups', groupsMarkup(s));
  replace('al-details', detailsMarkup(s));
  replace('al-range', rangeMarkup(s));
  replace(
    'al-composition-values',
    s.composition
      .map(
        (c) =>
          `<span>${esc(c.name)}<strong>${number(c.value)}${state.scenario === 'sales' ? ' 元' : ' 次'}</strong></span>`,
      )
      .join(''),
  );
  document.getElementById('al-rank-title').textContent = s.dimension
    ? s.dimension.label + '排行'
    : '明细层';
  document.getElementById('al-metric-label').textContent = s.metric.label + ' / ' + s.metric.unit;
  document.getElementById('al-composition-title').textContent = compositionTitle();
  document.getElementById('al-selection-note').textContent = s.selected
    ? '已联动 ' +
      s.selected +
      ' · ' +
      s.metric.label +
      ' ' +
      number(analysisValue(s.totals, s.metric.id)) +
      ' ' +
      s.metric.unit
    : s.dimension
      ? '点击分组以联动其他图表与明细；排行保留同层分组供对比。'
      : '已到最深层，可返回上层继续比较。';
  const options = analysisOptions(
    s,
    chartTheme(),
    matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  if (!s.dimension)
    options.rank.graphic = [
      {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: '已展开到明细层\n请查看下方数据明细',
          fill: chartTheme().muted,
          lineHeight: 24,
          textAlign: 'center',
        },
      },
    ];
  if (!s.rows.length)
    options.composition.graphic = [
      {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: { text: '当前范围没有数据', fill: chartTheme().muted },
      },
    ];
  updating = true;
  try {
    for (const [key, chart] of Object.entries(charts))
      chart.setOption(options[key], { notMerge: true, silent: true });
  } finally {
    updating = false;
  }
  refreshStatus();
  if (focus) document.querySelector(focus)?.focus({ preventScroll: true });
  else if (focusKey && !previous.isConnected) {
    const target = focusKey.id
      ? document.getElementById(focusKey.id)
      : [...document.querySelectorAll('.analysis-lab button')].find(
          (el) =>
            focusKey.data.length &&
            focusKey.data.every(([key, value]) => el.dataset[key] === value) &&
            el.getAttribute('aria-label') === focusKey.label,
        );
    target?.focus({ preventScroll: true });
  }
}
function refreshStatus() {
  if (!active()) return;
  const el = document.getElementById('al-refresh-status');
  if (!el) return;
  const suffix = `第 ${state.revision} 版 · ${state.lastSuccess ? '最近成功 ' + time(state.lastSuccess) + '（北京时间）' : '初始演示快照'}`;
  el.textContent =
    state.error ||
    (state.busy
      ? '正在异步生成下一版… · '
      : document.hidden && state.auto
        ? '标签不可见，刷新已暂停 · '
        : state.auto
          ? `${Math.max(0, Math.ceil((deadline - Date.now()) / 1000))} 秒后刷新 · `
          : '自动刷新已暂停 · ') + suffix;
  el.classList.toggle('al-error', !!state.error);
  const auto = document.querySelector('[data-al-auto]');
  auto.textContent = state.auto ? '暂停自动刷新' : '开始自动刷新';
  auto.setAttribute('aria-pressed', String(state.auto));
  document
    .getElementById('al-live-dot')
    .classList.toggle('is-live', state.auto && !document.hidden && !state.error);
  const refresh = document.querySelector('[data-al-refresh]');
  refresh.disabled = state.busy;
  refresh.textContent = state.busy ? '刷新中…' : state.error ? '重试刷新' : '立即刷新';
  const fail = document.querySelector('[data-al-fail]');
  fail.setAttribute('aria-pressed', String(state.failNext));
  fail.textContent = state.failNext ? '下次将模拟失败' : '模拟一次失败';
  fail.disabled = state.busy;
}
function clearScheduler() {
  if (scheduler !== null) clearInterval(scheduler);
  scheduler = null;
}
function cancelPending() {
  if (pending) {
    clearTimeout(pending.timer);
    pending = null;
  }
  state.busy = false;
}
function startScheduler() {
  clearScheduler();
  deadline = Date.now() + state.interval * 1000;
  if (!state.auto || document.hidden || !active()) return;
  scheduler = setInterval(() => {
    if (!active() || document.hidden) return;
    if (!state.busy && Date.now() >= deadline) requestRefresh();
    refreshStatus();
  }, 250);
}
function requestRefresh() {
  if (!active() || state.busy || document.hidden) return;
  state.busy = true;
  const token = generation,
    scenario = state.scenario,
    fail = state.failNext;
  state.failNext = false;
  state.error = '';
  pending = {
    timer: setTimeout(() => {
      pending = null;
      if (token !== generation || !active() || scenario !== state.scenario) return;
      state.busy = false;
      if (fail) {
        state.error = `模拟刷新失败 · 保留第 ${state.revision} 版数据，自动刷新已暂停。点击“重试刷新”继续。`;
        state.auto = false;
        clearScheduler();
        refreshStatus();
        return;
      }
      state.revision++;
      state.lastSuccess = new Date();
      state.error = '';
      deadline = Date.now() + state.interval * 1000;
      paint();
      document.getElementById('al-feedback').textContent =
        '刷新成功：已保留当前下钻路径、联动分组、时间区间与分页位置。';
    }, 350),
  };
  refreshStatus();
}
export function disposeAnalysisLab() {
  generation++;
  clearScheduler();
  cancelPending();
  observer?.disconnect();
  observer = null;
  Object.values(charts).forEach((chart) => chart.dispose());
  charts = {};
  if (!active()) state.auto = false;
}
function selectGroup(key, drill = false) {
  const s = getSnapshot();
  if (!s.dimension || !s.groups.some((g) => g.key === key)) return;
  if (drill) {
    state.path.push({ key: s.dimension.key, value: key });
    state.selected = null;
  } else state.selected = state.selected === key ? null : key;
  state.page = 1;
  paint(drill ? '[data-al-depth="' + state.path.length + '"]' : undefined);
  document.getElementById('al-feedback').textContent =
    (drill ? '已下钻：' : '已更新联动：') +
    (state.selected || state.path.map((p) => p.value).join(' / ') || '全部分组');
}
export async function mountAnalysisLab() {
  if (!active()) return;
  const token = ++generation,
    host = document.getElementById('al-trend');
  if (!host) return;
  paint();
  try {
    const echarts = await loadChartLibrary(chartProviders[0]);
    if (token !== generation || !active() || !host.isConnected) return;
    for (const key of ['trend', 'rank', 'composition']) {
      const el = document.getElementById('al-' + key);
      charts[key] = echarts.init(el, null, { renderer: 'canvas' });
      el.dataset.renderedLibrary = 'echarts';
    }
    charts.rank.on('click', (event) => {
      if (event.data?.groupKey) selectGroup(event.data.groupKey);
    });
    charts.rank.on('dblclick', (event) => {
      if (event.data?.groupKey) selectGroup(event.data.groupKey, true);
    });
    charts.trend.on('click', (event) => {
      if (event.componentType !== 'series' || !snapshot.periods.includes(event.name)) return;
      state.range =
        state.range?.[0] === event.name && state.range?.[1] === event.name
          ? null
          : [event.name, event.name];
      state.page = 1;
      paint();
    });
    charts.trend.on('datazoom', (event) => {
      if (updating) return;
      const option = charts.trend.getOption().dataZoom[0],
        zoom = event.batch?.[0] || event,
        periods = snapshot.periods;
      const index = (value, percent, fallback) =>
        typeof value === 'string' && periods.includes(value)
          ? periods.indexOf(value)
          : Number.isFinite(value)
            ? Math.min(periods.length - 1, Math.max(0, Math.round(value)))
            : Number.isFinite(percent)
              ? Math.round(((periods.length - 1) * percent) / 100)
              : fallback;
      const start = index(zoom.startValue, zoom.start ?? option.start, 0),
        finish = index(zoom.endValue, zoom.end ?? option.end, periods.length - 1);
      state.range =
        start === 0 && finish === periods.length - 1
          ? null
          : [periods[Math.min(start, finish)], periods[Math.max(start, finish)]];
      state.page = 1;
      paint();
    });
    observer =
      typeof ResizeObserver === 'function'
        ? new ResizeObserver(() => Object.values(charts).forEach((chart) => chart.resize()))
        : null;
    for (const key of Object.keys(charts)) observer?.observe(document.getElementById('al-' + key));
    paint();
    startScheduler();
    document.getElementById('al-feedback').textContent =
      '3 个 ECharts 图表已就绪 · 点击排行联动，双击或使用按钮下钻。';
  } catch (error) {
    if (token !== generation || !active()) return;
    Object.values(charts).forEach((chart) => chart.dispose());
    charts = {};
    document.getElementById('al-feedback').innerHTML =
      `图表加载失败：${esc(error.message)} <button class="btn" type="button" data-al-retry>重试图表</button>`;
  }
}
export function initAnalysisLab({ intro, esc, toast, renderView, getView }) {
  api = Object.freeze({ intro, esc, toast, renderView, getView });
  new MutationObserver(() => {
    if (active()) paint();
  }).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-palette'],
  });
  document.addEventListener('visibilitychange', () => {
    if (!active()) return;
    if (document.hidden) {
      clearScheduler();
      cancelPending();
    } else startScheduler();
    refreshStatus();
  });
  document.addEventListener('change', (event) => {
    if (!active()) return;
    const { id, value } = event.target;
    if (id === 'al-metric' && current().metrics.some((m) => m.id === value)) {
      state.metric = value;
      paint('#al-metric');
    }
    if (id === 'al-days' && [7, 30, 90].includes(Number(value))) {
      state.days = Number(value);
      state.range = null;
      state.page = 1;
      paint('#al-days');
    }
    if (id === 'al-sample' && ['normal', 'zero', 'empty'].includes(value)) {
      state.sample = value;
      state.page = 1;
      paint('#al-sample');
    }
    if (id === 'al-interval' && [3, 5, 10].includes(Number(value))) {
      state.interval = Number(value);
      startScheduler();
      refreshStatus();
    }
    if (['al-start', 'al-end'].includes(id)) {
      const start = document.getElementById('al-start').value,
        end = document.getElementById('al-end').value;
      if (start > end) {
        document.getElementById('al-feedback').textContent =
          '开始时间不能晚于结束时间，请重新选择。';
        document.getElementById(id).value =
          id === 'al-start'
            ? snapshot.range?.[0] || snapshot.periods[0]
            : snapshot.range?.[1] || snapshot.periods.at(-1);
        return;
      }
      state.range = [start, end];
      state.page = 1;
      paint('#' + id);
    }
  });
  document.addEventListener('click', (event) => {
    if (!active()) return;
    const button = event.target.closest('button');
    if (!button || button.disabled) return;
    const d = button.dataset;
    if (d.alScenario && analysisScenarios.some((s) => s.id === d.alScenario)) {
      if (d.alScenario === state.scenario) return;
      Object.assign(state, {
        scenario: d.alScenario,
        metric: analysisScenarios.find((s) => s.id === d.alScenario).metrics[0].id,
        path: [],
        selected: null,
        range: null,
        revision: 0,
        page: 1,
        auto: false,
        error: '',
        failNext: false,
        lastSuccess: null,
      });
      api.renderView();
      document
        .querySelector(`[data-al-scenario="${state.scenario}"]`)
        .focus({ preventScroll: true });
      return;
    }
    if (d.alSelect !== undefined) {
      selectGroup(d.alSelect);
      document.querySelectorAll('[data-al-select]').forEach((el) => {
        if (el.dataset.alSelect === d.alSelect) el.focus({ preventScroll: true });
      });
    }
    if (d.alDrill !== undefined) selectGroup(d.alDrill, true);
    if (
      d.alDepth !== undefined &&
      /^\d+$/.test(d.alDepth) &&
      Number(d.alDepth) <= state.path.length
    ) {
      state.path = state.path.slice(0, Number(d.alDepth));
      state.selected = null;
      state.page = 1;
      paint('[data-al-depth="' + d.alDepth + '"]');
    }
    if (d.alUp !== undefined && state.path.length) {
      state.path.pop();
      state.selected = null;
      state.page = 1;
      paint('[data-al-up]');
    }
    if (d.alClearSelection !== undefined) {
      state.selected = null;
      state.page = 1;
      paint('[data-al-clear-selection]');
    }
    if (d.alClearRange !== undefined) {
      state.range = null;
      state.page = 1;
      paint('[data-al-clear-range]');
    }
    if (d.alReset !== undefined) {
      Object.assign(state, { path: [], selected: null, range: null, sample: 'normal', page: 1 });
      document.getElementById('al-sample').value = 'normal';
      paint('[data-al-reset]');
    }
    if (d.alAuto !== undefined) {
      state.auto = !state.auto;
      state.error = '';
      if (!state.auto) cancelPending();
      startScheduler();
      refreshStatus();
    }
    if (d.alRefresh !== undefined) requestRefresh();
    if (d.alFail !== undefined) {
      state.failNext = !state.failNext;
      refreshStatus();
    }
    if (d.alRetry !== undefined) {
      disposeAnalysisLab();
      for (const key of ['trend', 'rank', 'composition'])
        document.getElementById('al-' + key).replaceChildren();
      void mountAnalysisLab();
    }
    if (d.alPage !== undefined && ['-1', '1'].includes(d.alPage)) {
      state.page += Number(d.alPage);
      paint('[data-al-page="' + d.alPage + '"]');
    }
    if (d.alExport !== undefined) {
      const url = URL.createObjectURL(
        new Blob([chartExampleCsv(analysisExport(getSnapshot()))], {
          type: 'text/csv;charset=utf-8',
        }),
      );
      const a = document.createElement('a');
      a.href = url;
      a.download = `nova-analysis-${state.scenario}-v${state.revision}-demo.csv`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      api.toast('已导出当前范围全部模拟明细');
    }
  });
}
