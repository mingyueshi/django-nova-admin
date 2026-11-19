import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';

const points = [{date: '2026-05-01', value: 0}, {date: '2026-05-02', value: null}];
const stub = `export function init(plot) {
    return {
        setOption(options) { plot.options = options; },
        on(name, callback) { if (name === 'click') plot.clickLabel = callback; },
        getZr() { return { on(name, callback) { if (name === 'click') plot.clickGrid = callback; } }; },
        containPixel(grid, [x, y]) { return grid.gridIndex === 0 && x >= 0 && y >= 0; },
        convertFromPixel(grid, [x, y]) { return [x, y]; },
        resize() { plot.resized = true; },
        dispose() { plot.disposed = true; },
    };
}`;
function card(id, module, rows = '') {
    return `<section class="nova-daily-chart" id="${id}" aria-label="Daily count">
        <div class="nova-chart-plot" hidden></div><p class="nova-chart-load-error" hidden></p>
        <details open><summary>Daily values</summary>${rows}</details><script type="application/json">${JSON.stringify({schema_version: 1, state: 'ready', points})}</script>
        <script data-nova-echarts="data:text/javascript,${encodeURIComponent(module)}"></script></section>`;
}
const dayLink = '<a href="/catalog/product/?day=1" data-nova-chart-day="2026-05-01">2026-05-01</a>';
const dom = new JSDOM(card('ready', stub, dayLink) + card('plain', stub) + card('failed', 'throw Error("load failure")', dayLink));
const {document} = dom.window;
Object.defineProperty(dom.window.HTMLElement.prototype, 'clientHeight', {get: () => 220});
const globals = {window: dom.window, document, getComputedStyle: el => dom.window.getComputedStyle(el)};
const prior = Object.fromEntries(Object.keys(globals).map(k => [k, Object.getOwnPropertyDescriptor(globalThis, k)]));
try {
    Object.assign(globalThis, globals);
    await import('../src/nova_admin/static/nova_admin/daily-chart.js');
    // Wait for both asynchronous module imports to settle.
    const ready = document.querySelector('#ready .nova-chart-plot');
    const failureMessage = document.querySelector('#failed .nova-chart-load-error');
    for (let i = 0; i < 100 && (!ready.options || failureMessage.hidden); i++) {
        await new Promise(resolve => setTimeout(resolve, 5));
    }
    const scenarios = [
        ['Local dates, real zeros and missing observations reach the chart', () => {
            assert.equal(ready.hidden, false);
            assert.deepEqual(ready.options.series[0].data, [0, null]);
            assert.deepEqual(ready.options.xAxis.data, points.map(point => point.date));
            assert.equal(document.querySelector('#ready details').open, false);
        }],
        ['Failed module retains the accessible table', () => {
            assert.equal(failureMessage.hidden, false);
            assert.equal(document.querySelector('#failed details').open, true);
            assert.equal(document.querySelector('#failed .nova-chart-plot').hidden, true);
            assert.equal(document.querySelector('#failed details a').getAttribute('href'), '/catalog/product/?day=1');
        }],
        ['Day columns and date labels open the native link, including zero-valued days', () => {
            const anchor = document.querySelector('#ready details a');
            let visits = 0;
            anchor.addEventListener('click', event => { event.preventDefault(); visits++; });
            ready.clickGrid({offsetX: 0, offsetY: 10});
            ready.clickLabel({componentType: 'xAxis', targetType: 'axisLabel', value: points[0].date});
            assert.equal(visits, 2);
            ready.clickGrid({offsetX: 1, offsetY: 10}); // Missing observation has no link.
            ready.clickGrid({offsetX: 0, offsetY: -1});
            ready.clickLabel({componentType: 'series', value: 0});
            assert.equal(visits, 2);
        }],
        ['Cards without host links retain the plain chart', () => {
            const plain = document.querySelector('#plain .nova-chart-plot');
            assert.equal(plain.options.xAxis.triggerEvent, false);
            assert.equal(plain.clickGrid, undefined);
        }],
        ['Page exit releases the chart and resize listener', () => {
            dom.window.dispatchEvent(new dom.window.Event('resize'));
            assert.equal(ready.resized, true);
            dom.window.dispatchEvent(new dom.window.Event('pagehide'));
            assert.equal(ready.disposed, true);
            ready.resized = false;
            dom.window.dispatchEvent(new dom.window.Event('resize'));
            assert.equal(ready.resized, false);
        }],
    ];
    for (const [name, test] of scenarios) { test(); console.log('PASS', name); }
    console.log(`${scenarios.length} daily chart DOM scenarios passed.`);
} finally {
    for (const [name, descriptor] of Object.entries(prior)) {
        if (descriptor) Object.defineProperty(globalThis, name, descriptor);
        else delete globalThis[name];
    }
    dom.window.close();
}
