import { icon } from './icons.js';
import { analyticsChannels } from './analytics-data.js';
import {
  chartProviders,
  chartScenes,
  createChartExample,
  chartExampleCsv,
} from './chart-lab-data.js';
import {
  buildEChartsOption,
  buildChartJsConfig,
  buildUPlotOptions,
  serializeChartConfig,
} from './chart-lab-options.js';
let api,
  instance = null,
  resizeObserver = null,
  playback = null,
  generation = 0,
  currentExample = null,
  themeFrame = null;
const loading = new Map();
export { loadLibrary as loadChartLibrary, theme as chartTheme };
const state = {
  library: 'echarts',
  scene: 'trend',
  days: 30,
  channel: 'all',
  hours: 6,
  sample: 'normal',
  seed: 0,
  tick: 0,
  code: 'js',
  playing: false,
  details: false,
};
const provider = () => chartProviders.find((item) => item.id === state.library);
const scene = () => chartScenes.find((item) => item.id === state.scene);
const esc = (value) => api.esc(value);
const ops = () => state.scene.startsWith('ops-');
function theme() {
  const style = getComputedStyle(document.documentElement),
    read = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
  const colors = [
    read('--accent', '#2563eb'),
    read('--mint', '#168462'),
    read('--blue', '#527ae8'),
    read('--peach', '#da956c'),
    read('--muted', '#8997ac'),
  ];
  const hex = colors[0].match(/^#([a-f0-9]{6})$/i),
    rgb = hex
      ? [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16))
      : colors[0].match(/[\d.]+/g)?.slice(0, 3);
  return {
    colors,
    text: read('--text', '#1e293b'),
    muted: read('--muted', '#7b8799'),
    line: read('--line', '#e2e8f0'),
    panel: read('--panel', '#fff'),
    bg: read('--bg', '#f5f7fb'),
    fill: rgb ? 'rgba(' + rgb.join(',') + ',0.18)' : colors[0],
  };
}
function emptyReason(example) {
  if (!example.rows.length) return '当前筛选没有数据';
  if (
    example.sample === 'zero' &&
    ['channels', 'products', 'funnel', 'radar', 'sankey', 'scatter', 'boxplot'].includes(example.id)
  )
    return '当前数值为 0，暂无可绘制的占比或分布';
  if (example.id === 'scatter' && !example.points.length) return '支付订单为 0，无法计算客单价';
  return '';
}
function configFor(example, t = theme()) {
  if (state.library === 'echarts') return buildEChartsOption(example, t);
  if (state.library === 'chartjs') return buildChartJsConfig(example, t);
  return buildUPlotOptions(example, t);
}
export function chartLabSnippet(kind = state.code) {
  const example = createChartExample(state.scene, state),
    p = provider(),
    t = theme();
  if (kind === 'data') return JSON.stringify(example, null, 2);
  if (kind === 'config') return serializeChartConfig(configFor(example, t));
  const builder = {
    echarts: 'buildEChartsOption',
    chartjs: 'buildChartJsConfig',
    uplot: 'buildUPlotOptions',
  }[p.id];
  const css = p.css ? `<link rel="stylesheet" href="${p.css}">\n` : '';
  const container =
    p.id === 'chartjs'
      ? '<div style="height:420px;position:relative"><canvas id="chart" role="img" aria-label="' +
        example.title +
        '"></canvas></div>'
      : '<div id="chart" style="height:420px" role="img" aria-label="' + example.title + '"></div>';
  const data =
    p.id === 'uplot'
      ? `\nconst values = [data.timestamps, ...data.series.map(series => series.values)];`
      : '';
  const initialize =
    p.id === 'echarts'
      ? `const chart = echarts.init(el);\nchart.setOption(${builder}(data, theme));\nconst observer = new ResizeObserver(() => chart.resize());\nobserver.observe(el);\n// 页面卸载时：observer.disconnect(); chart.dispose();`
      : p.id === 'chartjs'
        ? `const chart = new Chart(el, ${builder}(data, theme));\n// 页面卸载时：chart.destroy();`
        : `const chart = new uPlot(${builder}(data, theme, el.clientWidth, 420), values, el);\nconst observer = new ResizeObserver(() => chart.setSize({width: el.clientWidth, height: 420}));\nobserver.observe(el);\n// 实时更新：chart.setData(nextValues);\n// 页面卸载时：observer.disconnect(); chart.destroy();`;
  if (kind === 'django') {
    const staticPath = p.script.replace('./', 'nova_charts/');
    return `{% load static %}\n${p.css ? `<link rel="stylesheet" href="{% static '${p.css.replace('./', 'nova_charts/')}' %}">\n` : ''}${container}\n{{ chart_data|json_script:"chart-data" }}\n<script src="{% static '${staticPath}' %}"></script>\n<script type="module">\nimport { ${builder} } from "{% static 'nova_charts/js/chart-lab-options.js' %}";\nconst el = document.getElementById('chart');\nconst data = JSON.parse(document.getElementById('chart-data').textContent);\nconst theme = ${JSON.stringify(t, null, 2)};${data}\n${initialize}\n</script>\n\n{# 先复制 vendor/charts 与适配器到宿主 static/nova_charts/。\n   chart_data 由服务端按权限生成，结构参见“数据”。\n   非法/空数据应先校验；不要直接把接口内容当作脚本。 #}`;
  }
  return `${css}${container}\n<script src="${p.script}"></script>\n<script type="module">\nimport { ${builder} } from './js/chart-lab-options.js';\nconst el = document.getElementById('chart');\nconst data = ${JSON.stringify(example, null, 2)};\nconst theme = ${JSON.stringify(t, null, 2)};${data}\n${initialize}\n</script>`;
}
function codeMarkup() {
  return `<div class="cl-code-tabs" role="group" aria-label="图表用法类型">${[
    ['js', 'JavaScript'],
    ['django', 'Django'],
    ['config', '原始配置'],
    ['data', '数据'],
  ]
    .map(
      ([id, label]) =>
        `<button type="button" data-cl-code="${id}" aria-pressed="${state.code === id}">${label}</button>`,
    )
    .join(
      '',
    )}<button type="button" class="btn subtle" data-cl-copy>${icon('book')}复制</button></div><pre class="cl-code"><code>${esc(chartLabSnippet())}</code></pre><p id="cl-copy-status" role="status" class="cl-small"></p><textarea id="cl-copy-fallback" aria-label="手动复制图表代码" readonly rows="5" hidden></textarea>`;
}
function tableMarkup(example) {
  return `<details class="panel cl-details" id="cl-details"${state.details ? ' open' : ''}><summary>数据明细 <span>${example.rows.length} 行 · 与图形和 CSV 同源</span></summary><div class="table-scroll" role="region" aria-label="图表数据明细，可横向滚动" tabindex="0"><table><thead><tr>${example.columns.map((label) => `<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${
    example.rows
      .slice(0, 300)
      .map((row) => `<tr>${row.map((value) => `<td>${esc(value)}</td>`).join('')}</tr>`)
      .join('') || `<tr><td colspan="${example.columns.length}">没有数据</td></tr>`
  }</tbody></table></div></details>`;
}
export function renderChartLab() {
  const p = provider(),
    selected = scene(),
    example = createChartExample(state.scene, state),
    available = chartScenes.filter((item) => item.libraries.includes(p.id));
  return `<div class="chart-lab">${api.intro('开源图表实验室', '选择图表库，查看真实渲染、数据与接入代码。', `<a class="btn" href="#analysis">${icon('activity')}联动与下钻</a><a class="btn" href="#analytics">${icon('lucide:chart-column')}统计分析</a><span class="pill">3 套图表库 · 17 类场景</span>`)}<div class="cl-providers">${chartProviders.map((item) => `<section class="panel cl-provider"><button type="button" data-cl-library="${item.id}" aria-pressed="${p.id === item.id}"><span class="cl-provider-mark">${icon(item.id === 'uplot' ? 'activity' : item.id === 'chartjs' ? 'lucide:chart-pie' : 'lucide:chart-column')}</span><span><strong>${item.name}</strong><small>${item.version} · ${chartScenes.filter((s) => s.libraries.includes(item.id)).length} 个演示场景</small></span><span class="pill">${item.license}</span></button><p>${item.description}</p><div><a href="${item.docs}" target="_blank" rel="noopener">官方文档 ↗</a><a href="./vendor/charts/${item.id}/${item.id === 'chartjs' ? 'LICENSE.md' : 'LICENSE'}" target="_blank" rel="noopener">本地许可证 ↗</a></div></section>`).join('')}</div><section class="panel cl-toolbar" aria-label="开源图表筛选"><label>统计场景<select id="cl-scene" aria-label="开源图表统计场景">${available.map((item) => `<option value="${item.id}"${item.id === state.scene ? ' selected' : ''}>${item.title} · ${item.kind}</option>`).join('')}</select></label>${ops() ? `<label>时间窗口<select id="cl-hours" aria-label="运维时间窗口">${[1, 6, 24].map((hours) => `<option value="${hours}"${hours === state.hours ? ' selected' : ''}>最近 ${hours} 小时</option>`).join('')}</select></label>` : state.scene === 'boxplot' ? '<span class="cl-small">独立接口基准样本</span>' : `<label>时间范围<select id="cl-days" aria-label="图表时间范围">${[7, 30, 90].map((days) => `<option value="${days}"${days === state.days ? ' selected' : ''}>最近 ${days} 天</option>`).join('')}</select></label><label>来源渠道<select id="cl-channel" aria-label="图表来源渠道"><option value="all">全部渠道</option>${analyticsChannels.map((item) => `<option value="${item.id}"${item.id === state.channel ? ' selected' : ''}>${item.name}</option>`).join('')}</select></label>`}<label>数据示例<select id="cl-sample" aria-label="图表数据示例">${[
    ['normal', '正常数据'],
    ['zero', '全零数据'],
    ['empty', '无数据'],
  ]
    .map(
      ([value, label]) =>
        `<option value="${value}"${value === state.sample ? ' selected' : ''}>${label}</option>`,
    )
    .join(
      '',
    )}</select></label><div class="cl-toolbar-actions">${ops() ? `<button type="button" class="btn${state.playing ? ' primary' : ''}" data-cl-play aria-pressed="${state.playing}">${icon(state.playing ? 'history' : 'activity')}${state.playing ? '暂停回放' : '播放模拟'}</button>` : ''}<button class="btn subtle" type="button" data-cl-reset>${icon('history')}重置</button></div></section><div class="cl-workspace"><aside class="panel cl-scenes" aria-label="图表场景目录">${[
    '经营分析',
    '用户运营',
    '系统运维',
  ]
    .map((category) => {
      const choices = available.filter((item) => item.category === category);
      return choices.length
        ? `<h2>${category}</h2>${choices.map((item) => `<button type="button" data-cl-scene="${item.id}" aria-pressed="${item.id === selected.id}">${icon(item.icon)}<span>${item.title}<small>${item.kind}</small></span></button>`).join('')}`
        : '';
    })
    .join(
      '',
    )}<p class="cl-small">显示本库已接入的场景；切换图表库可查看其他类型。</p></aside><div class="cl-main"><section class="panel cl-chart-panel"><div class="cl-chart-head"><div><span class="cl-eyebrow">${p.name} / ${selected.category}</span><h2>${selected.title}</h2><p id="cl-description">${example.description}</p></div><div class="cl-chart-actions"><button type="button" class="btn" data-cl-download="csv">${icon('download')}CSV</button><button type="button" class="btn" data-cl-download="png" disabled>${icon('download')}PNG</button><button type="button" class="btn subtle" data-cl-zoom-reset>重置缩放</button></div></div><div class="cl-render-status" id="cl-status" role="status">准备从本地加载 ${p.name} ${p.version}…</div><div class="cl-chart-host" id="cl-chart" aria-label="${selected.title}，${p.name}渲染，完整数据见明细" aria-busy="true" tabindex="0"></div><p class="cl-chart-hint">${p.id === 'echarts' ? '悬停查看数值；点击图例切换序列；时序图支持底部滑块与滚轮缩放。' : p.id === 'chartjs' ? '悬停查看数值，点击图例显示或隐藏序列。' : '拖拽选择时间区间进行缩放，双击恢复；悬停查看各时序值。'}<span id="cl-play-status">${state.playing ? '模拟回放中' : ''}</span></p><p id="cl-interaction" class="cl-small" role="status"></p></section><section class="panel cl-code-panel"><div class="cl-section-head"><h2>支持与用法</h2><span class="pill">${p.license}</span></div><div id="cl-code-area">${codeMarkup()}</div><p class="cl-small">示例来自当前场景与筛选。JavaScript / Django 示例复用随源码交付的适配器；复制时保留图表库许可。</p></section>${tableMarkup(example)}</div></div><section class="panel cl-capabilities"><h2>场景覆盖与图表库支持</h2><div class="table-scroll"><table><thead><tr><th>统计场景</th>${chartProviders.map((item) => `<th>${item.name}</th>`).join('')}</tr></thead><tbody>${chartScenes.map((item) => `<tr><th scope="row">${item.title}</th>${chartProviders.map((p) => `<td>${item.libraries.includes(p.id) ? '<span class="positive">已接入</span>' : '—'}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p>本地固定版本按需加载，离开页面会销毁实例并停止回放。数据均为模拟样本；通用 Django 主题不自动暴露统计接口。各库完整功能以官方文档为准，表格只说明本演示已接入范围。</p></section></div>`;
}
function loadLibrary(p) {
  if (window[p.global]) return Promise.resolve(window[p.global]);
  if (loading.has(p.id)) return loading.get(p.id);
  const promise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = p.script;
    script.async = true;
    script.dataset.chartLibrary = p.id;
    let done = false;
    const timer = setTimeout(() => finish(new Error('本地资源加载超时')), 15000);
    function finish(error) {
      if (done) return;
      done = true;
      clearTimeout(timer);
      script.onload = null;
      script.onerror = null;
      if (error) {
        script.remove();
        loading.delete(p.id);
        reject(error);
      } else resolve(window[p.global]);
    }
    script.onload = () => finish(window[p.global] ? null : new Error('图表库初始化失败'));
    script.onerror = () => finish(new Error('无法读取本地图表资源'));
    document.head.append(script);
  });
  loading.set(p.id, promise);
  if (p.css && !document.querySelector('link[data-chart-library="' + p.id + '"]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = p.css;
    link.dataset.chartLibrary = p.id;
    document.head.append(link);
  }
  return promise;
}
function stopPlayback() {
  if (playback) clearInterval(playback);
  playback = null;
  state.playing = false;
}
export function disposeChartLab() {
  generation++;
  resizeObserver?.disconnect();
  resizeObserver = null;
  if (instance) {
    if (typeof instance.dispose === 'function') instance.dispose();
    else instance.destroy();
    instance = null;
  }
  stopPlayback();
}
function status(text, failed = false) {
  const target = document.getElementById('cl-status');
  if (target) {
    target.textContent = text;
    if (failed) {
      const button = document.createElement('button');
      button.className = 'btn';
      button.type = 'button';
      button.dataset.clRetry = '';
      button.textContent = '重试加载';
      target.append(' ', button);
    }
  }
}
export async function mountChartLab() {
  if (api.getView() !== 'charts') return;
  const request = ++generation,
    p = provider(),
    host = document.getElementById('cl-chart');
  if (!host) return;
  const example = createChartExample(state.scene, state),
    reason = emptyReason(example);
  currentExample = example;
  if (reason) {
    host.innerHTML = `<div class="cl-empty">${icon('lucide:chart-column')}<strong>${reason}</strong><p>更换数据示例或筛选后继续查看。</p></div>`;
    host.setAttribute('aria-busy', 'false');
    status(reason);
    return;
  }
  try {
    const library = await loadLibrary(p);
    if (request !== generation || !host.isConnected || api.getView() !== 'charts') return;
    const t = theme();
    if (p.id === 'echarts') {
      instance = library.init(host, null, { renderer: 'canvas' });
      instance.setOption(buildEChartsOption(example, t));
      instance.on('click', (event) => {
        const out = document.getElementById('cl-interaction');
        if (out)
          out.textContent =
            (event.name || event.seriesName || '数据') + ' · ' + JSON.stringify(event.value);
      });
    } else if (p.id === 'chartjs') {
      const canvas = document.createElement('canvas');
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', example.title + '，完整数值见数据明细');
      host.append(canvas);
      instance = new library(canvas, buildChartJsConfig(example, t));
    } else {
      instance = new library(
        buildUPlotOptions(
          example,
          t,
          Math.max(1, host.clientWidth),
          Math.max(260, host.clientHeight - 44),
        ),
        [example.timestamps, ...example.series.map((s) => s.values)],
        host,
      );
    }
    resizeObserver =
      typeof ResizeObserver === 'function'
        ? new ResizeObserver(() => {
            if (!instance || !host.isConnected) return;
            if (p.id === 'echarts') instance.resize();
            else if (p.id === 'chartjs') instance.resize();
            else
              instance.setSize({
                width: Math.max(1, host.clientWidth),
                height: Math.max(260, host.clientHeight - 44),
              });
          })
        : null;
    resizeObserver?.observe(host);
    host.setAttribute('aria-busy', 'false');
    host.dataset.renderedLibrary = p.id;
    host.dataset.renderedScene = state.scene;
    status(`${p.name} ${p.version} · 已渲染 · ${example.rows.length} 行模拟数据`);
    document.querySelector('[data-cl-download="png"]').disabled = false;
  } catch (error) {
    if (request !== generation) return;
    host.setAttribute('aria-busy', 'false');
    status('图表暂时无法加载：' + error.message, true);
  }
}
function redraw(focus) {
  api.renderView();
  if (focus) document.querySelector(focus)?.focus({ preventScroll: true });
}
function saveFile(url, name, revoke = false) {
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  if (revoke) setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function updatePlayback() {
  if (!instance || !ops() || api.getView() !== 'charts') {
    stopPlayback();
    return;
  }
  state.tick++;
  const data = createChartExample(state.scene, state);
  currentExample = data;
  if (state.library === 'echarts')
    instance.setOption(buildEChartsOption(data, theme()), { notMerge: true });
  else instance.setData([data.timestamps, ...data.series.map((s) => s.values)]);
  const status = document.getElementById('cl-play-status');
  if (status) status.textContent = '模拟回放 · 已推进 ' + state.tick + ' 分钟';
  const code = document.querySelector('#cl-code-area .cl-code code');
  if (code) code.textContent = chartLabSnippet();
  const details = document.getElementById('cl-details');
  if (details) details.outerHTML = tableMarkup(data);
}
export function initChartLab({ intro, esc, toast, renderView, getView }) {
  api = Object.freeze({ intro, esc, toast, renderView, getView });
  new MutationObserver(() => {
    if (getView() !== 'charts' || themeFrame) return;
    themeFrame = requestAnimationFrame(() => {
      themeFrame = null;
      redraw();
    });
  }).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-palette'],
  });
  document.addEventListener(
    'toggle',
    (event) => {
      if (event.target.id === 'cl-details') state.details = event.target.open;
    },
    true,
  );
  document.addEventListener('change', (event) => {
    if (getView() !== 'charts') return;
    const { id, value } = event.target;
    const fields = {
      'cl-days': ['days', [7, 30, 90], Number(value)],
      'cl-hours': ['hours', [1, 6, 24], Number(value)],
      'cl-channel': ['channel', ['all', ...analyticsChannels.map((c) => c.id)], value],
      'cl-sample': ['sample', ['normal', 'zero', 'empty'], value],
    };
    if (
      id === 'cl-scene' &&
      chartScenes.some((item) => item.id === value && item.libraries.includes(state.library))
    ) {
      state.scene = value;
      state.tick = 0;
      redraw('#cl-scene');
      return;
    }
    const item = fields[id];
    if (item && item[1].includes(item[2])) {
      state[item[0]] = item[2];
      state.tick = 0;
      redraw('#' + id);
    }
  });
  document.addEventListener('click', async (event) => {
    if (getView() !== 'charts') return;
    const lib = event.target.closest('[data-cl-library]');
    if (lib && chartProviders.some((p) => p.id === lib.dataset.clLibrary)) {
      state.library = lib.dataset.clLibrary;
      if (!scene().libraries.includes(state.library))
        state.scene = chartScenes.find((s) => s.libraries.includes(state.library)).id;
      state.tick = 0;
      redraw(`[data-cl-library="${state.library}"]`);
      return;
    }
    const choice = event.target.closest('[data-cl-scene]');
    if (
      choice &&
      chartScenes.some(
        (s) => s.id === choice.dataset.clScene && s.libraries.includes(state.library),
      )
    ) {
      state.scene = choice.dataset.clScene;
      state.tick = 0;
      redraw(`[data-cl-scene="${state.scene}"]`);
      if (innerWidth < 900)
        document.querySelector('.cl-chart-panel').scrollIntoView({ block: 'start' });
      return;
    }
    const code = event.target.closest('[data-cl-code]');
    if (code && ['js', 'django', 'config', 'data'].includes(code.dataset.clCode)) {
      state.code = code.dataset.clCode;
      document.getElementById('cl-code-area').innerHTML = codeMarkup();
      document.querySelector(`[data-cl-code="${state.code}"]`).focus({ preventScroll: true });
      return;
    }
    if (event.target.closest('[data-cl-copy]')) {
      const text = chartLabSnippet();
      try {
        if (!navigator.clipboard?.writeText) throw Error('Clipboard unavailable');
        await navigator.clipboard.writeText(text);
        const status = document.getElementById('cl-copy-status');
        if (status) status.textContent = '代码已复制';
        const fallback = document.getElementById('cl-copy-fallback');
        if (fallback) fallback.hidden = true;
      } catch {
        const fallback = document.getElementById('cl-copy-fallback');
        if (fallback) {
          fallback.value = text;
          fallback.hidden = false;
          fallback.focus();
          fallback.select();
          document.getElementById('cl-copy-status').textContent =
            '自动复制不可用，请手动复制下方代码';
        }
      }
      return;
    }
    if (event.target.closest('[data-cl-retry]')) {
      disposeChartLab();
      document.getElementById('cl-chart').innerHTML = '';
      document.getElementById('cl-chart').setAttribute('aria-busy', 'true');
      status('正在重新加载本地资源…');
      void mountChartLab();
      return;
    }
    if (event.target.closest('[data-cl-reset]')) {
      Object.assign(state, {
        library: 'echarts',
        scene: 'trend',
        days: 30,
        channel: 'all',
        hours: 6,
        sample: 'normal',
        seed: 0,
        tick: 0,
        code: 'js',
      });
      redraw('#cl-scene');
      return;
    }
    if (event.target.closest('[data-cl-play]')) {
      if (!ops() || !instance) return;
      if (state.playing) {
        stopPlayback();
      } else {
        state.playing = true;
        playback = setInterval(updatePlayback, 1500);
      }
      const button = document.querySelector('[data-cl-play]');
      button.setAttribute('aria-pressed', String(state.playing));
      button.textContent = state.playing ? '暂停回放' : '播放模拟';
      document.getElementById('cl-play-status').textContent = state.playing
        ? '模拟回放中'
        : '回放已暂停';
      return;
    }
    if (event.target.closest('[data-cl-zoom-reset]')) {
      if (!instance) return;
      if (state.library === 'echarts')
        instance.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
      else if (state.library === 'uplot') {
        const e = currentExample;
        instance.setScale('x', { min: e.timestamps[0], max: e.timestamps.at(-1) });
      } else api.toast('Chart.js 当前展示完整范围');
      return;
    }
    const download = event.target.closest('[data-cl-download]');
    if (download) {
      const example = currentExample || createChartExample(state.scene, state);
      try {
        if (download.dataset.clDownload === 'csv')
          saveFile(
            URL.createObjectURL(
              new Blob([chartExampleCsv(example)], { type: 'text/csv;charset=utf-8' }),
            ),
            `nova-${state.library}-${state.scene}-demo.csv`,
            true,
          );
        else {
          if (!instance) return;
          let url;
          if (state.library === 'echarts')
            url = instance.getDataURL({
              type: 'png',
              pixelRatio: 2,
              backgroundColor: theme().panel,
            });
          else {
            const source = state.library === 'chartjs' ? instance.canvas : instance.ctx.canvas;
            const canvas = document.createElement('canvas');
            canvas.width = source.width;
            canvas.height = source.height;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = theme().panel;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(source, 0, 0);
            url = canvas.toDataURL('image/png');
          }
          saveFile(url, `nova-${state.library}-${state.scene}.png`);
        }
        api.toast('已导出当前图表' + (download.dataset.clDownload === 'csv' ? '数据' : '图片'));
      } catch {
        api.toast('导出失败，请重试或查看明细', 'error');
      }
    }
  });
}
