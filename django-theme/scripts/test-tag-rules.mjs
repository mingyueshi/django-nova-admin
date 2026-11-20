import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const source = readFileSync(new URL('../demo/catalog/static/catalog/product-tag-rules.js', import.meta.url), 'utf8');
const sides = ['chart_tag', 'chart_tag_exclude'];
const mixedModes = ['values_or_ranges', 'not_values_or_ranges'];
const fields = sides.map(name => `
    <select multiple name="${name}">${[1, 2, 3, 4, 5, 6].map(n => `<option selected>${n}</option>`).join('')}</select>
    <select name="${name}_mode">${['any', 'any_range', ...mixedModes].map(mode => `<option>${mode}</option>`).join('')}</select>
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
        for (const rule of mixedModes) {
            mode.value = rule;
            mode.dispatchEvent(new window.Event('change'));
            assert.ok(input.required && !input.closest('label').hidden);
            for (const [value, valid] of [
                ['0、2 到 4、6', true], ['3, 2-4，4', true], ['0', true], ['0-6', true],
                ['0、2 到 4、6 及以上', true], ['至多 2 个、至少 4 个', true], ['2 个及以下、>=4', true],
                ['≤0、≥6', true], ['至少0、<=6', true], ['0 及以上、至多 7 个', false], ['7 及以上', false],
                ['至多 -1 个', false], ['>=01', false], ['1.5 及以下', false], ['至少', false], ['至多 1 及以上', false],
                ['<1', true], ['少于 0 个、多于 6 个', true], ['<0,>6', true], ['少于2、3-4、多于5、≥6', true],
                ['>7', false], ['0、少于 7 个', false], ['< -1', false], ['多于', false], ['少于 1 及以上', false],
                ['<<1', false], ['>>2', false], ['多于01个', false], ['>=1-2', false],
                ['(0,6)', true], ['[0,6)', true], ['(0,6]', true], ['[0,6]', true], ['[0,0)', true], ['(6,6]', true],
                ['0,(1,4]，[5,6)', true], ['（0，3］、[2,5),2,>5', true], [' ( 1 , 3 ] , 2 到 4 , ≤1 ', true],
                ['≥0,(2,7]', false], ['(4,3]', false], ['(,2]', false], ['(2,)', false], ['(1,2', false],
                ['[0,1,2)', false], ['([0,2))', false], ['(0,1][1,2)', false], ['(0,2),', false],
                ['[-1,2)', false], ['[00,1)', false], ['1,2)', false],
                ['0,7', false], ['2-7', false], ['4-2', false], ['1.5', false], ['01', false], ['0,,2', false], ['', false],
            ]) {
                input.value = value;
                input.dispatchEvent(new window.Event('input'));
                assert.equal(input.checkValidity(), valid, value);
            }
            input.value = '0、(1,4]、[5,6)';
            tags.options[5].selected = false;
            tags.dispatchEvent(new window.Event('change'));
            assert.equal(input.validationMessage, 'Invalid count or range');
            tags.options[5].selected = true;
            window.dispatchEvent(new window.Event('pageshow'));
            assert.ok(input.checkValidity());
            const data = new window.FormData(form);
            assert.equal(data.get(name + '_mode'), rule);
            assert.equal(data.get(name + '_ranges'), input.value);
        }
        mode.value = 'any_range';
        mode.dispatchEvent(new window.Event('change'));
        assert.equal(input.validationMessage, 'Invalid range');
        input.value = '少于 1 个';
        input.dispatchEvent(new window.Event('input'));
        assert.equal(input.validationMessage, 'Invalid range');
        mode.value = 'any';
        mode.dispatchEvent(new window.Event('change'));
        assert.ok(!new window.FormData(form).has(name + '_ranges'));
    }
    console.log('PASS mixed tag count entry, bounds, form restoration and mode switching on both sides');
} finally {
    window.close();
}
