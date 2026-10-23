// Independent synthetic fixtures: never reads or writes editable business records.
export const analysisScenarios = [
  {
    id: 'sales',
    title: '经营收入',
    icon: 'lucide:chart-column',
    description: '从区域表现定位城市与商品，追踪支付、订单与退款。',
    dimensions: [
      { key: 'region', label: '区域' },
      { key: 'city', label: '城市' },
      { key: 'product', label: '商品' },
    ],
    metrics: [
      { id: 'revenue', label: '支付金额', unit: '元' },
      { id: 'orders', label: '支付订单', unit: '笔' },
      { id: 'refunds', label: '退款金额', unit: '元' },
    ],
    columns: [
      '模拟订单',
      '日期',
      '区域',
      '城市',
      '商品',
      '渠道',
      '状态',
      '支付金额（元）',
      '退款金额（元）',
    ],
    detail: '订单样本',
  },
  {
    id: 'growth',
    title: '用户转化',
    icon: 'users',
    description: '按渠道、推广活动和终端追踪访问、注册与付费。',
    dimensions: [
      { key: 'channel', label: '渠道' },
      { key: 'campaign', label: '活动' },
      { key: 'device', label: '终端' },
    ],
    metrics: [
      { id: 'visits', label: '访问会话', unit: '次' },
      { id: 'signups', label: '注册会话', unit: '次' },
      { id: 'paid', label: '付费会话', unit: '次' },
    ],
    columns: ['日期', '渠道', '活动', '终端', '访问会话', '注册会话', '付费会话'],
    detail: '每日转化队列',
  },
  {
    id: 'ops',
    title: '服务监控',
    icon: 'activity',
    description: '定位服务、接口与实例，联动请求量、错误率和响应时间。',
    dimensions: [
      { key: 'service', label: '服务' },
      { key: 'endpoint', label: '接口' },
      { key: 'instance', label: '实例' },
    ],
    metrics: [
      { id: 'requests', label: '请求量', unit: '次' },
      { id: 'errors', label: '错误请求', unit: '次' },
      { id: 'latency', label: '平均响应', unit: 'ms' },
    ],
    columns: ['北京时间', '服务', '接口', '实例', '请求量', '错误请求', '平均响应（ms）'],
    detail: '每分钟接口样本',
  },
];
const day = 86400000,
  end = Date.UTC(2026, 9, 23),
  opsEnd = end + 10 * 3600000;
