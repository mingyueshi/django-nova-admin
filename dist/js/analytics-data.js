// Deterministic synthetic cohorts, independent of the demo's editable records.
export const analyticsChannels = [
  { id: 'organic', name: '自然访问' },
  { id: 'search', name: '搜索推广' },
  { id: 'social', name: '社交媒体' },
  { id: 'partner', name: '合作渠道' },
];
export const analyticsProducts = ['办公设备', '文创用品', '生活家居', '数码配件', '订阅服务'];
const end = Date.UTC(2026, 9, 23);
const dayMs = 86400000;
const sum = (values) => values.reduce((total, value) => total + value, 0);
export function allocate(total, weights) {
  const denominator = sum(weights);
  if (!denominator) return weights.map(() => 0);
  const exact = weights.map((weight) => (total * weight) / denominator);
  const values = exact.map(Math.floor);
  const priority = exact.map((value, i) => [value - values[i], i]).sort((a, b) => b[0] - a[0]);
  const remainder = total - sum(values);
  for (let i = 0; i < remainder; i++) values[priority[i][1]]++;
  return values;
}
const source = Array.from({ length: 180 }, (_, i) => {
  const date = new Date(end - (179 - i) * dayMs).toISOString().slice(0, 10);
  const weekday = new Date(date + 'T00:00:00Z').getUTCDay();
  return analyticsChannels.map((channel, c) => {
    const visits = Math.round(
      (760 + i * 2 + Math.sin(i * 0.65 + c) * 140 + (weekday === 0 || weekday === 6 ? -100 : 50)) *
        [1.25, 0.92, 0.7, 0.48][c],
    );
    const viewed = Math.floor(visits * (0.6 + c * 0.025));
    const checkouts = Math.floor(viewed * (0.19 + Math.sin(i / 4 + c) * 0.025));
    const paid = Math.floor(checkouts * (0.72 + Math.cos(i / 8 + c) * 0.045));
    const productOrders = allocate(paid, [34 + c * 3, 22, 18, 17 - c * 2, 9]);
    const productRevenue = productOrders.map(
      (orders, p) =>
        orders *
        Math.round([29900, 12900, 9900, 19900, 5900][p] * (1 + Math.sin(i / 6 + c) * 0.12)),
    );
    return {
      date,
      channel: channel.id,
      visits,
      viewed,
      checkouts,
      paid,
      signups: Math.floor(visits * (0.12 + c * 0.015)),
      newOrders: Math.floor(paid * (0.66 - c * 0.05)),
      revenue: sum(productRevenue),
      productOrders,
      productRevenue,
    };
  });
}).flat();
const totals = (rows) =>
  Object.fromEntries(
    ['visits', 'viewed', 'checkouts', 'paid', 'signups', 'newOrders', 'revenue'].map((key) => [
      key,
      sum(rows.map((row) => row[key])),
    ]),
  );
const byDay = (rows) =>
  [...new Set(rows.map((row) => row.date))].map((date) => ({
    date,
    ...totals(rows.filter((row) => row.date === date)),
  }));
export function percentChange(current, previous) {
  return previous === 0 ? null : ((current - previous) / previous) * 100;
}
export function analyticsSnapshot({ days = 30, channel = 'all', sample = 'normal' } = {}) {
  days = [7, 30, 90].includes(Number(days)) ? Number(days) : 30;
  channel = analyticsChannels.some((item) => item.id === channel) ? channel : 'all';
  sample = ['normal', 'empty', 'zero'].includes(sample) ? sample : 'normal';
  const selected = source
    .filter((row) => channel === 'all' || row.channel === channel)
    .map((row) =>
      sample === 'zero'
        ? {
            ...row,
            ...Object.fromEntries(Object.keys(totals([row])).map((key) => [key, 0])),
            productOrders: [0, 0, 0, 0, 0],
            productRevenue: [0, 0, 0, 0, 0],
          }
        : row,
    );
  const cutoff = new Date(end - (days - 1) * dayMs).toISOString().slice(0, 10);
  const previousStart = new Date(end - (days * 2 - 1) * dayMs).toISOString().slice(0, 10);
  const current = sample === 'empty' ? [] : selected.filter((row) => row.date >= cutoff);
  const previous =
    sample === 'empty'
      ? []
      : selected.filter((row) => row.date >= previousStart && row.date < cutoff);
  const daily = byDay(current),
    prior = byDay(previous);
  const heatmap = Array.from({ length: 7 }, () => Array(24).fill(0));
  for (const row of current) {
    const weekday = (new Date(row.date + 'T00:00:00Z').getUTCDay() + 6) % 7;
    const hours = allocate(
      row.paid,
      Array.from(
        { length: 24 },
        (_, hour) =>
          1 + Math.exp(-((hour - 11) ** 2) / 12) * 6 + Math.exp(-((hour - 20) ** 2) / 9) * 9,
      ),
    );
    hours.forEach((value, hour) => {
      heatmap[weekday][hour] += value;
    });
  }
  return {
    days,
    channel,
    sample,
    start: cutoff,
    end: '2026-10-23',
    previousStart,
    current: totals(current),
    previous: totals(previous),
    daily,
    prior,
    heatmap,
    channels: analyticsChannels
      .filter((item) => channel === 'all' || item.id === channel)
      .map((item) => ({ ...item, ...totals(current.filter((row) => row.channel === item.id)) })),
    products: analyticsProducts.map((name, p) => ({
      name,
      revenue: sum(current.map((row) => row.productRevenue[p])),
      paid: sum(current.map((row) => row.productOrders[p])),
    })),
  };
}
export function analyticsBuckets(rows, group = 'day') {
  if (group !== 'week')
    return rows.map((row) => ({ ...row, label: row.date.slice(5), end: row.date }));
  const buckets = [];
  for (let i = 0; i < rows.length; i += 7) {
    const part = rows.slice(i, i + 7);
    buckets.push({
      date: part[0].date,
      end: part.at(-1).date,
      label: part[0].date.slice(5),
      ...totals(part),
    });
  }
  return buckets;
}
export function analyticsCsv(snapshot) {
  const rows = [
    ['NOVA 统计分析（模拟数据）'],
    ['时间范围', snapshot.start, snapshot.end],
    ['渠道', analyticsChannels.find((item) => item.id === snapshot.channel)?.name || '全部渠道'],
    ['数据示例', { normal: '正常数据', zero: '全零数据', empty: '无数据' }[snapshot.sample]],
    [
      '日期',
      '访问会话数',
      '商品浏览会话数',
      '发起结账会话数',
      '支付订单数',
      '新增用户数',
      '新客订单数',
      '复购订单数',
      '支付金额（元）',
    ],
    ...snapshot.daily.map((row) => [
      row.date,
      row.visits,
      row.viewed,
      row.checkouts,
      row.paid,
      row.signups,
      row.newOrders,
      row.paid - row.newOrders,
      (row.revenue / 100).toFixed(2),
    ]),
  ];
  return (
    '\uFEFF' +
    rows
      .map((row) =>
        row
          .map(
            (value) =>
              '"' +
              String(value)
                .replace(/^[=+@-]/, "'$&")
                .replaceAll('"', '""') +
              '"',
          )
          .join(','),
      )
      .join('\r\n')
  );
}
