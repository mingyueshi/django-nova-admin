import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const source = readFileSync(new URL('../demo/catalog/static/catalog/product-tag-rules.js', import.meta.url), 'utf8');
const sides = ['chart_tag', 'chart_tag_exclude'];
const fields = sides.map(name => `
    <select multiple name="${name}">${[1, 2, 3, 4, 5, 6].map(n => `<option selected>${n}</option>`).join('')}</select>
    <select name="${name}_mode"><option>any</option><option>any_range</option><option>values_or_ranges</option></select>
    <label><input type="number" name="${name}_min" data-minimum-for="${name}"></label>
    <label><input type="number" name="${name}_max"></label>
    <label><select multiple name="${name}_counts"></select></label>
    <label><input name="${name}_ranges" data-range-error="Invalid range" data-mixed-error="Invalid count or range"></label>
`).join('');
const {window} = new JSDOM(`<section id="product-tag-ranking"><form>${fields}</form></section>`, {runScripts: 'outside-only'});
try {
    window.eval(source);
    const form = window.document.querySelector('form');
    for (const name of sides) {
        const mode = form.elements.namedItem(name + '_mode');
        const input = form.elements.namedItem(name + '_ranges');
        const tags = form.elements.namedItem(name);
        mode.value = 'values_or_ranges';
        mode.dispatchEvent(new window.Event('change'));
        assert.ok(input.required && !input.closest('label').hidden);
        for (const [value, valid] of [
            ['0、2 到 4、6', true], ['3, 2-4，4', true], ['0', true], ['0-6', true],
            ['0,7', false], ['2-7', false], ['4-2', false], ['1.5', false], ['01', false], ['0,,2', false], ['', false],
        ]) {
            input.value = value;
            input.dispatchEvent(new window.Event('input'));
            assert.equal(input.checkValidity(), valid, value);
        }
        input.value = '0、2 到 4、6';
        tags.options[5].selected = false;
        tags.dispatchEvent(new window.Event('change'));
        assert.equal(input.validationMessage, 'Invalid count or range');
        tags.options[5].selected = true;
        window.dispatchEvent(new window.Event('pageshow'));
        assert.ok(input.checkValidity());
        assert.equal(new window.FormData(form).get(name + '_ranges'), input.value);
        mode.value = 'any_range';
        mode.dispatchEvent(new window.Event('change'));
        assert.equal(input.validationMessage, 'Invalid range');
        mode.value = 'any';
        mode.dispatchEvent(new window.Event('change'));
        assert.ok(!new window.FormData(form).has(name + '_ranges'));
    }
    console.log('PASS mixed tag count entry, bounds, form restoration and mode switching on both sides');
} finally {
    window.close();
}