const regions = [
  ['华东', '上海', '杭州'],
  ['华南', '广州', '深圳'],
  ['华北', '北京', '天津'],
  ['西南', '成都', '重庆'],
];
const products = ['办公设备', '文创用品', '生活家居', '数码配件', '订阅服务'];
const channels = ['自然访问', '搜索推广', '社交媒体', '合作渠道'];
const services = [
  ['订单服务', '/orders', '/payments'],
  ['用户服务', '/login', '/profiles'],
  ['商品服务', '/products', '/inventory'],
  ['任务服务', '/jobs', '/callbacks'],
];
const devices = ['桌面端', '移动端', '小程序'];
const sum = (rows, key) => rows.reduce((n, row) => n + (row[key] || 0), 0);
const beijing = (time) => new Date(time + 8 * 3600000).toISOString().slice(0, 16).replace('T', ' ');
function sale(i, period) {
  const r = regions[i % 4],
    p = (i * 7 + Math.floor(i / 4)) % 5;
  const amount = [29900, 12900, 9900, 19900, 5900][p] + (i % 7) * 100;
  const refunded = i % 17 === 0;
  return {
    id: 'DEMO-' + String(i + 1).padStart(6, '0'),
    period,
    region: r[0],
    city: r[1 + (Math.floor(i / 4) % 2)],
    product: products[p],
    channel: channels[Math.floor(i / 3) % 4],
    status: refunded ? '已退款' : i % 3 ? '已完成' : '已支付',
    revenue: amount,
    orders: 1,
    refunds: refunded ? amount : 0,
  };
}
const sales = Array.from({ length: 90 * 48 }, (_, i) =>
  sale(i, new Date(end - (89 - Math.floor(i / 48)) * day).toISOString().slice(0, 10)),
);
const growth = Array.from({ length: 90 * 24 }, (_, i) => {
  const c = Math.floor(i / 6) % 4,
    a = Math.floor(i / 3) % 2,
    d = i % 3;
  const visits = 150 + ((i * 37) % 240),
    signups = Math.floor(visits * (0.15 + c * 0.025 + d * 0.01));
  return {
    period: new Date(end - (89 - Math.floor(i / 24)) * day).toISOString().slice(0, 10),
    channel: channels[c],
    campaign: channels[c] + ['·常规计划', '·秋季活动'][a],
    device: devices[d],
    visits,
    signups,
    paid: Math.floor(signups * (0.24 + a * 0.06)),
  };
});
let cache = new Map();
export function analysisRecords(scenario = 'sales', revision = 0) {
  revision = Math.max(0, Math.floor(Number(revision) || 0));
  const cached = cache.get(scenario);
  if (cached?.revision === revision) return cached.rows;
  let rows;
  if (scenario === 'growth')
    rows = growth.map((row, i) => {
      if (i < growth.length - 24) return { ...row };
      const visits = row.visits + revision * (5 + (i % 4)),
        signups = row.signups + revision,
        paid = row.paid + Math.floor(revision / 2);
      return { ...row, visits, signups, paid };
    });
  else if (scenario === 'ops')
    rows = Array.from({ length: 60 * 16 }, (_, i) => {
      const minute = revision - 59 + Math.floor(i / 16),
        s = Math.floor(i / 4) % 4,
        e = Math.floor(i / 2) % 2;
      const requests = 160 + (((minute + 12000) * 19 + i * 13) % 280);
      const errors =
        (minute + s * 7 + 12000) % 19 < 3
          ? Math.floor(requests * (0.03 + e * 0.02))
          : i % 5 === 0
            ? 1
            : 0;
      const latency =
        45 + (((minute + 12000) * 11 + s * 43 + e * 17) % 190) + (errors > 3 ? 130 : 0);
      return {
        period: beijing(opsEnd + minute * 60000),
        service: services[s][0],
        endpoint: services[s][e + 1],
        instance: services[s][0] + '-' + (i % 2 ? '02' : '01'),
        requests,
        errors,
        latencyTotal: latency * requests,
      };
    });
  else
    rows = [
      ...sales.map((row) => ({ ...row })),
      ...Array.from({ length: revision }, (_, i) => sale(sales.length + i, '2026-10-23')),
    ];
  rows.forEach(Object.freeze);
  Object.freeze(rows);
  cache.set(scenario, { revision, rows });
  return rows;
}
export function aggregateAnalysis(rows) {
  const value = Object.fromEntries(
    [
      'revenue',
      'orders',
      'refunds',
      'visits',
      'signups',
      'paid',
      'requests',
      'errors',
      'latencyTotal',
    ].map((key) => [key, sum(rows, key)]),
  );
  value.latency = value.requests ? value.latencyTotal / value.requests : 0;
  return value;
}
export function analysisValue(total, metric) {
  return ['revenue', 'refunds'].includes(metric) ? total[metric] / 100 : total[metric] || 0;
}
export function analysisSnapshot(input = {}) {
  const scenario = analysisScenarios.find((s) => s.id === input.scenario) || analysisScenarios[0];
  const days = [7, 30, 90].includes(Number(input.days)) ? Number(input.days) : 30;
  const metric = scenario.metrics.find((m) => m.id === input.metric) || scenario.metrics[0];
  const raw = analysisRecords(scenario.id, input.revision);
  const periods =
    scenario.id === 'ops'
      ? [...new Set(raw.map((r) => r.period))]
      : Array.from({ length: days }, (_, i) =>
          new Date(end - (days - i - 1) * day).toISOString().slice(0, 10),
        );
  const path = [];
  let scoped = raw.filter((r) => r.period >= periods[0] && r.period <= periods.at(-1));
  for (const part of (Array.isArray(input.path) ? input.path : []).slice(0, 3)) {
    if (
      part.key !== scenario.dimensions[path.length].key ||
      !scoped.some((r) => r[part.key] === part.value)
    )
      break;
    path.push({ key: part.key, value: part.value });
    scoped = scoped.filter((r) => r[part.key] === part.value);
  }
  const dimension = scenario.dimensions[path.length] || null;
  const selected =
    dimension && scoped.some((r) => r[dimension.key] === input.selected) ? input.selected : null;
  const range =
    Array.isArray(input.range) &&
    input.range.length === 2 &&
    input.range.every((v) => typeof v === 'string') &&
    input.range[0] <= input.range[1]
      ? [...input.range]
      : null;
  const inRange = (row) => !range || (row.period >= range[0] && row.period <= range[1]);
  const sample = ['empty', 'zero'].includes(input.sample) ? input.sample : 'normal';
  if (sample === 'empty') scoped = [];
  if (sample === 'zero')
    scoped = scoped.map((r) => ({
      ...r,
      ...Object.fromEntries(
        [
          'revenue',
          'orders',
          'refunds',
          'visits',
          'signups',
          'paid',
          'requests',
          'errors',
          'latencyTotal',
        ].map((k) => [k, 0]),
      ),
    }));
  const rows = scoped.filter((r) => inRange(r) && (!selected || r[dimension.key] === selected));
  const totals = aggregateAnalysis(rows);
  const groups = dimension
    ? [...new Set(scoped.map((r) => r[dimension.key]))]
        .map((key) => {
          const items = scoped.filter((r) => r[dimension.key] === key && inRange(r));
          return {
            key,
            count: items.length,
            totals: aggregateAnalysis(items),
            value: analysisValue(aggregateAnalysis(items), metric.id),
          };
        })
        .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key, 'zh-CN'))
    : [];
  const trend = periods.map((period) => {
    const all = scoped.filter((r) => r.period === period),
      focus = selected ? all.filter((r) => r[dimension.key] === selected) : all;
    return {
      period,
      value: analysisValue(aggregateAnalysis(focus), metric.id),
      baseline: analysisValue(aggregateAnalysis(all), metric.id),
    };
  });
  const composition =
    scenario.id === 'growth'
      ? [
          { key: 'visits', name: '访问会话', value: totals.visits },
          { key: 'signups', name: '注册会话', value: totals.signups },
          { key: 'paid', name: '付费会话', value: totals.paid },
        ]
      : scenario.id === 'ops'
        ? [
            { name: '成功请求', value: totals.requests - totals.errors },
            { name: '错误请求', value: totals.errors },
          ]
        : channels.map((name) => ({
            name,
            value: aggregateAnalysis(rows.filter((r) => r.channel === name)).revenue / 100,
          }));
  const details = [...rows]
    .reverse()
    .map((r) =>
      scenario.id === 'sales'
        ? [
            r.id,
            r.period,
            r.region,
            r.city,
            r.product,
            r.channel,
            r.status,
            r.revenue / 100,
            r.refunds / 100,
          ]
        : scenario.id === 'growth'
          ? [r.period, r.channel, r.campaign, r.device, r.visits, r.signups, r.paid]
          : [
              r.period,
              r.service,
              r.endpoint,
              r.instance,
              r.requests,
              r.errors,
              Number((r.requests ? r.latencyTotal / r.requests : 0).toFixed(2)),
            ],
    );
  return {
    scenario,
    metric,
    days,
    path,
    dimension,
    selected,
    range,
    sample,
    periods,
    rows,
    totals,
    groups,
    trend,
    composition,
    columns: scenario.columns,
    details,
  };
}
export function analysisExport(snapshot) {
  return {
    title: snapshot.scenario.title + ' · 模拟数据',
    description: [
      '范围：' + (snapshot.range || [snapshot.periods[0], snapshot.periods.at(-1)]).join(' 至 '),
      ...snapshot.path.map((p) => p.value),
      snapshot.selected || '全部分组',
    ].join(' / '),
    columns: snapshot.columns,
    rows: snapshot.details,
  };
}
