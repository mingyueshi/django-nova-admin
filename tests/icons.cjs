const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { JSDOM } = require('jsdom');
const root = path.join(__dirname, '..');
let count = 0;
function check(name, fn) { fn(); count++; console.log('PASS', name); }
(async () => {
  const { icon, iconCatalog, iconCategories } = await import(pathToFileURL(path.join(root, 'dist/js/icons.js')));
  const source = JSON.parse(fs.readFileSync(path.join(root, 'django-theme/src/nova_admin/icons.json'), 'utf8'));
  check('Preview exactly matches the packaged Django catalog', () => {
    assert.deepEqual(iconCatalog, source.icons);
    assert.deepEqual(iconCategories, source.categories);
    assert.ok(iconCatalog.length >= 90);
    assert.equal(new Set(iconCatalog.map(i => i.name)).size, iconCatalog.length);
    assert.ok(Object.isFrozen(iconCatalog) && iconCatalog.every(Object.isFrozen));
  });
  const dom = new JSDOM('<main></main>');
  const main = dom.window.document.querySelector('main');
  check('Every icon renders one decorative nonfocusable SVG with trusted path data', () => {
    for (const entry of iconCatalog) {
      main.innerHTML = icon(entry.name);
      const svg = main.querySelector('svg');
      assert.equal(main.children.length, 1);
      assert.equal(svg.getAttribute('aria-hidden'), 'true');
      assert.equal(svg.getAttribute('focusable'), 'false');
      assert.equal(svg.getAttribute('viewBox'), '0 0 24 24');
      assert.equal(svg.children.length, 1);
      assert.equal(svg.firstElementChild.localName, 'path');
      assert.equal(svg.firstElementChild.getAttribute('d'), entry.path);
      assert.match(entry.path, /^[Mm][MmLlHhVvCcSsQqTtAaZz0-9., +\-]*$/);
    }
  });
  check('Unknown, prototype and malformed names safely use grid', () => {
    for (const value of ['missing', '__proto__', 'constructor', 'toString', '<svg onload=alert(1)>', 'BOX', '', null, [], {}, 4]) {
      assert.equal(icon(value), icon('grid'));
    }
  });
  check('Class API preserves valid multiple classes and blocks attribute injection', () => {
    main.innerHTML = icon('receipt', 'small business-icon');
    assert.equal(main.firstElementChild.getAttribute('class'), 'icon small business-icon');
    for (const value of ['" onload="alert(1)', '\"><script>alert(1)</script>', 'x\"><foreignObject>', 'a'.repeat(257), {}, null]) {
      main.innerHTML = icon('receipt', value);
      assert.equal(main.children.length, 1);
      assert.equal(main.querySelectorAll('script,foreignObject,img').length, 0);
      assert.equal(main.firstElementChild.hasAttribute('onload'), false);
      for (const attr of main.firstElementChild.attributes) assert.ok(!/^on/i.test(attr.name));
    }
  });
  dom.window.close();
  const guide = new JSDOM(fs.readFileSync(path.join(root, 'dist/icons.html'), 'utf8'));
  const d = guide.window.document;
  const { initIconGuide } = await import(pathToFileURL(path.join(root, 'dist/js/icons-guide.js')));
  initIconGuide(d);
  const visible = () => [...d.querySelectorAll('.icon-card')].filter(n => !n.hidden);
  const search = (value) => { d.querySelector('#icon-search').value = value; d.querySelector('#icon-search').dispatchEvent(new guide.window.Event('input')); };
  check('Catalog exposes all names and Chinese uses with labelled filters', () => {
    assert.equal(visible().length, iconCatalog.length);
    assert.equal(d.querySelectorAll('#icon-category option').length, Object.keys(iconCategories).length + 1);
    assert.ok(d.querySelector('label[for="icon-search"]'));
    assert.ok(d.querySelector('label[for="icon-category"]'));
    assert.equal(d.querySelector('#icon-results').getAttribute('role'), 'status');
  });
  check('English and Chinese search, category intersection and reset work', () => {
    search('  RECEIPT  '); assert.equal(visible().length, 1); assert.ok(visible()[0].textContent.includes('订单'));
    search('订单'); assert.equal(visible().length, 1);
    d.querySelector('#icon-category').value = 'people';
    d.querySelector('#icon-category').dispatchEvent(new guide.window.Event('change'));
    assert.equal(visible().length, 0); assert.equal(d.querySelector('#icon-empty').hidden, false);
    d.querySelector('#icon-reset').click(); assert.equal(visible().length, iconCatalog.length);
    assert.equal(d.activeElement.id, 'icon-search');
  });
  check('Search input is never interpreted as markup and repeated setup is harmless', () => {
    search('<img src=x onerror=alert(1)>');
    assert.equal(visible().length, 0); assert.equal(d.querySelectorAll('img').length, 0);
    initIconGuide(d); assert.equal(d.querySelectorAll('.icon-card').length, iconCatalog.length);
  });
  check('Catalog is discoverable from extension page with local assets only', () => {
    const extensions = fs.readFileSync(path.join(root, 'dist/extensions.html'), 'utf8');
    assert.ok(extensions.includes('href="./icons.html"'));
    for (const node of d.querySelectorAll('[src],link[href],a[href]')) {
      const target = node.getAttribute('src') || node.getAttribute('href');
      assert.ok(target.startsWith('./'));
      assert.ok(fs.statSync(path.join(root, 'dist', target)).isFile());
    }
  });
  guide.window.close();
  console.log(`TOTAL ${count} icon tests passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
