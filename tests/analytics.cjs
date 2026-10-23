const assert = require('node:assert/strict');
const { createApp } = require('./dom-runtime.cjs');
let count=0;
const check=(name,fn)=>{fn();count++;console.log('PASS',name);};
const wait=()=>new Promise(resolve=>setTimeout(resolve,25));
(async()=>{
 const {analyticsSnapshot,analyticsBuckets,analyticsCsv,allocate,percentChange}=await import('../dist/js/analytics-data.js');
 check('allocation retains every unit when rounding',()=>{
   assert.deepEqual(allocate(7,[1,1,1]),[3,2,2]);assert.deepEqual(allocate(0,[3,1]),[0,0]);assert.deepEqual(allocate(3,[0,0]),[0,0]);
   for(let n=1;n<100;n++)assert.equal(allocate(n,[34,22,18,17,9]).reduce((a,b)=>a+b,0),n);
 });
 const total=(rows,key)=>rows.reduce((sum,row)=>sum+row[key],0);
 for(const days of [7,30,90])for(const channel of ['all','organic','search','social','partner']){
   const s=analyticsSnapshot({days,channel});
   check(`${days}d ${channel}: current and prior ranges are adjacent, complete and disjoint`,()=>{
     assert.equal(s.daily.length,days);assert.equal(s.prior.length,days);assert.equal(s.daily.at(-1).date,'2026-10-23');assert.equal(Date.parse(s.daily[0].date)-Date.parse(s.prior.at(-1).date),86400000);
     assert.equal(new Set([...s.daily,...s.prior].map(row=>row.date)).size,days*2);
   });
   check(`${days}d ${channel}: every chart reconciles with the same totals`,()=>{
     for(const key of ['revenue','paid','visits','signups']){assert.equal(total(s.daily,key),s.current[key]);assert.equal(total(s.prior,key),s.previous[key]);assert.equal(total(s.channels,key),s.current[key]);}
     assert.equal(total(s.products,'revenue'),s.current.revenue);assert.equal(total(s.products,'paid'),s.current.paid);
     assert.equal(s.heatmap.flat().reduce((a,b)=>a+b,0),s.current.paid);
     assert.ok(s.daily.every(row=>row.visits>=row.viewed&&row.viewed>=row.checkouts&&row.checkouts>=row.paid&&row.paid>=row.newOrders&&Number.isInteger(row.revenue)));
     const weeks=analyticsBuckets(s.daily,'week');for(const key of ['revenue','paid','visits'])assert.equal(total(weeks,key),s.current[key]);
   });
 }
 check('channel-specific results add back to all-channel totals',()=>{
   const all=analyticsSnapshot();for(const key of ['revenue','paid','visits'])assert.equal(['organic','search','social','partner'].reduce((n,channel)=>n+analyticsSnapshot({channel}).current[key],0),all.current[key]);
 });
 check('zero baseline has no invented percent change',()=>{assert.equal(percentChange(1,0),null);assert.equal(percentChange(0,0),null);assert.equal(percentChange(0,100),-100);assert.equal(percentChange(125,100),25);});
 check('empty and zero are distinct datasets; invalid filter values normalize safely',()=>{
   assert.equal(analyticsSnapshot({sample:'empty'}).daily.length,0);const zero=analyticsSnapshot({sample:'zero'});assert.equal(zero.daily.length,30);assert.equal(zero.current.revenue,0);assert.equal(zero.current.paid,0);
   const fallback=analyticsSnapshot({days:999,channel:'<img>',sample:'<script>'});assert.equal(fallback.days,30);assert.equal(fallback.channel,'all');assert.equal(fallback.sample,'normal');
 });
 check('CSV has BOM, precise cents and exactly the filtered rows',()=>{
   const s=analyticsSnapshot({days:7,channel:'search'}),csv=analyticsCsv(s),lines=csv.slice(1).split('\r\n');assert.equal(csv[0],'\uFEFF');assert.equal(lines.length,12);assert.match(lines[2],/搜索推广/);assert.ok(lines.at(-1).endsWith(`"${(s.daily.at(-1).revenue/100).toFixed(2)}"`));assert.equal(analyticsCsv(analyticsSnapshot({sample:'empty'})).split('\r\n').length,5);
 });
 const app=await createApp({url:'https://example.test/#analytics'});const {w,d}=app,q=s=>d.querySelector(s),all=s=>[...d.querySelectorAll(s)];const errors=[];w.addEventListener('error',e=>errors.push(e.message));
 const click=s=>{assert.ok(q(s),s);q(s).click();};
 const change=(selector,value)=>{const el=q(selector);if(typeof value==='boolean')el.checked=value;else el.value=value;el.dispatchEvent(new w.Event('change',{bubbles:true}));};
 check('direct statistics route renders eight chart scenes and meaningful labels',()=>{assert.equal(q('h1').textContent,'统计分析');assert.equal(all('[data-an-card]').length,8);assert.equal(all('.an-metrics .metric').length,4);assert.ok(q('[href="#analytics"][aria-current=page]'));assert.ok(q('[data-an-card=heatmap] [data-an-point]'));assert.match(q('.an-notes').textContent,/模拟/);});
 check('compact currency headline retains precise accessible amount',()=>{assert.equal(q('.an-metrics abbr').title,'¥1,778,106.83');assert.equal(q('.an-metrics abbr').getAttribute('aria-label'),'¥1,778,106.83');assert.equal(q('.an-metrics abbr').textContent,'¥177.81万');});
 const initial=q('.an-metrics .metric-value').textContent;
 change('#an-days','7');check('date filtering changes KPIs, table and period consistently',()=>{assert.notEqual(q('.an-metrics .metric-value').textContent,initial);assert.equal(all('#an-details tbody tr').length,7);assert.match(q('.an-context').textContent,/2026-10-17/);assert.equal(d.activeElement,q('#an-days'));});
 const original7=q('.an-metrics .metric-value').textContent;
 change('#an-channel','search');check('channel filter updates KPIs and accessible channel state',()=>{assert.notEqual(q('.an-metrics .metric-value').textContent,original7);assert.match(q('.an-context').textContent,/搜索推广/);assert.equal(all('.an-channel-row').length,1);});
 for(const metric of ['paid','signups','revenue']){change('#an-metric',metric);check(metric+': trend metric updates the plotted measure and unit',()=>assert.match(q('#an-title-trend').textContent,new RegExp({paid:'支付订单',signups:'新增用户',revenue:'支付金额'}[metric])));}
 change('#an-group','week');check('week aggregation shows one point per complete seven-day period',()=>assert.equal(all('[data-an-card=trend] circle[data-an-point]').length,2));
 change('#an-compare',false);check('comparison toggle removes previous series',()=>{assert.equal(q('[data-an-toggle=previous]'),null);assert.equal(all('[data-an-card=trend] circle[data-an-point]').length,1);});
 click('[data-an-toggle=current]');check('all-hidden trend gives a recoverable empty state',()=>assert.match(q('[data-an-card=trend]').textContent,/图例已全部隐藏/));click('[data-an-toggle=current]');
 change('#an-compare',true);change('#an-group','day');
 click('[data-an-setting=trend][data-an-value=line]');check('line mode removes area fills while retaining point interaction',()=>{assert.equal(all('[data-an-card=trend] path[opacity]').length,0);assert.equal(all('[data-an-card=trend] circle[data-an-point]').length,14);});
 const points=all('[data-an-card=trend] [data-an-point]');points[0].focus();
 check('keyboard focus announces actual date and value with one tab entry',()=>{assert.equal(q('[data-an-card=trend] .an-readout').textContent,points[0].dataset.anPoint);assert.equal(all('[data-an-card=trend] [data-an-point][tabindex="0"]').length,1);});
 points[0].dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));check('arrow navigation reaches the next point and updates readout',()=>{assert.equal(d.activeElement,points[1]);assert.equal(q('[data-an-card=trend] .an-readout').textContent,points[1].dataset.anPoint);});
 points[1].dispatchEvent(new w.KeyboardEvent('keydown',{key:'End',bubbles:true}));check('End moves to the last available point',()=>assert.equal(d.activeElement,points.at(-1)));
 const barHeight=q('[data-an-card=orders] rect').getAttribute('height');click('[data-an-setting=bars][data-an-value=grouped]');check('grouped bars render separate category positions',()=>{const bars=all('[data-an-card=orders] rect');assert.notEqual(bars[0].getAttribute('x'),bars[1].getAttribute('x'));assert.ok(Number(barHeight)>=0);});
 click('[data-an-toggle=newOrders]');click('[data-an-toggle=repeatOrders]');check('hidden order series can be restored',()=>assert.match(q('[data-an-card=orders]').textContent,/图例已全部隐藏/));click('[data-an-toggle=repeatOrders]');
 click('[data-an-setting=pie][data-an-value=pie]');check('single-channel pie draws a complete circle',()=>{assert.equal(all('[data-an-card=channels] circle[data-an-channel]').length,1);assert.equal(q('[data-an-card=channels] circle').getAttribute('r'),'96');});
 change('#an-channel','all');click('.an-channel-row[data-an-channel=social]');check('channel legend drills into the page and retains focus',()=>{assert.equal(q('#an-channel').value,'social');assert.equal(d.activeElement,q('#an-channel'));});
 const input=q('#an-target');input.value='1';q('#an-goal-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));check('custom target permits actual completion above 100 percent without overflowing the ring',()=>{assert.match(q('.an-goal-ring').textContent,/已达成/);assert.equal(q('#an-target').value,'1');assert.ok(parseFloat(q('.an-goal-ring strong').textContent)>100);const dash=q('.an-goal-ring circle:last-child').getAttribute('stroke-dasharray').split(' ').map(Number);assert.ok(dash[0]<=dash[1]);});
 change('#an-days','30');check('custom goal remains explicit when filters change',()=>{assert.equal(q('#an-target').value,'1');assert.match(q('#an-goal-form label').textContent,/自定义/);});
 q('#an-target').value='0';q('#an-goal-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));check('invalid goal leaves the accepted target intact',()=>{change('#an-metric','paid');assert.equal(q('#an-target').value,'1');});
 q('#an-details').open=true;q('#an-details').dispatchEvent(new w.Event('toggle'));change('#an-group','week');check('detail expansion survives filter changes',()=>assert.ok(q('#an-details').open));
 change('#an-sample','zero');check('all-zero charts have no NaN, fake shares or invented averages',()=>{assert.doesNotMatch(q('.analytics-page').innerHTML,/NaN|Infinity/);assert.match(q('[data-an-card=channels]').textContent,/支付金额为 0/);assert.match(q('[data-an-card=scatter]').textContent,/暂无可计算/);assert.equal(q('[data-an-card=channels] .an-donut-layout'),null);assert.equal(all('#an-details tbody tr').length,30);assert.match(q('[data-an-card=funnel]').textContent,/起点 —/);});
 change('#an-sample','empty');check('missing data is shown as unknown and the detail table is usable',()=>{assert.equal(q('.an-metrics .metric-value').textContent,'—');assert.equal(all('.an-empty').length,7);assert.match(q('#an-details tbody').textContent,/没有数据/);assert.doesNotMatch(q('.analytics-page').innerHTML,/NaN|Infinity/);});
 click('[data-an-reset]');check('reset restores full dataset, legend, target and chart styles',()=>{assert.equal(q('#an-days').value,'30');assert.equal(q('#an-channel').value,'all');assert.equal(q('#an-sample').value,'normal');assert.match(q('#an-goal-form label').textContent,/自动参考/);assert.equal(all('#an-details tbody tr').length,30);assert.equal(q('[data-an-setting=trend][data-an-value=area]').getAttribute('aria-pressed'),'true');});
 let exported,downloadName;w.URL.createObjectURL=blob=>{exported=blob;return 'blob:statistics-demo';};w.URL.revokeObjectURL=()=>{};const originalClick=w.HTMLAnchorElement.prototype.click;w.HTMLAnchorElement.prototype.click=function(){downloadName=this.download;};change('#an-channel','partner');change('#an-days','7');click('[data-an-export]');
 check('export creates the actual filtered CSV Blob with a descriptive filename',()=>{assert.ok(exported instanceof w.Blob);assert.equal(exported.type,'text/csv;charset=utf-8');assert.equal(downloadName,'nova-analytics-demo-7d-partner.csv');assert.match(q('#toast-root').textContent,/已导出/);});
 w.HTMLAnchorElement.prototype.click=originalClick;
 w.location.hash='overview';await wait();check('overview has a working statistics shortcut',()=>assert.ok(q('.page-actions [href="#analytics"]')));click('.page-actions [href="#analytics"]');await wait();check('navigation preserves chart filters within the session',()=>{assert.equal(q('#an-channel').value,'partner');assert.equal(q('#an-days').value,'7');});
 check('no uncaught runtime errors or preference-storage side effects',()=>{assert.deepEqual(errors,[]);assert.equal(w.localStorage.getItem('nova-analytics'),null);});
 app.close();console.log('TOTAL',count,'analytics checks passed');
})().catch(error=>{console.error(error);process.exit(1);});
