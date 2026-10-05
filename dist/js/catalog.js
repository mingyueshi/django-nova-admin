import { createCollection } from './collection.js';
import { pagination, submitPageJump } from './pagination.js';
import { thumbnail, imageSpec } from './media.js';
// Complex ModelAdmin-style workflow. Data is synthetic and local-only.
let ui, routing, saveRecords, recordAudit;
let switchGeneration = 0;
const switchStates = new Map();
const seed = [
  {
    id: 101,
    title: '便携无线键盘',
    sku: 'NOVA-KB-01',
    category: '数码设备',
    supplier: '星云制造',
    tags: ['精选', '新品'],
    price: 299,
    cost: 158,
    status: '已发布',
    description: '轻量设计，适合日常办公。此处为合成示例内容。',
    featured: true,
    variants: [
      { key: 1, name: '雾白', sku: 'KB-WHT', stock: 36, price: 299, deleted: false },
      { key: 2, name: '石墨', sku: 'KB-GRY', stock: 24, price: 299, deleted: false },
    ],
  },
  {
    id: 102,
    title: '桌面收纳套装',
    sku: 'NOVA-DS-02',
    category: '办公用品',
    supplier: '青川设计',
    tags: ['推荐'],
    price: 168,
    cost: 80,
    status: '草稿',
    description: '模块化桌面配件。',
    featured: false,
    variants: [{ key: 1, name: '标准套装', sku: 'DS-STD', stock: 18, price: 168, deleted: false }],
  },
  {
    id: 103,
    title: '轻量通勤背包',
    sku: 'NOVA-BG-03',
    category: '出行装备',
    supplier: '星云制造',
    tags: ['新品'],
    price: 459,
    cost: 230,
    status: '已发布',
    description: '简洁通勤方案。',
    featured: false,
    variants: [{ key: 1, name: '深灰 / 18L', sku: 'BG-18', stock: 12, price: 459, deleted: false }],
  },
  {
    id: 104,
    title: '磁吸便签板',
    sku: 'NOVA-NT-04',
    category: '办公用品',
    supplier: '青川设计',
    tags: [],
    price: 89,
    cost: 42,
    status: '归档',
    description: '已归档的演示记录。',
    featured: false,
    variants: [{ key: 1, name: '雾紫', sku: 'NT-PUR', stock: 0, price: 89, deleted: false }],
  },
  {
    id: 105,
    title: '折叠支架',
    sku: 'NOVA-ST-05',
    category: '数码设备',
    supplier: '星云制造',
    tags: ['精选'],
    price: 129,
    cost: 60,
    status: '草稿',
    description: '便携折叠结构。',
    featured: false,
    variants: [{ key: 1, name: '银色', sku: 'ST-SLV', stock: 41, price: 129, deleted: false }],
  },
  {
    id: 106,
    title: '旅行收纳包',
    sku: 'NOVA-TR-06',
    category: '出行装备',
    supplier: '青川设计',
    tags: ['推荐'],
    price: 109,
    cost: 52,
    status: '已发布',
    description: '让物品各归其位。',
    featured: false,
    variants: [{ key: 1, name: '海盐蓝', sku: 'TR-BLU', stock: 26, price: 109, deleted: false }],
  },
  {
    id: 107,
    title: '桌面阅读灯',
    sku: 'NOVA-LT-07',
    category: '办公用品',
    supplier: '星云制造',
    tags: ['新品'],
    price: 329,
    cost: 168,
    status: '草稿',
    description: '柔和的桌面照明。',
    featured: false,
    variants: [{ key: 1, name: '暖白', sku: 'LT-WHT', stock: 15, price: 329, deleted: false }],
  },
];
const extraProductNames = [
  '无线输入套装',
  '文具整理盒',
  '城市出行包',
  '日程展示板',
  '铝合金托架',
  '轻便洗漱包',
  '双模输入套装',
  '笔具托盘',
  '周末随行包',
  '软木记录板',
  '阅读托架',
  '多层整理袋',
  '办公输入套装',
  '模块整理盒',
  '短途随行包',
  '桌边记录板',
  '金属托架',
];
extraProductNames.forEach((title, i) => {
  const original = seed[i % 6];
  const id = 108 + i;
  seed.push({
    ...structuredClone(original),
    id,
    title,
    sku: `NOVA-DEMO-${id}`,
    description: '合成商品，用于多页列表与批量操作演示。',
    variants: original.variants.map((variant, n) => ({ ...variant, sku: `DEMO-${id}-${n + 1}` })),
  });
});
let records,
  categories = ['数码设备', '办公用品', '出行装备'],
  mode = '管理员',
  draft = null,
  draftKey = '',
  dirty = false,
  draftFeaturedTouched = false,
  errors = [],
  pendingBatch = '',
  listRoute = 'catalog';
const collection = createCollection({
  getRecords: () => records,
  pageSize: 10,
  filters: {
    query: { default: '', param: 'q', parse: (value) => (value || '').slice(0, 100) },
    status: {
      default: '全部状态',
      parse: (value) => (['草稿', '已发布', '归档'].includes(value) ? value : '全部状态'),
    },
    category: {
      default: '全部分类',
      parse: (value) => (categories.includes(value) ? value : '全部分类'),
    },
  },
  matches: (record, list) =>
    (record.title + record.sku).toLowerCase().includes(list.query.toLowerCase()) &&
    (list.status === '全部状态' || record.status === list.status) &&
    (list.category === '全部分类' || record.category === list.category),
});
const list = collection.state;
const esc = (x) => ui.esc(x),
  ico = (x) => ui.icon(x);
