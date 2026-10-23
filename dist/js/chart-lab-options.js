// Adapter functions use the same scene data for native library options and copyable examples.
const blank = (example) => !example.rows.length;
export function buildEChartsOption(example, theme) {
  const colors = theme.colors;
  const option = {
    backgroundColor: theme.panel,
    color: colors,
    textStyle: { color: theme.text, fontFamily: 'system-ui, sans-serif' },
    animation: false,
    aria: { enabled: true },
    tooltip: { trigger: 'axis', confine: true },
    legend: { top: 8, textStyle: { color: theme.text }, type: 'scroll' },
    grid: { left: 65, right: 35, top: 65, bottom: 65 },
    xAxis: {
      type: 'category',
      data: example.labels,
      axisLabel: { color: theme.muted, hideOverlap: true },
      axisLine: { lineStyle: { color: theme.line } },
    },
    yAxis: {
      type: 'value',
      name: example.series[0]?.unit || '',
      axisLabel: { color: theme.muted },
      splitLine: { lineStyle: { color: theme.line } },
    },
    series: [],
  };
  const points = example.labels.length;
  if (points > 12)
    option.dataZoom = [
      { type: 'inside' },
      {
        type: 'slider',
        height: 18,
        bottom: 12,
        borderColor: theme.line,
        textStyle: { color: theme.muted },
      },
    ];
  if (example.id === 'trend' || example.id === 'orders' || example.id === 'mixed') {
    option.series = example.series.map((series, i) => ({
      name: series.name,
      type: example.id === 'trend' || (example.id === 'mixed' && i === 1) ? 'line' : 'bar',
      data: series.values,
      smooth: example.id === 'trend',
      showSymbol: points < 40,
      areaStyle: example.id === 'trend' ? { opacity: 0.1 } : undefined,
      stack: example.id === 'orders' ? 'orders' : undefined,
      yAxisIndex: example.id === 'mixed' ? i : 0,
      barMaxWidth: 38,
    }));
    if (example.id === 'mixed')
      option.yAxis = [
        { ...option.yAxis, name: '金额 / 元' },
        { ...option.yAxis, name: '订单 / 单', splitLine: { show: false } },
      ];
  } else if (example.id === 'channels') {
    delete option.xAxis;
    delete option.yAxis;
    delete option.dataZoom;
    option.tooltip = { trigger: 'item', confine: true };
    option.series = [
      {
        name: '支付金额',
        type: 'pie',
        radius: ['38%', '66%'],
        center: ['50%', '54%'],
        label: { color: theme.text, formatter: '{b}\n{d}%' },
        data: example.labels.map((name, i) => ({ name, value: example.series[0].values[i] })),
      },
    ];
  } else if (example.id === 'funnel') {
    delete option.xAxis;
    delete option.yAxis;
    option.tooltip = { trigger: 'item', confine: true };
    option.series = [
      {
        name: '会话数',
        type: 'funnel',
        left: '16%',
        right: '16%',
        top: 35,
        bottom: 25,
        sort: 'descending',
        gap: 5,
        label: { position: 'inside', color: theme.text, formatter: '{b}: {c}' },
        itemStyle: { opacity: 0.8 },
        data: example.labels.map((name, i) => ({ name, value: example.series[0].values[i] })),
      },
    ];
  } else if (example.id === 'products') {
    delete option.xAxis;
    delete option.yAxis;
    option.tooltip = { trigger: 'item', confine: true };
    option.series = [
      {
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        top: 15,
        bottom: 15,
        left: 10,
        right: 10,
        label: { formatter: '{b}\n{c} 元' },
        data: example.labels.map((name, i) => ({ name, value: example.series[0].values[i] })),
      },
    ];
  } else if (example.id === 'radar') {
    delete option.xAxis;
    delete option.yAxis;
    option.tooltip = { trigger: 'item', confine: true };
    option.radar = {
      radius: '61%',
      center: ['50%', '58%'],
      indicator: example.labels.map((name) => ({ name, max: 100 })),
      axisName: { color: theme.text },
      splitLine: { lineStyle: { color: theme.line } },
      splitArea: { areaStyle: { color: [theme.panel, theme.bg] } },
    };
    option.series = [
      {
        type: 'radar',
        data: example.series.map((series, i) => ({
          name: series.name,
          value: series.values,
          areaStyle: { opacity: i === 0 ? 0.12 : 0 },
        })),
      },
    ];
  } else if (example.id === 'heatmap') {
    option.legend = { show: false };
    option.xAxis = { ...option.xAxis, data: example.hours, splitArea: { show: true } };
    option.yAxis = {
      type: 'category',
      data: example.labels,
      axisLabel: { color: theme.muted },
      splitArea: { show: true },
    };
    option.grid.bottom = 78;
    option.visualMap = {
      min: 0,
      max: Math.max(1, ...example.cells.map((cell) => cell[2])),
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      calculable: true,
      inRange: { color: [theme.bg, colors[0]] },
      textStyle: { color: theme.text },
    };
    option.tooltip = { position: 'top', confine: true };
    option.series = [
      {
        name: '支付订单 / 单',
        type: 'heatmap',
        data: example.cells,
        label: { show: false },
        emphasis: { itemStyle: { borderColor: theme.text, borderWidth: 1 } },
      },
    ];
  } else if (example.id === 'sankey') {
    delete option.xAxis;
    delete option.yAxis;
    option.tooltip = { trigger: 'item', confine: true };
    option.series = [
      {
        type: 'sankey',
        top: 25,
        bottom: 25,
        left: 55,
        right: 105,
        nodeWidth: 18,
        nodeGap: 22,
        label: { color: theme.text },
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.4 },
        emphasis: { focus: 'adjacency' },
        data: example.nodes,
        links: example.links,
      },
    ];
  } else if (example.id === 'scatter') {
    option.legend = { show: false };
    option.xAxis = { ...option.yAxis, name: '支付订单 / 单' };
    option.yAxis.name = '客单价 / 元';
    option.tooltip = { trigger: 'item', confine: true };
    option.series = [
      {
        name: '订单 / 客单价 / 访问会话 / 日期',
        type: 'scatter',
        symbolSize: 14,
        data: example.points.map(([x, y, visits, date]) => ({
          value: [x, y, visits, date],
          symbolSize: 6 + Math.sqrt(visits / Math.max(1, ...example.points.map((p) => p[2]))) * 15,
        })),
        itemStyle: { opacity: 0.6 },
      },
    ];
  } else if (example.id === 'waterfall') {
    option.legend = { show: false };
    option.yAxis.name = '金额 / 元';
    option.series = [
      {
        name: '基座',
        type: 'bar',
        stack: 'flow',
        silent: true,
        itemStyle: { color: 'transparent' },
        emphasis: { itemStyle: { color: 'transparent' } },
        data: example.ranges.map((range) => range[0]),
      },
      {
        name: '区间金额',
        type: 'bar',
        stack: 'flow',
        barMaxWidth: 55,
        data: example.ranges.map((range, i) => ({
          value: range[1] - range[0],
          itemStyle: { color: i === 0 || i === 4 ? colors[0] : colors[3] },
        })),
      },
    ];
    option.tooltip = { trigger: 'item', confine: true };
  } else if (example.id === 'boxplot') {
    option.legend = { show: false };
    option.yAxis.name = '响应耗时 / ms';
    option.tooltip = { trigger: 'item', confine: true };
    option.series = [
      {
        name: '最小值 / Q1 / 中位数 / Q3 / 最大值',
        type: 'boxplot',
        data: example.boxes,
        itemStyle: { color: theme.fill, borderColor: colors[0] },
      },
    ];
  } else if (example.id === 'goal') {
    delete option.xAxis;
    delete option.yAxis;
    option.tooltip = { show: false };
    option.series = [
      {
        type: 'gauge',
        min: 0,
        max: 100,
        startAngle: 210,
        endAngle: -30,
        progress: { show: true, width: 20 },
        axisLine: { lineStyle: { width: 20, color: [[1, theme.line]] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: theme.muted, distance: 26 },
        pointer: { show: false },
        anchor: { show: false },
        detail: {
          valueAnimation: false,
          formatter: example.percent + '%',
          color: theme.text,
          fontSize: 32,
          offsetCenter: [0, '10%'],
        },
        title: { offsetCenter: [0, '45%'], color: theme.muted, fontSize: 13 },
        data: [{ value: Math.min(100, example.percent), name: '目标完成率' }],
      },
    ];
  } else if (example.id.startsWith('ops-')) {
    option.xAxis = { ...option.xAxis, type: 'time', name: '北京时间' };
    option.series = example.series.map((series, i) => ({
      name: series.name,
      type: 'line',
      showSymbol: false,
      yAxisIndex: example.id === 'ops-throughput' ? i : 0,
      data: series.values.map((value, j) => [(example.timestamps[j] + 28800) * 1000, value]),
    }));
    option.dataZoom = [{ type: 'inside' }, { type: 'slider', bottom: 12, height: 18 }];
    if (example.id === 'ops-throughput')
      option.yAxis = [
        { ...option.yAxis, name: 'req/s' },
        { ...option.yAxis, name: '错误率 / %', splitLine: { show: false } },
      ];
    if (example.id === 'ops-resources') {
      option.yAxis.min = 0;
      option.yAxis.max = 100;
    }
    // The time axis is shifted by UTC+8 and rendered in UTC, independent of browser locale.
    option.useUTC = true;
  }
  if (blank(example)) option.series = [];
  return option;
}
export function buildChartJsConfig(example, theme) {
  if (
    !['trend', 'orders', 'channels', 'mixed', 'radar', 'scatter', 'waterfall'].includes(example.id)
  )
    throw new Error('此场景未接入 Chart.js');
  const config = {
    type: 'line',
    data: {
      labels: example.labels,
      datasets: example.series.map((series, i) => ({
        label: series.name + ' / ' + series.unit,
        data: series.values,
        borderColor: theme.colors[i % theme.colors.length],
        backgroundColor: i === 0 ? theme.fill : theme.colors[i % theme.colors.length],
        borderWidth: 2,
        pointRadius: example.labels.length > 40 ? 0 : 3,
        tension: 0.25,
        fill: example.id === 'trend',
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: theme.text, usePointStyle: true, boxWidth: 9 } },
        tooltip: { enabled: true },
      },
      scales: {
        x: { ticks: { color: theme.muted, maxTicksLimit: 8 }, grid: { color: theme.line } },
        y: {
          beginAtZero: true,
          ticks: { color: theme.muted },
          grid: { color: theme.line },
          title: { display: true, text: example.series[0]?.unit || '', color: theme.muted },
        },
      },
    },
  };
  if (example.id === 'orders') {
    config.type = 'bar';
    config.options.scales.x.stacked = true;
    config.options.scales.y.stacked = true;
    config.data.datasets.forEach((dataset, i) => {
      dataset.backgroundColor = theme.colors[i];
    });
  }
  if (example.id === 'channels') {
    config.type = 'doughnut';
    delete config.options.scales;
    config.options.cutout = '58%';
    config.options.interaction = { mode: 'nearest', intersect: true };
    config.data.datasets = [
      {
        label: '支付金额 / 元',
        data: example.series[0].values,
        backgroundColor: theme.colors,
        borderColor: theme.panel,
        borderWidth: 3,
      },
    ];
  }
  if (example.id === 'mixed') {
    config.type = 'bar';
    config.data.datasets[0].backgroundColor = theme.colors[0];
    config.data.datasets[0].yAxisID = 'y';
    config.data.datasets[1].type = 'line';
    config.data.datasets[1].yAxisID = 'y1';
    config.options.scales.y1 = {
      type: 'linear',
      position: 'right',
      beginAtZero: true,
      grid: { drawOnChartArea: false },
      ticks: { color: theme.muted },
      title: { display: true, text: '订单 / 单', color: theme.muted },
    };
  }
  if (example.id === 'radar') {
    config.type = 'radar';
    config.options.scales = {
      r: {
        min: 0,
        max: 100,
        pointLabels: { color: theme.text },
        ticks: { color: theme.muted, backdropColor: theme.panel },
        grid: { color: theme.line },
        angleLines: { color: theme.line },
      },
    };
    config.data.datasets.forEach((dataset, i) => {
      dataset.fill = i === 0;
      dataset.backgroundColor = i === 0 ? theme.fill : 'transparent';
    });
  }
  if (example.id === 'scatter') {
    config.type = 'bubble';
    config.options.interaction = { mode: 'nearest', intersect: true };
    config.data = {
      datasets: [
        {
          label: '每日订单与客单价',
          data: example.points.map(([x, y, visits]) => ({
            x,
            y,
            r: 4 + Math.sqrt(visits / Math.max(1, ...example.points.map((p) => p[2]))) * 10,
          })),
          backgroundColor: theme.fill,
          borderColor: theme.colors[0],
          borderWidth: 1.5,
        },
      ],
    };
    config.options.scales.x.type = 'linear';
    config.options.scales.x.title = { display: true, text: '支付订单 / 单', color: theme.muted };
    config.options.scales.y.title.text = '客单价 / 元';
  }
  if (example.id === 'waterfall') {
    config.type = 'bar';
    config.data.datasets = [
      {
        label: '区间金额 / 元',
        data: example.ranges,
        backgroundColor: example.labels.map((_, i) =>
          i === 0 || i === 4 ? theme.colors[0] : theme.colors[3],
        ),
        borderWidth: 0,
      },
    ];
    config.options.scales.y.title.text = '金额 / 元';
    config.options.plugins.legend.display = false;
  }
  return config;
}
export function buildUPlotOptions(example, theme, width = 700, height = 400) {
  if (!example.id.startsWith('ops-')) throw new Error('uPlot 演示只接入运维时序场景');
  const isDual = example.id === 'ops-throughput';
  const series = [
    {
      label: '北京时间',
      value: (u, value) =>
        value == null ? '—' : new Date((value + 28800) * 1000).toISOString().slice(11, 19),
    },
    ...example.series.map((s, i) => ({
      label: s.name,
      scale: isDual && i === 1 ? 'right' : 'y',
      stroke: theme.colors[i],
      width: 2,
      value:
        s.unit === '%'
          ? (u, value) => (value == null ? '—' : value.toFixed(2) + '%')
          : (u, value) => (value == null ? '—' : value.toFixed(1)),
      points: { show: false },
    })),
  ];
  const axes = [
    {
      stroke: theme.muted,
      grid: { stroke: theme.line },
      values: (u, values) =>
        values.map((value) => new Date((value + 28800) * 1000).toISOString().slice(11, 16)),
    },
    {
      stroke: theme.muted,
      grid: { stroke: theme.line },
      label: example.series[0].unit,
      font: '11px system-ui',
    },
  ];
  const scales = { x: { time: true }, y: { auto: true } };
  if (example.id === 'ops-resources') scales.y = { range: [0, 100] };
  if (isDual) {
    scales.right = { auto: true };
    axes.push({
      side: 1,
      scale: 'right',
      stroke: theme.muted,
      grid: { show: false },
      label: '错误率 / %',
      font: '11px system-ui',
    });
  }
  return {
    width,
    height,
    series,
    scales,
    axes,
    legend: { show: true, live: true },
    cursor: { drag: { x: true, y: false } },
    select: { show: true },
  };
}
export function serializeChartConfig(value, level = 0) {
  if (typeof value === 'function') return value.toString();
  if (value === undefined) return undefined;
  if (Array.isArray(value))
    return (
      '[\n' +
      value
        .map((item) => '  '.repeat(level + 1) + serializeChartConfig(item, level + 1))
        .join(',\n') +
      '\n' +
      '  '.repeat(level) +
      ']'
    );
  if (value && typeof value === 'object')
    return (
      '{\n' +
      Object.entries(value)
        .filter(([, item]) => item !== undefined)
        .map(
          ([key, item]) =>
            '  '.repeat(level + 1) +
            JSON.stringify(key) +
            ': ' +
            serializeChartConfig(item, level + 1),
        )
        .join(',\n') +
      '\n' +
      '  '.repeat(level) +
      '}'
    );
  return JSON.stringify(value);
}
