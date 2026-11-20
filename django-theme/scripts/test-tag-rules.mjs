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
                ['≥0,(2,7]', false], ['(4,3]', false], ['(1,2', false],
                ['(,2)', true], ['(,2]', true], ['(2,)', true], ['[2,)', true], ['(,0),(6,)', true],
                [' ( , 0 ] ，（ 2 ， ）,1-2,［6，）', true], ['(,3],2,(2,4],(3,)', true],
                ['(,)', true], ['0,(1,4],(,),[6,)', true], ['（ ， ）、(,)', true],
                ['*', true], ['0,(1,4], *,[3,6],>5', true], ['*、(,) ， *', true],
                ['(*,3)', true], ['(*,3]', true], ['(3,*)', true], ['[3,*)', true], ['(*,*)', true],
                ['(*,0], [6,*)', true], ['(*,),3、(,*)', true], ['0、（ * ，2］, [2,4),3,[5,*)', true],
                ['(*,7]', false], ['[7,*)', false], ['[*,2)', false], ['(2,*]', false], ['[*,*)', false],
                ['(*,*]', false], ['(*,*),7', false], ['(1*,2]', false], ['(1,**)', false], ['(*,*,1)', false],
                ['(-∞,3)', true], ['(-∞,3]', true], ['(3,+∞)', true], ['[3,+∞)', true], ['(-∞,+∞)', true],
                ['(-∞,0], [6,+∞)', true], ['(-∞,*), 1、(, +∞)', true], ['（ -∞ ，2］、[2,4),3,[5,+∞)', true],
                ['(+∞,1]', false], ['[1,-∞)', false], ['(+∞,-∞)', false], ['(-∞,-∞)', false], ['(+∞,+∞)', false],
                ['[-∞,2]', false], ['[2,+∞]', false], ['(-∞,7]', false], ['[7,+∞)', false], ['(-∞,01]', false],
                ['(-∞,+∞),(+∞,1]', false], ['[1,-∞),*', false], ['(∞,2]', false], ['+∞', false], ['-∞', false],
                ['(-inf,3)', true], ['(-InF,3]', true], ['(3,+iNF)', true], ['[3,+INF)', true], ['(-INF,+inf)', true],
                ['(-inf,0], [6,+InF)', true], ['（ -Inf ，2］、[2,4),3,[5,+∞)', true], ['(-∞,+inF),(-INF,*)', true],
                ['(+InF,1]', false], ['[1,-iNf)', false], ['(+INF,-inf)', false], ['(-Inf,+inf),(+inf,1]', false],
                ['[1,-inf),*', false], ['[-inf,2]', false], ['[2,+INF]', false], ['(-inf,7]', false], ['[7,+inf)', false],
                ['(-inf,01]', false], ['(inf,2]', false], ['+inf', false], ['-INF', false],
                ['(1,+inf2)', false], ['(-ınf,2]', false],
                ['(-infinity,3)', true], ['(-InFiNiTy,3]', true], ['(3,+INFINITY)', true], ['[3,+iNfInItY)', true],
                ['(-INFINITY,+infinity)', true], ['(-Infinity,0],[6,+Infinity)', true], ['（ -INFINITY ，2］、3,[5,+inf)', true],
                ['(+Infinity,1]', false], ['[1,-infinity)', false], ['[1,-Infinity),*', false], ['(+infinity,-infinity)', false],
                ['[-infinity,2]', false], ['[2,+Infinity]', false], ['(-Infinity,7]', false], ['[7,+INFINITY)', false],
                ['(infinity,2]', false], ['+Infinity', false], ['-infinity', false],
                ['(-infin,1]', false], ['(-infinityx,1]', false], ['(1,+infinity2)', false], ['(-infınity,2]', false],
                ['[3,∞)', true], ['[3,inf)', true], ['[3,Infinity)', true], ['(3,iNf)', true],
                ['[0,INFINITY)', true], ['(6,inf)', true], ['(-Inf,Infinity)', true], ['0,2-4,［4，InFiNiTy）、≥6', true],
                ['[7,inf)', false], ['(2,∞]', false], ['*,(Infinity,2]', false], ['[0,Infinity),[1,-inf)', false],
                ['Infinity', false], ['(1,infinityx)', false], ['(1,ınf)', false],
                ['(−∞,3]', true], ['(−inf,3)', true], ['(−Infinity,0]', true], ['(−iNf,0)', true], ['(−INFINITY,6]', true],
                ['(−Inf,Infinity)', true], ['（ −InFiNiTy ，2］、[2,4)、3、[5,inf)', true],
                ['(1,−∞)', false], ['*,(1,−Inf)', false], ['(1,−INFINITY),*', false], ['[−inf,2]', false], ['(−∞,7]', false],
                ['(−infinity,−1]', false], ['1−2', false], ['(−−inf,2]', false], ['(−ınf,1]', false], ['−∞', false],
                ['*,7', false], ['2-1,*', false], ['**', false], ['1*', false], ['[*,2]', false], ['*,', false],
                ['(,),7', false], ['(7,), (,)', false], ['(,),4-2', false], ['(,),', false], ['(,,)', false],
                ['[,)', false], ['[,]', false], ['(,]', false], ['[,1)', false], ['[,1]', false], ['(1,]', false], ['[1,]', false],
                ['(,7]', false], ['[7,)', false], ['(,01)', false], ['(,-1]', false], ['(1,,)', false], ['(,1][2,)', false],
                ['[0,1,2)', false], ['([0,2))', false], ['(0,1][1,2)', false], ['(0,2),', false],
                ['[-1,2)', false], ['[00,1)', false], ['1,2)', false],
                ['0,7', false], ['2-7', false], ['4-2', false], ['1.5', false], ['01', false], ['0,,2', false], ['', false],
            ]) {
                input.value = value;
                input.dispatchEvent(new window.Event('input'));
                assert.equal(input.checkValidity(), valid, value);
            }
            input.value = '(−InFiNiTy,2]、(1,4]、[6,iNfInItY)';
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
        input.value = '*';
        input.dispatchEvent(new window.Event('input'));
        assert.equal(input.validationMessage, 'Invalid range');
        input.value = '(*,2]';
        input.dispatchEvent(new window.Event('input'));
        assert.equal(input.validationMessage, 'Invalid range');
        input.value = '(-∞,2]';
        input.dispatchEvent(new window.Event('input'));
        assert.equal(input.validationMessage, 'Invalid range');
        input.value = '[2,+INF)';
        input.dispatchEvent(new window.Event('input'));
        assert.equal(input.validationMessage, 'Invalid range');
        input.value = '[2,+INFINITY)';
        input.dispatchEvent(new window.Event('input'));
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