// saveRecords is synchronous: false preserves records, selection and drafts.
export function initCatalog(dependencies) {
  ({ ui, routing, saveRecords, recordAudit } = dependencies);
  try {
    let saved = JSON.parse(localStorage.getItem('nova-catalog'));
    records =
      Array.isArray(saved) &&
      saved.every((x) => typeof x.title === 'string' && Array.isArray(x.variants))
        ? saved
        : structuredClone(seed);
  } catch {
    records = structuredClone(seed);
  }
  categories = [
    ...new Set([
      ...categories,
      ...records.map((r) => r.category).filter((x) => typeof x === 'string'),
    ]),
  ];
  document.addEventListener('click', click);
  document.addEventListener('input', input);
  document.addEventListener('change', change);
  document.addEventListener('submit', submit);
}
export const catalogDirty = () => dirty;
export function discardCatalogDraft() {
  dirty = false;
  draftFeaturedTouched = false;
  draft = null;
  draftKey = '';
  errors = [];
}
export function resetCatalog() {
  switchGeneration++;
  switchStates.clear();
  categories = ['数码设备', '办公用品', '出行装备'];
  records = structuredClone(seed);
  collection.resetFilters({ resetPageSize: true });
  mode = '管理员';
  discardCatalogDraft();
  try {
    localStorage.removeItem('nova-catalog');
  } catch {}
}
export function catalogRouteLabel(route) {
  if (route === 'catalog/add') return '新增商品';
  if (route.startsWith('catalog/edit/'))
    return records?.find((x) => x.id === Number(route.split('/')[2]))?.title || '记录不存在';
  return '';
}
const productStatus = (s) =>
  `<span class="pill ${s === '已发布' ? 'status-normal' : s === '草稿' ? 'status-pending' : ''}">${esc(s)}</span>`;
function options(items, value) {
  return items.map((x) => `<option ${x === value ? 'selected' : ''}>${esc(x)}</option>`).join('');
}
function modePicker() {
  return `<label class="demo-role-picker">演示身份 <select id="catalog-mode" aria-label="商品页演示身份">${options(['管理员', '只读成员', '无访问权限'], mode)}</select></label>`;
}
function syncListUrl(push = false) {
  listRoute = 'catalog' + collection.queryString();
  routing.replaceListRoute(listRoute, { push });
}
function restoreListUrl(route) {
  collection.restore(route);
}
export function renderCatalog(route) {
  if (mode === '无访问权限')
    return `${ui.intro('商品管理', '当前展示的是无权限界面，不提供真实鉴权。', modePicker())}<section class="panel access-boundary">${ico('shield')}<span class="error-code">403</span><h2>你没有查看商品的权限</h2><p>切换演示身份继续体验。真实权限由 Django 的 ModelAdmin 与服务端校验负责。</p><button class="btn primary" data-catalog="restore-access">恢复管理员演示</button></section>`;
  if (route === 'catalog/add' || route.startsWith('catalog/edit/')) return editor(route);
  restoreListUrl(route);
  return `${ui.intro('商品管理', '关联资料、规格明细与发布状态在同一个工作流中管理。', modePicker() + (mode === '管理员' ? '<a class="btn primary" href="#catalog/add">' + ico('plus') + '新增商品</a>' : ''))}<div class="model-hint">${ico('circle')}ModelAdmin 交互样例 · 所有数据仅在当前浏览器 · ${mode === '只读成员' ? '只读模式：操作按钮与可编辑字段均已禁用' : '模拟原生列表、关联字段、Inline 与保存流程'}</div><section class="panel"><div class="catalog-toolbar"><div class="search-input">${ico('search')}<input id="catalog-search" aria-label="搜索商品" placeholder="搜索商品名称或 SKU…" value="${esc(list.query)}"></div><select id="catalog-status" aria-label="商品状态">${options(['全部状态', '草稿', '已发布', '归档'], list.status)}</select><select id="catalog-category" aria-label="商品分类筛选">${options(['全部分类', ...categories], list.category)}</select><button class="btn subtle" data-catalog="reset-filters">清除筛选</button><span class="spacer"></span><span class="muted">${records.length} 条记录</span></div>${mode === '管理员' ? `<details class="switch-demo-tools"><summary>保存状态演示</summary><label class="check-label"><input type="checkbox" class="checkbox" id="catalog-fail-next">模拟下一次开关保存失败</label><p>开关仅更新本地演示；失败时保持原状态。真实 Django 列表编辑需点击“保存”。</p></details>` : ''}<div id="catalog-results">${results()}</div></section>`;
}
function results() {
  const { all, pages, rows, selectedVisible } = collection.pageItems();
  syncListUrl();
  return `${list.selected.size && mode === '管理员' ? `<div class="bulk-bar"><strong>已选 ${list.selected.size} 条</strong><span>本页 ${selectedVisible} 条 · 其他页 ${list.selected.size - selectedVisible} 条</span><select id="catalog-bulk" aria-label="商品批量动作"><option value="">选择操作…<option value="已发布">发布所选</option><option value="归档">归档所选</option></select><button class="btn" data-catalog="apply-batch">执行</button><button class="btn subtle" data-catalog="clear-selected">取消选择</button></div>` : ''}${rows.length ? `${mobileCards(rows, selectedVisible)}<div class="table-scroll catalog-table-wrap"><table class="catalog-table"><thead><tr>${mode === '管理员' ? `<th class="check-cell"><input type="checkbox" class="checkbox" id="catalog-all" ${selectedVisible === rows.length ? 'checked' : ''} aria-label="选择本页全部商品"></th>` : ''}<th>商品 / SKU</th><th>分类与供应商</th><th>状态</th><th>精选展示</th><th>售价</th><th>库存</th><th>操作</th></tr></thead><tbody>${rows.map((r) => `<tr>${mode === '管理员' ? `<td class="check-cell"><input class="checkbox catalog-check" type="checkbox" value="${r.id}" ${list.selected.has(r.id) ? 'checked' : ''} aria-label="选择${esc(r.title)}"></td>` : ''}<td><div class="media-title-cell">${thumbnail(imageSpec('product', r.id, r.title))}<div><a class="object-link" href="#catalog/edit/${r.id}">${esc(r.title)}</a><span class="cell-subline">${esc(r.sku)}</span></div></div></td><td>${esc(r.category)}<span class="cell-subline">${esc(r.supplier)}</span></td><td>${productStatus(r.status)}</td><td>${featureSwitch(r)}</td><td class="numeric">¥${Number(r.price).toFixed(2)}</td><td class="numeric">${r.variants.filter((v) => !v.deleted).reduce((s, v) => s + Number(v.stock), 0)}</td><td><a class="row-link" href="#catalog/edit/${r.id}">${mode === '只读成员' ? '查看' : '编辑'} ${ico('chevron')}</a></td></tr>`).join('')}</tbody></table></div>` : `<div class="empty-state">${ico('search')}<h3>没有匹配的商品</h3><p>试试其他名称、SKU 或分类</p><button class="btn subtle" data-catalog="reset-filters">清除筛选</button></div>`}${pagination(collection, 'catalog', 'data-catalog-page', '商品', '条')}`;
}

