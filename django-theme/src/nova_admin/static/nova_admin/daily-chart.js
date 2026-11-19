// Django resolves both module URLs through its configured staticfiles storage.
const cleanups = [];
let leaving = false;

async function mount(card, url) {
    const plot = card.querySelector('.nova-chart-plot');
    const details = card.querySelector('details');
    let chart;
    try {
        const data = JSON.parse(card.querySelector('script[type="application/json"]').textContent);
        if (data.schema_version !== 1 || data.state !== 'ready') throw new Error();
        const echarts = await import(url);
        if (leaving || !card.isConnected) return;
        plot.hidden = false;
        if (!plot.clientHeight) throw new Error();
        chart = echarts.init(plot);
        const dayLinks = new Map(Array.from(card.querySelectorAll('a[data-nova-chart-day]'),
            anchor => [anchor.dataset.novaChartDay, anchor]));
        const style = getComputedStyle(card);
        chart.setOption({
            animation: false,
            color: [style.getPropertyValue('--link-fg').trim() || '#417690'],
            textStyle: {color: style.color},
            grid: {left: 12, right: 16, top: 16, bottom: 12, containLabel: true},
            tooltip: {trigger: 'axis', renderMode: 'richText', confine: true},
            xAxis: {type: 'category', triggerEvent: dayLinks.size > 0, data: data.points.map(point => point.date), axisLabel: {hideOverlap: true, color: style.color}},
            yAxis: {
                type: 'value',
                minInterval: data.points.every(point => point.value === null || Number.isInteger(point.value)) ? 1 : undefined,
                axisLabel: {color: style.color},
                splitLine: {lineStyle: {color: style.getPropertyValue('--hairline-color').trim()}},
            },
            series: [{type: 'bar', name: card.getAttribute('aria-label'), data: data.points.map(point => point.value)}],
        });
        if (dayLinks.size) {
            chart.on('click', event => {
                if (event.componentType === 'xAxis' && event.targetType === 'axisLabel') {
                    dayLinks.get(event.value)?.click();
                }
            });
            // Hit-test the whole day column so a zero-height bar is also selectable.
            const grid = {gridIndex: 0};
            chart.getZr().on('click', event => {
                const pixel = [event.offsetX, event.offsetY];
                if (!chart.containPixel(grid, pixel)) return;
                const [index] = chart.convertFromPixel(grid, pixel);
                dayLinks.get(data.points[index]?.date)?.click();
            });
        }
        const resize = () => chart.resize();
        const observer = window.ResizeObserver ? new ResizeObserver(resize) : null;
        if (observer) observer.observe(plot);
        else window.addEventListener('resize', resize);
        cleanups.push(() => {
            observer?.disconnect();
            window.removeEventListener('resize', resize);
            chart.dispose();
        });
        details.open = false;
    } catch {
        chart?.dispose();
        plot.hidden = true;
        details.open = true;
        card.querySelector('.nova-chart-load-error').hidden = false;
    }
}

for (const entry of document.querySelectorAll('script[data-nova-echarts]')) {
    mount(entry.closest('.nova-daily-chart'), entry.dataset.novaEcharts);
}
window.addEventListener('pagehide', () => {
    leaving = true;
    for (const cleanup of cleanups.splice(0)) cleanup();
});
window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
});
