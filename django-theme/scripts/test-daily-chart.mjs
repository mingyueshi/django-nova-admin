import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';

const points = [{date: '2026-05-01', value: 0}, {date: '2026-05-02', value: null}];
const stub = `export function init(plot) {
    return {
        setOption(options) { plot.options = options; },
        resize() { plot.resized = true; },
        dispose() { plot.disposed = true; },
    };
}`;
function card(id, module) {
    return `<section class="nova-daily-chart" id="${id}" aria-label="Daily count">
        <div class="nova-chart-plot" hidden></div><p class="nova-chart-load-error" hidden></p>
        <details open></details><script type="application/json">${JSON.stringify({schema_version: 1, state: 'ready', points})}</script>
        <script data-nova-echarts="data:text/javascript,${encodeURIComponent(module)}"></script></section>`;
}
const dom = new JSDOM(card('ready', stub) + card('failed', 'throw Error("load failure")'));
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
