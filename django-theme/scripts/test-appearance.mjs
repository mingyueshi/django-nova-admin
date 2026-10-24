/* Run against actual Django filters.js, either installed beside nav_sidebar.js
   or extracted beside a pinned django-X.Y.Z.js by scripts/ci_support.py. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
const {JSDOM,VirtualConsole}=createRequire(import.meta.url)('jsdom');
const source=readFileSync(new URL('../src/nova_admin/static/nova_admin/appearance.js',import.meta.url),'utf8');
let paths=process.argv.slice(2);
if(!paths.length)paths=[execFileSync(process.env.PYTHON||'python3',['-c','from pathlib import Path; import django; print(Path(django.__file__).parent / "contrib/admin/static/admin/js/filters.js")'],{encoding:'utf8'}).trim()];
paths=paths.map(file=>path.basename(file)==='nav_sidebar.js'?path.join(path.dirname(file),'filters.js'):/^django-\d+\.\d+\.\d+\.js$/.test(path.basename(file))?file.replace(/\.js$/,'-filters.js'):file);
const delay=()=>new Promise(resolve=>setTimeout(resolve,0));
let count=0;
for(const file of paths){
 const upstream=readFileSync(file,'utf8');
 async function setup(options={}){
  const errors=[],console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e));
  const form='<form class="nova-theme-switcher" method="post" action="/admin/_theme/preference/"><input type="hidden" name="csrfmiddlewaretoken" value="test-only"><input type="hidden" name="next" value="/admin/catalog/product/?q=x"><select id="nova-admin-mode" name="mode"><option value="light">Light</option><option value="dark">Dark</option></select><select id="nova-admin-palette" name="palette"><option value="default">Default</option><option value="plum">Plum</option></select><button type="submit">Apply</button></form>';
  const dom=new JSDOM(`<!doctype html><body class="nova-admin">${options.noAppearance?form:`<details class="nova-appearance"><summary>Appearance settings</summary>${form}</details>`}<details data-filter-title="Status" open><summary>By status</summary><p>Native filter</p></details><form id="business"><input name="unsaved" value="preserved"></form></body>`,{runScripts:'outside-only',url:'https://example.invalid/admin/catalog/product/',virtualConsole:console});
  const w=dom.window,d=w.document,values=new Map(Object.entries(options.storage||{}));const writes=[];
  const storage={getItem:k=>values.get(k)??null,setItem:(k,v)=>{writes.push([k,String(v)]);values.set(k,String(v));}};
  const storageDenied=new w.DOMException('Storage denied','SecurityError');let storageDenials=0;
  const denyStorage=()=>{storageDenials++;throw storageDenied;};
  if(options.denyStorage)assert.throws(denyStorage,error=>error===storageDenied&&error.name==='SecurityError');
  Object.defineProperty(w,'sessionStorage',{get(){if(options.denyStorage)return denyStorage();return storage;}});
  Object.defineProperty(w,'localStorage',{get(){throw Error('Appearance must not use storage');}});
  for(const key of ['fetch','XMLHttpRequest','open'])w[key]=()=>{throw Error('No preference requests or windows');};
  w.CSS={escape:value=>String(value)};
  const preference=d.querySelector('.nova-appearance'),filter=d.querySelector('[data-filter-title]'),originalForm=d.querySelector('.nova-theme-switcher');
  let nativeError,nativeStorageDenials=0,submits=0;originalForm.addEventListener('submit',event=>{event.preventDefault();submits++;});
  const runNative=()=>{const before=storageDenials;try{w.eval(upstream);}catch(error){nativeError=error;}finally{nativeStorageDenials+=storageDenials-before;}};
  if(options.nativeFirst){runNative();w.eval(source);}else{w.eval(source);runNative();}
  await delay();
  return{w,d,preference,filter,originalForm,nativeError,nativeStorageDenials,writes,storage,
   async toggle(element,open){element.open=open;await delay();},
   finish(){assert.deepEqual(errors,[]);assert.equal(submits,0);w.close();}};
 }
 async function test(name,run){try{await run();count++;}catch(error){error.message=`${file}: appearance ${name}: ${error.message}`;throw error;}}
 await test('guard before native hook prevents undefined filter storage',async()=>{const r=await setup();const before=r.storage.getItem('django.admin.filtersState');await r.toggle(r.preference,true);await r.toggle(r.preference,false);assert.equal(r.storage.getItem('django.admin.filtersState'),before);assert.equal(r.preference.hasAttribute('data-filter-title'),false);r.finish();});
 await test('capture guard also works when native listener was registered first',async()=>{const r=await setup({nativeFirst:true});const before=r.storage.getItem('django.admin.filtersState');await r.toggle(r.preference,true);await r.toggle(r.preference,false);assert.equal(r.storage.getItem('django.admin.filtersState'),before);r.finish();});
 await test('genuine native filter still persists open and closed state',async()=>{const r=await setup();await r.toggle(r.filter,false);assert.equal(JSON.parse(r.storage.getItem('django.admin.filtersState')).Status,false);await r.toggle(r.filter,true);const state=JSON.parse(r.storage.getItem('django.admin.filtersState'));assert.equal(state.Status,true);assert.equal(Object.hasOwn(state,'undefined'),false);r.finish();});
 await test('stored native filter states restored without appearance history or key cleanup',async()=>{const r=await setup({storage:{'django.admin.filtersState':'{"Status":false,"undefined":true}'}});assert.equal(r.filter.open,false);assert.equal(r.preference.open,false);const before=r.storage.getItem('django.admin.filtersState');await r.toggle(r.preference,true);await r.toggle(r.preference,false);assert.equal(r.storage.getItem('django.admin.filtersState'),before);r.finish();});
 // Node 26/JSDOM may turn a denied bare-global getter into ReferenceError; strict SecurityError preflight plus native denial/interruption checks preserve this scenario.
 await test('blocked storage does not disable the disclosure or original form',async()=>{const r=await setup({denyStorage:true});assert.ok(r.nativeStorageDenials>0,'Native filters must reach the controlled storage denial');assert.ok(r.nativeError,'Native filters must stop when storage is denied');await r.toggle(r.preference,true);assert.equal(r.preference.open,true);assert.equal(r.d.querySelector('#nova-admin-mode').disabled,false);assert.equal(r.originalForm.isConnected,true);assert.deepEqual(r.writes,[]);r.finish();});
 await test('form nodes values tokens business state and host change listeners remain original',async()=>{const r=await setup(),mode=r.d.querySelector('#nova-admin-mode'),token=r.d.querySelector('[name=csrfmiddlewaretoken]');let changed=0;mode.addEventListener('change',()=>changed++);mode.value='dark';mode.dispatchEvent(new r.w.Event('change',{bubbles:true}));const values=[...new r.w.FormData(r.originalForm)];await r.toggle(r.preference,true);await r.toggle(r.preference,false);assert.equal(changed,1);assert.equal(r.d.querySelector('.nova-theme-switcher'),r.originalForm);assert.equal(r.d.querySelector('[name=csrfmiddlewaretoken]'),token);assert.deepEqual([...new r.w.FormData(r.originalForm)],values);assert.equal(r.d.querySelector('#business input').value,'preserved');r.finish();});
 await test('reinitialization affects only the settings toggle and no field events',async()=>{const r=await setup();r.w.eval(source);let changes=0;r.originalForm.addEventListener('change',()=>changes++);r.d.querySelector('#nova-admin-palette').dispatchEvent(new r.w.Event('change',{bubbles:true}));await r.toggle(r.preference,true);await r.toggle(r.filter,false);assert.equal(changes,1);assert.equal(JSON.parse(r.storage.getItem('django.admin.filtersState')).Status,false);r.finish();});
 await test('missing settings disclosure leaves native recovery form and native filter untouched',async()=>{const r=await setup({noAppearance:true});assert.equal(r.preference,null);assert.equal(r.originalForm.method,'post');await r.toggle(r.filter,false);assert.equal(JSON.parse(r.storage.getItem('django.admin.filtersState')).Status,false);r.finish();});
 console.log(`Appearance DOM: passed with ${file}`);
}
console.log(`${count} appearance DOM scenarios passed (${paths.length} Django script versions).`);