function mobileCards(rows, visible) {
  return `<div class="catalog-mobile-cards">${mode === '管理员' ? `<div class="mobile-catalog-tools"><label><input type="checkbox" class="checkbox" id="catalog-mobile-all" ${visible === rows.length ? 'checked' : ''} aria-label="选择本页全部商品">本页全选</label><span>图片可点开预览</span></div>` : ''}${rows.map((r) => `<article class="catalog-card"><div class="catalog-card-main">${mode === '管理员' ? `<input class="checkbox catalog-check" type="checkbox" value="${r.id}" ${list.selected.has(r.id) ? 'checked' : ''} aria-label="选择${esc(r.title)}">` : ''}${thumbnail(imageSpec('product', r.id, r.title))}<div class="catalog-card-title"><a class="object-link" href="#catalog/edit/${r.id}">${esc(r.title)}</a><span class="cell-subline">${esc(r.sku)}</span><span class="cell-subline">${esc(r.category)} · ${esc(r.supplier)}</span></div></div><div class="catalog-card-meta">${productStatus(r.status)}<strong>¥${Number(r.price).toFixed(2)}</strong><span>库存 ${r.variants.filter((v) => !v.deleted).reduce((s, v) => s + Number(v.stock), 0)}</span></div><div class="catalog-card-footer">${featureSwitch(r, 'mobile')}<a class="row-link" href="#catalog/edit/${r.id}">${mode === '只读成员' ? '查看' : '编辑'} ${ico('chevron')}</a></div></article>`).join('')}</div>`;
}
function featureSwitch(record, scope = '') {
  const suffix = scope ? '-' + scope : '';
  const state = mode === '管理员' ? switchStates.get(record.id) : undefined,
    pending = state === 'pending',
    failed = state === 'error';
  return `<div class="list-switch-cell"><button type="button" role="switch" class="list-switch" data-feature-toggle="${record.id}" data-feature-scope="${scope}" aria-label="${esc(record.title)}精选展示" aria-checked="${!!record.featured}" ${pending ? 'aria-busy="true" aria-disabled="true"' : ''} ${mode !== '管理员' ? 'disabled' : ''} aria-describedby="featured-state-${record.id}${suffix}"><span class="switch-track" aria-hidden="true"><span></span></span><span>${record.featured ? '已开启' : '已关闭'}</span></button><small id="featured-state-${record.id}${suffix}" class="switch-feedback ${failed ? 'is-error' : ''}" role="status">${pending ? '正在保存…' : failed ? '保存失败，原状态已保留。可重试' : state === 'saved' ? '已保存到本地' : mode !== '管理员' ? '只读' : '本地即时保存'}</small></div>`;
}
async function toggleFeatured(id, scope = '') {
  const focusSelector = `[data-feature-toggle="${id}"][data-feature-scope="${scope}"]`;
  if (mode !== '管理员' || switchStates.get(id) === 'pending') return;
  const record = records.find((r) => r.id === id);
  if (!record) return;
  const target = !record.featured,
    generation = switchGeneration;
  const failControl = document.querySelector('#catalog-fail-next'),
    simulateFailure = !!failControl?.checked;
  if (failControl) failControl.checked = false;
  switchStates.set(id, 'pending');
  renderResults(focusSelector);
  await new Promise((resolve) => setTimeout(resolve, 450));
  if (generation !== switchGeneration) return;
  const refocus = document.activeElement?.dataset.featureToggle === String(id);
  const next = records.map((r) => (r.id === id ? { ...r, featured: target } : r));
  if (simulateFailure || !saveRecords(next)) {
    switchStates.set(id, 'error');
    if (simulateFailure) ui.toast('模拟保存失败，开关保持原状态', 'error');
  } else {
    records = next;
    switchStates.set(id, 'saved');
    if (draft?.id === id && !draftFeaturedTouched) {
      draft.featured = target;
      const field = document.querySelector('#catalog-form [name=featured]');
      if (field) field.checked = target;
    }
    recordAudit('更新精选状态', record.title, target ? '开启精选展示' : '关闭精选展示');
    ui.toast(target ? '已开启精选展示' : '已关闭精选展示');
  }
  if (draft?.id === id) {
    const feedback = document.querySelector('#product-save-feedback');
    if (feedback)
      feedback.textContent =
        switchStates.get(id) === 'saved'
          ? draftFeaturedTouched
            ? '列表精选状态已保存，表单中的新选择仍待保存。'
            : '列表精选状态已保存，当前表单已同步。'
          : '列表精选状态未保存，原状态已保留。';
  }
  renderResults(refocus ? focusSelector : null);
}

