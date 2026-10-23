import { icon } from './icons.js';
import {
  analyticsChannels,
  analyticsSnapshot,
  analyticsBuckets,
  analyticsCsv,
  percentChange,
} from './analytics-data.js';

let api;
const state = {
  days: 30,
  channel: 'all',
  sample: 'normal',
  metric: 'revenue',
  group: 'day',
  trend: 'area',
  bars: 'stacked',
  pie: 'donut',
  compare: true,
  current: true,
  previous: true,
  newOrders: true,
  repeatOrders: true,
  target: null,
  details: false,
};
const colors = ['var(--accent)', 'var(--mint)', 'var(--blue)', 'var(--peach)', 'var(--muted)'];
const metrics = {
  revenue: { label: '支付金额', unit: '元', value: (row) => row.revenue / 100 },
  paid: { label: '支付订单', unit: '单', value: (row) => row.paid },
  signups: { label: '新增用户', unit: '人', value: (row) => row.signups },
};
const integer = (value) => Math.round(value).toLocaleString('zh-CN');
const money = (cents) =>
  '¥' +
  (cents / 100).toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const compact = (value) => (value >= 10000 ? (value / 10000).toFixed(1) + '万' : integer(value));
const rate = (numerator, denominator) =>
  denominator ? ((numerator / denominator) * 100).toFixed(1) + '%' : '—';
const esc = (value) => api.esc(value);
const selection = (id, value) => (state[id] === value ? ' selected' : '');
const control = (key, choices, label) =>
  `<div class="an-switch" role="group" aria-label="${label}">${choices.map(([value, text]) => `<button type="button" data-an-setting="${key}" data-an-value="${value}" aria-pressed="${state[key] === value}">${text}</button>`).join('')}</div>`;
const legend = (key, name, color) =>
  `<button type="button" class="an-legend" data-an-toggle="${key}" aria-pressed="${state[key]}"><i style="--series:${color}"></i>${name}</button>`;
const empty = (text = '当前筛选没有数据', detail = '切换渠道、时间范围或数据示例后重试。') =>
  `<div class="an-empty">${icon('lucide:chart-column')}<strong>${text}</strong><span>${detail}</span></div>`;
const svgOpen = (title, viewBox = '0 0 600 260', interactive = true) =>
  `<svg class="an-svg" viewBox="${viewBox}" role="${interactive ? 'group' : 'img'}" aria-label="${title}"><title>${title}</title>`;
const pointAttrs = (label, first = false) =>
  `data-an-point="${esc(label)}" role="button" tabindex="${first ? 0 : -1}" aria-label="${esc(label)}"`;
const wrap = (svg, label, cls = '') =>
  `<div class="an-plot ${cls}" role="region" aria-label="${label}绘图区，可横向滚动" tabindex="0">${svg}</div>`;
const readout = (text = '悬停、点击或键盘聚焦数据点查看数值；方向键可切换数据点。') =>
  `<div class="an-readout" role="status" aria-live="polite">${text}</div>`;
