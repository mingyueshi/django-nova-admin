const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createApp } = require('./dom-runtime.cjs');
let count = 0;
const check = (name, fn) => { fn(); count++; console.log('PASS', name); };
const tick = () => new Promise(resolve => setTimeout(resolve, 15));
(async () => {
  const { icon, openIcons, iconLibraries } = await import('../dist/js/icons.js');
  check('five versioned libraries expose exactly 320 namespaced offline icons', () => {
    assert.equal(iconLibraries.length, 5); assert.equal(Object.keys(openIcons).length, 320);
    for (const provider of iconLibraries) assert.equal(Object.values(openIcons).filter(entry => entry.library === provider.id).length, 64);
  });
  for (const [id, entry] of Object.entries(openIcons)) {
    check(id + ': real SVG geometry and local original are available', () => {
      const markup = icon(id, '', {size:32,strokeWidth:2.5,label:entry.label});
      assert.ok(markup.includes(entry.body)); assert.match(markup, /width="32" height="32"/); assert.match(markup, entry.stroke === 'none' ? /stroke-width="0"/ : /stroke-width="2.5"/); assert.ok(markup.includes(`viewBox="${entry.viewBox}"`)); assert.match(markup,/role="img"/);
      assert.ok(fs.existsSync(path.join(__dirname, '../dist/assets/icons', entry.file)));
    });
  }
  check('legacy names, unknown-name fallback and escaping remain reliable', () => {
    assert.equal(icon('missing'), icon('grid')); assert.equal(icon('__proto__'), icon('grid'));
    assert.match(icon('search'), /aria-hidden="true"/);
    assert.doesNotMatch(icon('lucide:search', '"><img src=x>', {label:'"><script>x</script>',size:999,strokeWidth:999}), /<img|<script|width="999"|stroke-width="999"/);
  });
  const app = await createApp({url:'https://example.test/#icons'}); const {w,d} = app; const q = s => d.querySelector(s);
  const change = (id,value) => {q(id).value=value;q(id).dispatchEvent(new w.Event('change',{bubbles:true}));};
  const search = value => {q('#icon-search').value=value;q('#icon-search').dispatchEvent(new w.Event('input',{bubbles:true}));};
  check('icon route, sidebar and initial grid are directly accessible', () => {
    assert.match(q('h1').textContent,/图标/); assert.equal(d.querySelectorAll('[data-icon-select]').length,48); assert.ok(q('[href="#icons"]'));
  });
  const seen = new Set();
  for (let page=1;page<=7;page++) {
    const tiles=[...d.querySelectorAll('[data-icon-select]')];
    check('page '+page+': unique bounded results with a visible selected icon',()=>{
      assert.equal(tiles.length,page===7?32:48);
      for(const tile of tiles){assert.ok(!seen.has(tile.dataset.iconSelect));seen.add(tile.dataset.iconSelect);}
      assert.equal(d.querySelectorAll('[data-icon-select][aria-pressed="true"]').length,1);
    });
    if(page<7)q(`[data-icon-page="${page+1}"]`).click();
  }
  check('pagination covers all 320 icons without gaps and disables the last next button',()=>{assert.equal(seen.size,320);assert.ok(q('[data-icon-page="8"]').disabled);});
  search('退款');
  check('business synonyms reset pagination and find all five refund concepts',()=>{assert.equal(d.querySelectorAll('[data-icon-select]').length,5);assert.equal(q('.icon-pagination'),null);});
  for(const keyword of ['库存','审批','工单','报表','备份','API','令牌']) {
    search(keyword);check(keyword+': business keyword search spans five libraries',()=>assert.equal(new Set([...d.querySelectorAll('[data-icon-select]')].map(el=>el.dataset.iconSelect.split(':')[0])).size,5));
  }
  search('');
  q('[data-icon-library="heroicons"]').click();
  check('library selection filters to 64 with 48 visible entries', () => { assert.equal(d.querySelectorAll('[data-icon-select]').length,48);assert.match(q('.icon-id').textContent,/^heroicons:/);assert.match(q('#icon-result-count').textContent,/64 \/ 320/); });
  search('搜索');
  check('Chinese meaning search finds official names across naming conventions',()=>{assert.equal(d.querySelectorAll('[data-icon-select]').length,1);assert.match(q('.icon-id').textContent,/magnifying-glass/);});
  search('<img onerror=alert(1)>');
  check('no-result search is safe and offers a usable reset',()=>{assert.ok(q('[data-icon-reset]'));assert.equal(q('img[onerror]'),null);});
  q('[data-icon-reset]').click();
  check('reset restores all libraries, categories and query without changing focus',()=>{assert.equal(d.querySelectorAll('[data-icon-select]').length,48);assert.equal(d.activeElement,q('#icon-search'));});
  search('ARROW-RIGHT');
  check('English search is case-insensitive and works across libraries',()=>assert.equal(d.querySelectorAll('[data-icon-select]').length,5));
  search(''); change('#icon-category','用户与权限');
  check('category filtering includes the five user and security concepts per library',()=>assert.equal(d.querySelectorAll('[data-icon-select]').length,25));
  change('#icon-category','all'); change('#icon-size','48');change('#icon-stroke','1.5');
  check('size and stroke controls update both preview and code',()=>{assert.equal(q('.icon-detail-preview svg').getAttribute('width'),'48');assert.equal(q('.icon-detail-preview svg').getAttribute('stroke-width'),'1.5');assert.match(q('.icon-code').textContent,/"size": 48/);});
  q('[data-icon-library="tabler"]').click();
  const tile=q('[data-icon-select="tabler:download"]');tile.focus();tile.querySelector('svg').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  check('clicking nested SVG selects exactly one icon and keeps focus',()=>{assert.equal(d.querySelectorAll('[data-icon-select][aria-pressed="true"]').length,1);assert.equal(d.activeElement,tile);assert.match(q('.icon-id').textContent,/tabler:download/);});
  q('[data-icon-code="django"]').click();
  check('Django snippet is a real template call with matching size and stroke',()=>{assert.match(q('.icon-code').textContent,/{% nova_icon "tabler:download" size=48 stroke_width=1.5/);assert.doesNotMatch(q('.icon-code').textContent,/settings.py/);});
  q('[data-icon-code="navigation"]').click();
  check('navigation configuration is separate and uses the same identifier',()=>assert.match(q('.icon-code').textContent,/NOVA_ADMIN_NAV_ICONS[\s\S]*tabler:download/));
  q('[data-icon-code="svg"]').click();
  check('SVG code is text and download points to the reviewed original',()=>{assert.match(q('.icon-code').textContent,/<svg/);assert.equal(q('.icon-code svg'),null);assert.ok(q('[download]').href.endsWith('/assets/icons/tabler/download.svg'));});
  Object.defineProperty(w.navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('Denied');}}});
  q('[data-icon-copy]').click();await tick();
  check('clipboard denial provides selected manual-copy text without claiming success',()=>{assert.equal(q('#icon-copy-fallback').hidden,false);assert.match(q('#icon-copy-status').textContent,/未能自动复制/);assert.equal(d.activeElement,q('#icon-copy-fallback'));});
  let copied='';Object.defineProperty(w.navigator,'clipboard',{configurable:true,value:{writeText:async value=>{copied=value;}}});
  q('[data-icon-copy]').click();await tick();
  check('successful copy uses the displayed snippet and reports completion',()=>{assert.equal(copied,q('.icon-code').textContent);assert.match(q('#icon-copy-status').textContent,/已复制/);});
  q('[data-icon-library="bootstrap"]').click();search('支付方式');
  check('Bootstrap preserves 16-unit filled geometry and ignores outline width',()=>{
    const svg=q('.icon-detail-preview svg');assert.equal(svg.getAttribute('viewBox'),'0 0 16 16');assert.equal(svg.getAttribute('fill'),'currentColor');assert.equal(svg.getAttribute('stroke'),'none');assert.equal(svg.getAttribute('stroke-width'),'0');
    assert.match(q('.icon-detail-head').textContent,/填充样式/);
  });
  q('[data-icon-code="django"]').click();
  check('filled Django snippets omit inapplicable stroke controls',()=>{assert.match(q('.icon-code').textContent,/bootstrap:credit-card/);assert.doesNotMatch(q('.icon-code').textContent,/stroke_width/);});
  q('[data-icon-code="js"]').click();
  check('filled JavaScript snippets omit inapplicable stroke controls',()=>assert.doesNotMatch(q('.icon-code').textContent,/strokeWidth/));
  search('');q('[data-icon-page="2"]').click();q('[data-icon-library="iconoir"]').click();
  check('library changes reset pagination and preserve native Iconoir strokes',()=>{assert.ok(q('[data-icon-page="0"]').disabled);assert.equal(q('.icon-detail-preview svg').getAttribute('viewBox'),'0 0 24 24');});
  for (const provider of iconLibraries) {
    check(provider.id + ': attribution and local license are delivered',()=>{assert.ok(fs.existsSync(path.join(__dirname,'../dist/assets/icons',provider.license_path)));assert.ok(provider.docs.startsWith('https://'));});
  }
  app.close(); console.log('TOTAL',count,'icon checks passed');
})().catch(error=>{console.error(error);process.exit(1);});
