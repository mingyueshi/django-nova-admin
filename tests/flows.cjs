const {createApp}=require('./dom-runtime.cjs');const assert=require('node:assert/strict');
(async()=>{const {w,d,close}=await createApp();let n=0;const q=s=>d.querySelector(s),all=s=>[...d.querySelectorAll(s)],wait=()=>new Promise(r=>setTimeout(r,20));const check=(t,f)=>{f();console.log('PASS',t);n++};const route=async r=>{w.location.hash=r;await wait()};const click=s=>{q(s).dispatchEvent(new w.MouseEvent('click',{bubbles:true}))};

await route('import');
check('Import wizard opens at step one with sample data and honest notice',()=>{assert.equal(q('h1').textContent,'导入向导');assert.equal(all('.stepper > div').length,4);assert.match(q('#import-raw').value,/NOVA-P001/);assert.match(q('.model-hint').textContent,/仅解析当前输入/)});
q('#import-raw').value='名称,SKU,分类,价格,库存\n测试样品,NOVA-T01,数码配件,10,1';
click('[data-flow="import-parse"]');
check('Parsing advances to mapping with auto-matched columns',()=>{assert.equal(all('.import-mapping select').length,5);assert.equal(q('.import-mapping select').value,'名称');assert.equal(all('.import-mapping select')[1].value,'SKU')});
click('[data-flow="import-apply"]');
check('Single clean row passes validation after mapping',()=>{const rows=all('.import-check tbody tr');assert.equal(rows.length,1);assert.match(rows[0].textContent,/✓ 可导入/)});
await route('import');
click('[data-flow="import-back"][data-flow-step="2"]');click('[data-flow="import-back"][data-flow-step="1"]');
q('#import-raw').value='名称,SKU,分类,价格,库存\n无线充电板,NOVA-P001,数码配件,129.00,42\n磁吸手机壳,NOVA-P002,数码配件,69.00,120\n胡桃木收纳盘,NOVA-H010,家居生活,89.50,30\n CSV 首尾空格 ,NOVA-H011,家居生活,45,8\n未命名样品,,服饰鞋包,199.00,5\n复古帆布包,NOVA-B003,服饰鞋包,等于三百,17\n便携补光灯,NOVA-P003,摄影器材,259.00,-4\n重复编号样品,NOVA-P001,数码配件,59.00,66';
click('[data-flow="import-parse"]');click('[data-flow="import-apply"]');
const badRows=all('.import-check tbody tr');
check('Sample validation marks missing SKU, bad price, unknown category and duplicate SKU',()=>{assert.equal(badRows.length,8);assert.match(badRows[4].textContent,/缺少 SKU/);assert.match(badRows[5].textContent,/价格非法/);assert.match(badRows[6].textContent,/分类不在目录内/);assert.match(badRows[6].textContent,/库存非法/);assert.match(badRows[7].textContent,/SKU 在文件内重复/)});
const okCount=badRows.filter(r=>r.textContent.includes('可导入')).length;
click('[data-flow="import-run"]');
check('Execution skips invalid rows, writes audit and finishes the wizard',()=>{assert.equal(q('h1').textContent,'导入向导');assert.match(q('.option-card').textContent,new RegExp(`可导入 ${okCount}`));assert.match(q('.option-card').textContent,/跳过 \d+ 条/);assert.match(w.localStorage.getItem('nova-audit')||'',/批量导入/)});
click('[data-flow="import-restart"]');
check('Restart returns to step one with the sample restored',()=>{assert.match(q('#import-raw').value,/NOVA-P001/)});

await route('kanban');
check('Board renders four labelled columns with counts and cards',()=>{assert.equal(q('h1').textContent,'状态看板');assert.equal(all('.kanban-column').length,4);assert.match(q('.kanban-column[data-flow-column="todo"] .count-badge').textContent,/2/);assert.ok(q('.kanban-card[draggable="true"]'))});
const moving=q('.kanban-card[data-flow-card="2"] .btn');
click('[data-flow="kanban-move"][data-flow-card="2"]');
check('Button fallback moves a card forward and records the audit',()=>{assert.match(q('.kanban-column[data-flow-column="doing"] .count-badge').textContent,/3/);assert.match(q('.kanban-column[data-flow-column="todo"] .count-badge').textContent,/1/);assert.match(w.localStorage.getItem('nova-audit')||'',/看板流转/)});
const cardEl=q('.kanban-card[data-flow-card="2"]');
cardEl.dispatchEvent(new w.Event('dragstart',{bubbles:true}));
q('.kanban-column[data-flow-column="review"]').dispatchEvent(new w.Event('drop',{bubbles:true}));
check('Drag and drop moves the card between columns',()=>{assert.match(q('.kanban-column[data-flow-column="review"] .count-badge').textContent,/2/);assert.ok(q('.kanban-column[data-flow-column="review"]').textContent.includes('会员积分规则文档'))});

await route('approvals');
check('Approval list renders synthetic documents with status badges',()=>{assert.equal(q('h1').textContent,'审批工作流');assert.equal(all('.approval-table tbody tr').length,4);assert.ok(q('.approval-table .status-normal'))});
click('[data-flow="approval-filter"][data-flow-filter="待审批"]');
check('Status filter narrows the list',()=>{assert.equal(all('.approval-table tbody tr').length,2)});
click('[data-flow="approval-open"][data-flow-id="2"]');
check('Flow drawer shows the timeline and pending node actions',()=>{assert.ok(q('.approval-drawer .timeline'));assert.equal(all('.approval-drawer .timeline > div').length,2);assert.ok(q('[data-flow="approval-approve"]'));assert.ok(q('[data-flow="approval-reject"]'))});
click('[data-flow="approval-approve"]');
check('Approval advances the node and writes the audit',()=>{assert.equal(q('.approval-drawer'),null);assert.match(w.localStorage.getItem('nova-audit')||'',/审批通过/);click('[data-flow="approval-filter"][data-flow-filter="全部"]');const row=all('.approval-table tbody tr').find(r=>r.textContent.includes('AP-2602'));assert.match(row.textContent,/二级审批/);assert.match(row.textContent,/待审批/)});
click('[data-flow="approval-open"][data-flow-id="2"]');click('[data-flow="approval-approve"]');
check('Second approval archives the document',()=>{const row=all('.approval-table tbody tr').find(r=>r.textContent.includes('AP-2602'));assert.match(row.textContent,/已通过/)});
click('[data-flow="approval-filter"][data-flow-filter="全部"]');
await route('approvals');
click('[data-flow="approval-open"]');
click('[data-flow="approval-reject"]');
check('Rejection ends the flow with a recorded reason',()=>{click('[data-flow="approval-filter"][data-flow-filter="已驳回"]');assert.match(q('.approval-table').textContent,/请补充材料后重新提交|已驳回/)});

await route('tree');
check('Tree table renders hierarchical rows with toggles and counts',()=>{assert.equal(q('h1').textContent,'分类树');assert.equal(all('.tree-table tbody tr').length,13);assert.ok(q('.tree-toggle[aria-expanded="true"]'))});
click('[data-flow="tree-toggle"][data-flow-id="1"]');
check('Collapsing a parent hides its subtree',()=>{assert.equal(all('.tree-table tbody tr').length,10);assert.equal(q('[data-flow="tree-toggle"][data-flow-id="1"]').getAttribute('aria-expanded'),'false')});
click('[data-flow="tree-expand-all"]');
check('Expand all reveals every level including nested nodes',()=>{assert.equal(all('.tree-table tbody tr').length,13)});
click('[data-flow="tree-collapse-all"]');
check('Collapse all keeps only root rows',()=>{assert.equal(all('.tree-table tbody tr').length,4)});
q('[data-flow="tree-down"][data-flow-id="1"]').click();
check('Moving down swaps siblings and records the audit',()=>{assert.match(all('.tree-table tbody tr')[1].textContent,/数码配件/);assert.match(w.localStorage.getItem('nova-audit')||'',/分类排序/)});
q('[data-flow="tree-up"][data-flow-id="2"]').click();
check('Moving up restores the previous order',()=>assert.match(all('.tree-table tbody tr')[1].textContent,/数码配件/));

const checkA=async(t,f)=>{await f();console.log('PASS',t);n++};

await route('calendar');
check('Calendar renders a month grid with events and today marker',()=>{assert.equal(q('h1').textContent,'发布日历');assert.equal(all('.cal-week span').length,7);assert.ok(all('.cal-cell').length>=28);assert.ok(q('.cal-day.cal-today'));assert.ok(q('.cal-dots i'))});
const monthLabel=q('.cal-month').textContent;
click('[data-flow="cal-next"]');
check('Month navigation shifts the grid',()=>assert.notEqual(q('.cal-month').textContent,monthLabel));
click('[data-flow="cal-today-btn"]');
check('Today button returns to the current month',()=>assert.equal(q('.cal-month').textContent,monthLabel));
const dayBtn=q('.cal-dots i')?.closest('.cal-cell');
const dayLabel=dayBtn.getAttribute('data-flow-date');
dayBtn.click();
check('Selecting a day lists its schedule with accessible labels',()=>{assert.match(q('.cal-day-panel h2').textContent,new RegExp(dayLabel));assert.ok(all('.cal-item').length>=1);assert.match(q(`.cal-cell[data-flow-date="${dayLabel}"]`).getAttribute('aria-label'),/项内容/)});

await route('columns');
check('Column configurator renders six columns with controls',()=>{assert.equal(q('h1').textContent,'列配置与视图');assert.equal(all('.column-rule').length,6);assert.equal(all('.demo-columns-table th').length,6)});
q('[data-flow="col-toggle"][data-flow-key="owner"]').click();
check('Unchecking hides the column and persists the order',()=>{assert.equal(all('.demo-columns-table th').length,5);assert.ok(!w.localStorage.getItem('nova-view-columns').includes('owner'))});
click('[data-flow="col-up"][data-flow-key="status"]');
check('Arrows reorder columns persistently',()=>{const order=JSON.parse(w.localStorage.getItem('nova-view-columns'));assert.equal(order[2],'status');assert.match(q('.demo-columns-table thead').textContent,/状态/)});
click('[data-flow="col-reset"]');
check('Reset restores all six columns in default order',()=>{assert.equal(all('.demo-columns-table th').length,6);assert.equal(all('.demo-columns-table thead th')[2].textContent,'金额')});

await route('recycle');
check('Recycle splits live and deleted content',()=>{const counts=all('.demo-recycle-layout .pill').map(x=>x.textContent);assert.deepEqual(counts,['3 项','4 项'])});
click('[data-flow="recycle-delete"][data-flow-id="101"]');
check('Deleting moves an item into the bin and records it',()=>{const counts=all('.demo-recycle-layout .pill').map(x=>x.textContent);assert.deepEqual(counts,['2 项','5 项']);assert.match(w.localStorage.getItem('nova-audit')||'',/移入回收站/)});
click('[data-flow="recycle-restore"][data-flow-id="1"]');
check('Restore returns an item to the live list',()=>{assert.ok(q('.demo-recycle-layout').textContent.includes('过期的促销公告'));assert.match(w.localStorage.getItem('nova-audit')||'',/从回收站恢复/)});
click('[data-flow="recycle-purge-ask"][data-flow-id="2"]');
check('Purge asks for confirmation first',()=>{assert.match(q('#recycle-confirm-title').textContent,/彻底删除/)});
click('[data-flow="recycle-purge-run"]');
check('Confirmed purge removes the item permanently',()=>{assert.equal(q('#recycle-confirm-title'),null);assert.equal(q('.demo-recycle-layout').textContent.includes('旧版会员规则草稿'),false)});
click('[data-flow="recycle-clear-ask"]');click('[data-flow="recycle-clear-run"]');
check('Clear bin empties it and records the action',()=>{assert.match(q('.demo-recycle-layout').textContent,/回收站是空的/);assert.match(w.localStorage.getItem('nova-audit')||'',/清空回收站/)});

await route('tasks');
check('Task queue renders progressbar semantics',()=>{assert.equal(q('h1').textContent,'任务进度中心');assert.equal(all('.task-row').length,4);assert.equal(q('.task-progress').getAttribute('role'),'progressbar');assert.equal(q('.task-progress').getAttribute('aria-valuenow'),'0')});
const nativeInterval=w.setInterval.bind(w),nativeClear=w.clearInterval.bind(w);
const timers=new Map();let timerId=900000;
w.setInterval=(fn,ms)=>ms===700?(timers.set(++timerId,fn),timerId):nativeInterval(fn,ms);
w.clearInterval=id=>{if(timers.has(id))timers.delete(id);else nativeClear(id);};
const fireTicks=n=>{for(let i=0;i<n;i++)timers.forEach(fn=>fn())};
click('[data-flow="task-start"][data-flow-id="1"]');
fireTicks(3);
await checkA('Started task runs and gains progress over ticks',async()=>{await wait();const now=Number(q('.task-row .task-progress').getAttribute('aria-valuenow'));assert.ok(now>=18);assert.match(q('.task-row .pill').textContent,/运行中/)});
click('[data-flow="task-pause"][data-flow-id="1"]');
fireTicks(4);
await checkA('Pause freezes the percent',async()=>{await wait();const frozen=Number(q('.task-row .task-progress').getAttribute('aria-valuenow'));fireTicks(4);await wait();assert.equal(Number(q('.task-row .task-progress').getAttribute('aria-valuenow')),frozen)});
click('[data-flow="task-start"][data-flow-id="1"]');click('[data-flow="task-fail"][data-flow-id="1"]');
fireTicks(4);
await checkA('Simulated failure stops the task and offers retry',async()=>{await wait();assert.match(q('.task-row .pill').textContent,/失败/);assert.match(q('[data-flow="task-start"][data-flow-id="1"]').textContent,/重试/)});
click('[data-flow="task-start"][data-flow-id="1"]');
fireTicks(1);
await checkA('Retry restarts the task as running from zero',async()=>{await wait();assert.match(q('.task-row .pill').textContent,/运行中/);assert.ok(Number(q('.task-row .task-progress').getAttribute('aria-valuenow'))<20)});



const badgeBefore=Number(q('.notice-badge').textContent);
click('[data-action="notifications"]');
check('Notification center groups notices by type with live badge',()=>{assert.ok(q('.notice-drawer'));assert.ok(all('.notice-group').length>=2);assert.equal(q('.notice-badge').textContent,String(badgeBefore));assert.match(q('.notice-drawer .drawer-header p').textContent,new RegExp(`未读 ${badgeBefore} 条`))});
click('.notice-item.notice-unread');
check('Clicking a notice marks it read and decrements the badge',()=>{assert.equal(Number(q('.notice-badge').textContent),badgeBefore-1);assert.equal(all('.notice-item.notice-unread').length,badgeBefore-1)});
click('[data-flow="notice-filter"][data-flow-filter="任务"]');
check('Type filter narrows the drawer',()=>{assert.ok(all('.notice-group').length<=1)});
click('[data-flow="notice-read-all"]');
check('Mark all read hides the badge',()=>{assert.equal(q('.notice-badge').hidden,true)});
q('[aria-label="关闭通知中心"]').click();

await route('bilingual');
check('Bilingual page shows side-by-side copy coverage',()=>{assert.equal(q('h1').textContent,'双语对照');assert.ok(q('.bilingual-table'));assert.match(q('.bilingual-sample strong').textContent,/季度经营简报/)});
click('[data-flow="bilingual-lang"][data-flow-lang="en"]');
check('Language toggle switches the live sample',()=>{assert.match(q('.bilingual-sample strong').textContent,/Quarterly/);assert.match(q('.bilingual-actions').textContent,/Save/)});

await route('inline');
check('Inline editor renders editable rows with seeded validation',()=>{assert.equal(q('h1').textContent,'行内编辑');assert.equal(all('.inline-table tbody tr').length,5);assert.match(q('.panel-head .pill').textContent,/全部已保存/);assert.match(q('.inline-table').textContent,/库存需为/)});
const stockInput=q('[data-flow-inline="stock"][data-flow-id="1"]');stockInput.value='58';stockInput.dispatchEvent(new w.Event('input',{bubbles:true}));stockInput.dispatchEvent(new w.Event('change',{bubbles:true}));
check('Editing marks the row dirty with save and revert actions',()=>{assert.ok(q('.inline-row-dirty'));assert.ok(q('[data-flow="inline-save"][data-flow-id="1"]'));assert.ok(q('[data-flow="inline-revert"][data-flow-id="1"]'))});
q('[data-flow-inline="stock"][data-flow-id="1"]').value='-3';q('[data-flow-inline="stock"][data-flow-id="1"]').dispatchEvent(new w.Event('input',{bubbles:true}));q('[data-flow-inline="stock"][data-flow-id="1"]').dispatchEvent(new w.Event('change',{bubbles:true}));
click('[data-flow="inline-save"][data-flow-id="1"]');
check('Invalid stock blocks the save with a toast',()=>{assert.match(q('.toast').textContent,/库存需为/);assert.ok(q('.inline-row-dirty'))});
q('[data-flow-inline="stock"][data-flow-id="1"]').value='58';q('[data-flow-inline="stock"][data-flow-id="1"]').dispatchEvent(new w.Event('input',{bubbles:true}));q('[data-flow-inline="stock"][data-flow-id="1"]').dispatchEvent(new w.Event('change',{bubbles:true}));
click('[data-flow="inline-save"][data-flow-id="1"]');
check('Valid save records the audit and clears dirty state',()=>{assert.match(w.localStorage.getItem('nova-audit')||'',/行内编辑/);assert.equal(q('[data-flow="inline-save"][data-flow-id="1"]'),null)});

check('New flows appear in the sidebar navigation with a dedicated group',()=>{assert.ok(all('.sidebar .nav-group').some(b=>b.textContent.includes('业务流程')));assert.ok(all('.sidebar .nav-item').some(a=>a.getAttribute('href')==='#import'));assert.ok(all('.sidebar .nav-item').some(a=>a.getAttribute('href')==='#calendar'));assert.ok(all('.sidebar .nav-item').some(a=>a.getAttribute('href')==='#bilingual'));assert.ok(all('.sidebar .nav-item').some(a=>a.getAttribute('href')==='#inline'))});

// Regression coverage for interrupted, repeated and restored flow interactions.
const editInline = (id, field, value, event='input') => {
  const input=q(`[data-flow-inline="${field}"][data-flow-id="${id}"]`);
  input.value=value;
  input.dispatchEvent(new w.Event(event,{bubbles:true}));
  return input;
};
const typing=editInline(1,'stock','67');typing.focus();typing.setSelectionRange(1,1);
check('Inline input immediately updates dirty controls without losing focus or selection',()=>{
  typing.dispatchEvent(new w.Event('input',{bubbles:true}));
  assert.ok(q('[data-flow="inline-save"][data-flow-id="1"]'));
  assert.match(q('.panel-head p').textContent,/1 行/);
  assert.equal(d.activeElement,typing);assert.equal(typing.selectionStart,1);
});
const saveTarget=q('[data-flow="inline-save"][data-flow-id="1"]');
check('Inline change keeps both form control and pending click target connected',()=>{
  typing.dispatchEvent(new w.Event('change',{bubbles:true}));
  assert.equal(typing.isConnected,true);assert.equal(saveTarget.isConnected,true);
  assert.equal(q('[data-flow="inline-save"][data-flow-id="1"]'),saveTarget);
});
editInline(2,'note','未保存备注');click('[data-flow="inline-reset"]');
check('Discard all restores last saved values for every dirty row',()=>{
  assert.equal(q('[data-flow-inline="stock"][data-flow-id="1"]').value,'58');
  assert.equal(q('[data-flow-inline="note"][data-flow-id="2"]').value,'');
  assert.equal(q('.inline-row-dirty'),null);
});
editInline(1,'stock','-3');click('[data-flow="inline-save"][data-flow-id="1"]');
check('Invalid inline save retains focus and exposes the associated error',()=>{
  const input=q('[data-flow-inline="stock"][data-flow-id="1"]');
  assert.equal(d.activeElement,input);assert.equal(input.getAttribute('aria-invalid'),'true');
  assert.match(d.getElementById(input.getAttribute('aria-describedby')).textContent,/库存需为/);
});
editInline(1,'stock','9007199254740992');click('[data-flow="inline-save"][data-flow-id="1"]');
check('Unsafe integer stock remains unsaved',()=>assert.ok(q('[data-flow="inline-save"][data-flow-id="1"]')));
editInline(1,'stock','60');click('[data-flow="inline-save"][data-flow-id="1"]');
editInline(1,'stock','70');click('[data-flow="inline-revert"][data-flow-id="1"]');
check('Row revert restores the latest successful save',()=>assert.equal(q('[data-flow-inline="stock"][data-flow-id="1"]').value,'60'));
editInline(1,'status','停售','change');click('[data-flow="inline-reset"]');
check('Discard restores a changed select without altering the saved stock',()=>{
  assert.equal(q('[data-flow-inline="status"][data-flow-id="1"]').value,'正常');
  assert.equal(q('[data-flow-inline="stock"][data-flow-id="1"]').value,'60');
});
await route('columns');click('[data-flow="col-toggle"][data-flow-key="owner"]');
check('Hidden columns retain an unchecked control and can be shown again',()=>{
  const hidden=q('[data-flow="col-toggle"][data-flow-key="owner"]');assert.ok(hidden);assert.equal(hidden.checked,false);
  hidden.click();assert.equal(all('.demo-columns-table th').length,6);
});
click('[data-flow="col-toggle"][data-flow-key="owner"]');click('[data-flow="col-up"][data-flow-key="status"]');
await checkA('Reload restores the exact visible column subset and order',async()=>{
  const saved=w.localStorage.getItem('nova-view-columns');
  const restored=await createApp({url:'https://example.test/#columns',storage:{'nova-view-columns':saved}});
  try {assert.equal(restored.d.querySelectorAll('.demo-columns-table th').length,5);
    assert.equal(restored.d.querySelectorAll('.demo-columns-table th')[2].textContent,'状态');
    assert.equal(restored.d.querySelector('[data-flow-key="owner"]').checked,false);
  } finally {restored.close();}
});
for(const key of ['customer','status','amount','date'])click(`[data-flow="col-toggle"][data-flow-key="${key}"]`);
check('The last visible column cannot be hidden',()=>{click('[data-flow="col-toggle"][data-flow-key="order"]');assert.equal(all('.demo-columns-table th').length,1);assert.equal(q('[data-flow-key="order"]').checked,true)});
await checkA('Invalid stored column configurations recover to defaults',async()=>{
  for(const value of ['null','[]','["owner","owner"]','["not-a-column"]','{']) {
    const app=await createApp({url:'https://example.test/#columns',storage:{'nova-view-columns':value}});
    try {assert.equal(app.d.querySelectorAll('.demo-columns-table th').length,6);} finally {app.close();}
  }
});
await checkA('Denied column persistence is reported while retaining current-page controls',async()=>{
  const app=await createApp({url:'https://example.test/#columns',beforeLoad(w){w.Storage.prototype.setItem=()=>{throw Error('quota')};}});
  try {app.d.querySelector('[data-flow-key="owner"]').click();assert.equal(app.d.querySelectorAll('.demo-columns-table th').length,5);assert.match(app.d.querySelector('.toast').textContent,/未能保存/);} finally {app.close();}
});
await checkA('Denied preference removal still resets current-page columns and reports the limit',async()=>{
  const app=await createApp({url:'https://example.test/#columns',storage:{'nova-view-columns':'["order","customer"]'},beforeLoad(w){w.Storage.prototype.removeItem=()=>{throw Error('denied')};}});
  try {app.d.querySelector('[data-flow="col-reset"]').click();assert.equal(app.d.querySelectorAll('.demo-columns-table th').length,6);assert.match(app.d.querySelector('.toast').textContent,/未能清除/);assert.equal(app.w.localStorage.getItem('nova-view-columns'),'["order","customer"]');} finally {app.close();}
});
await route('tree');click('[data-flow="tree-collapse-all"]');click('[data-flow="tree-expand-all"]');
check('Expand all after full collapse includes nested grandchildren',()=>{assert.equal(all('.tree-table tbody tr').length,13);assert.equal(q('[data-flow="tree-toggle"][data-flow-id="33"]').getAttribute('aria-expanded'),'true')});
click('[data-flow="tree-collapse-all"]');click('[data-flow="tree-expand-all"]');
check('Repeated full collapse and expand remain idempotent',()=>assert.equal(all('.tree-table tbody tr').length,13));
await route('calendar');click('.cal-dots i');click('[data-flow="cal-next"]');
check('Changing months selects a date in the displayed month',()=>{
  const selected=q('.cal-cell[aria-pressed="true"]');assert.ok(selected);
  assert.match(q('.cal-day-panel h2').textContent,new RegExp(selected.dataset.flowDate));
});
await route('tasks');click('[data-flow="task-start"][data-flow-id="2"]');fireTicks(1);
const taskPercent=qAll=>qAll[1].getAttribute('aria-valuenow');
const pausedPercent=taskPercent(all('.task-progress'));
await route('calendar');
check('Leaving tasks clears the running timer immediately',()=>assert.equal(timers.size,0));
await route('tasks');fireTicks(3);
check('Returning keeps the task paused until explicitly resumed',()=>{
  assert.equal(taskPercent(all('.task-progress')),pausedPercent);
  assert.match(all('.task-row')[1].textContent,/已暂停/);
});
click('[data-flow="task-start"][data-flow-id="2"]');fireTicks(1);
check('Paused tasks resume progress with a single timer',()=>{assert.equal(timers.size,1);assert.ok(Number(taskPercent(all('.task-progress')))>Number(pausedPercent))});
await route('settings');click('[data-action="reset-demo"]');click('[data-action="confirm-reset-demo"]');
await route('columns');
check('Global reset clears the in-memory column cache as well as storage',()=>{assert.equal(all('.demo-columns-table th').length,6);assert.equal(w.localStorage.getItem('nova-view-columns'),null)});
await route('inline');
check('Global reset restores inline values and validation baseline',()=>{assert.equal(q('[data-flow-inline="stock"][data-flow-id="1"]').value,'42');assert.equal(q('.inline-row-dirty'),null)});
await route('tasks');
check('Global reset restores queued tasks and clears every timer',()=>{assert.equal(timers.size,0);assert.ok(all('.task-progress').every(x=>x.getAttribute('aria-valuenow')==='0'));assert.ok(all('.task-row').every(x=>x.textContent.includes('排队中')))});
await route('recycle');
check('Global reset restores both sides of the recycle demo',()=>assert.deepEqual(all('.demo-recycle-layout .pill').map(x=>x.textContent),['3 项','4 项']));
await route('approvals');
check('Global reset restores initial approvals and notification unread count',()=>{assert.equal(all('.approval-table tbody tr').length,4);assert.match(all('.approval-table tbody tr')[1].textContent,/待审批/);assert.equal(q('.notice-badge').textContent,'3');assert.equal(q('.notice-badge').hidden,false)});

console.log('TOTAL',n,'flow demo checks passed');close()})().catch(e=>{console.error(e);process.exitCode=1});