function panel(id, title, subtitle, content, controls = '', wide = '') {
  return `<section class="panel an-card ${wide}" data-an-card="${id}" aria-labelledby="an-title-${id}"><div class="an-card-head"><div><h2 id="an-title-${id}">${title}</h2><p>${subtitle}</p></div>${controls}</div>${content}</section>`;
}
function changeText(current, previous, suffix = '%') {
  if (current === null || previous === null) return '<span class="an-muted">暂无可比值</span>';
  const delta = percentChange(current, previous);
  if (delta === null) return '<span class="an-muted">上期为 0，暂无可比增幅</span>';
  return `<span class="${delta >= 0 ? 'positive' : 'an-negative'}">${delta >= 0 ? '↑' : '↓'} ${Math.abs(delta).toFixed(1)}${suffix}</span><span>较上期</span>`;
}
function headline(cents) {
  const exact = money(cents);
  return `<abbr title="${exact}" aria-label="${exact}">${cents >= 1000000 ? '¥' + (cents / 1000000).toFixed(2) + '万' : exact}</abbr>`;
}
function kpis(snapshot) {
  const a = snapshot.current,
    b = snapshot.previous;
  const cards = [
    ['支付金额', headline(a.revenue), a.revenue, b.revenue, 'lucide:wallet'],
    ['支付订单', integer(a.paid) + '<small>单</small>', a.paid, b.paid, 'lucide:shopping-bag'],
    [
      '平均客单价',
      a.paid ? money(a.revenue / a.paid) : '—',
      a.paid ? a.revenue / a.paid : null,
      b.paid ? b.revenue / b.paid : null,
      'lucide:receipt-text',
    ],
    [
      '支付转化率',
      rate(a.paid, a.visits),
      a.visits ? a.paid / a.visits : null,
      b.visits ? b.paid / b.visits : null,
      'lucide:chart-line',
    ],
  ];
  return `<section class="metrics an-metrics" aria-label="统计关键指标">${cards.map(([title, value, current, previous, name], index) => `<article class="metric"><div class="metric-top"><span>${title}</span><span class="metric-icon">${icon(name)}</span></div><div class="metric-value"${index === 0 ? ` data-an-exact="${snapshot.daily.length ? money(snapshot.current.revenue) : '—'}"` : ''}>${snapshot.daily.length ? value : '—'}</div><div class="metric-foot">${snapshot.daily.length ? changeText(current, previous) : '<span>暂无数据</span>'}</div></article>`).join('')}</section>`;
}
function ceiling(values) {
  const max = Math.max(4, ...values);
  const step = 10 ** Math.floor(Math.log10(max / 4));
  return Math.ceil(max / (4 * step)) * step * 4;
}
function axes(max, labels, unit = '') {
  return `${[0, 1, 2, 3, 4].map((i) => `<line class="an-gridline" x1="58" y1="${216 - i * 47}" x2="580" y2="${216 - i * 47}"/><text class="an-axis" x="48" y="${220 - i * 47}" text-anchor="end">${compact((i * max) / 4)}</text>`).join('')}<text class="an-axis" x="6" y="15">${unit}</text>${labels.map((label, i) => `<text class="an-axis" x="${58 + (label.index * 522) / Math.max(1, label.count - 1)}" y="246" text-anchor="${i === 0 ? 'start' : i === labels.length - 1 ? 'end' : 'middle'}">${label.text}</text>`).join('')}`;
}
function trend(snapshot) {
  const metric = metrics[state.metric];
  const rows = analyticsBuckets(snapshot.daily, state.group),
    previous = analyticsBuckets(snapshot.prior, state.group);
  const currentValues = rows.map(metric.value),
    previousValues = previous.map(metric.value);
  const max = ceiling([
    ...(state.current ? currentValues : []),
    ...(state.compare && state.previous ? previousValues : []),
  ]);
  const enabled = state.current || (state.compare && state.previous);
  const labels = rows
    .map((row, i) => ({ text: row.label, index: i, count: rows.length }))
    .filter((_, i) => i === 0 || i === rows.length - 1 || i % Math.ceil(rows.length / 5) === 0);
  let graphic =
    svgOpen(
      `${metric.label}趋势，${metric.unit}，${state.group === 'week' ? '每7天汇总，末段可能不足7天' : '每日数据'}`,
    ) + axes(max, labels, metric.unit);
  let first = true;
  for (const [series, values, enabled, color] of [
    ['本期', currentValues, state.current, colors[0]],
    ['上期', previousValues, state.compare && state.previous, colors[1]],
  ]) {
    if (!enabled) continue;
    const points = values.map((value, i) => [
      58 + (i * 522) / Math.max(1, values.length - 1),
      216 - (value / max) * 188,
    ]);
    const d = points
      .map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`)
      .join(' ');
    if (state.trend === 'area')
      graphic += `<path d="${d} L${points.at(-1)?.[0] || 58} 216 L58 216 Z" fill="${color}" opacity=".1"/>`;
    graphic += `<path d="${d}" fill="none" stroke="${color}" stroke-width="2.4" ${series === '上期' ? 'stroke-dasharray="6 5"' : ''}/>`;
    graphic += points
      .map(([x, y], i) => {
        const row = series === '本期' ? rows[i] : previous[i];
        const text = `${series} · ${row.date}${row.end === row.date ? '' : ' 至 ' + row.end} · ${metric.label} ${metric.unit === '元' ? money(row.revenue) : integer(values[i]) + metric.unit}`;
        const attrs = pointAttrs(text, first);
        first = false;
        return `<circle ${attrs} cx="${x}" cy="${y}" r="5" fill="${color}" stroke="var(--panel)" stroke-width="2"/>`;
      })
      .join('');
  }
  graphic += '</svg>';
  return panel(
    'trend',
    `${metric.label}趋势`,
    '本期与紧邻上期对比 · 周汇总按所选范围每 7 天分组',
    `<div class="an-series">${legend('current', '本期', colors[0])}${state.compare ? legend('previous', '上期', colors[1]) : ''}<strong>${metric.unit === '元' ? money(snapshot.current.revenue) : integer(snapshot.current[state.metric]) + metric.unit}</strong></div>${!snapshot.daily.length ? empty() : !enabled ? empty('图例已全部隐藏', '点击上方图例重新显示序列。') : wrap(graphic, '趋势图')}${readout()}`,
    control(
      'trend',
      [
        ['line', '折线'],
        ['area', '面积'],
      ],
      '趋势图样式',
    ),
    'an-span-8',
  );
}
function orders(snapshot) {
  const rows = analyticsBuckets(snapshot.daily, 'week');
  const max = ceiling(
    rows.map((row) =>
      state.bars === 'stacked'
        ? (state.newOrders ? row.newOrders : 0) +
          (state.repeatOrders ? row.paid - row.newOrders : 0)
        : Math.max(
            state.newOrders ? row.newOrders : 0,
            state.repeatOrders ? row.paid - row.newOrders : 0,
          ),
    ),
  );
  const count = rows.length,
    step = 522 / Math.max(1, count),
    width = Math.min(34, step * 0.55);
  let graphic = svgOpen('新客与复购支付订单，每7天汇总，单位：单') + axes(max, [], '单'),
    first = true;
  rows.forEach((row, i) => {
    let bottom = 216;
    for (const [series, value, enabled, color, j] of [
      ['新客订单', row.newOrders, state.newOrders, colors[0], 0],
      ['复购订单', row.paid - row.newOrders, state.repeatOrders, colors[1], 1],
    ]) {
      if (!enabled) continue;
      const height = (value / max) * 188;
      const x =
        58 +
        i * step +
        step / 2 -
        width / 2 +
        (state.bars === 'grouped' ? (j ? width / 4 : -width / 4) : 0);
      const y = state.bars === 'stacked' ? bottom - height : 216 - height;
      const label = `${row.date} 至 ${row.end} · ${series} ${integer(value)}单`;
      graphic += `<rect ${height ? pointAttrs(label, first) : 'aria-hidden="true"'} x="${x}" y="${y}" width="${state.bars === 'grouped' ? width / 2 : width}" height="${height}" rx="2" fill="${color}"/>`;
      // A zero value still has a keyboard and pointer target at the baseline.
      if (!height)
        graphic += `<circle ${pointAttrs(label, first)} cx="${x + width / 2}" cy="216" r="5" fill="${color}"/>`;
      first = false;
      if (state.bars === 'stacked') bottom = y;
    }
    if (count <= 5 || i % 2 === 0 || i === count - 1)
      graphic += `<text class="an-axis" x="${58 + i * step + step / 2}" y="246" text-anchor="middle">${row.label}</text>`;
  });
  graphic += '</svg>';
  return panel(
    'orders',
    '订单构成',
    '新客订单 + 复购订单 = 支付订单 · 每7天汇总',
    `<div class="an-series">${legend('newOrders', '新客订单', colors[0])}${legend('repeatOrders', '复购订单', colors[1])}</div>${!snapshot.daily.length ? empty() : !state.newOrders && !state.repeatOrders ? empty('图例已全部隐藏', '点击图例显示订单序列。') : wrap(graphic, '订单柱状图')}${readout()}`,
    control(
      'bars',
      [
        ['stacked', '堆叠'],
        ['grouped', '分组'],
      ],
      '柱状图样式',
    ),
  );
}
function channels(snapshot) {
  const total = snapshot.current.revenue;
  let offset = 0;
  let graphic = svgOpen('渠道支付金额占比；选择扇区筛选渠道', '0 0 240 240');
  snapshot.channels.forEach((channel) => {
    const index = analyticsChannels.findIndex((item) => item.id === channel.id),
      fraction = total ? channel.revenue / total : 0;
    const label = `${channel.name} · ${money(channel.revenue)} · 占比 ${rate(channel.revenue, total)}，点击筛选`;
    const start = offset;
    offset += fraction;
    if (!fraction) return;
    const attrs = `data-an-channel="${channel.id}" role="button" tabindex="0" aria-label="${esc(label)}"`;
    if (state.pie === 'donut')
      graphic += `<circle ${attrs} cx="120" cy="120" r="79" pathLength="100" fill="none" stroke="${colors[index]}" stroke-width="31" stroke-dasharray="${fraction * 100} ${100 - fraction * 100}" stroke-dashoffset="${-start * 100}" transform="rotate(-90 120 120)"/>`;
    else if (fraction > 0.99999)
      graphic += `<circle ${attrs} cx="120" cy="120" r="96" fill="${colors[index]}"/>`;
    else {
      const a = start * Math.PI * 2 - Math.PI / 2,
        b = offset * Math.PI * 2 - Math.PI / 2;
      graphic += `<path ${attrs} d="M120 120 L${120 + 96 * Math.cos(a)} ${120 + 96 * Math.sin(a)} A96 96 0 ${fraction > 0.5 ? 1 : 0} 1 ${120 + 96 * Math.cos(b)} ${120 + 96 * Math.sin(b)} Z" fill="${colors[index]}" stroke="var(--panel)" stroke-width="2"/>`;
    }
  });
  if (state.pie === 'donut')
    graphic += `<text x="120" y="115" text-anchor="middle" class="an-donut-value">${compact(total / 100)}</text><text x="120" y="140" text-anchor="middle" class="an-axis">支付金额 / 元</text>`;
  graphic += '</svg>';
  const list = snapshot.channels
    .map(
      (channel) =>
        `<button type="button" data-an-channel="${channel.id}" class="an-channel-row" aria-label="筛选${channel.name}"><i style="--series:${colors[analyticsChannels.findIndex((item) => item.id === channel.id)]}"></i><span>${channel.name}<small>${money(channel.revenue)}</small></span><strong>${rate(channel.revenue, total)}</strong></button>`,
    )
    .join('');
  return panel(
    'channels',
    '渠道贡献',
    '点击扇区或渠道名称，联动筛选整页数据',
    !snapshot.daily.length
      ? empty()
      : !total
        ? empty('支付金额为 0，暂无占比', '零值不显示成占比相等的扇区。')
        : `<div class="an-donut-layout">${graphic}<div>${list}</div></div>`,
    control(
      'pie',
      [
        ['donut', '环形'],
        ['pie', '饼图'],
      ],
      '占比图样式',
    ),
  );
}
function ranking(snapshot) {
  const rows = [...snapshot.products].sort((a, b) => b.revenue - a.revenue),
    max = Math.max(1, ...rows.map((row) => row.revenue));
  return panel(
    'ranking',
    '商品收入排行',
    '按支付金额降序 · 与上方金额口径一致',
    !snapshot.daily.length
      ? empty()
      : `<div class="an-rank-list">${rows.map((row, i) => `<div class="an-rank"><span class="an-rank-number">${String(i + 1).padStart(2, '0')}</span><div><div><strong>${row.name}</strong><span>${money(row.revenue)}</span></div><div class="an-rank-track"><span style="width:${(row.revenue / max) * 100}%;background:${colors[i]}"></span></div><small>${integer(row.paid)} 单 · 金额占比 ${rate(row.revenue, snapshot.current.revenue)}</small></div></div>`).join('')}</div>`,
  );
}
function funnel(snapshot) {
  const t = snapshot.current;
  const rows = [
    ['访问会话', t.visits],
    ['浏览商品', t.viewed],
    ['发起结账', t.checkouts],
    ['完成支付', t.paid],
  ];
  let graphic = svgOpen('同一批模拟会话的支付漏斗，各阶段为会话数', '0 0 520 280');
  rows.forEach(([label, value], i) => {
    const width = t.visits ? (value / t.visits) * 460 : 0;
    const next = i < 3 && t.visits ? (rows[i + 1][1] / t.visits) * 460 : width;
    const left = (520 - width) / 2,
      right = left + width;
    const attrs = pointAttrs(
      `${label} ${integer(value)} · 占访问 ${rate(value, t.visits)} · ${i ? '上步转化 ' + rate(value, rows[i - 1][1]) : '起始阶段'}`,
      i === 0,
    );
    graphic += `<g ${attrs}>`;
    if (width)
      graphic += `<path d="M${left} ${i * 65 + 8} H${right} L${(520 + next) / 2} ${i * 65 + 61} H${(520 - next) / 2} Z" fill="${colors[i]}" opacity=".22"/>`;
    graphic += `<text x="260" y="${i * 65 + 30}" text-anchor="middle" class="an-funnel-label">${label} · ${integer(value)}</text><text x="260" y="${i * 65 + 50}" text-anchor="middle" class="an-axis">${i ? '上一步转化 ' + rate(value, rows[i - 1][1]) : '起点 ' + (t.visits ? '100%' : '—')}</text></g>`;
  });
  graphic += '</svg>';
  return panel(
    'funnel',
    '支付转化漏斗',
    '同一批模拟会话 · 每个会话最多产生一笔支付',
    !snapshot.daily.length ? empty() : wrap(graphic, '转化漏斗', 'an-funnel-plot') + readout(),
  );
}
function heatmap(snapshot) {
  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  const max = Math.max(1, ...snapshot.heatmap.flat());
  let graphic = svgOpen('每周星期与24小时支付订单分布，单位：单', '0 0 730 235');
  snapshot.heatmap.forEach((hours, day) => {
    graphic += `<text x="40" y="${42 + day * 25}" text-anchor="end" class="an-axis">${days[day]}</text>`;
    hours.forEach((value, hour) => {
      graphic += `<rect ${pointAttrs(`${days[day]} ${String(hour).padStart(2, '0')}:00–${String(hour).padStart(2, '0')}:59 · ${integer(value)}单`, day === 0 && hour === 0)} x="${51 + hour * 27}" y="${27 + day * 25}" width="23" height="21" rx="3" fill="${value ? 'var(--accent)' : 'var(--line)'}" fill-opacity="${value ? 0.15 + (value / max) * 0.85 : 0.6}"/>`;
    });
  });
  for (let hour = 0; hour < 24; hour += 3)
    graphic += `<text x="${62 + hour * 27}" y="16" text-anchor="middle" class="an-axis">${hour}:00</text>`;
  graphic += '</svg>';
  return panel(
    'heatmap',
    '订单活跃时段',
    '按星期与小时汇总 · 单位：单 · 北京时间模拟分配',
    !snapshot.daily.length
      ? empty()
      : wrap(graphic, '订单时段热力图', 'an-heatmap') +
          `<div class="an-heat-key"><span>较少</span>${[0.15, 0.4, 0.65, 1].map((opacity) => `<i style="opacity:${opacity}"></i>`).join('')}<span>较多 · 单格最高 ${integer(Math.max(...snapshot.heatmap.flat()))} 单</span></div>` +
          readout(),
    '',
    'an-span-7',
  );
}
function scatter(snapshot) {
  const rows = snapshot.daily.filter((row) => row.paid > 0);
  const maxX = ceiling(rows.map((row) => row.paid)),
    maxY = ceiling(rows.map((row) => row.revenue / row.paid / 100));
  const maxVisits = Math.max(1, ...rows.map((row) => row.visits));
  let graphic =
    svgOpen('每日支付订单与客单价散点图，点大小表示访问会话数') + axes(maxY, [], '客单价 / 元');
  [0, 1, 2, 3, 4].forEach((i) => {
    graphic += `<text class="an-axis" x="${58 + i * 130.5}" y="246" text-anchor="middle">${compact((i * maxX) / 4)}</text>`;
  });
  graphic += '<text class="an-axis" x="580" y="260" text-anchor="end">支付订单 / 单</text>';
  rows.forEach((row, i) => {
    const average = row.revenue / row.paid;
    graphic += `<circle ${pointAttrs(`${row.date} · ${integer(row.paid)}单 · 客单价 ${money(average)} · ${integer(row.visits)}个访问会话`, i === 0)} cx="${58 + (row.paid / maxX) * 522}" cy="${216 - (average / 100 / maxY) * 188}" r="${4 + Math.sqrt(row.visits / maxVisits) * 6}" fill="var(--accent)" fill-opacity=".38" stroke="var(--accent)" stroke-width="1.5"/>`;
  });
  graphic += '</svg>';
  return panel(
    'scatter',
    '订单与客单价',
    '每个点代表一天 · 点越大，访问会话越多',
    !snapshot.daily.length
      ? empty()
      : !rows.length
        ? empty('暂无可计算的客单价', '支付订单为 0 时不计算客单价。')
        : wrap(graphic, '订单客单价散点图') + readout(),
    '',
    'an-span-5',
  );
}
function goal(snapshot) {
  const target = state.target ?? snapshot.days * (snapshot.channel === 'all' ? 4 : 1) * 12500;
  const actual = snapshot.current.revenue / 100;
  const fraction = actual / target;
  const percent = snapshot.daily.length ? (fraction * 100).toFixed(1) + '%' : '—';
  const circumference = 2 * Math.PI * 76;
  return panel(
    'goal',
    '支付金额目标',
    '按当前筛选计算 · 可修改目标金额',
    `<div class="an-goal-ring">${svgOpen(`目标完成率 ${percent}`, '0 0 210 210', false)}<circle cx="105" cy="105" r="76" fill="none" stroke="var(--line)" stroke-width="15"/><circle cx="105" cy="105" r="76" fill="none" stroke="var(--accent)" stroke-width="15" stroke-linecap="round" stroke-dasharray="${Math.min(1, fraction) * circumference} ${circumference}" transform="rotate(-90 105 105)"/></svg><div><strong>${percent}</strong><span>${!snapshot.daily.length ? '暂无数据' : fraction >= 1 ? '已达成目标' : '目标完成率'}</span></div></div><div class="an-goal-values"><span>已完成<strong>${snapshot.daily.length ? money(snapshot.current.revenue) : '—'}</strong></span><span>${fraction >= 1 ? '超出目标' : '距目标'}<strong>${snapshot.daily.length ? money(Math.abs(target * 100 - snapshot.current.revenue)) : '—'}</strong></span></div><form id="an-goal-form"><label for="an-target">目标金额（元）${state.target === null ? ' · 自动参考值' : ' · 自定义值'}</label><div><input id="an-target" name="target" type="number" min="1" max="1000000000" step="1" required value="${target}" inputmode="numeric"><button class="btn" type="submit">设置</button></div></form><p class="an-small">${state.target === null ? '参考目标随天数和渠道数调整。' : '自定义目标在切换筛选时保留；重置可恢复。'}超过目标时圆环按 100% 绘制，数值保留实际比例。</p>`,
    '',
    'an-span-4',
  );
}
function detailTable(snapshot) {
  return `<details class="panel an-details" id="an-details"${state.details ? ' open' : ''}><summary>查看数据明细 <span>${snapshot.daily.length} 天 · CSV 与此表使用同一份筛选结果</span></summary><div class="table-scroll" role="region" aria-label="统计数据明细表，可横向滚动" tabindex="0"><table><caption class="an-small">${snapshot.start} 至 ${snapshot.end} · 金额单位：元</caption><thead><tr><th>日期</th><th>访问会话</th><th>商品浏览</th><th>发起结账</th><th>支付订单</th><th>新增用户</th><th>新客 / 复购订单</th><th>支付金额</th></tr></thead><tbody>${snapshot.daily.map((row) => `<tr><th scope="row">${row.date}</th><td>${integer(row.visits)}</td><td>${integer(row.viewed)}</td><td>${integer(row.checkouts)}</td><td>${integer(row.paid)}</td><td>${integer(row.signups)}</td><td>${row.newOrders} / ${row.paid - row.newOrders}</td><td>${money(row.revenue)}</td></tr>`).join('') || '<tr><td colspan="8">当前筛选没有数据</td></tr>'}</tbody>${snapshot.daily.length ? `<tfoot><tr><th scope="row">合计</th><td>${integer(snapshot.current.visits)}</td><td>${integer(snapshot.current.viewed)}</td><td>${integer(snapshot.current.checkouts)}</td><td>${integer(snapshot.current.paid)}</td><td>${integer(snapshot.current.signups)}</td><td>${snapshot.current.newOrders} / ${snapshot.current.paid - snapshot.current.newOrders}</td><td>${money(snapshot.current.revenue)}</td></tr></tfoot>` : ''}</table></div></details>`;
}
export function renderAnalytics() {
  const snapshot = analyticsSnapshot(state);
  return `<div class="analytics-page">${api.intro('统计分析', '从趋势到构成，让每一组数据都更清楚。', `<a class="btn" href="#analysis">${icon('activity')}联动与下钻</a><a class="btn" href="#charts">${icon('lucide:chart-line')}开源图表演示</a><span class="pill">8 类图表 · 本地模拟数据</span><button class="btn" type="button" data-an-export>${icon('download')}导出 CSV</button>`)}<section class="panel an-toolbar" aria-label="统计筛选"><label>时间范围<select id="an-days" aria-label="统计时间范围">${[7, 30, 90].map((days) => `<option value="${days}"${state.days === days ? ' selected' : ''}>最近 ${days} 天</option>`).join('')}</select></label><label>来源渠道<select id="an-channel" aria-label="统计来源渠道"><option value="all">全部渠道</option>${analyticsChannels.map((channel) => `<option value="${channel.id}"${selection('channel', channel.id)}>${channel.name}</option>`).join('')}</select></label><label>趋势指标<select id="an-metric" aria-label="趋势统计指标">${Object.entries(
    metrics,
  )
    .map(
      ([key, metric]) =>
        `<option value="${key}"${selection('metric', key)}>${metric.label}</option>`,
    )
    .join(
      '',
    )}</select></label><label>趋势粒度<select id="an-group" aria-label="趋势汇总粒度"><option value="day"${selection('group', 'day')}>按日</option><option value="week"${selection('group', 'week')}>每7天</option></select></label><label class="an-check"><input type="checkbox" id="an-compare"${state.compare ? ' checked' : ''}>对比上期</label><label>数据示例<select id="an-sample" aria-label="统计数据示例">${[
    ['normal', '正常数据'],
    ['empty', '无数据'],
    ['zero', '全零数据'],
  ]
    .map(([key, text]) => `<option value="${key}"${selection('sample', key)}>${text}</option>`)
    .join(
      '',
    )}</select></label><button class="btn subtle" type="button" data-an-reset>${icon('history')}重置</button></section><div class="an-context" role="status"><span>${icon('lucide:calendar')}<strong>${snapshot.start} — ${snapshot.end}</strong><span>${snapshot.days} 天 · ${analyticsChannels.find((channel) => channel.id === state.channel)?.name || '全部渠道'}</span></span><span>上期 ${snapshot.previousStart} — ${snapshot.prior.at(-1)?.date || new Date(Date.parse(snapshot.start + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10)}</span></div>${kpis(snapshot)}<div class="an-grid">${trend(snapshot)}${goal(snapshot)}${orders(snapshot)}${channels(snapshot)}${ranking(snapshot)}${funnel(snapshot)}${heatmap(snapshot)}${scatter(snapshot)}</div>${detailTable(snapshot)}<section class="an-notes"><h2>读图与使用</h2><p>图例仅控制对应图表的显示；渠道筛选联动整页。图形支持鼠标、触摸和键盘操作，数据明细与 CSV 提供精确数值。支付金额为模拟支付流水，客单价 = 支付金额 ÷ 支付订单，转化率 = 支付订单 ÷ 访问会话数；上期为紧邻本期、天数相同的区间。</p><p>固定演示快照截至 2026-10-23，按北京时间演示日与时段分布。图表使用本地 SVG；接入真实后台时需由服务端提供经过权限过滤、口径一致的统计数据。</p></section></div>`;
}
function refresh(focus) {
  if (api.getView() !== 'analytics') return;
  document.getElementById('view').innerHTML =
    `<div class="view-animate">${renderAnalytics()}</div>`;
  document.querySelector('.analytics-page h1')?.setAttribute('tabindex', '-1');
  if (focus) document.querySelector(focus)?.focus({ preventScroll: true });
}
function inspect(point) {
  const card = point.closest('[data-an-card]');
  const output = card?.querySelector('.an-readout');
  if (output) output.textContent = point.dataset.anPoint;
  card?.querySelectorAll('[data-an-point]').forEach((other) => {
    other.setAttribute('tabindex', other === point ? '0' : '-1');
    other.classList.toggle('an-selected', other === point);
  });
}
export function initAnalytics({ intro, esc, toast, getView }) {
  api = Object.freeze({ intro, esc, toast, getView });
  document.addEventListener('change', (event) => {
    if (getView() !== 'analytics') return;
    const { id, value, checked } = event.target;
    const fields = {
      'an-days': ['days', [7, 30, 90], Number(value)],
      'an-channel': ['channel', ['all', ...analyticsChannels.map((channel) => channel.id)], value],
      'an-metric': ['metric', Object.keys(metrics), value],
      'an-group': ['group', ['day', 'week'], value],
      'an-sample': ['sample', ['normal', 'empty', 'zero'], value],
    };
    const field = fields[id];
    if (field && field[1].includes(field[2])) {
      state[field[0]] = field[2];
      refresh('#' + id);
    } else if (id === 'an-compare') {
      state.compare = checked;
      if (checked) state.previous = true;
      refresh('#an-compare');
    }
  });
  document.addEventListener('submit', (event) => {
    if (getView() !== 'analytics' || event.target.id !== 'an-goal-form') return;
    event.preventDefault();
    const input = document.getElementById('an-target'),
      value = Number(input.value);
    if (!Number.isInteger(value) || value < 1 || value > 1000000000) {
      input.reportValidity();
      return;
    }
    state.target = value;
    refresh('#an-target');
    toast('已更新当前统计目标');
  });
  document.addEventListener(
    'toggle',
    (event) => {
      if (event.target.id === 'an-details') state.details = event.target.open;
    },
    true,
  );
  document.addEventListener('pointerover', (event) => {
    if (getView() === 'analytics') {
      const point = event.target.closest('[data-an-point]');
      if (point) inspect(point);
    }
  });
  document.addEventListener('focusin', (event) => {
    if (getView() === 'analytics' && event.target.matches('[data-an-point]')) inspect(event.target);
  });
  document.addEventListener('keydown', (event) => {
    if (getView() !== 'analytics' || !event.target.matches('[data-an-point],[data-an-channel]'))
      return;
    if (['Enter', ' '].includes(event.key)) {
      event.preventDefault();
      event.target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      return;
    }
    if (
      !event.target.matches('[data-an-point]') ||
      !['ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)
    )
      return;
    event.preventDefault();
    const points = [...event.target.closest('[data-an-card]').querySelectorAll('[data-an-point]')],
      index = points.indexOf(event.target);
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? points.length - 1
          : (index + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + points.length) %
            points.length;
    points[next].focus();
  });
  document.addEventListener('click', (event) => {
    if (getView() !== 'analytics') return;
    const point = event.target.closest('[data-an-point]');
    if (point) {
      inspect(point);
      return;
    }
    const channel = event.target.closest('[data-an-channel]');
    if (channel && analyticsChannels.some((item) => item.id === channel.dataset.anChannel)) {
      state.channel = channel.dataset.anChannel;
      refresh('#an-channel');
      return;
    }
    const toggle = event.target.closest('[data-an-toggle]');
    if (
      toggle &&
      ['current', 'previous', 'newOrders', 'repeatOrders'].includes(toggle.dataset.anToggle)
    ) {
      state[toggle.dataset.anToggle] = !state[toggle.dataset.anToggle];
      refresh(`[data-an-toggle="${toggle.dataset.anToggle}"]`);
      return;
    }
    const setting = event.target.closest('[data-an-setting]');
    if (
      setting &&
      { trend: ['line', 'area'], bars: ['stacked', 'grouped'], pie: ['donut', 'pie'] }[
        setting.dataset.anSetting
      ]?.includes(setting.dataset.anValue)
    ) {
      state[setting.dataset.anSetting] = setting.dataset.anValue;
      refresh(
        `[data-an-setting="${setting.dataset.anSetting}"][data-an-value="${setting.dataset.anValue}"]`,
      );
      return;
    }
    if (event.target.closest('[data-an-reset]')) {
      Object.assign(state, {
        days: 30,
        channel: 'all',
        sample: 'normal',
        metric: 'revenue',
        group: 'day',
        trend: 'area',
        bars: 'stacked',
        pie: 'donut',
        compare: true,
        current: true,
        previous: true,
        newOrders: true,
        repeatOrders: true,
        target: null,
      });
      refresh('#an-days');
      return;
    }
    if (event.target.closest('[data-an-export]')) {
      try {
        const snapshot = analyticsSnapshot(state),
          csv = analyticsCsv(snapshot),
          url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `nova-analytics-demo-${snapshot.days}d-${snapshot.channel}.csv`;
        anchor.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        toast('当前筛选的统计数据已导出（模拟数据）');
      } catch {
        toast('浏览器未能导出，请重试或查看数据明细', 'error');
      }
    }
  });
}
