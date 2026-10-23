import {
  analyticsChannels,
  analyticsSnapshot,
  analyticsBuckets,
  allocate,
} from './analytics-data.js';
export const chartProviders = [
  {
    id: 'echarts',
    name: 'Apache ECharts',
    version: '6.1.0',
    license: 'Apache-2.0',
    global: 'echarts',
    script: './vendor/charts/echarts/echarts.min.js',
    docs: 'https://echarts.apache.org/handbook/en/get-started/',
    description: '经营报表、关系流向、分布与复杂分析。',
  },
  {
    id: 'chartjs',
    name: 'Chart.js',
    version: '4.6.1',
    license: 'MIT',
    global: 'Chart',
    script: './vendor/charts/chartjs/chart.umd.min.js',
    docs: 'https://www.chartjs.org/docs/latest/',
    description: '常规报表、多轴组合与交互图例。',
  },
  {
    id: 'uplot',
    name: 'uPlot',
    version: '1.6.32',
    license: 'MIT',
    global: 'uPlot',
    script: './vendor/charts/uplot/uPlot.iife.min.js',
    css: './vendor/charts/uplot/uPlot.min.css',
    docs: 'https://github.com/leeoniya/uPlot/tree/master/docs',
    description: '运维监控、时序缩放与模拟数据回放。',
  },
];
export const chartScenes = [
  ['trend', '支付金额趋势', '经营分析', '折线 / 面积', 'chart-line', ['echarts', 'chartjs']],
  ['orders', '新客与复购订单', '经营分析', '堆叠柱状', 'chart-column', ['echarts', 'chartjs']],
  ['channels', '渠道收入贡献', '经营分析', '环形占比', 'chart-pie', ['echarts', 'chartjs']],
  ['mixed', '金额与订单对照', '经营分析', '双轴组合', 'chart-column', ['echarts', 'chartjs']],
  ['funnel', '支付转化漏斗', '用户运营', '漏斗', 'funnel', ['echarts']],
  ['products', '商品收入结构', '经营分析', '矩形树图', 'package', ['echarts']],
  ['radar', '渠道转化画像', '用户运营', '雷达', 'users', ['echarts', 'chartjs']],
  ['heatmap', '星期与时段活跃度', '用户运营', '热力图', 'calendar', ['echarts']],
  ['sankey', '渠道与商品流向', '用户运营', '桑基图', 'network', ['echarts']],
  ['scatter', '订单与客单价', '经营分析', '散点 / 气泡', 'chart-line', ['echarts', 'chartjs']],
  ['waterfall', '收支与结余构成', '经营分析', '瀑布 / 浮动柱', 'wallet', ['echarts', 'chartjs']],
  ['boxplot', '接口响应分布', '系统运维', '箱线图', 'server', ['echarts']],
  ['goal', '支付金额目标', '经营分析', '仪表盘', 'badge-check', ['echarts']],
  ['ops-latency', 'P95 / P99 响应延迟', '系统运维', '时序折线', 'chart-line', ['echarts', 'uplot']],
  ['ops-resources', 'CPU 与内存使用率', '系统运维', '百分比时序', 'cpu', ['echarts', 'uplot']],
  ['ops-throughput', '吞吐量与错误率', '系统运维', '双轴时序', 'network', ['echarts', 'uplot']],
  ['ops-queue', '任务队列积压', '系统运维', '队列时序', 'clipboard-list', ['echarts', 'uplot']],
].map(([id, title, category, kind, icon, libraries]) => ({
  id,
  title,
  category,
  kind,
  icon: 'lucide:' + icon,
  libraries,
}));
const sum = (values) => values.reduce((a, b) => a + b, 0);
const round = (value, digits = 2) => Number(value.toFixed(digits));
const zeroExample = (example) => {
  if (example.sample !== 'zero') return example;
  for (const series of example.series || []) series.values = series.values.map(() => 0);
  if (example.boxes) example.boxes = example.boxes.map((box) => box.map(() => 0));
  example.rows = example.rows.map((row) =>
    row.map((value, i) => (i === 0 ? value : typeof value === 'number' ? 0 : value)),
  );
  return example;
};
export function createChartExample(id, filters = {}) {
  const scene = chartScenes.find((item) => item.id === id) || chartScenes[0];
  const sample = ['normal', 'zero', 'empty'].includes(filters.sample) ? filters.sample : 'normal';
  const snapshot = scene.id.startsWith('ops-') ? null : analyticsSnapshot({ ...filters, sample });
  const base = {
    id: scene.id,
    title: scene.title,
    category: scene.category,
    kind: scene.kind,
    sample,
    columns: [],
    rows: [],
    labels: [],
    series: [],
    description: '固定合成数据；筛选会同步更新图形、表格和导出。',
  };
  const currency = (cents) => round(cents / 100),
    ratio = (n, d) => (d ? round((n / d) * 100) : 0);
  if (scene.id.startsWith('ops-')) {
    const hours = [1, 6, 24].includes(Number(filters.hours)) ? Number(filters.hours) : 6;
    const count = hours === 1 ? 60 : hours === 6 ? 180 : 288,
      step = (hours * 3600) / (count - 1),
      tick = Math.max(0, Number(filters.tick) || 0);
    const end = Date.UTC(2026, 9, 23, 10) / 1000 + tick * 60;
    base.timestamps = Array.from({ length: count }, (_, i) =>
      Math.round(end - (count - 1 - i) * step),
    );
    base.labels = base.timestamps.map((t) =>
      new Date((t + 28800) * 1000).toISOString().slice(11, 16),
    );
    const n = filters.seed || 0;
    const wave = Array.from({ length: count }, (_, i) => i + tick + n * 13);
    const records = {
      'ops-latency': [
        ['P95', 'ms', wave.map((i) => round(80 + Math.sin(i / 8) * 22 + (i % 47 > 42 ? 55 : 0)))],
        ['P99', 'ms', wave.map((i) => round(130 + Math.sin(i / 8) * 28 + (i % 47 > 42 ? 95 : 0)))],
      ],
      'ops-resources': [
        ['CPU', '%', wave.map((i) => round(42 + Math.sin(i / 11) * 18 + (i % 59 > 55 ? 20 : 0)))],
        ['内存', '%', wave.map((i) => round(64 + Math.sin(i / 24) * 6))],
      ],
      'ops-throughput': [
        ['吞吐量', 'req/s', wave.map((i) => round(550 + Math.sin(i / 13) * 180))],
        [
          '错误率',
          '%',
          wave.map((i) => round(0.3 + Math.abs(Math.sin(i / 17)) * 0.7 + (i % 47 > 42 ? 1.4 : 0))),
        ],
      ],
      'ops-queue': [
        [
          '待处理任务',
          '个',
          wave.map((i) => Math.round(170 + Math.sin(i / 12) * 100 + (i % 61 > 54 ? 180 : 0))),
        ],
        ['处理中任务', '个', wave.map((i) => Math.round(45 + Math.sin(i / 9) * 15))],
      ],
    }[scene.id];
    base.series = records.map(([name, unit, values]) => ({
      name,
      unit,
      values: sample === 'zero' ? values.map(() => 0) : values,
    }));
    base.columns = ['时间（北京时间）', ...base.series.map((s) => `${s.name}（${s.unit}）`)];
    base.rows = base.timestamps.map((t, i) => [
      new Date((t + 28800) * 1000).toISOString().replace('T', ' ').slice(0, 19),
      ...base.series.map((s) => s.values[i]),
    ]);
    base.description = `最近 ${hours} 小时 · ${count} 个采样点 · 北京时间合成快照；回放每次向前推进1分钟，不连接实时监控。`;
    if (sample === 'empty') {
      base.timestamps = [];
      base.labels = [];
      base.series.forEach((s) => (s.values = []));
      base.rows = [];
    }
    return base;
  }
  if (scene.id === 'trend' || scene.id === 'mixed') {
    base.labels = snapshot.daily.map((row) => row.date);
    base.series =
      scene.id === 'trend'
        ? [
            {
              name: '本期金额',
              unit: '元',
              values: snapshot.daily.map((row) => currency(row.revenue)),
            },
            {
              name: '上期金额',
              unit: '元',
              values: snapshot.prior.map((row) => currency(row.revenue)),
            },
          ]
        : [
            {
              name: '支付金额',
              unit: '元',
              values: snapshot.daily.map((row) => currency(row.revenue)),
            },
            { name: '支付订单', unit: '单', values: snapshot.daily.map((row) => row.paid) },
          ];
    base.columns = ['本期日期', ...base.series.map((s) => `${s.name}（${s.unit}）`)];
    base.rows = base.labels.map((label, i) => [label, ...base.series.map((s) => s.values[i])]);
    if (scene.id === 'trend') {
      base.columns.push('对比上期日期');
      base.rows.forEach((row, i) => row.push(snapshot.prior[i].date));
      base.description = '按区间内相同序号比较；悬停显示本期日期，上期实际日期见明细。';
    }
  } else if (scene.id === 'orders') {
    const weeks = analyticsBuckets(snapshot.daily, 'week');
    base.labels = weeks.map((row) => row.date);
    base.series = [
      { name: '新客订单', unit: '单', values: weeks.map((row) => row.newOrders) },
      { name: '复购订单', unit: '单', values: weeks.map((row) => row.paid - row.newOrders) },
    ];
    base.columns = ['分组起点', '新客订单（单）', '复购订单（单）'];
    base.rows = base.labels.map((label, i) => [label, ...base.series.map((s) => s.values[i])]);
    base.description = '从所选起点每7天分组，最后一段可能不足7天；新客与复购订单相加为支付订单。';
  } else if (scene.id === 'channels' || scene.id === 'products') {
    const items = scene.id === 'channels' ? snapshot.channels : snapshot.products;
    base.labels = items.map((item) => item.name);
    base.series = [
      { name: '支付金额', unit: '元', values: items.map((item) => currency(item.revenue)) },
    ];
    base.columns = ['名称', '支付金额（元）'];
    base.rows = base.labels.map((label, i) => [label, base.series[0].values[i]]);
  } else if (scene.id === 'funnel') {
    base.labels = ['访问会话', '商品浏览', '发起结账', '完成支付'];
    base.series = [
      {
        name: '会话数',
        unit: '次',
        values: [
          snapshot.current.visits,
          snapshot.current.viewed,
          snapshot.current.checkouts,
          snapshot.current.paid,
        ],
      },
    ];
    base.columns = ['阶段', '会话数（次）'];
    base.rows = base.labels.map((label, i) => [label, base.series[0].values[i]]);
    base.description = '同一批模拟会话，最多产生一次支付；转化率的分母应使用对应前置阶段。';
  } else if (scene.id === 'radar') {
    base.labels = ['浏览率', '结账率', '支付率', '新客占比', '注册率'];
    base.series = snapshot.channels.map((c) => ({
      name: c.name,
      unit: '%',
      values: [
        ratio(c.viewed, c.visits),
        ratio(c.checkouts, c.viewed),
        ratio(c.paid, c.checkouts),
        ratio(c.newOrders, c.paid),
        ratio(c.signups, c.visits),
      ],
    }));
    base.columns = ['指标', ...base.series.map((s) => s.name + '（%）')];
    base.rows = base.labels.map((label, i) => [label, ...base.series.map((s) => s.values[i])]);
    base.description =
      '各轴均为0–100%的比例；浏览/结账/支付率分别以上一阶段为分母，新客占比以支付订单为分母。';
  } else if (scene.id === 'heatmap') {
    base.labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    base.hours = Array.from({ length: 24 }, (_, i) => i + ':00');
    base.cells = snapshot.heatmap.flatMap((values, day) =>
      values.map((value, hour) => [hour, day, value]),
    );
    base.columns = ['星期', '小时（北京时间）', '支付订单（单）'];
    base.rows = base.cells.map(([h, d, n]) => [base.labels[d], base.hours[h], n]);
    base.description = '星期与小时的累计支付订单；合成小时权重分配与总订单数保持一致。';
  } else if (scene.id === 'sankey') {
    base.nodes = [
      ...snapshot.channels.map((c) => ({ name: c.name })),
      ...snapshot.products.map((p) => ({ name: p.name })),
    ];
    base.links = snapshot.channels.flatMap((c) =>
      allocate(
        Math.round(c.revenue),
        snapshot.products.map((p) => p.revenue || 1),
      ).map((cents, i) => ({
        source: c.name,
        target: snapshot.products[i].name,
        value: currency(cents),
      })),
    );
    base.columns = ['来源渠道', '目标商品类别', '分配金额（元）'];
    base.rows = base.links.map((link) => [link.source, link.target, link.value]);
    base.description =
      '流向金额由各渠道总金额按商品总结构模拟分配；不表示真实逐笔订单关系。每个渠道的流出金额与其支付金额一致。';
  } else if (scene.id === 'scatter') {
    base.points = snapshot.daily
      .filter((row) => row.paid > 0)
      .map((row) => [row.paid, round(row.revenue / 100 / row.paid), row.visits, row.date]);
    base.columns = ['日期', '支付订单（单）', '客单价（元）', '访问会话数'];
    base.rows = base.points.map(([x, y, v, date]) => [date, x, y, v]);
    base.description = '横轴为支付订单，纵轴为客单价；圆点大小表示访问会话数，每点代表一天。';
  } else if (scene.id === 'waterfall') {
    const revenue = currency(snapshot.current.revenue);
    const expenses = [round(revenue * 0.48), round(revenue * 0.12), round(revenue * 0.08)];
    base.labels = ['支付收入', '商品成本', '投放费用', '履约费用', '模拟结余'];
    base.deltas = [revenue, ...expenses.map((n) => -n), round(revenue - sum(expenses))];
    let running = 0;
    base.ranges = base.deltas.map((delta, i) => {
      if (i === 4) return [0, delta];
      const old = running;
      running = round(running + delta);
      return [Math.min(old, running), Math.max(old, running)];
    });
    base.columns = ['项目', '变动或结余（元）', '区间下界（元）', '区间上界（元）'];
    base.rows = base.labels.map((label, i) => [label, base.deltas[i], ...base.ranges[i]]);
    base.description =
      '成本及费用按固定比例模拟，并非真实利润核算；最后一列为收入减各项模拟费用后的结余。';
  } else if (scene.id === 'boxplot') {
    base.labels = ['用户查询', '商品列表', '订单详情', '文件上传'];
    const seed = Number(filters.seed) || 0;
    base.boxes = [
      [30, 48, 62, 85, 142],
      [42, 61, 85, 115, 195],
      [55, 72, 101, 145, 245],
      [90, 135, 180, 240, 390],
    ].map((row) => row.map((n) => n + (seed % 5) * 3));
    base.columns = ['接口', '最小值（ms）', 'Q1（ms）', '中位数（ms）', 'Q3（ms）', '最大值（ms）'];
    base.rows = base.labels.map((label, i) => [label, ...base.boxes[i]]);
    base.description =
      '独立合成的接口响应五数概括；不是业务订单接口的真实性能采集。时间/渠道筛选不作用于这组接口基准。';
  } else if (scene.id === 'goal') {
    base.actual = currency(snapshot.current.revenue);
    base.target = snapshot.days * (snapshot.channel === 'all' ? 4 : 1) * 12500;
    base.percent = round((base.actual / base.target) * 100, 1);
    base.columns = ['指标', '金额（元）'];
    base.rows = [
      ['已完成', base.actual],
      ['参考目标', base.target],
    ];
    base.description = '参考目标随天数与渠道数量调整；圆弧最多绘制100%，读数保留真实超额比例。';
  }
  if (sample === 'empty') {
    base.rows = [];
    base.labels = [];
    for (const key of ['cells', 'points', 'links', 'nodes', 'boxes', 'ranges', 'deltas']) {
      if (base[key]) base[key] = [];
    }
    base.series.forEach((s) => (s.values = []));
  }
  return zeroExample(base);
}
export function chartExampleCsv(example) {
  const rows = [
    ['NOVA 开源图表演示（模拟数据）'],
    ['场景', example.title],
    ['说明', example.description],
    example.columns,
    ...example.rows,
  ];
  return (
    '\uFEFF' +
    rows
      .map((row) =>
        row
          .map(
            (value) =>
              '"' +
              (typeof value === 'number'
                ? String(value)
                : String(value).replace(/^[=+@-]/, "'$&")
              ).replaceAll('"', '""') +
              '"',
          )
          .join(','),
      )
      .join('\r\n')
  );
}
