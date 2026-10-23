import { icon, openIcons, iconLibraries } from './icons.js';

let api;
const state = {
  library: 'all',
  category: 'all',
  query: '',
  size: 24,
  stroke: 'source',
  selected: 'lucide:search',
  code: 'js',
  page: 1,
};
const pageSize = 48;
const entries = Object.entries(openIcons);
const categories = [...new Set(entries.map(([, entry]) => entry.category))];
const library = (id) => iconLibraries.find((item) => item.id === id);
const options = (label = '') => ({
  size: state.size,
  ...(state.stroke === 'source' ? {} : { strokeWidth: Number(state.stroke) }),
  ...(label ? { label } : {}),
});
const filtered = () =>
  entries.filter(
    ([id, entry]) =>
      (state.library === 'all' || entry.library === state.library) &&
      (state.category === 'all' || entry.category === state.category) &&
      `${id} ${entry.label} ${entry.category} ${entry.keywords} ${library(entry.library).name}`
        .toLowerCase()
        .includes(state.query.trim().toLowerCase()),
  );

export function iconSnippet(kind = state.code) {
  const entry = openIcons[state.selected];
  const config = options(entry.label);
  if (entry.stroke === 'none') delete config.strokeWidth;
  if (kind === 'svg') return icon(state.selected, '', config);
  if (kind === 'django')
    return `{% load nova_tags %}\n{% nova_icon "${state.selected}" size=${state.size}${state.stroke === 'source' || entry.stroke === 'none' ? '' : ` stroke_width=${state.stroke}`} label="${entry.label}" %}`;
  if (kind === 'navigation')
    return `# settings.py\nNOVA_ADMIN_NAV_ICONS = {\n    "catalog.product": "${state.selected}",\n}`;
  const serialized = JSON.stringify(config, null, 2);
  return `import { icon } from './js/icons.js';\n\nconst markup = icon('${state.selected}', '', ${serialized});\n// 将 markup 放入你的图标容器\n// 随文字显示的装饰图标可省略 label`;
}

function resultsMarkup() {
  const list = filtered();
  if (!list.length)
    return `<div class="empty-state">${icon('search')}<h3>没有匹配的图标</h3><p>试试“搜索”“用户”、英文名称或更换图标库。</p><button class="btn" type="button" data-icon-reset>清除筛选</button></div>`;
  const pages = Math.ceil(list.length / pageSize);
  const visible = list.slice((state.page - 1) * pageSize, state.page * pageSize);
  return `<div class="icon-tile-grid">${visible.map(([id, entry]) => `<button type="button" class="icon-tile" data-icon-select="${id}" aria-pressed="${id === state.selected}" aria-label="查看 ${library(entry.library).name} ${entry.label} ${entry.name}"><span class="icon-tile-preview" aria-hidden="true">${icon(id, '', options())}</span><strong>${entry.label}</strong><code>${entry.name}</code><small>${library(entry.library).name}</small></button>`).join('')}</div>${pages > 1 ? `<nav class="icon-pagination" aria-label="图标分页"><button class="btn" type="button" data-icon-page="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''}>上一页</button><span>第 ${state.page} / ${pages} 页 · 每页 ${pageSize} 个</span><button class="btn" type="button" data-icon-page="${state.page + 1}" ${state.page === pages ? 'disabled' : ''}>下一页</button></nav>` : ''}`;
}

function detailMarkup() {
  const entry = openIcons[state.selected],
    provider = library(entry.library);
  return `<div class="icon-detail-head"><span class="pill">${provider.name}</span><span>${state.size}px · ${entry.stroke === 'none' ? '填充样式' : state.stroke === 'source' ? '原始线宽' : state.stroke + 'px 线宽'}</span></div><div class="icon-detail-preview">${icon(state.selected, '', options(entry.label))}</div><h2>${entry.label}</h2><p class="icon-id">${state.selected}</p><div class="icon-example-row"><button class="btn primary" type="button" data-icon-example>${icon(state.selected, '', options())}按钮用法</button><span class="pill">${icon(state.selected, '', { size: 16 })}状态标签</span></div><div class="icon-code-tabs" role="group" aria-label="使用示例语言">${[
    ['js', 'JavaScript'],
    ['django', 'Django 模板'],
    ['navigation', '导航配置'],
    ['svg', 'SVG'],
  ]
    .map(
      ([id, label]) =>
        `<button type="button" data-icon-code="${id}" aria-pressed="${state.code === id}">${label}</button>`,
    )
    .join(
      '',
    )}</div><pre class="icon-code"><code>${api.esc(iconSnippet())}</code></pre><div class="icon-code-actions"><button class="btn" type="button" data-icon-copy>${icon('book')}复制代码</button><a class="btn subtle" href="./assets/icons/${entry.file}" download="${entry.library}-${entry.name}.svg">${icon('download')}下载原始 SVG</a></div><p class="icon-copy-status" id="icon-copy-status" role="status" aria-live="polite"></p><textarea class="icon-copy-fallback" id="icon-copy-fallback" aria-label="手动复制图标代码" rows="6" readonly hidden>${api.esc(iconSnippet())}</textarea><p class="icon-license-note">${provider.name} ${provider.version} · ${provider.license}<br><a href="./assets/icons/${provider.license_path}" target="_blank" rel="noopener">查看随附许可证 ↗</a></p>`;
}

