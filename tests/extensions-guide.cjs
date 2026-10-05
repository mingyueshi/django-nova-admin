const { JSDOM } = require('jsdom');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..', 'dist');
const html = fs.readFileSync(path.join(root, 'extensions.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'js/extensions-guide.js'), 'utf8');
const make = () => new JSDOM(html, {url:'https://example.invalid/extensions.html',runScripts:'outside-only'});
let count = 0;
const check = (name, fn) => {fn();count++;console.log('PASS',name);};
const dom = make();
try {
  dom.window.localStorage.setItem('nova-theme','dark');
  dom.window.eval(script);
  check('Guide preserves saved dark appearance',()=>{
    assert.equal(dom.window.document.documentElement.dataset.theme,'dark');
    assert.equal(dom.window.document.querySelector('#guide-theme').textContent,'切换浅色');
  });
  check('Appearance switch updates accessible label and preference',()=>{
    dom.window.document.querySelector('#guide-theme').click();
    assert.equal(dom.window.document.documentElement.dataset.theme,'light');
    assert.equal(dom.window.localStorage.getItem('nova-theme'),'light');
    assert.equal(dom.window.document.querySelector('#guide-theme').getAttribute('aria-label'),'切换深色');
  });
  check('Every guide link resolves to a local delivered page without downloads',()=>{
    for(const a of dom.window.document.querySelectorAll('a[href]')) {
      assert.ok(a.getAttribute('href').startsWith('./'));
      assert.ok(fs.statSync(path.join(root,a.getAttribute('href').split('#')[0])).isFile());
      assert.ok(!a.hasAttribute('download'));
    }
  });
} finally {dom.window.close();}
const denied = make();
try {
  Object.defineProperty(denied.window,'localStorage',{get(){throw Error('Storage unavailable');}});
  denied.window.eval(script);
  check('Guide remains keyboard-click usable without storage',()=>{
    denied.window.document.querySelector('#guide-theme').click();
    assert.equal(denied.window.document.documentElement.dataset.theme,'dark');
  });
} finally {denied.window.close();}
const auto = make();
try {
  auto.window.localStorage.setItem('nova-theme','auto');
  auto.window.matchMedia = () => ({matches:true});
  auto.window.eval(script);
  check('Guide honors automatic dark preference without overwriting it',()=>{
    assert.equal(auto.window.document.documentElement.dataset.theme,'dark');
    assert.equal(auto.window.localStorage.getItem('nova-theme'),'auto');
  });
} finally {auto.window.close();}
console.log(`TOTAL ${count} extensions guide tests passed`);
