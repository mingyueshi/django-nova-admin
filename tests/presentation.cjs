const { createApp } = require('./dom-runtime.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
let count = 0;
const check = (name, fn) => { fn(); count++; console.log('PASS', name); };
const wait = () => new Promise(r => setTimeout(r, 25));
(async () => {
  for (const [platform, text, shortcut] of [['Win32','Ctrl K','Control+k'],['Linux x86_64','Ctrl K','Control+k'],['MacIntel','⌘ K','Meta+k'],['','Ctrl K','Control+k']]) {
    const app = await createApp({ platform });
    try {
      check(`Search shortcut presentation matches ${platform || 'unknown platform'}`, () => {
        const b = app.d.querySelector('.global-search');
        assert.equal(b.querySelector('kbd').textContent, text);
        assert.equal(b.getAttribute('aria-keyshortcuts'), shortcut);
        assert.match(b.getAttribute('aria-label'), /搜索页面或用户（(Control|Command) 加 K）/);
      });
      for (const key of ['ctrlKey','metaKey']) {
        app.d.dispatchEvent(new app.w.KeyboardEvent('keydown',{key:'k',[key]:true,bubbles:true}));
        check(`${platform || 'unknown'} ${key} still opens keyboard search`, () => assert.ok(app.d.querySelector('#command-search')));
        app.d.dispatchEvent(new app.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
      }
    } finally { app.close(); }
  }
  const app = await createApp();
  try {
    check('Chinese dashboard units are compact', () => {
      assert.ok(app.d.querySelector('.metrics').textContent.includes('99.2%'));
      assert.ok(app.d.querySelector('.health-list').textContent.includes('124ms'));
    });
    for (const route of ['overview','users','catalog','news','roles','audit','components','settings','native-samples','login-preview']) {
      app.w.location.hash=route; await wait();
      check(`${route} exposes a direct title without decorative eyebrow`, () => {
        assert.ok(app.d.querySelector('h1')?.textContent.trim());
        assert.equal(app.d.querySelector('.eyebrow'),null);
        assert.doesNotMatch(app.d.querySelector('main').textContent, /WORKSPACE OVERVIEW|MEMBERS & ACCESS|BUSINESS \/ CATALOG|NATIVE ADMIN \/ VERIFIED/);
      });
    }
    app.w.location.hash='catalog'; await wait();
    check('Price presentation is compact and does not alter numeric values', () => {
      assert.match(app.d.querySelector('.catalog-table').textContent,/¥299\.00/);
      assert.doesNotMatch(app.d.querySelector('.catalog-table').textContent,/¥\s+\d/);
    });
    app.w.location.hash='catalog/edit/101'; await wait();
    check('Numeric editor still retains original value and native semantics', () => {
      const input=app.d.querySelector('#product-price');
      assert.equal(input.value,'299');assert.equal(input.type,'number');assert.equal(input.step,'0.01');
    });
  } finally { app.close(); }
  const read=(name)=>fs.readFileSync(path.join(__dirname,'../dist',name),'utf8');
  check('All preview Chinese stacks include the same available local fallbacks', () => {
    for (const file of ['styles.css','login-preview.css']) for(const font of ['Noto Sans SC','Source Han Sans SC','HarmonyOS Sans SC','Microsoft YaHei']) assert.ok(read(file).includes(`"${font}"`));
  });
  const css=read('styles.css');
  const light=css.match(/:root\[data-theme=light\]\{([^}]+)\}/)[1];
  const token=(key)=>light.match(new RegExp(`--${key}:(#[a-f0-9]{3,6})`))[1];
  const rgb=(hex)=>{const value=hex.length===4?'#'+[...hex.slice(1)].map(x=>x+x).join(''):hex;return value.slice(1).match(/../g).map(x=>parseInt(x,16)/255);};
  const luminance=(a)=>a.map(x=>x<=0.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((n,x,i)=>n+x*[.2126,.7152,.0722][i],0);
  const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
  check('Error text retains readable contrast on panel and actual tinted feedback surfaces', () => {
    const fg=rgb(token('danger')),base=rgb(token('panel'));
    for(const alpha of [0,.06,.07,.1]) assert.ok(contrast(fg,base.map((v,i)=>v*(1-alpha)+fg[i]*alpha))>=4.5);
  });
  check('Main accent has one explicit blue declaration for each mode', () => {
    const roots = [...css.matchAll(/:root(?:\[data-theme=light\])?\{([^}]+)\}/g)].map(m=>m[1]).join(';');
    assert.equal((roots.match(/--accent:/g)||[]).length,2);
    assert.ok(css.includes('--accent:#417690'), 'The native comparison retains its own color');
    assert.equal(token('accent'),'#1d4ed8');
  });
  console.log('TOTAL',count,'presentation checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
