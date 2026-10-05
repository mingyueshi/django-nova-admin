// Node/jsdom workflow regression checks. Browser rendering and real image decoding
// are intentionally outside this suite; image events exercise the shared handlers.
const {createApp}=require('./dom-runtime.cjs');
const assert=require('node:assert/strict');
let passed=0;
const wait=(ms=20)=>new Promise(resolve=>setTimeout(resolve,ms));
async function session(run){const app=await createApp(),{w,d}=app,errors=[];w.addEventListener('error',event=>errors.push(event.error));const q=selector=>d.querySelector(selector),all=selector=>[...d.querySelectorAll(selector)];const route=async path=>{w.location.hash=path;await wait();};const input=(selector,value)=>{const field=q(selector);field.value=value;field.dispatchEvent(new w.Event('input',{bubbles:true}));};const change=(selector,value)=>{const field=q(selector);if(typeof value==='boolean')field.checked=value;else field.value=value;field.dispatchEvent(new w.Event('change',{bubbles:true}));};const submit=(mode='continue',form=q('#catalog-form'))=>form.dispatchEvent(new w.SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:q(`[data-save-mode="${mode}"]`)}));const check=(name,fn)=>{fn();console.log('PASS',name);passed++;};try{await run({w,d,q,all,route,input,change,submit,check});assert.deepEqual(errors,[],'No uncaught workflow exception');}finally{app.close();}}
(async()=>{
 await session(async({w,q,all,route,input,change,check,d})=>{
  for(const [name,search] of [['catalog','catalog-search'],['users','user-search'],['news','news-search']]){
   await route(name+'?q=不存在');await route('overview');await route(name);
   check(name+' bare route clears previous search',()=>{assert.equal(q('#'+search).value,'');assert.equal(w.location.hash,'#'+name);});
   await route(name+'?page=1.5');check(name+' fractional page is normalized',()=>{assert.equal(w.location.hash,'#'+name);assert.equal(q('.pagination [aria-current]').textContent,'1');});
   await route(name+'?page=999');const expected=3;check(name+' oversized page clamps URL and current control together',()=>{assert.equal(w.location.hash,'#'+name+'?page='+expected);assert.equal(q('.pagination [aria-current]').textContent,String(expected));});
  }
  await route('catalog');change('.catalog-table .catalog-check',true);await route('catalog?q=键盘');check('URL filter changes clear hidden catalog selection',()=>assert.equal(q('.bulk-bar'),null));
  input('#catalog-search','不存在');q('[data-catalog="reset-filters"]').click();check('Catalog empty recovery returns keyboard focus to search',()=>{assert.equal(d.activeElement.id,'catalog-search');assert.equal(all('.catalog-table tbody tr').length,10);});
  await route('news');change('.news-table .news-check',true);await route('news?category=产品故事');check('URL category changes clear hidden news selection',()=>assert.equal(q('.bulk-bar'),null));
  input('#news-search','不存在');check('Empty news view disables select-all',()=>assert.ok(q('#news-mobile-all').disabled));q('[data-news="reset"]').click();check('News empty recovery returns keyboard focus to search',()=>assert.equal(d.activeElement.id,'news-search'));
 });
 await session(async({w,q,route,input,submit,check})=>{
  await route('catalog');q('.catalog-table [data-feature-toggle="101"]').click();await route('catalog/edit/101');input('#product-title','正在编辑的键盘');submit();
  check('Pending list switch blocks competing form save without losing input',()=>{assert.equal(w.localStorage.getItem('nova-catalog'),null);assert.match(q('#product-save-feedback').textContent,/请稍候/);assert.equal(q('#product-title').value,'正在编辑的键盘');});
  await wait(490);check('Completed switch synchronizes an open dirty editor',()=>{assert.equal(q('[name="featured"]').checked,false);assert.match(q('#product-dirty-status').textContent,/未保存/);assert.equal(q('#product-title').value,'正在编辑的键盘');});
  submit();check('Saving the editor retains the completed list switch value',()=>{const row=JSON.parse(w.localStorage.getItem('nova-catalog')).find(r=>r.id===101);assert.equal(row.featured,false);assert.equal(row.title,'正在编辑的键盘');});
 });
 await session(async({w,q,route,input,change,submit,check})=>{
  await route('catalog');q('[data-feature-toggle="101"]').click();await route('catalog/edit/101');change('[name="featured"]',false);change('[name="featured"]',true);await wait(490);
  check('An explicit editor choice is retained when the list save finishes',()=>{assert.equal(q('[name="featured"]').checked,true);assert.match(q('#product-save-feedback').textContent,/新选择仍待保存/);});submit();check('Saving an explicit editor override commits that choice',()=>assert.equal(JSON.parse(w.localStorage.getItem('nova-catalog')).find(r=>r.id===101).featured,true));
  await route('catalog');q('#catalog-fail-next').checked=true;q('[data-feature-toggle="101"]').click();await route('catalog/edit/101');input('#product-title','失败后继续编辑');await wait(490);
  check('Failed list save retains original editor state and current text',()=>{assert.equal(q('[name="featured"]').checked,true);assert.equal(q('#product-title').value,'失败后继续编辑');assert.match(q('#product-save-feedback').textContent,/原状态已保留/);});
  submit();check('Form remains saveable after the interrupted list save fails',()=>assert.equal(JSON.parse(w.localStorage.getItem('nova-catalog')).find(r=>r.id===101).title,'失败后继续编辑'));
 });
 await session(async({w,q,route,input,submit,check})=>{
  await route('catalog/edit/101');input('#product-title','只保存一次');const form=q('#catalog-form');submit('list',form);submit('list',form);await wait();
  check('Repeated save-and-return submits only one record change and audit event',()=>{assert.ok(q('.catalog-table'));assert.equal(JSON.parse(w.localStorage.getItem('nova-audit')).filter(event=>event.type==='修改商品').length,1);});
  await route('catalog/edit/101');input('#product-title','保留输入再试');const setItem=w.Storage.prototype.setItem;w.Storage.prototype.setItem=()=>{throw new Error('quota');};submit();
  check('Failed form persistence keeps input and leaves retry enabled',()=>{assert.equal(q('#product-title').value,'保留输入再试');assert.equal(q('[data-save-mode="continue"]').disabled,false);assert.notEqual(q('#catalog-form').dataset.saving,'true');});w.Storage.prototype.setItem=setItem;submit();
  check('Form persistence retry commits once and clears dirty status',()=>{assert.equal(JSON.parse(w.localStorage.getItem('nova-catalog')).find(r=>r.id===101).title,'保留输入再试');assert.equal(q('#product-dirty-status').textContent,'没有未保存的更改');});
  const stock=q('[data-variant-field="stock"]');input('#'+stock.id,'9007199254740992');submit();check('Inventory rejects unsafe integers rather than silently rounding',()=>{assert.match(q('#'+stock.id+'-error').textContent,/安全范围/);assert.equal(q('#'+stock.id).value,'9007199254740992');});
 });
 await session(async({w,d,q,route,check})=>{
  await route('catalog/edit/101');const select=q('#product-category'),combo=q('#product-category-combobox');select.insertAdjacentHTML('beforeend','<optgroup label="不可用分类" disabled><option value="disabled-category">不可用分类</option></optgroup>');combo.click();combo.dispatchEvent(new w.KeyboardEvent('keydown',{key:'End',bubbles:true,cancelable:true}));combo.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
  check('Searchable select skips options in a disabled group',()=>{assert.equal(select.value,'出行装备');assert.equal(combo.value,'出行装备');assert.equal(d.activeElement,combo);});
  select.required=true;await wait();check('Searchable select exposes the native required state',()=>{assert.equal(combo.required,true);assert.equal(combo.getAttribute('aria-required'),'true');});
  combo.click();select.closest('fieldset').disabled=true;await wait();check('Disabling an open searchable field closes its popup',()=>{assert.ok(combo.disabled);assert.equal(combo.getAttribute('aria-expanded'),'false');assert.equal(combo.getAttribute('aria-activedescendant'),null);});
 });
 await session(async({w,d,q,route,check})=>{
  await route('news');const trigger=q('.news-table .media-thumb'),image=trigger.querySelector('img');image.dispatchEvent(new w.Event('error'));trigger.focus();trigger.click();
  check('Unexpected image failure has the same retry path as the demo fixture',()=>{assert.equal(trigger.dataset.mediaState,'error');assert.ok(q('[data-media-retry]'));assert.ok(q('#media-fail-next'));});
  q('[data-media-retry]').click();q('.media-preview img').dispatchEvent(new w.Event('error'));
  check('A failed image retry restores the retry button and readable status',()=>{assert.equal(q('[data-media-retry]').disabled,false);assert.equal(q('.media-full').dataset.mediaState,'error');assert.match(q('#media-preview-status').textContent,/再次重新加载/);});
  q('[data-media-retry]').click();q('.media-preview img').dispatchEvent(new w.Event('load'));
  check('Image retry success clears stale error and loading state',()=>{assert.equal(q('.media-full').dataset.mediaState,'ready');assert.ok(q('.media-full.media-loaded'));assert.equal(q('.media-full').getAttribute('aria-busy'),'false');assert.equal(q('[data-media-retry]').disabled,false);});
  q('#media-fail-next').checked=true;q('[data-media-retry]').click();q('.media-preview img').dispatchEvent(new w.Event('load'));
  check('Visible one-shot image control produces a repeatable local failure',()=>{assert.equal(q('#media-fail-next').checked,false);assert.ok(q('.media-full.media-error'));assert.equal(q('[data-media-retry]').disabled,false);assert.ok(q('.media-preview img').src.endsWith('/assets/demo/covers-sheet.webp'));});
  q('[data-media-retry]').click();q('.media-preview img').dispatchEvent(new w.Event('load'));q('[aria-label="关闭图片预览"]').click();check('Recovery and close restore the original thumbnail focus',()=>assert.equal(d.activeElement,trigger));trigger.click();q('.media-preview img').dispatchEvent(new w.Event('load'));check('Reopened recovered image does not replay an old error',()=>assert.ok(q('.media-full.media-loaded')));
 });
 await session(async({w,q,route,check})=>{
  await route('news');q('[data-news-detail="205"]').click();const original=q('.news-detail-cover');original.querySelector('img').dispatchEvent(new w.Event('error'));original.focus();original.click();q('[data-media-retry]').click();q('.media-preview img').dispatchEvent(new w.Event('load'));q('[aria-label="关闭图片预览"]').click();
  check('Nested image recovery refreshes the restored parent drawer thumbnail',()=>{assert.equal(q('.news-detail-cover'),original);assert.equal(original.querySelector('img').dataset.simulateFailure,'false');assert.equal(original.getAttribute('aria-busy'),'true');});original.querySelector('img').dispatchEvent(new w.Event('load'));check('Restored parent image reaches loaded state after its own load event',()=>{assert.equal(original.dataset.mediaState,'ready');assert.ok(original.classList.contains('media-loaded'));});
 });
 console.log('TOTAL',passed,'recovery edge tests passed (Node/jsdom)');
})().catch(error=>{console.error(error);process.exitCode=1;});
