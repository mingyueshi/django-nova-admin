import { createCollection } from './collection.js';
import { pagination, submitPageJump } from './pagination.js';
import { thumbnail, imageSpec } from './media.js';
let ui, routing, saveRecords, recordAudit, records;
const seed = [
  [
    201,
    '城市里的新公共空间：把设计带回日常',
    '设计观察',
    '林知夏',
    '已发布',
    '2026-10-01',
    1280,
    '从开放的建筑与公共空间，探索人与城市的连接。',
  ],
  [
    202,
    '更轻盈的协作：工作空间的一次小更新',
    '团队动态',
    '陈屿',
    '已发布',
    '2026-09-29',
    864,
    '为讨论、专注与灵感留出更合适的位置。',
  ],
  [
    203,
    '走向山野，寻找另一种节奏',
    '生活方式',
    '苏念',
    '草稿',
    '2026-09-27',
    0,
    '自然光线、远山与湖泊，作为视觉专题的封面示例。',
  ],
  [
    204,
    '十月内容计划与编辑规范',
    '团队动态',
    '周予安',
    '待审核',
    '2026-09-25',
    0,
    '缺少封面时保留相同尺寸，不影响标题与行的对齐。',
  ],
  [
    205,
    '从草图到实物：产品细节记录',
    '产品故事',
    '沈言',
    '已发布',
    '2026-09-23',
    642,
    '此记录用于演示封面加载失败以及重新加载。',
  ],
  [
    206,
    '小尺度的设计，让城市更友好',
    '设计观察',
    '许清和',
    '已发布',
    '2026-09-20',
    928,
    '以日常出行场景呈现功能与美感的平衡。',
  ],
  [
    207,
    '工艺与材料的细节展览',
    '产品故事',
    '林知夏',
    '草稿',
    '2026-09-17',
    0,
    '以合成图片展示新闻列表，不代表真实新闻事件。',
  ],
  [
    208,
    '秋日编辑部：本周精选阅读',
    '生活方式',
    '陈屿',
    '归档',
    '2026-09-12',
    458,
    '轻量内容示例，仅用于后台图文列表预览。',
  ],
].map(([id, title, category, author, status, date, views, summary]) => ({
  id,
  title,
  category,
  author,
  status,
  date,
  views,
  summary,
}));
const extraNewsTitles = [
  '共享场所的光与影',
  '跨团队交流日记',
  '沿着河岸慢慢走',
  '材料实验室开放日',
  '街区里的阅读角',
  '编辑协作流程回顾',
  '清晨公园的色彩',
  '工坊里的制作过程',
  '公共艺术与日常生活',
  '本月内容归档记录',
  '城市边缘的自然观察',
  '可重复使用的包装设计',
  '空间更新的观察笔记',
  '团队工作方法记录',
  '周末出行的轻装方案',
  '小物件的设计故事',
];
extraNewsTitles.forEach((title, i) => {
  const original = seed[i % 4];
  seed.push({
    ...original,
    id: 209 + i,
    title,
    date: `2026-08-${String(28 - i).padStart(2, '0')}`,
    views: i % 3 ? 240 + i * 17 : 0,
    summary: '合成编辑资料，用于分页、筛选与状态操作演示。',
  });
});
const collection = createCollection({
  getRecords: () => records,
  pageSize: 10,
  sort: 'desc',
  filters: {
    query: { default: '', param: 'q', parse: (value) => (value || '').slice(0, 100) },
    category: {
      default: '全部栏目',
      parse: (value) =>
        ['设计观察', '团队动态', '生活方式', '产品故事'].includes(value) ? value : '全部栏目',
    },
    status: {
      default: '全部状态',
      parse: (value) => (['草稿', '待审核', '已发布', '归档'].includes(value) ? value : '全部状态'),
    },
  },
  matches: (record, list) =>
    (record.title + record.author).includes(list.query) &&
    (list.category === '全部栏目' || record.category === list.category) &&
    (list.status === '全部状态' || record.status === list.status),
  compare: (a, b, list) =>
    list.sort === 'desc' ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date),
});
const list = collection.state;
const esc = (x) => ui.esc(x);
// This screen can persist only its news records, not arbitrary app state.
export function initNews(dependencies) {
  ({ ui, routing, saveRecords, recordAudit } = dependencies);
  try {
    const saved = JSON.parse(localStorage.getItem('nova-news'));
    records =
      Array.isArray(saved) &&
      saved.length &&
      saved.every(
        (x) =>
          seed.some((y) => y.id === x.id) &&
          typeof x.title === 'string' &&
          typeof x.date === 'string' &&
          /^\d{4}-\d{2}-\d{2}$/.test(x.date) &&
          typeof x.author === 'string' &&
          typeof x.category === 'string' &&
          typeof x.summary === 'string' &&
          Number.isFinite(x.views) &&
          ['草稿', '待审核', '已发布', '归档'].includes(x.status),
      )
        ? saved
        : structuredClone(seed);
  } catch {
    records = structuredClone(seed);
  }
  document.addEventListener('click', click);
  document.addEventListener('input', input);
  document.addEventListener('change', change);
  document.addEventListener('submit', (event) =>
    submitPageJump(event, collection, 'news', (focus) => {
      sync(true);
      refresh(focus);
    }),
  );
}
export function resetNews() {
  records = structuredClone(seed);
  collection.resetFilters({ resetSort: true, resetPageSize: true });
}
const options = (items, value) =>
  items.map((x) => `<option ${x === value ? 'selected' : ''}>${esc(x)}</option>`).join('');
