import { analysisValue } from './analysis-lab-data.js';
export function analysisOptions(snapshot, theme, reducedMotion = false) {
  const s = snapshot,
    t = theme;
  const base = {
    backgroundColor: t.panel,
    color: t.colors,
    textStyle: { color: t.text, fontFamily: 'system-ui, sans-serif' },
    animation: !reducedMotion,
    animationDurationUpdate: 180,
    aria: { enabled: true, decal: { show: true } },
    tooltip: { confine: true, renderMode: 'richText' },
  };
  const axis = {
    axisLine: { lineStyle: { color: t.line } },
    axisTick: { show: false },
    axisLabel: { color: t.muted, fontSize: 10 },
    splitLine: { lineStyle: { color: t.line } },
  };
  const lower = s.range
    ? Math.max(
        0,
        s.periods.findIndex((p) => p >= s.range[0]),
      )
    : 0;
  const upper = s.range
    ? Math.max(
        lower,
        s.periods.findLastIndex((p) => p <= s.range[1]),
      )
    : s.periods.length - 1;
  const trend = {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'axis' },
    legend: { top: 0, textStyle: { color: t.muted } },
    grid: { left: 12, right: 22, top: 45, bottom: 65, containLabel: true },
    xAxis: {
      ...axis,
      type: 'category',
      data: s.periods,
      axisLabel: {
        color: t.muted,
        fontSize: 10,
        formatter: (v) => (s.scenario.id === 'ops' ? v.slice(11) : v.slice(5)),
      },
    },
    yAxis: { ...axis, type: 'value', name: s.metric.unit },
    dataZoom: [
      {
        type: 'slider',
        bottom: 2,
        height: 22,
        startValue: lower,
        endValue: upper,
        filterMode: 'none',
        textStyle: { color: t.muted },
        borderColor: t.line,
        dataBackground: { lineStyle: { color: t.muted }, areaStyle: { color: t.fill } },
        selectedDataBackground: { lineStyle: { color: t.colors[0] }, areaStyle: { color: t.fill } },
      },
    ],
    series: [
      {
        id: 'focus',
        name: s.selected || '当前范围',
        type: 'line',
        smooth: 0.2,
        symbolSize: 7,
        showSymbol: s.periods.length <= 30,
        lineStyle: { width: 2 },
        areaStyle: { color: t.fill },
        data: s.trend.map((r) => r.value),
      },
      ...(s.selected
        ? [
            {
              id: 'baseline',
              name: '本层合计（对照）',
              type: 'line',
              showSymbol: false,
              lineStyle: { type: 'dashed', width: 1 },
              data: s.trend.map((r) => r.baseline),
            },
          ]
        : []),
    ],
  };
  const rank = {
    ...base,
    grid: { left: 12, right: 25, top: 25, bottom: 15, containLabel: true },
    xAxis: { ...axis, type: 'value', name: s.metric.unit },
    yAxis: {
      ...axis,
      type: 'category',
      inverse: true,
      data: s.groups.map((g) => g.key),
      axisLabel: { color: t.text, fontSize: 11, width: 90, overflow: 'truncate' },
    },
    series: [
      {
        id: 'groups',
        type: 'bar',
        barMaxWidth: 26,
        cursor: 'pointer',
        data: s.groups.map((g) => ({
          name: g.key,
          groupKey: g.key,
          value: g.value,
          itemStyle: {
            color: s.selected && g.key !== s.selected ? t.muted : t.colors[0],
            opacity: s.selected && g.key !== s.selected ? 0.3 : 1,
            borderRadius: [0, 4, 4, 0],
          },
        })),
      },
    ],
  };
  const positive = s.composition.some((r) => r.value > 0);
  const composition = {
    ...base,
    legend: { bottom: 0, textStyle: { color: t.muted, fontSize: 10 } },
    ...(positive
      ? {}
      : {
          graphic: [
            {
              type: 'text',
              left: 'center',
              top: 'middle',
              style: { text: '暂无可计算的构成', fill: t.muted, fontSize: 12 },
            },
          ],
        }),
    series: !positive
      ? []
      : s.scenario.id === 'growth'
        ? [
            {
              type: 'funnel',
              left: '12%',
              top: 12,
              bottom: 45,
              width: '76%',
              min: 0,
              max: s.totals.visits,
              sort: 'descending',
              gap: 5,
              label: { position: 'inside', color: t.text, formatter: '{b}\n{c}' },
              data: s.composition,
            },
          ]
        : [
            {
              type: 'pie',
              radius: ['45%', '68%'],
              center: ['50%', '42%'],
              label: { show: false },
              data: s.composition,
            },
          ],
  };
  return { trend, rank, composition, selectedValue: analysisValue(s.totals, s.metric.id) };
}