export function renderIconDemo() {
  return `<div class="icon-demo"><div class="icon-library-cards">${iconLibraries.map((provider) => `<section class="panel icon-library-card"><button type="button" data-icon-library="${provider.id}" aria-pressed="${state.library === provider.id}"><span class="icon-library-mark">${icon(provider.preview)}</span><span><strong>${provider.name}</strong><small>${provider.version} · ${provider.count} 个精选</small></span><span class="pill">${provider.license_label}</span></button><p>${provider.description}</p><a href="${provider.docs}" target="_blank" rel="noopener">官方使用文档 ↗</a></section>`).join('')}</div><section class="panel icon-toolbar" aria-label="图标筛选与预览"><label class="icon-search">${icon('search')}<input id="icon-search" type="search" placeholder="搜索图标、退款、工单、服务器…" aria-label="搜索图标" value="${api.esc(state.query)}"></label><label>分类<select id="icon-category"><option value="all">全部分类</option>${categories.map((category) => `<option${state.category === category ? ' selected' : ''}>${category}</option>`).join('')}</select></label><label>尺寸<select id="icon-size">${[16, 20, 24, 32, 48].map((size) => `<option value="${size}"${state.size === size ? ' selected' : ''}>${size}px</option>`).join('')}</select></label><label>轮廓线宽<select id="icon-stroke">${['source', '1', '1.5', '2', '2.5'].map((width) => `<option value="${width}"${state.stroke === width ? ' selected' : ''}>${width === 'source' ? '跟随原库' : width + 'px'}</option>`).join('')}</select></label></section><div class="icon-workspace"><section class="panel icon-browser"><div class="panel-head"><div class="icon-browser-title"><h2 tabindex="-1" id="icon-browser-heading">图标目录</h2><span id="icon-result-count">${filtered().length} / ${entries.length} 个</span></div><button class="btn subtle" type="button" data-icon-library="all" aria-pressed="${state.library === 'all'}">全部图标库</button></div><div id="icon-results">${resultsMarkup()}</div></section><aside class="panel icon-detail" id="icon-detail" aria-label="图标预览与用法">${detailMarkup()}</aside></div><section class="panel icon-usage-notes"><h2>接入与使用</h2><div><article><h3>本地 SVG，随主题配色</h3><p>页面收录五套图标库的常用图标精选集，覆盖订单支付、库存物流、审核工单、数据分析和系统运维。轮廓图标支持调整线宽，填充图标保留原生样式。图标随代码交付，通过 currentColor 跟随文字与配色，不依赖远程图标服务或字体。</p></article><article><h3>名称固定，按需使用</h3><p>JavaScript 使用 icon('lucide:search')；Django 使用 nova_icon 模板标签，也可在导航配置中选择同样的名称。完整接入及添加图标步骤见源码 ICONS.md。</p></article><article><h3>名称与许可一起保留</h3><p>下载与复用 SVG 时保留对应图标库的版权和许可文件。文字旁的图标默认作装饰；独立图标操作应为按钮提供清楚的可访问名称。</p></article></div></section></div>`;
}

function refresh() {
  if (api.getView() !== 'icons') return;
  const list = filtered();
  state.page = Math.max(1, Math.min(state.page, Math.ceil(list.length / pageSize) || 1));
  const visible = list.slice((state.page - 1) * pageSize, state.page * pageSize);
  if (visible.length && !visible.some(([id]) => id === state.selected))
    state.selected = visible[0][0];
  document.getElementById('icon-results').innerHTML = resultsMarkup();
  document.getElementById('icon-result-count').textContent =
    `${list.length} / ${entries.length} 个`;
  document.getElementById('icon-detail').innerHTML = detailMarkup();
  document
    .querySelectorAll('[data-icon-library]')
    .forEach((button) =>
      button.setAttribute('aria-pressed', String(button.dataset.iconLibrary === state.library)),
    );
}