const badge = (s) =>
  `<span class="pill ${s === '已发布' ? 'status-normal' : s === '待审核' ? 'status-pending' : ''}">${esc(s)}</span>`;
function sync(push = false) {
  routing.replaceListRoute('news' + collection.queryString(), { push });
}
export function renderNews(route) {
  collection.restore(route);
  return (
    ui.intro('新闻资讯', '封面、栏目与发布状态，一目了然。', '') +
    `<div class="model-hint">${ui.icon('circle')}合成内容与本地图片 · 点击封面预览 · 包含缺图与加载失败场景</div><section class="panel"><div class="catalog-toolbar"><div class="search-input">${ui.icon('search')}<input id="news-search" aria-label="搜索新闻" placeholder="搜索标题或作者…" value="${esc(list.query)}"></div><select id="news-category" aria-label="新闻栏目">${options(['全部栏目', '设计观察', '团队动态', '生活方式', '产品故事'], list.category)}</select><select id="news-status" aria-label="新闻状态">${options(['全部状态', '草稿', '待审核', '已发布', '归档'], list.status)}</select><button class="btn subtle" data-news="reset">清除筛选</button><span class="spacer"></span><span class="muted">${records.length} 篇内容</span></div><div id="news-results">${results()}</div></section>`
  );
}
function results() {
  const { all, pages, rows, selectedVisible: visible } = collection.pageItems();
  sync();
  return `${list.selected.size ? `<div class="bulk-bar"><strong>已选 ${list.selected.size} 篇</strong><span>本页 ${visible} 篇 · 其他页 ${list.selected.size - visible} 篇</span><button class="btn" data-news="publish">发布所选</button><button class="btn" data-news="archive">归档所选</button><button class="btn subtle" data-news="clear">取消选择</button></div>` : ''}<div class="mobile-news-tools"><label><input class="checkbox" type="checkbox" id="news-mobile-all" ${rows.length && visible === rows.length ? 'checked' : ''} ${rows.length ? '' : 'disabled'} aria-label="选择本页新闻">本页全选</label><button class="btn subtle" data-news="sort">日期 ${list.sort === 'desc' ? '↓' : '↑'}</button></div>${rows.length ? `<div class="table-scroll news-table-wrap"><table class="news-table"><thead><tr><th class="check-cell"><input type="checkbox" id="news-all" class="checkbox" ${visible === rows.length ? 'checked' : ''} aria-label="选择本页全部新闻"></th><th>封面 / 标题</th><th>栏目</th><th>状态</th><th>作者</th><th><button class="sort-btn" data-news="sort">发布日期 ${list.sort === 'desc' ? '↓' : '↑'}</button></th><th>阅读量</th><th>操作</th></tr></thead><tbody>${rows.map((r) => `<tr><td class="check-cell">${check(r)}</td><td><div class="media-title-cell">${thumbnail(imageSpec('cover', r.id, r.title))}<div><button class="object-link news-title" data-news-detail="${r.id}">${esc(r.title)}</button><span class="cell-subline">${esc(r.summary)}</span></div></div></td><td>${esc(r.category)}</td><td>${badge(r.status)}</td><td>${esc(r.author)}</td><td class="muted numeric">${r.date}</td><td class="numeric">${r.views.toLocaleString()}</td><td><button class="row-link" data-news-detail="${r.id}">详情 ${ui.icon('chevron')}</button></td></tr>`).join('')}</tbody></table></div><div class="mobile-news-cards">${rows.map((r) => `<article class="news-card"><div class="news-card-select">${check(r)}<span>${esc(r.category)}</span>${badge(r.status)}</div><div class="media-title-cell">${thumbnail(imageSpec('cover', r.id, r.title))}<button class="news-title object-link" data-news-detail="${r.id}">${esc(r.title)}</button></div><div class="news-card-meta"><span>${esc(r.author)} · ${r.date}</span><span>${r.views.toLocaleString()} 阅读</span><button class="row-link" data-news-detail="${r.id}">详情</button></div></article>`).join('')}</div>` : `<div class="empty-state">${ui.icon('search')}<h3>没有符合条件的新闻</h3><p>试试其他标题、作者或栏目</p><button class="btn" data-news="reset">清除筛选</button></div>`}${pagination(collection, 'news', 'data-news-page', '新闻', '篇')}`;
}
function check(r) {
  return `<input class="checkbox news-check" type="checkbox" value="${r.id}" ${list.selected.has(r.id) ? 'checked' : ''} aria-label="选择${esc(r.title)}">`;
}
export function syncNewsSelection() {
  if (!document.getElementById('news-results')) return;
  const { indeterminate } = collection.pageItems();
  for (const checkbox of document.querySelectorAll('#news-all,#news-mobile-all'))
    checkbox.indeterminate = indeterminate;
}
function refresh(focus) {
  sync();
  const el = document.querySelector('#news-results');
  if (el) {
    el.innerHTML = results();
    syncNewsSelection();
    if (focus) document.querySelector(focus)?.focus();
  }
}
function detail(id) {
  const r = records.find((x) => x.id === id);
  if (!r) return;
  ui.openOverlay(
    `<section class="drawer news-detail" role="dialog" aria-modal="true" aria-labelledby="news-detail-title"><div class="drawer-header"><div><h2 id="news-detail-title">${esc(r.title)}</h2><p>${esc(r.category)} · ${esc(r.author)}</p></div><button class="icon-button" data-action="close" aria-label="关闭新闻详情">${ui.icon('close')}</button></div><div class="drawer-content">${thumbnail(imageSpec('cover', r.id, r.title), 'news-detail-cover')}<div class="news-detail-status">${badge(r.status)}<span>${r.date}</span><span>${r.views.toLocaleString()} 阅读</span></div><p class="news-summary">${esc(r.summary)}</p><div class="notice">${ui.icon('circle')}这是图文列表与详情样例，不连接内容发布系统。图片与人物均为合成演示素材。</div></div><div class="drawer-footer"><button class="btn primary" data-action="close">关闭详情</button></div></section>`,
  );
}
function click(e) {
  const d = e.target.closest('[data-news-detail]');
  if (d) {
    detail(Number(d.dataset.newsDetail));
    return;
  }
  const p = e.target.closest('[data-news-page]');
  if (p && !p.disabled) {
    collection.setPage(p.dataset.newsPage);
    sync(true);
    refresh(`[data-news-page="${list.page}"]`);
    return;
  }
  const b = e.target.closest('[data-news]');
  if (!b) return;
  const a = b.dataset.news;
  if (a === 'sort') {
    list.sort = list.sort === 'desc' ? 'asc' : 'desc';
    list.page = 1;
    refresh('[data-news="sort"]');
    return;
  }
  if (a === 'reset') {
    collection.resetFilters();
    sync();
    ui.renderView();
    document.querySelector('#news-search')?.focus();
    return;
  }
  if (a === 'clear') {
    list.selected.clear();
    refresh();
    return;
  }
  if (['publish', 'archive'].includes(a)) {
    const target = a === 'publish' ? '已发布' : '归档',
      chosen = records.filter((r) => list.selected.has(r.id));
    ui.openOverlay(
      `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="news-batch-title"><h2 id="news-batch-title">${target} ${chosen.length} 篇演示内容？</h2><p>只更新当前浏览器中的模拟状态。</p><ul class="batch-preview">${chosen.map((r) => `<li>${esc(r.title)}</li>`).join('')}</ul><div class="modal-actions"><button class="btn" data-action="close">取消</button><button class="btn primary" data-news="confirm" data-news-target="${target}">确认更新</button></div></section>`,
      true,
    );
    return;
  }
  if (a === 'confirm') {
    const target = b.dataset.newsTarget;
    if (!['已发布', '归档'].includes(target)) return;
    const next = records.map((r) => (list.selected.has(r.id) ? { ...r, status: target } : r));
    if (!saveRecords(next)) return;
    records = next;
    recordAudit('新闻批量更新', `${list.selected.size} 篇内容 → ${target}`);
    list.selected.clear();
    ui.closeOverlay(true);
    refresh();
    ui.toast('演示新闻状态已更新');
  }
}
function input(e) {
  if (e.target.id === 'news-search') {
    collection.setFilter('query', e.target.value);
    refresh();
  }
}
function change(e) {
  if (e.target.dataset.pageSize === 'news') {
    if (collection.setPageSize(e.target.value)) {
      sync(true);
      refresh('#news-page-size');
    }
    return;
  }
  if (['news-category', 'news-status'].includes(e.target.id)) {
    collection.setFilter(e.target.id === 'news-category' ? 'category' : 'status', e.target.value);
    refresh();
  }
  if (e.target.matches('.news-check')) {
    collection.select(Number(e.target.value), e.target.checked);
    refresh(
      `.${e.target.closest('.mobile-news-cards') ? 'mobile-news-cards' : 'news-table-wrap'} .news-check[value="${e.target.value}"]`,
    );
  }
  if (['news-all', 'news-mobile-all'].includes(e.target.id)) {
    collection.selectPage(e.target.checked);
    refresh('#' + e.target.id);
  }
}