function newDraft() {
  return {
    id: null,
    title: '',
    sku: '',
    category: categories[0],
    supplier: '星云制造',
    tags: [],
    price: '',
    cost: '',
    status: '草稿',
    description: '',
    featured: false,
    variants: [{ key: Date.now(), name: '', sku: '', stock: 0, price: '', deleted: false }],
  };
}
function editor(route) {
  const existing = route.startsWith('catalog/edit/')
    ? records.find((x) => x.id === Number(route.split('/')[2]))
    : null;
  if (route.startsWith('catalog/edit/') && !existing)
    return `<section class="panel access-boundary">${ico('circle')}<span class="error-code">404</span><h2>记录不存在</h2><p>这条记录可能已从本地演示中移除。</p><a class="btn primary" href="#${listRoute}">返回商品列表</a></section>`;
  if (draftKey !== route) {
    draft = existing ? structuredClone(existing) : newDraft();
    draftKey = route;
    dirty = false;
    draftFeaturedTouched = false;
    errors = [];
  }
  const readonly = mode === '只读成员';
  return `${ui.intro(existing ? (readonly ? '查看商品' : '编辑商品') : '新增商品', existing ? `${existing.sku} · 本地演示记录` : '完成基本信息，并添加至少一条商品规格。', `<a class="btn" href="#${listRoute}">${ico('arrow')}返回列表</a>`)}<div class="model-hint">${ico(readonly ? 'shield' : 'circle')}${readonly ? '只读模式：可查看关联与规格，不能修改或提交。' : '未保存的更改会提示确认；返回列表保留搜索与筛选。真实业务仍由 Django 服务端处理。'}</div><form id="catalog-form" novalidate><div id="catalog-errors" tabindex="-1"></div><div class="model-form-layout"><div class="model-form-main"><section class="panel model-fieldset"><div class="fieldset-heading"><div><h2>基本信息</h2><p>标识与展示内容</p></div><span class="count-badge">01</span></div><fieldset ${readonly ? 'disabled' : ''}><div class="field"><label for="product-title">商品名称 <span class="required">*</span></label><input id="product-title" name="title" value="${esc(draft.title)}" maxlength="80" aria-describedby="product-title-error" placeholder="输入商品名称"><small id="product-title-error" class="field-error"></small></div><div class="field-row"><div class="field"><label for="product-sku">主 SKU <span class="required">*</span></label><input id="product-sku" name="sku" value="${esc(draft.sku)}" maxlength="32" aria-describedby="product-sku-error" placeholder="如 NOVA-NEW-01"><small>唯一编号，支持字母、数字和短横线</small><small id="product-sku-error" class="field-error"></small></div><div class="field"><label for="product-status">发布状态</label><select id="product-status" name="status">${options(['草稿', '已发布', '归档'], draft.status)}</select></div></div><div class="field"><label for="product-description">商品描述</label><textarea id="product-description" name="description" rows="4" maxlength="2000" placeholder="描述商品用途与特点…">${esc(draft.description)}</textarea><small>最多 2,000 字符，纯文本内容</small></div></fieldset></section><section class="panel model-fieldset"><div class="fieldset-heading"><div><h2>关联资料</h2><p>外键选择与多对多标签</p></div><span class="count-badge">02</span></div><fieldset ${readonly ? 'disabled' : ''}><div class="field-row"><div class="field"><label for="product-category">商品分类 <span class="required">*</span></label><div class="related-input"><select data-searchable id="product-category" name="category">${options(categories, draft.category)}</select><button type="button" class="icon-button related-add" data-catalog="add-category" aria-label="添加关联分类" ${readonly ? 'disabled' : ''}>${ico('plus')}</button></div><small>可搜索分类；新增后自动选中，保留当前表单</small></div><div class="field"><label for="product-supplier">供应商</label><select data-searchable id="product-supplier" name="supplier">${options(['星云制造', '青川设计'], draft.supplier)}</select></div></div><div class="field"><label>内容标签</label><div class="relation-tags">${['精选', '推荐', '新品', '可预订'].map((t) => `<label><input type="checkbox" class="checkbox product-tag" value="${t}" ${draft.tags.includes(t) ? 'checked' : ''}>${t}</label>`).join('')}</div><small>可多选；映射 Django ManyToManyField 的交互示例</small></div></fieldset></section><section class="panel model-fieldset"><div class="fieldset-heading"><div><h2>价格与规格</h2><p>Inline 子记录与跨字段验证</p></div><span class="count-badge">03</span></div><fieldset ${readonly ? 'disabled' : ''}><div class="field-row"><div class="field"><label for="product-price">基础售价 <span class="required">*</span></label><div class="input-affix"><span aria-hidden="true">¥</span><input id="product-price" name="price" type="number" inputmode="decimal" min="0" step="0.01" value="${esc(draft.price)}" aria-describedby="product-price-error"></div><small id="product-price-error" class="field-error"></small></div><div class="field"><label for="product-cost">成本 <span class="required">*</span></label><div class="input-affix"><span aria-hidden="true">¥</span><input id="product-cost" name="cost" type="number" inputmode="decimal" min="0" step="0.01" value="${esc(draft.cost)}" aria-describedby="product-cost-error"></div><small id="product-cost-error" class="field-error"></small></div></div></fieldset><div class="inline-heading"><h3>商品规格</h3><span id="inline-count">${draft.variants.filter((v) => !v.deleted).length} 条有效规格</span></div><div id="variant-list">${inlineRows(readonly)}</div>${readonly ? '' : `<button type="button" class="inline-add" data-catalog="add-variant">${ico('plus')}添加一条规格</button>`}</section><details class="panel model-fieldset advanced-fieldset"><summary>高级选项</summary><fieldset ${readonly ? 'disabled' : ''}><label class="check-label"><input type="checkbox" class="checkbox" name="featured" ${draft.featured ? 'checked' : ''}>标记为精选内容</label><div class="field"><label for="product-id">记录编号</label><input id="product-id" value="${draft.id ? '#' + draft.id : '保存后生成'}" readonly><small>只读字段由系统维护</small></div></fieldset></details></div><aside class="model-summary panel"><h2>记录状态</h2><div class="product-editor-image">${thumbnail(imageSpec('product', draft.id, draft.title || '新商品'))}</div><div id="product-summary">${summary()}</div><div class="notice">${ico('circle')}此页面模拟 ModelAdmin 工作流，不会发布真实商品或修改服务器。</div><h3>保存行为</h3><p>保存会一起验证主表单与所有有效规格。有错误时保留全部输入，并定位到错误摘要。</p><a href="#audit" class="row-link">查看本地操作日志 ${ico('arrow')}</a></aside></div><div id="product-save-feedback" class="model-hint" role="status" aria-live="polite">${switchStates.get(draft.id) === 'pending' ? '列表精选状态正在保存，请稍候再提交表单。' : ''}</div><div class="model-submit-row"><span id="product-dirty-status">${readonly ? '只读记录' : '没有未保存的更改'}</span><div>${readonly ? `<a class="btn" href="#${listRoute}">返回列表</a>` : `<button type="submit" class="btn" data-save-mode="continue">保存并继续编辑</button><button type="submit" class="btn" data-save-mode="add">保存并新增</button><button type="submit" class="btn primary" data-save-mode="list">${ico('check')}保存并返回列表</button>`}</div></div></form>`;
}
function summary() {
  return `<div class="summary-status">${productStatus(draft.status)}<span class="muted">${draft.id ? '#' + draft.id : '新增记录'}</span></div><dl class="detail-list"><div><dt>基础售价</dt><dd>¥${draft.price === '' ? '—' : Number(draft.price).toFixed(2)}</dd></div><div><dt>规格数量</dt><dd>${draft.variants.filter((v) => !v.deleted).length}</dd></div><div><dt>总库存</dt><dd>${draft.variants.filter((v) => !v.deleted).reduce((s, v) => s + (Number(v.stock) || 0), 0)}</dd></div><div><dt>关联分类</dt><dd>${esc(draft.category)}</dd></div></dl>`;
}
function inlineRows(readonly = false) {
  return draft.variants
    .map(
      (v, i) =>
        `<div class="variant-row ${v.deleted ? 'pending-delete' : ''}" data-variant-key="${v.key}"><div class="variant-row-head"><strong>规格 ${i + 1}</strong>${readonly ? '' : `<button type="button" class="row-link ${v.deleted ? '' : 'danger-text'}" data-delete-variant="${v.key}">${v.deleted ? '撤销移除' : '移除'}</button>`}</div><fieldset class="variant-fields" ${readonly || v.deleted ? 'disabled' : ''}><div class="field"><label for="variant-${v.key}-name">规格名称 *</label><input id="variant-${v.key}-name" data-variant-field="name" value="${esc(v.name)}" maxlength="40"><small class="field-error" id="variant-${v.key}-name-error"></small></div><div class="field"><label for="variant-${v.key}-sku">规格 SKU *</label><input id="variant-${v.key}-sku" data-variant-field="sku" value="${esc(v.sku)}" maxlength="32"><small class="field-error" id="variant-${v.key}-sku-error"></small></div><div class="field"><label for="variant-${v.key}-price">规格售价 *</label><input id="variant-${v.key}-price" type="number" inputmode="decimal" min="0" step="0.01" data-variant-field="price" value="${esc(v.price)}"><small class="field-error" id="variant-${v.key}-price-error"></small></div><div class="field"><label for="variant-${v.key}-stock">库存 *</label><input id="variant-${v.key}-stock" type="number" inputmode="numeric" min="0" step="1" data-variant-field="stock" value="${esc(v.stock)}"><small class="field-error" id="variant-${v.key}-stock-error"></small></div></fieldset>${v.deleted ? '<p class="deletion-note">保存时移除这条规格；现在仍可撤销</p>' : ''}</div>`,
    )
    .join('');
}
function capture() {
  const form = document.querySelector('#catalog-form');
  if (!form || !draft) return;
  const data = new FormData(form);
  for (const k of [
    'title',
    'sku',
    'category',
    'supplier',
    'price',
    'cost',
    'status',
    'description',
  ])
    if (data.has(k)) draft[k] = data.get(k);
  draft.featured = data.has('featured');
  draft.tags = [...form.querySelectorAll('.product-tag:checked')].map((x) => x.value);
  for (const row of form.querySelectorAll('[data-variant-key]')) {
    const v = draft.variants.find((x) => x.key === Number(row.dataset.variantKey));
    for (const input of row.querySelectorAll('[data-variant-field]'))
      v[input.dataset.variantField] = input.value;
  }
}
function markDirty() {
  dirty = true;
  let s = document.querySelector('#product-dirty-status');
  if (s) s.textContent = '有未保存的更改';
  let summaryNode = document.querySelector('#product-summary');
  if (summaryNode) summaryNode.innerHTML = summary();
}
function refreshInline(focusNew = false) {
  document.querySelector('#variant-list').innerHTML = inlineRows(mode === '只读成员');
  document.querySelector('#inline-count').textContent =
    `${draft.variants.filter((v) => !v.deleted).length} 条有效规格`;
  markDirty();
  if (focusNew) document.getElementById(`variant-${draft.variants.at(-1).key}-name`)?.focus();
}
export function syncCatalogSelection() {
  if (!document.getElementById('catalog-results')) return;
  const { indeterminate } = collection.pageItems();
  for (const checkbox of document.querySelectorAll('#catalog-all,#catalog-mobile-all'))
    checkbox.indeterminate = indeterminate;
}
function renderResults(focusSelector) {
  syncListUrl();
  let el = document.querySelector('#catalog-results');
  if (el) {
    el.innerHTML = results();
    syncCatalogSelection();
    if (focusSelector) document.querySelector(focusSelector)?.focus();
  }
}
function validate() {
  const e = [];
  const add = (id, msg) => e.push({ id, msg });
  if (draft.title.trim().length < 2) add('product-title', '商品名称至少需要 2 个字符');
  if (!/^[A-Za-z0-9-]{3,32}$/.test(draft.sku))
    add('product-sku', '主 SKU 需为 3–32 个字母、数字或短横线');
  else if (
    records.some((r) => r.id !== draft.id && r.sku.toLowerCase() === draft.sku.toLowerCase())
  )
    add('product-sku', '主 SKU 已被其他商品使用');
  if (draft.price === '' || !Number.isFinite(Number(draft.price)) || Number(draft.price) < 0)
    add('product-price', '请输入有效的非负售价');
  if (draft.cost === '' || !Number.isFinite(Number(draft.cost)) || Number(draft.cost) < 0)
    add('product-cost', '请输入有效的非负成本');
  else if (Number(draft.cost) > Number(draft.price)) add('product-cost', '成本不能高于基础售价');
  for (const [key, label] of [
    ['price', '基础售价'],
    ['cost', '成本'],
  ])
    if (
      draft[key] !== '' &&
      Number.isFinite(Number(draft[key])) &&
      Math.abs(Number(draft[key]) * 100 - Math.round(Number(draft[key]) * 100)) > 1e-7
    )
      add('product-' + key, label + '最多保留两位小数');
  const live = draft.variants.filter((v) => !v.deleted),
    skus = new Set();
  if (!live.length) add('variant-list', '至少保留一条商品规格');
  for (const v of live) {
    if (v.name.trim().length < 1) add(`variant-${v.key}-name`, '请填写规格名称');
    if (!/^[A-Za-z0-9-]{2,32}$/.test(v.sku))
      add(`variant-${v.key}-sku`, '规格 SKU 需为 2–32 个字母、数字或短横线');
    else if (skus.has(v.sku.toLowerCase()))
      add(`variant-${v.key}-sku`, '同一商品的规格 SKU 不能重复');
    skus.add(v.sku.toLowerCase());
    if (v.price === '' || !Number.isFinite(Number(v.price)) || Number(v.price) < 0)
      add(`variant-${v.key}-price`, '请填写有效的规格售价');
    if (
      v.price !== '' &&
      Number.isFinite(Number(v.price)) &&
      Math.abs(Number(v.price) * 100 - Math.round(Number(v.price) * 100)) > 1e-7
    )
      add(`variant-${v.key}-price`, '规格售价最多保留两位小数');
    if (v.stock === '' || !Number.isSafeInteger(Number(v.stock)) || Number(v.stock) < 0)
      add(`variant-${v.key}-stock`, '库存必须为安全范围内的非负整数');
  }
  return e;
}
function showErrors() {
  document
    .querySelectorAll('#catalog-form [aria-invalid]')
    .forEach((x) => x.removeAttribute('aria-invalid'));
  document.querySelectorAll('#catalog-form .field-error').forEach((x) => (x.textContent = ''));
  const node = document.querySelector('#catalog-errors');
  if (!errors.length) {
    node.innerHTML = '';
    return;
  }
  node.innerHTML = `<div class="error-summary" role="alert"><div>${ico('circle')}<h2>请修正 ${errors.length} 处问题后再保存</h2></div><p>输入已保留。点击问题可定位到对应字段。</p><ul>${errors.map((e) => `<li><button type="button" data-error-target="${e.id}">${esc(e.msg)}</button></li>`).join('')}</ul></div>`;
  for (const e of errors) {
    const field = document.getElementById(e.id);
    field?.setAttribute('aria-invalid', 'true');
    const msg = document.getElementById(e.id + '-error');
    if (msg) {
      msg.textContent = e.msg;
      field?.setAttribute('aria-describedby', msg.id);
    }
  }
  node.focus();
  node.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
}
function click(e) {
  const toggle = e.target.closest('[data-feature-toggle]');
  if (toggle) {
    e.preventDefault();
    toggleFeatured(Number(toggle.dataset.featureToggle), toggle.dataset.featureScope);
    return;
  }
  const err = e.target.closest('[data-error-target]');
  if (err) {
    const field = document.getElementById(err.dataset.errorTarget);
    field?.focus();
    field?.scrollIntoView?.({ block: 'center' });
    return;
  }
  const pg = e.target.closest('[data-catalog-page]');
  if (pg && !pg.disabled) {
    collection.setPage(pg.dataset.catalogPage);
    syncListUrl(true);
    renderResults(`[data-catalog-page="${list.page}"]`);
    return;
  }
  const del = e.target.closest('[data-delete-variant]');
  if (del && mode === '管理员') {
    capture();
    const v = draft.variants.find((v) => v.key === Number(del.dataset.deleteVariant));
    v.deleted = !v.deleted;
    refreshInline();
    document.querySelector(`[data-delete-variant="${v.key}"]`)?.focus();
    return;
  }
  const target = e.target.closest('[data-catalog]');
  if (!target) return;
  const action = target.dataset.catalog;
  if (action === 'restore-access') {
    mode = '管理员';
    ui.renderView();
    return;
  }
  if (action === 'reset-filters') {
    collection.resetFilters();
    syncListUrl();
    ui.renderView();
    document.querySelector('#catalog-search')?.focus();
    return;
  }
  if (action === 'clear-selected') {
    list.selected.clear();
    renderResults();
    return;
  }
  if (action === 'add-variant' && mode === '管理员') {
    capture();
    draft.variants.push({
      key: Date.now(),
      name: '',
      sku: '',
      price: draft.price,
      stock: 0,
      deleted: false,
    });
    refreshInline(true);
    return;
  }
  if (action === 'add-category' && mode === '管理员') {
    capture();
    ui.openOverlay(
      `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="category-dialog-title"><h2 id="category-dialog-title">添加关联分类</h2><p class="lab-copy">保存后回到当前商品表单，自动选中此分类。</p><form id="category-form" novalidate><div class="field" style="margin-top:20px"><label for="new-category-name">分类名称 *</label><input id="new-category-name" maxlength="20"><small id="category-error" class="field-error"></small></div><div class="modal-actions"><button type="button" class="btn" data-action="close">取消</button><button type="submit" class="btn primary">保存并选中</button></div></form></section>`,
      true,
    );
    return;
  }
  if (action === 'apply-batch') {
    pendingBatch = document.querySelector('#catalog-bulk')?.value;
    if (!pendingBatch) {
      ui.toast('请先选择批量操作', 'info');
      return;
    }
    const chosen = records.filter((r) => list.selected.has(r.id));
    ui.openOverlay(
      `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="batch-title"><div class="modal-icon">${ico('layers')}</div><h2 id="batch-title">${pendingBatch === '已发布' ? '发布' : '归档'} ${chosen.length} 条演示记录？</h2><p>这次操作包含以下记录，可能来自多个页面。仅修改本地演示状态。</p><ul class="batch-preview">${chosen.map((r) => `<li>${esc(r.title)}<span>${esc(r.sku)}</span></li>`).join('')}</ul><div class="modal-actions"><button type="button" class="btn" data-action="close">取消</button><button type="button" class="btn primary" data-catalog="confirm-batch">确认执行</button></div></section>`,
      true,
    );
    return;
  }
  if (action === 'confirm-batch' && mode === '管理员') {
    const next = records.map((r) => (list.selected.has(r.id) ? { ...r, status: pendingBatch } : r));
    if (!saveRecords(next)) return;
    const count = list.selected.size;
    records = next;
    list.selected.clear();
    recordAudit('商品批量更新', `${count} 条记录 → ${pendingBatch}`);
    ui.closeOverlay(true);
    renderResults();
    ui.toast(`已更新 ${count} 条演示记录`);
  }
}
function input(e) {
  if (e.target.id === 'catalog-search') {
    collection.setFilter('query', e.target.value);
    renderResults();
  }
  if (e.target.closest('#catalog-form') && mode === '管理员') {
    if (e.target.name === 'featured') draftFeaturedTouched = true;
    capture();
    markDirty();
  }
}
function change(e) {
  if (e.target.dataset.pageSize === 'catalog') {
    if (collection.setPageSize(e.target.value)) {
      syncListUrl(true);
      renderResults('#catalog-page-size');
    }
    return;
  }
  if (e.target.id === 'catalog-mode') {
    mode = e.target.value;
    list.selected.clear();
    ui.renderView();
    return;
  }
  if (['catalog-status', 'catalog-category'].includes(e.target.id)) {
    collection.setFilter(e.target.id === 'catalog-status' ? 'status' : 'category', e.target.value);
    renderResults();
  }
  if (e.target.classList.contains('catalog-check')) {
    const id = Number(e.target.value);
    collection.select(id, e.target.checked);
    renderResults(
      `${e.target.closest('.catalog-mobile-cards') ? '.catalog-mobile-cards' : '.catalog-table-wrap'} .catalog-check[value="${id}"]`,
    );
  }
  if (['catalog-all', 'catalog-mobile-all'].includes(e.target.id)) {
    const focusId = e.target.id;
    collection.selectPage(e.target.checked);
    renderResults('#' + focusId);
  }
  if (e.target.closest('#catalog-form') && mode === '管理员') {
    if (e.target.name === 'featured') draftFeaturedTouched = true;
    capture();
    markDirty();
  }
}
function submit(e) {
  if (
    submitPageJump(e, collection, 'catalog', (focus) => {
      syncListUrl(true);
      renderResults(focus);
    })
  )
    return;
  if (e.target.id === 'category-form') {
    e.preventDefault();
    const name = document.querySelector('#new-category-name').value.trim();
    const error = document.querySelector('#category-error');
    if (name.length < 2) {
      error.textContent = '分类名称至少需要 2 个字符';
      return;
    }
    if (categories.includes(name)) {
      error.textContent = '该分类已存在';
      return;
    }
    categories.push(name);
    draft.category = name;
    const select = document.querySelector('#product-category');
    select.innerHTML = options(categories, name);
    select.dispatchEvent(new Event('change', { bubbles: true }));
    ui.closeOverlay(true);
    markDirty();
    (document.getElementById(select.id + '-combobox') || select).focus();
    ui.toast('关联分类已添加到当前演示表单');
    return;
  }
  if (e.target.id !== 'catalog-form') return;
  e.preventDefault();
  if (e.target.dataset.saving === 'true') return;
  if (mode !== '管理员') {
    ui.toast('只读演示模式不能保存', 'error');
    return;
  }
  if (switchStates.get(draft?.id) === 'pending') {
    document.querySelector('#product-save-feedback').textContent =
      '列表精选状态正在保存，请稍候再提交表单；当前输入已保留。';
    return;
  }
  capture();
  errors = validate();
  showErrors();
  if (errors.length) return;
  const created = !draft.id;
  const saved = {
    ...structuredClone(draft),
    id: draft.id || Math.max(...records.map((r) => r.id)) + 1,
    price: Number(draft.price),
    cost: Number(draft.cost),
    variants: draft.variants
      .filter((v) => !v.deleted)
      .map((v) => ({ ...v, price: Number(v.price), stock: Number(v.stock), deleted: false })),
  };
  const next = created ? [saved, ...records] : records.map((r) => (r.id === saved.id ? saved : r));
  if (!saveRecords(next)) return;
  e.target.dataset.saving = 'true';
  e.target.querySelectorAll('[data-save-mode]').forEach((button) => (button.disabled = true));
  records = next;
  recordAudit(
    created ? '新增商品' : '修改商品',
    saved.title,
    `保存主记录与 ${saved.variants.length} 条规格。`,
  );
  dirty = false;
  draft = null;
  draftKey = '';
  const saveMode = e.submitter?.dataset.saveMode || 'list';
  ui.toast('商品与规格已一同保存在当前浏览器');
  if (saveMode === 'continue') routing.navigate(`catalog/edit/${saved.id}`);
  else if (saveMode === 'add') {
    if (routing.current() === 'catalog/add') ui.renderView();
    else routing.navigate('catalog/add');
  } else routing.navigate(listRoute);
}
