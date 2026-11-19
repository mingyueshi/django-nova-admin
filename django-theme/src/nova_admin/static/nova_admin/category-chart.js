// Keep the native links usable before initialization, on failure and without a canvas.
(() => {
    const card = document.currentScript.closest('.nova-category-chart');
    const plot = card.querySelector('.nova-chart-plot');
    const canvas = plot.querySelector('canvas');
    let chart;
    try {
        const snapshot = JSON.parse(card.querySelector('script[type="application/json"]').textContent);
        const links = new Map(Array.from(card.querySelectorAll('a[data-nova-category]'),
            link => [link.dataset.novaCategory, link]));
        const style = getComputedStyle(card);
        plot.hidden = false;
        chart = new window.Chart(canvas, {
            type: 'bar',
            data: {
                labels: snapshot.points.map(point => point.label),
                datasets: [{
                    data: snapshot.points.map(point => point.value),
                    label: card.getAttribute('aria-label'),
                    backgroundColor: style.getPropertyValue('--link-fg').trim() || '#417690',
                }],
            },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
                color: style.color,
                scales: {
                    x: {beginAtZero: true, ticks: {precision: 0, color: style.color}},
                    y: {ticks: {color: style.color}, grid: {display: false}},
                },
                plugins: {legend: {display: false}},
            },
        });
        if (!chart.ctx) throw new Error();
        canvas.addEventListener('click', event => {
            const {x, y} = window.Chart.helpers.getRelativePosition(event, chart);
            const area = chart.chartArea;
            if (x < chart.scales.y.left || x > area.right || y < area.top || y >= area.bottom) return;
            const index = chart.scales.y.getValueForPixel(y);
            links.get(snapshot.points[index]?.key)?.click();
        });
        window.addEventListener('pagehide', event => {
            if (!event.persisted) chart.destroy();
        });
    } catch {
        chart?.destroy();
        plot.hidden = true;
        card.querySelector('.nova-chart-load-error').hidden = false;
    }
})();