export function initIconDemo({ esc, toast, getView }) {
  api = Object.freeze({ esc, toast, getView });
  document.addEventListener('input', (event) => {
    if (getView() === 'icons' && event.target.id === 'icon-search') {
      state.query = event.target.value;
      state.page = 1;
      refresh();
    }
  });
  document.addEventListener('change', (event) => {
    if (getView() !== 'icons') return;
    const { id, value } = event.target;
    if (id === 'icon-category' && ['all', ...categories].includes(value)) {
      state.category = value;
      state.page = 1;
    } else if (id === 'icon-size' && ['16', '20', '24', '32', '48'].includes(value))
      state.size = Number(value);
    else if (id === 'icon-stroke' && ['source', '1', '1.5', '2', '2.5'].includes(value))
      state.stroke = value;
    else return;
    refresh();
  });
  document.addEventListener('click', async (event) => {
    if (getView() !== 'icons') return;
    const button = event.target.closest(
      '[data-icon-library],[data-icon-select],[data-icon-code],[data-icon-copy],[data-icon-reset],[data-icon-example],[data-icon-page]',
    );
    if (!button) return;
    if (
      button.hasAttribute('data-icon-select') &&
      Object.hasOwn(openIcons, button.dataset.iconSelect)
    ) {
      state.selected = button.dataset.iconSelect;
      document
        .querySelectorAll('[data-icon-select]')
        .forEach((tile) =>
          tile.setAttribute('aria-pressed', String(tile.dataset.iconSelect === state.selected)),
        );
      document.getElementById('icon-detail').innerHTML = detailMarkup();
      if (window.innerWidth <= 950) {
        const detail = document.getElementById('icon-detail');
        detail.querySelector('h2').setAttribute('tabindex', '-1');
        detail.scrollIntoView({
          block: 'start',
          behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
            ? 'auto'
            : 'smooth',
        });
        detail.querySelector('h2').focus({ preventScroll: true });
      }
    } else if (
      button.hasAttribute('data-icon-library') &&
      ['all', ...iconLibraries.map((provider) => provider.id)].includes(button.dataset.iconLibrary)
    ) {
      state.library = button.dataset.iconLibrary;
      state.page = 1;
      refresh();
    } else if (
      button.hasAttribute('data-icon-code') &&
      ['js', 'django', 'navigation', 'svg'].includes(button.dataset.iconCode)
    ) {
      state.code = button.dataset.iconCode;
      document.getElementById('icon-detail').innerHTML = detailMarkup();
      document.querySelector(`[data-icon-code="${state.code}"]`).focus();
    } else if (button.hasAttribute('data-icon-page')) {
      const page = Number(button.dataset.iconPage);
      if (!Number.isInteger(page) || page < 1 || page > Math.ceil(filtered().length / pageSize))
        return;
      state.page = page;
      refresh();
      document.getElementById('icon-browser-heading').focus({ preventScroll: true });
      document
        .getElementById('icon-browser-heading')
        .scrollIntoView({ block: 'start', behavior: 'auto' });
    } else if (button.hasAttribute('data-icon-reset')) {
      state.page = 1;
      state.query = '';
      state.library = 'all';
      state.category = 'all';
      document.getElementById('icon-search').value = '';
      document.getElementById('icon-category').value = 'all';
      refresh();
      document.getElementById('icon-search').focus();
    } else if (button.hasAttribute('data-icon-example')) toast('这是图标与按钮的组合演示');
    else if (button.hasAttribute('data-icon-copy')) {
      const code = iconSnippet();
      try {
        if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(code);
        const status = document.getElementById('icon-copy-status');
        if (status) status.textContent = '代码已复制';
        const fallback = document.getElementById('icon-copy-fallback');
        if (fallback) fallback.hidden = true;
      } catch {
        const fallback = document.getElementById('icon-copy-fallback'),
          status = document.getElementById('icon-copy-status');
        if (fallback && status) {
          fallback.value = code;
          fallback.hidden = false;
          fallback.focus();
          fallback.select();
          status.textContent = '浏览器未能自动复制，请选中下方代码手动复制';
        }
      }
    }
  });
}
