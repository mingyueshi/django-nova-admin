import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const source = readFileSync(new URL('../src/nova_admin/static/nova_admin/category-chart.js', import.meta.url), 'utf8');
const points = [{key: 'draft', label: '草稿', value: 2}, {key: 'active', label: '已上架', value: 0},
    {key: 'archived', label: '已归档', value: null}];
const dom = new JSDOM(`<section class="nova-category-chart" aria-label="商品状态">
    <div class="nova-chart-plot" hidden><canvas></canvas></div><p class="nova-chart-load-error" hidden></p>
    <table><tbody>${points.map(p => `<tr><td>${p.value === null ? p.label :
        `<a data-nova-category="${p.key}" href="?status__exact=${p.key}">${p.label}</a>`}</td></tr>`).join('')}</tbody></table>
    <script type="application/json">${JSON.stringify({schema_version: 1, state: 'ready', points})}</script><script></script>
</section>`, {runScripts: 'outside-only'});
const {window} = dom;
const {document} = window;
Object.defineProperty(document, 'currentScript', {value: document.querySelector('script:last-child')});
const canvas = document.querySelector('canvas');
const visited = [];
document.querySelectorAll('a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); visited.push(a.dataset.novaCategory); }));
let chart;
window.Chart = class {
    static helpers = {getRelativePosition: event => ({x: event.clientX, y: event.clientY})};
    constructor(element, config) {
        assert.equal(element, canvas);
        chart = this;
        this.config = config;
        this.ctx = {};
        this.chartArea = {left: 20, right: 100, top: 10, bottom: 70};
        this.scales = {y: {left: 0, getValueForPixel: y => Math.floor((y - 10) / 20)}};
    }
    destroy() { this.destroyed = true; }
};
const click = (x, y) => canvas.dispatchEvent(new window.MouseEvent('click', {clientX: x, clientY: y}));
try {
    window.eval(source);
    const tests = [
        ['Labels and counts come from the same ordered snapshot', () => {
            assert.equal(document.querySelector('.nova-chart-plot').hidden, false);
            assert.deepEqual(Array.from(chart.config.data.labels), points.map(p => p.label));
            assert.deepEqual(Array.from(chart.config.data.datasets[0].data), [2, 0, null]);
        }],
        ['Bars, axis labels and empty bars use the corresponding native links', () => {
            click(50, 20); click(10, 40); click(50, 40);
            click(50, 60); click(110, 40); click(10, 70);
            assert.deepEqual(visited, ['draft', 'active', 'active']);
        }],
        ['A cached page retains its chart and a discarded page releases it', () => {
            window.dispatchEvent(new window.PageTransitionEvent('pagehide', {persisted: true}));
            assert.equal(chart.destroyed, undefined);
            window.dispatchEvent(new window.PageTransitionEvent('pagehide'));
            assert.equal(chart.destroyed, true);
        }],
        ['An unavailable runtime leaves the data table and links available', () => {
            delete window.Chart;
            window.eval(source);
            assert.equal(document.querySelector('.nova-chart-plot').hidden, true);
            assert.equal(document.querySelector('.nova-chart-load-error').hidden, false);
            assert.equal(document.querySelectorAll('table a').length, 2);
        }],
    ];
    for (const [name, run] of tests) { run(); console.log('PASS', name); }
    console.log(`${tests.length} category chart DOM scenarios passed.`);
} finally {
    window.close();
}
