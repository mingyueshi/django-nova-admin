// Business-flow demos: import wizard, status board, approval flow, category tree.
// All data is synthetic and lives in memory; a reload restores the initial state.
let ui, recordAudit, getView;
const esc = (x) => ui.esc(x);
const icon = (x) => ui.icon(x);
const hint = (text) => `<div class="model-hint">${icon('circle')}${text}</div>`;

export function initFlows(dependencies) {
  ({ ui, recordAudit, getView } = dependencies);
  document.addEventListener('click', flowsClick);
  document.addEventListener('input', flowsInput);
  document.addEventListener('change', flowsInput);
  document.addEventListener('dragstart', flowsDragStart);
  document.addEventListener('dragover', flowsDragOver);
  document.addEventListener('drop', flowsDrop);
}

/* ---------------------------------------------------------------- 导入向导 */

const IMPORT_FIELDS = ['名称', 'SKU', '分类', '价格', '库存'];
const IMPORT_CATEGORIES = ['数码配件', '家居生活', '服饰鞋包', '美妆个护'];
const IMPORT_SAMPLE = [
  '名称,SKU,分类,价格,库存',
  '无线充电板,NOVA-P001,数码配件,129.00,42',
  '磁吸手机壳,NOVA-P002,数码配件,69.00,120',
  '胡桃木收纳盘,NOVA-H010,家居生活,89.50,30',
  ' CSV 首尾空格 ,NOVA-H011,家居生活,45,8',
  '未命名样品,,服饰鞋包,199.00,5',
  '复古帆布包,NOVA-B003,服饰鞋包,等于三百,17',
  '便携补光灯,NOVA-P003,摄影器材,259.00,-4',
  '重复编号样品,NOVA-P001,数码配件,59.00,66',
].join('\n');
const importState = {
  step: 1,
  raw: IMPORT_SAMPLE,
  headers: [],
  rows: [],
  mapping: [],
  skipInvalid: true,
  checked: [],
  result: null,
};

function parseImport(raw) {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (!lines.length) return { headers: [], rows: [], error: '没有可解析的数据行' };
  const headers = lines[0].split(',').map((h) => h.replace(/^"|"$/g, '').trim());
  const rows = lines.slice(1).map((line, index) => ({
    line: index + 2,
    cells: line.split(',').map((c) => c.replace(/^"|"$/g, '').trim()),
  }));
  return { headers, rows, error: null };
}

function mappedRecords() {
  return importState.rows.map((row) => {
    const record = {};
    IMPORT_FIELDS.forEach((field, index) => {
      const column = importState.mapping.indexOf(field);
      record[field] = column >= 0 ? (row.cells[column] ?? '') : '';
    });
    return record;
  });
}

function validateRecords(records) {
  const seen = new Set();
  return records.map((record, index) => {
    const problems = [];
    if (!record['名称']) problems.push('缺少名称');
    if (!record['SKU']) problems.push('缺少 SKU');
    else if (seen.has(record['SKU'])) problems.push('SKU 在文件内重复');
    if (record['价格'] === '' || Number.isNaN(Number(record['价格'])) || Number(record['价格']) < 0)
      problems.push('价格非法');
    if (record['库存'] === '' || !/^\d+$/.test(record['库存'])) problems.push('库存非法');
    if (record['分类'] && !IMPORT_CATEGORIES.includes(record['分类']))
      problems.push('分类不在目录内');
    if (record['SKU']) seen.add(record['SKU']);
    return { index: index + 1, record, problems };
  });
}

function autoMapping(headers) {
  return headers.map((header) => {
    const name = header.replace(/\s/g, '');
    const hit = IMPORT_FIELDS.find((field) => name.includes(field) || field.includes(name));
    return hit || '忽略';
  });
}

export function renderImport() {
  importState.step = Math.min(Math.max(importState.step, 1), 4);
  const steps = ['选择数据', '字段映射', '校验结果', '完成导入'];
  const body =
    importState.step === 1
      ? importStep1()
      : importState.step === 2
        ? importStep2()
        : importState.step === 3
          ? importStep3()
          : importStep4();
  return (
    ui.intro('导入向导', '粘贴表格数据，映射字段并预演校验，全程不连接真实业务。', '') +
    hint('合成数据演示 · 仅解析当前输入 · 操作会写入本地操作日志') +
    `<section class="panel import-wizard"><div class="lab-body"><div class="stepper">${steps
      .map(
        (n, i) =>
          `<div class="${i + 1 === importState.step ? 'active' : i + 1 < importState.step ? 'complete' : ''}"><span>${i + 1 < importState.step ? '✓' : i + 1}</span><strong>${n}</strong></div>`,
      )
      .join('')}</div>${body}</div></section>`
  );
}
function importStep1() {
  return `<div class="field"><label for="import-raw">粘贴 CSV 数据（首行为表头，逗号分隔）</label><textarea id="import-raw" rows="9" spellcheck="false">${esc(importState.raw)}</textarea><small>演示模板字段：${IMPORT_FIELDS.join(' / ')}；分类限定 ${IMPORT_CATEGORIES.join('、')}</small></div><div class="lab-form-actions"><span></span><button class="btn primary" data-flow="import-parse">${icon('arrow')}解析并继续</button></div>`;
}
function importStep2() {
  const columns = importState.headers
    .map(
      (header, index) =>
        `<div class="field"><label>列「${esc(header)}」映射到</label><select data-flow-column="${index}">${['忽略', ...IMPORT_FIELDS].map((field) => `<option ${importState.mapping[index] === field ? 'selected' : ''}>${field}</option>`).join('')}</select></div>`,
    )
    .join('');
  return `<p class="import-note">已解析 ${importState.rows.length} 行。把每个来源列映射到模板字段；未映射或「忽略」的列不参与校验。</p><div class="import-mapping">${columns}</div><div class="lab-form-actions"><button class="btn" data-flow="import-back" data-flow-step="1">上一步</button><button class="btn primary" data-flow="import-apply">${icon('check')}应用映射并校验</button></div>`;
}
function importStep3() {
  const rows = mappedRecords();
  const checked = validateRecords(rows);
  importState.checked = checked;
  const valid = checked.filter((r) => !r.problems.length).length;
  return `<p class="import-note">校验 ${checked.length} 行：<strong class="import-ok">可导入 ${valid}</strong>，<strong class="import-bad">异常 ${checked.length - valid}</strong>。${checked.length - valid ? '异常行默认跳过，不会中断导入。' : '全部通过，可直接执行。'}</p><div class="table-scroll"><table class="import-check"><thead><tr><th>行号</th>${IMPORT_FIELDS.map((f) => `<th>${f}</th>`).join('')}<th>结果</th></tr></thead><tbody>${checked
    .map(
      (r) =>
        `<tr class="${r.problems.length ? 'import-row-bad' : ''}"><td>${r.index}</td>${IMPORT_FIELDS.map((f) => `<td>${esc(r.record[f]) || '<span class="muted">—</span>'}</td>`).join('')}<td>${r.problems.length ? `<span class="import-bad">✕ ${r.problems.join('；')}</span>` : '<span class="import-ok">✓ 可导入</span>'}</td></tr>`,
    )
    .join(
      '',
    )}</tbody></table></div><label class="check-label"><input class="checkbox" type="checkbox" data-flow="import-skip" ${importState.skipInvalid ? 'checked' : ''}>跳过异常行（取消则本批不可执行）</label><div class="lab-form-actions"><button class="btn" data-flow="import-back" data-flow-step="2">上一步</button><button class="btn primary" data-flow="import-run" ${checked.length - valid && !importState.skipInvalid ? 'disabled' : ''}>${icon('download')}执行导入</button></div>`;
}
function importStep4() {
  const r = importState.result;
  return `<div class="option-card"><h3>导入完成</h3><p>可导入 <strong>${r.imported}</strong> 条，跳过 <strong>${r.skipped}</strong> 条，共 ${r.total} 行数据。</p><p>${r.skipped ? '跳过明细已记录在操作日志；修正数据后可再次运行向导。' : '全部数据通过校验并导入演示列表。'}</p></div><div class="lab-form-actions"><span></span><button class="btn primary" data-flow="import-restart">${icon('history')}再导入一批</button></div>`;
}
function importRun() {
  const checked = importState.checked ?? [];
  const usable = checked.filter((r) => !r.problems.length);
  const skipped = checked.length - usable.length;
  importState.result = { imported: usable.length, skipped, total: checked.length };
  recordAudit(
    '批量导入',
    `解析 ${checked.length} 行，导入 ${usable.length} 条，跳过 ${skipped} 条`,
  );
  importState.step = 4;
}

/* ---------------------------------------------------------------- 状态看板 */

const KANBAN_COLUMNS = [
  ['todo', '待处理'],
  ['doing', '进行中'],
  ['review', '待验收'],
  ['done', '已完成'],
];
let kanbanCards = [
  { id: 1, title: '首页改版视觉稿', tag: '设计', owner: '林知夏', col: 'doing' },
  { id: 2, title: '会员积分规则文档', tag: '产品', owner: '陈屿', col: 'todo' },
  { id: 3, title: '结算页性能优化', tag: '研发', owner: '沈言', col: 'doing' },
  { id: 4, title: '客服话术手册更新', tag: '运营', owner: '苏念', col: 'review' },
  { id: 5, title: '开学季活动素材', tag: '运营', owner: '周予安', col: 'todo' },
  { id: 6, title: '数据看板配色适配', tag: '研发', owner: '许清和', col: 'done' },
];
let kanbanDragId = null;

export function renderKanban() {
  return (
    ui.intro('状态看板', '拖拽卡片流转状态，也可以用卡片上的按钮移动。', '') +
    hint('合成任务 · 拖拽或按钮均可流转 · 每次移动会写入本地操作日志') +
    `<div class="kanban-board" data-flow-board>${KANBAN_COLUMNS.map(([id, label]) => {
      const cards = kanbanCards.filter((c) => c.col === id);
      return `<section class="kanban-column" data-flow-column="${id}" aria-label="${label}"><header class="kanban-column-head"><strong>${label}</strong><span class="count-badge">${cards.length}</span></header><div class="kanban-cards">${
        cards
          .map(
            (c) =>
              `<article class="kanban-card" draggable="true" data-flow-card="${c.id}"><strong>${esc(c.title)}</strong><span class="kanban-meta"><span class="pill">${esc(c.tag)}</span><small>${esc(c.owner)}</small></span>${id === 'done' ? '' : `<button class="btn subtle" data-flow="kanban-move" data-flow-card="${c.id}">移动 →</button>`}</article>`,
          )
          .join('') || '<p class="kanban-empty">拖拽卡片到这里</p>'
      }</div></section>`;
    }).join('')}</div>`
  );
}
function moveCard(id, column) {
  const card = kanbanCards.find((c) => c.id === id);
  if (!card || card.col === column) return;
  const label = KANBAN_COLUMNS.find(([key]) => key === column)[1];
  card.col = column;
  recordAudit('看板流转', `${card.title} → ${label}`);
}

/* ---------------------------------------------------------------- 审批工作流 */

const APPROVAL_NODES = ['提交申请', '一级审批', '二级审批', '归档完成'];
let approvals = [
  {
    id: 1,
    no: 'AP-2601',
    title: '十月营销物料采购',
    type: '采购',
    applicant: '周予安',
    status: '待审批',
    timeline: [
      { label: '提交申请', time: '2026-11-05 09:20', note: '附件 3 份' },
      {
        label: '一级审批 · 陈屿',
        time: '2026-11-05 14:02',
        result: '通过',
        note: '预算符合季度计划',
      },
    ],
  },
  {
    id: 2,
    no: 'AP-2602',
    title: '会员体系改版发布',
    type: '发布',
    applicant: '林知夏',
    status: '待审批',
    timeline: [{ label: '提交申请', time: '2026-11-06 11:35', note: '灰度 20% 起量' }],
  },
  {
    id: 3,
    no: 'AP-2603',
    title: '临时扩容数据库磁盘',
    type: '运维',
    applicant: '沈言',
    status: '已驳回',
    timeline: [
      { label: '提交申请', time: '2026-11-04 16:10', note: '预计 500GB' },
      {
        label: '一级审批 · 陈屿',
        time: '2026-11-04 17:44',
        result: '驳回',
        note: '先出具容量评估',
      },
    ],
  },
  {
    id: 4,
    no: 'AP-2604',
    title: '客服知识库迁移',
    type: '发布',
    applicant: '苏念',
    status: '已通过',
    timeline: [
      { label: '提交申请', time: '2026-11-02 10:00', note: '' },
      { label: '一级审批 · 陈屿', time: '2026-11-02 13:30', result: '通过', note: '' },
      {
        label: '二级审批 · 管理员',
        time: '2026-11-03 09:15',
        result: '通过',
        note: '安排周末窗口',
      },
      { label: '归档完成', time: '2026-11-03 09:16', result: '通过', note: '' },
    ],
  },
];
let approvalFilter = '全部';

const approvalBadge = (status) =>
  `<span class="pill ${status === '已通过' ? 'status-normal' : status === '已驳回' || status === '已撤回' ? 'status-pending' : ''}">${esc(status)}</span>`;

export function renderApprovals() {
  const rows = approvals.filter((a) => approvalFilter === '全部' || a.status === approvalFilter);
  const filters = ['全部', '待审批', '已通过', '已驳回', '已撤回'];
  return (
    ui.intro('审批工作流', '多级节点流转，通过、驳回与撤回都会写入时间线和操作日志。', '') +
    hint('合成单据 · 时间线为本地演示 · 不产生真实通知或消息') +
    `<section class="panel"><div class="catalog-toolbar"><div class="segmented">${filters
      .map(
        (f) =>
          `<button data-flow="approval-filter" data-flow-filter="${f}" class="${approvalFilter === f ? 'active' : ''}">${f}</button>`,
      )
      .join(
        '',
      )}</div><span class="spacer"></span><span class="muted">${rows.length} 张单据</span></div><div class="table-scroll"><table class="approval-table"><thead><tr><th>单号</th><th>标题</th><th>类型</th><th>申请人</th><th>当前节点</th><th>状态</th><th>操作</th></tr></thead><tbody>${
      rows
        .map(
          (a) =>
            `<tr><td class="muted">${esc(a.no)}</td><td><button class="object-link" data-flow="approval-open" data-flow-id="${a.id}">${esc(a.title)}</button></td><td>${esc(a.type)}</td><td>${esc(a.applicant)}</td><td>${a.status === '待审批' ? esc(APPROVAL_NODES[Math.min(a.timeline.length, APPROVAL_NODES.length - 2)]) : '—'}</td><td>${approvalBadge(a.status)}</td><td>${a.status === '待审批' ? `<button class="btn subtle" data-flow="approval-withdraw" data-flow-id="${a.id}">撤回</button>` : ''}</td></tr>`,
        )
        .join('') ||
      `<tr><td colspan="7"><div class="empty-state">${icon('search')}<h3>没有符合条件的单据</h3><p>切换筛选查看其它状态</p></div></td></tr>`
    }</tbody></table></div></section>`
  );
}
function approvalDrawer(id) {
  const a = approvals.find((x) => x.id === id);
  if (!a) return;
  const current = a.timeline.length;
  const pending = a.status === '待审批';
  ui.openOverlay(
    `<section class="drawer approval-drawer" role="dialog" aria-modal="true" aria-labelledby="approval-title"><div class="drawer-header"><div><h2 id="approval-title">${esc(a.no)} · ${esc(a.title)}</h2><p>${esc(a.type)} · 申请人 ${esc(a.applicant)} · ${approvalBadge(a.status)}</p></div><button class="icon-button" data-action="close" aria-label="关闭审批流程">${icon('close')}</button></div><div class="drawer-content"><div class="timeline">${a.timeline
      .map(
        (t) =>
          `<div><i></i><strong>${esc(t.label)}</strong>${t.result ? `<span class="pill ${t.result === '通过' ? 'status-normal' : 'status-pending'}">${t.result}</span>` : ''}<p>${esc(t.note || '')}</p><small>${esc(t.time)}</small></div>`,
      )
      .join(
        '',
      )}${pending ? `<div><i></i><strong>${esc(APPROVAL_NODES[Math.min(current, APPROVAL_NODES.length - 2)])}</strong><p>等待当前节点处理</p></div>` : ''}</div>${
      pending
        ? `<div class="notice">${icon('circle')}通过后进入下一节点，驳回会结束流程并记录意见。</div>`
        : ''
    }</div><div class="drawer-footer">${pending ? `<button class="btn danger" data-flow="approval-reject" data-flow-id="${a.id}">驳回</button><button class="btn primary" data-flow="approval-approve" data-flow-id="${a.id}">${icon('check')}通过</button>` : `<button class="btn primary" data-action="close">关闭</button>`}</div></section>`,
    true,
  );
}
function approvalDecide(id, approve) {
  const a = approvals.find((x) => x.id === id);
  if (!a || a.status !== '待审批') return;
  const time = '2026-11-07 10:30';
  if (approve) {
    a.timeline.push({
      label: `${APPROVAL_NODES[Math.min(a.timeline.length, APPROVAL_NODES.length - 2)]} · 管理员`,
      time,
      result: '通过',
      note: '',
    });
    if (a.timeline.length >= APPROVAL_NODES.length - 1) {
      a.status = '已通过';
      a.timeline.push({ label: '归档完成', time, result: '通过', note: '' });
      recordAudit('审批通过', `${a.no} 归档完成`);
      addNotice('审批', `${a.no} 已全部通过`, `${a.title} 已归档`);
    } else {
      recordAudit('审批通过', `${a.no} → ${APPROVAL_NODES[a.timeline.length]}`);
      addNotice('审批', `${a.no} 进入下一节点`, APPROVAL_NODES[a.timeline.length]);
    }
    ui.toast(`${a.no} 已通过当前节点`);
  } else {
    a.status = '已驳回';
    a.timeline.push({
      label: `${APPROVAL_NODES[Math.min(a.timeline.length, APPROVAL_NODES.length - 2)]} · 管理员`,
      time,
      result: '驳回',
      note: '请补充材料后重新提交',
    });
    recordAudit('审批驳回', `${a.no} 驳回`);
    addNotice('审批', `${a.no} 已驳回`, '请查看驳回意见');
    ui.toast(`${a.no} 已驳回`);
  }
  ui.closeOverlay(true);
  ui.renderView();
}
function approvalWithdraw(id) {
  const a = approvals.find((x) => x.id === id);
  if (!a || a.status !== '待审批') return;
  a.status = '已撤回';
  a.timeline.push({ label: '申请人撤回', time: '2026-11-07 10:30', result: '撤回', note: '' });
  recordAudit('审批撤回', `${a.no} 撤回`);
  ui.renderView();
  ui.toast(`${a.no} 已撤回，可修改后重新提交`);
}

/* ---------------------------------------------------------------- 分类树 */

let treeNodes = [
  {
    id: 1,
    name: '数码配件',
    count: 128,
    children: [
      { id: 11, name: '手机壳', count: 46, children: [] },
      { id: 12, name: '充电器', count: 38, children: [] },
      { id: 13, name: '数据线', count: 44, children: [] },
    ],
  },
  {
    id: 2,
    name: '家居生活',
    count: 73,
    children: [
      { id: 21, name: '厨房用品', count: 25, children: [] },
      { id: 22, name: '收纳整理', count: 30, children: [] },
    ],
  },
  {
    id: 3,
    name: '服饰鞋包',
    count: 96,
    children: [
      { id: 31, name: '男装', count: 32, children: [] },
      { id: 32, name: '女装', count: 41, children: [] },
      {
        id: 33,
        name: '箱包',
        count: 23,
        children: [{ id: 331, name: '双肩包', count: 12, children: [] }],
      },
    ],
  },
  { id: 4, name: '美妆个护', count: 51, children: [] },
];
let treeExpanded = new Set([1, 2, 3, 33]);

function treeFlatten(nodes, level = 0, out = []) {
  for (const node of nodes) {
    out.push({ node, level });
    if (node.children.length && treeExpanded.has(node.id))
      treeFlatten(node.children, level + 1, out);
  }
  return out;
}
function treeFindParent(nodes, id, parent = null) {
  for (const node of nodes) {
    if (node.id === id) return parent;
    const hit = treeFindParent(node.children, id, node);
    if (hit !== undefined) return hit;
  }
  return undefined;
}
function treeSiblings(id) {
  const parent = treeFindParent(treeNodes, id);
  return parent ? parent.children : treeNodes;
}

export function renderTree() {
  const rows = treeFlatten(treeNodes);
  return (
    ui.intro('分类树', '层级分类的展开、收起与同级排序，全部为本地演示。', '') +
    hint('合成分类 · 上移/下移只影响同级顺序 · 每次调整会写入本地操作日志') +
    `<section class="panel"><div class="catalog-toolbar"><button class="btn subtle" data-flow="tree-expand-all">展开全部</button><button class="btn subtle" data-flow="tree-collapse-all">收起全部</button><span class="spacer"></span><span class="muted">${rows.filter((r) => r.level === 0).length} 个一级分类 · ${treeNodes.reduce((sum, n) => sum + 1 + n.children.length + n.children.reduce((s, c) => s + c.children.length, 0), 0)} 个节点</span></div><div class="table-scroll"><table class="tree-table"><thead><tr><th>分类</th><th>商品数</th><th>操作</th></tr></thead><tbody>${rows
      .map(({ node, level }) => {
        const siblings = treeSiblings(node.id);
        const index = siblings.findIndex((s) => s.id === node.id);
        const hasChildren = node.children.length > 0;
        const open = treeExpanded.has(node.id);
        return `<tr class="${level ? 'tree-row-child' : ''}"><td><span class="tree-indent" style="width:${level * 22}px"></span>${
          hasChildren
            ? `<button class="tree-toggle" data-flow="tree-toggle" data-flow-id="${node.id}" aria-expanded="${open}" aria-label="${open ? '收起' : '展开'}${esc(node.name)}">${open ? '▾' : '▸'}</button>`
            : '<span class="tree-leaf">·</span>'
        }<strong>${esc(node.name)}</strong>${hasChildren ? `<span class="count-badge">${node.children.length}</span>` : ''}</td><td class="numeric">${node.count}</td><td><span class="tree-actions"><button class="btn subtle" data-flow="tree-up" data-flow-id="${node.id}" ${index === 0 ? 'disabled' : ''} aria-label="上移${esc(node.name)}">↑</button><button class="btn subtle" data-flow="tree-down" data-flow-id="${node.id}" ${index === siblings.length - 1 ? 'disabled' : ''} aria-label="下移${esc(node.name)}">↓</button></span></td></tr>`;
      })
      .join('')}</tbody></table></div></section>`
  );
}
function treeToggle(id) {
  if (treeExpanded.has(id)) treeExpanded.delete(id);
  else treeExpanded.add(id);
}
function treeMove(id, delta) {
  const siblings = treeSiblings(id);
  const index = siblings.findIndex((s) => s.id === id);
  const target = index + delta;
  if (target < 0 || target >= siblings.length) return;
  const name = siblings[index].name;
  [siblings[index], siblings[target]] = [siblings[target], siblings[index]];
  recordAudit('分类排序', `${name} ${delta < 0 ? '上移' : '下移'}一位`);
}

/* ---------------------------------------------------------------- 发布日历 */

const CAL_TYPES = { 发布: 'cal-dot-publish', 审核: 'cal-dot-review', 复盘: 'cal-dot-retro' };
let calendarCursor = null;
let calendarSelected = null;
function calendarEvents() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();
  const day = (d) => `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  const prev = (d) =>
    `${month === 0 ? year - 1 : year}-${String(month === 0 ? 12 : month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  const next = (d) =>
    `${month === 11 ? year + 1 : year}-${String(month + 2 > 12 ? 1 : month + 2).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  return [
    { date: prev(24), title: '月末内容盘点', type: '复盘' },
    { date: prev(27), title: '秋季专题复盘会', type: '复盘' },
    { date: day(2), title: '会员体系公告', type: '发布' },
    { date: day(5), title: '新品预热素材', type: '发布' },
    { date: day(7), title: '每周编辑精选', type: '发布' },
    { date: day(9), title: '活动页文案终审', type: '审核' },
    { date: day(12), title: '产品故事专栏', type: '发布' },
    { date: day(15), title: '用户访谈纪要', type: '复盘' },
    { date: day(18), title: '月度数据速览', type: '发布' },
    { date: day(21), title: '品牌联合内容', type: '审核' },
    { date: day(24), title: '双旦活动预告', type: '发布' },
    { date: day(27), title: '年度专题排期', type: '审核' },
    { date: next(3), title: '下月内容启动会', type: '复盘' },
  ];
}
function calendarLabel(cursor) {
  return `${cursor.year} 年 ${cursor.month + 1} 月`;
}
function calendarShift(cursor, delta) {
  const date = new Date(cursor.year, cursor.month + delta, 1);
  return { year: date.getFullYear(), month: date.getMonth() };
}
export function renderCalendar() {
  if (!calendarCursor) {
    const now = new Date();
    calendarCursor = { year: now.getFullYear(), month: now.getMonth() };
  }
  const { year, month } = calendarCursor;
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7;
  const days = new Date(year, month + 1, 0).getDate();
  const events = calendarEvents().filter((e) =>
    e.date.startsWith(`${year}-${String(month + 1).padStart(2, '0')}`),
  );
  const byDay = {};
  for (const e of events) (byDay[Number(e.date.slice(-2))] ??= []).push(e);
  const todayKey = new Date();
  const today = `${todayKey.getFullYear()}-${String(todayKey.getMonth() + 1).padStart(2, '0')}-${String(todayKey.getDate()).padStart(2, '0')}`;
  const selectedKey =
    calendarSelected ||
    `${year}-${String(month + 1).padStart(2, '0')}-${String(Math.min(new Date().getDate(), days)).padStart(2, '0')}`;
  const cells = [];
  for (let i = 0; i < offset; i++) cells.push('<span class="cal-cell cal-blank"></span>');
  for (let d = 1; d <= days; d++) {
    const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const items = byDay[d] || [];
    cells.push(
      `<button type="button" class="cal-cell ${key === selectedKey ? 'cal-selected' : ''}" data-flow="cal-day" data-flow-date="${key}" aria-label="${month + 1} 月 ${d} 日，${items.length} 项内容" aria-pressed="${key === selectedKey}"><span class="cal-day ${key === today ? 'cal-today' : ''}">${d}</span><span class="cal-dots">${items
        .slice(0, 3)
        .map((e) => `<i class="${CAL_TYPES[e.type]}"></i>`)
        .join('')}${items.length > 3 ? `<i class="cal-more"></i>` : ''}</span></button>`,
    );
  }
  const dayItems = calendarEvents().filter((e) => e.date === selectedKey);
  return (
    ui.intro('发布日历', '按月查看内容排期，点击日期查看当天安排。', '') +
    hint('合成排期 · 与真实内容系统无关 · 只读演示') +
    `<section class="panel cal-panel"><div class="catalog-toolbar"><button class="btn subtle" data-flow="cal-prev" aria-label="上一月">‹</button><strong class="cal-month">${calendarLabel(calendarCursor)}</strong><button class="btn subtle" data-flow="cal-next" aria-label="下一月">›</button><button class="btn subtle" data-flow="cal-today-btn">今天</button><span class="spacer"></span><span class="muted">本月 ${events.length} 项安排</span></div><div class="cal-week">${['一', '二', '三', '四', '五', '六', '日'].map((d) => `<span>${d}</span>`).join('')}</div><div class="cal-grid">${cells.join('')}</div></section><section class="panel cal-day-panel"><div class="panel-head"><div><h2>${esc(selectedKey)} 的安排</h2><p>${dayItems.length ? '点击条目可在新闻列表查看同类内容样式。' : '当天没有安排。'}</p></div><span class="pill">${dayItems.length} 项</span></div><div class="cal-items">${dayItems.map((e) => `<div class="cal-item"><span class="cal-dot ${CAL_TYPES[e.type]}"></span><strong>${esc(e.title)}</strong><span class="pill">${e.type}</span></div>`).join('') || '<p class="muted cal-empty-day">空闲日期适合补充新排期。</p>'}</div></section>`
  );
}

/* ---------------------------------------------------------------- 列配置与视图 */

const COLUMN_FIELDS = [
  ['order', '订单号'],
  ['customer', '客户'],
  ['amount', '金额'],
  ['status', '状态'],
  ['date', '下单日期'],
  ['owner', '负责人'],
];
const COLUMN_ROWS = [
  {
    order: 'SO-1024',
    customer: '林曦',
    amount: '¥1,286.00',
    status: '已支付',
    date: '2026-11-02',
    owner: '苏念',
  },
  {
    order: 'SO-1025',
    customer: '顾北',
    amount: '¥329.50',
    status: '待支付',
    date: '2026-11-04',
    owner: '陈屿',
  },
  {
    order: 'SO-1026',
    customer: '许清和',
    amount: '¥89.00',
    status: '已支付',
    date: '2026-11-05',
    owner: '苏念',
  },
  {
    order: 'SO-1027',
    customer: '周予安',
    amount: '¥2,410.00',
    status: '已发货',
    date: '2026-11-06',
    owner: '沈言',
  },
  {
    order: 'SO-1028',
    customer: '陈屿',
    amount: '¥156.80',
    status: '已支付',
    date: '2026-11-06',
    owner: '林知夏',
  },
];
const COLUMN_DEFAULTS = { order: ['order', 'customer', 'amount', 'status', 'date', 'owner'] };
let columnState = null;
function columnLoad() {
  if (columnState) return columnState;
  try {
    const saved = JSON.parse(localStorage.getItem('nova-view-columns'));
    if (
      Array.isArray(saved) &&
      saved.length &&
      saved.every((x) => COLUMN_FIELDS.some(([key]) => key === x)) &&
      new Set(saved).size === saved.length
    ) {
      columnState = [...saved, ...COLUMN_DEFAULTS.order.filter((key) => !saved.includes(key))];
      return columnState;
    }
  } catch {}
  columnState = [...COLUMN_DEFAULTS.order];
  return columnState;
}
function columnSave() {
  try {
    localStorage.setItem('nova-view-columns', JSON.stringify(columnState));
  } catch {}
}
export function renderColumns() {
  const order = columnLoad();
  const label = (key) => COLUMN_FIELDS.find(([k]) => k === key)[1];
  const rows = COLUMN_ROWS.map(
    (row) =>
      `<tr>${order.map((key) => (key === 'amount' ? `<td class="numeric">${row[key]}</td>` : `<td>${esc(row[key])}</td>`)).join('')}</tr>`,
  ).join('');
  const controls = order
    .map(
      (key, index) =>
        `<div class="column-rule"><label class="check-label"><input class="checkbox" type="checkbox" data-flow="col-toggle" data-flow-key="${key}" checked>${label(key)}</label><span class="tree-actions"><button class="btn subtle" data-flow="col-up" data-flow-key="${key}" ${index === 0 ? 'disabled' : ''} aria-label="左移${label(key)}">↑</button><button class="btn subtle" data-flow="col-down" data-flow-key="${key}" ${index === order.length - 1 ? 'disabled' : ''} aria-label="右移${label(key)}">↓</button></span></div>`,
    )
    .join('');
  return (
    ui.intro('列配置与视图', '调整表格列的显隐与顺序，配置保存在当前浏览器。', '') +
    hint('演示订单表 · 配置独立存储于 nova-view-columns，可随时恢复默认') +
    `<div class="demo-columns-layout"><section class="panel"><div class="panel-head"><div><h2>列设置</h2><p>取消勾选隐藏列，箭头调整顺序。</p></div><button class="btn subtle" data-flow="col-reset">恢复默认</button></div><div class="component-body column">${controls}</div></section><section class="panel"><div class="panel-head"><div><h2>订单预览</h2><p>当前展示 ${order.length} / ${COLUMN_FIELDS.length} 列。</p></div></div><div class="table-scroll"><table class="demo-columns-table"><thead><tr>${order.map((key) => `<th>${label(key)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div></section></div>`
  );
}

/* ---------------------------------------------------------------- 回收站 */

let recycleItems = [
  { id: 1, title: '过期的促销公告', deletedFrom: '新闻资讯', deletedAt: '2026-11-01' },
  { id: 2, title: '旧版会员规则草稿', deletedFrom: '新闻资讯', deletedAt: '2026-11-03' },
  { id: 3, title: '测试商品 NOVA-TEST', deletedFrom: '商品管理', deletedAt: '2026-11-05' },
  { id: 4, title: '离职成员临时文档', deletedFrom: '新闻资讯', deletedAt: '2026-11-06' },
];
let recycleLive = [
  { id: 101, title: '十一月起的内容排期', from: '新闻资讯' },
  { id: 102, title: '热销配件补货说明', from: '商品管理' },
  { id: 103, title: '客服周末值班安排', from: '新闻资讯' },
];
let recyclePendingClear = false;
export function renderRecycle() {
  return (
    ui.intro('回收站', '删除的内容先进入回收站，可恢复或彻底清除。', '') +
    hint('本地演示 · 彻底删除不可恢复 · 真实系统由 Django 软删除与权限控制') +
    `<div class="demo-recycle-layout"><section class="panel"><div class="panel-head"><div><h2>在库内容</h2><p>删除后进入回收站。</p></div><span class="pill">${recycleLive.length} 项</span></div><div class="component-body column">${
      recycleLive
        .map(
          (item) =>
            `<div class="recycle-row"><div><strong>${esc(item.title)}</strong><small>来自 ${esc(item.from)}</small></div><button class="btn subtle" data-flow="recycle-delete" data-flow-id="${item.id}">${icon('close')}删除</button></div>`,
        )
        .join('') || '<p class="muted cal-empty-day">全部内容都已删除。</p>'
    }</div></section><section class="panel"><div class="panel-head"><div><h2>回收站</h2><p>保留 30 天，到期自动清除（演示）。</p></div><span class="pill">${recycleItems.length} 项</span>${recycleItems.length ? `<button class="btn subtle" data-flow="recycle-clear-ask">清空回收站</button>` : ''}</div><div class="component-body column">${
      recycleItems
        .map(
          (item) =>
            `<div class="recycle-row"><div><strong>${esc(item.title)}</strong><small>原位置 ${esc(item.deletedFrom)} · 删除于 ${esc(item.deletedAt)}</small></div><span class="tree-actions"><button class="btn subtle" data-flow="recycle-restore" data-flow-id="${item.id}">恢复</button><button class="btn danger" data-flow="recycle-purge-ask" data-flow-id="${item.id}">彻底删除</button></span></div>`,
        )
        .join('') || '<p class="muted cal-empty-day">回收站是空的。</p>'
    }</div></section></div>`
  );
}
function recycleAsk(kind, id) {
  recyclePendingClear = kind === 'clear';
  const target = recycleItems.find((x) => x.id === id);
  const title = kind === 'clear' ? '清空回收站？' : `彻底删除「${target?.title ?? ''}」？`;
  ui.openOverlay(
    `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="recycle-confirm-title"><h2 id="recycle-confirm-title">${esc(title)}</h2><p>彻底删除后无法恢复；恢复操作不受影响。</p><div class="modal-actions"><button class="btn" data-action="close">取消</button><button class="btn danger" data-flow="${kind === 'clear' ? 'recycle-clear-run' : 'recycle-purge-run'}" data-flow-id="${id ?? ''}">确认${kind === 'clear' ? '清空' : '删除'}</button></div></section>`,
    true,
  );
}

/* ---------------------------------------------------------------- 任务进度中心 */

let tasks = [
  { id: 1, name: '导出全部商品数据', status: 'queued', percent: 0 },
  { id: 2, name: '重建搜索索引', status: 'queued', percent: 0 },
  { id: 3, name: '生成月度经营报表', status: 'queued', percent: 0 },
  { id: 4, name: '批量发送会员通知', status: 'queued', percent: 0 },
];
const taskBadge = (status) =>
  ({ queued: '排队中', running: '运行中', paused: '已暂停', done: '已完成', failed: '失败' })[
    status
  ];
let taskTimer = null;
function ensureTaskTimer() {
  if (taskTimer === null) taskTimer = setInterval(taskTick, 700);
}
function taskTick() {
  if (!tasks.some((task) => task.status === 'running')) {
    clearInterval(taskTimer);
    taskTimer = null;
    return;
  }
  if (getView() !== 'tasks') return;
  (window.__tickLog = window.__tickLog || []).push('tick from=' + tasks[0].percent);
  let changed = false;
  for (const task of tasks) {
    if (task.status !== 'running') continue;
    task.percent = Math.min(100, task.percent + 6 + Math.round(Math.random() * 9));
    changed = true;
    if (task.failAt && task.percent >= task.failAt) {
      task.status = 'failed';
      task.failAt = null;
      recordAudit('后台任务', `${task.name} 失败于 ${task.percent}%`);
      ui.toast(`${task.name} 失败，可重试`);
      changed = true;
    } else if (task.percent >= 100) {
      task.status = 'done';
      recordAudit('后台任务', `${task.name} 完成`);
      addNotice('任务', `${task.name} 已完成`, '可在任务进度中心查看结果');
      ui.toast(`${task.name} 已完成`);
      changed = true;
    }
  }
  if (changed && getView() === 'tasks') taskRefresh();
}
function taskRows() {
  return tasks
    .map((task) => {
      const canStart = ['queued', 'paused', 'failed'].includes(task.status);
      return `<div class="task-row"><div class="task-copy"><strong>${esc(task.name)}</strong><span class="pill">${taskBadge(task.status)}</span></div><div class="task-progress" role="progressbar" aria-label="${esc(task.name)} 进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${task.percent}"><span style="width:${task.percent}%"></span></div><span class="task-percent">${task.percent}%</span><span class="tree-actions">${canStart ? `<button class="btn subtle" data-flow="task-start" data-flow-id="${task.id}">${task.status === 'failed' ? '重试' : task.status === 'paused' ? '继续' : '开始'}</button>` : ''}${task.status === 'running' ? `<button class="btn subtle" data-flow="task-pause" data-flow-id="${task.id}">暂停</button>` : ''}${task.status === 'running' ? `<button class="btn subtle" data-flow="task-fail" data-flow-id="${task.id}">模拟失败</button>` : ''}</span></div>`;
    })
    .join('');
}
function taskRefresh() {
  const queue = document.getElementById('task-queue');
  if (queue) queue.innerHTML = taskRows();
  const count = document.getElementById('task-running-count');
  if (count) count.textContent = `${tasks.filter((t) => t.status === 'running').length} 个运行中`;
}
export function renderTasks() {
  const running = tasks.some((t) => t.status === 'running');
  return (
    ui.intro('任务进度中心', '批量任务的真实进度语义：排队、运行、暂停、失败与重试。', '') +
    hint('模拟进度 · 离开本页自动暂停 · 不执行真实导出或通知') +
    `<section class="panel"><div class="panel-head"><div><h2>任务队列</h2><p>进度为本地模拟；失败任务可重试。</p></div><span class="pill" id="task-running-count">${tasks.filter((t) => t.status === 'running').length} 个运行中</span></div><div class="component-body column" id="task-queue">${taskRows()}</div></section>`
  );
}

/* ---------------------------------------------------------------- 通知中心 */

let notices = [
  {
    id: 1,
    type: '审批',
    title: 'AP-2601 等待二级审批',
    detail: '十月营销物料采购已通过一级审批',
    time: '36 分钟前',
    unread: true,
  },
  {
    id: 2,
    type: '任务',
    title: '数据看板配色适配已完成',
    detail: '导出结果可在任务进度中心下载',
    time: '2 小时前',
    unread: true,
  },
  {
    id: 3,
    type: '内容',
    title: '十月内容计划待审核',
    detail: '编辑规范更新需要二级确认',
    time: '5 小时前',
    unread: true,
  },
  {
    id: 4,
    type: '系统',
    title: '演示环境例行备份完成',
    detail: '本地数据已整理',
    time: '昨天 22:00',
    unread: false,
  },
  {
    id: 5,
    type: '内容',
    title: '秋季专题图片已替换',
    detail: '封面加载失败样本已修复',
    time: '昨天 18:20',
    unread: false,
  },
  {
    id: 6,
    type: '系统',
    title: '演示管理员登录提醒',
    detail: '本地演示 · 无真实账户',
    time: '前天 09:00',
    unread: false,
  },
];
let noticeFilter = '全部';
function addNotice(type, title, detail) {
  const id = notices.length ? Math.max(...notices.map((n) => n.id)) + 1 : 1;
  notices.unshift({ id, type, title, detail, time: '刚刚', unread: true });
  syncNoticeBadge();
}
function unreadNoticeCount() {
  return notices.filter((n) => n.unread).length;
}
function syncNoticeBadge() {
  const badge = document.querySelector('[data-notice-badge]');
  if (!badge) return;
  const count = unreadNoticeCount();
  badge.textContent = String(count);
  badge.hidden = count === 0;
}
export function unreadNoticeTotal() {
  return unreadNoticeCount();
}
export function renderNotificationCenter() {
  const types = ['全部', '审批', '任务', '内容', '系统'];
  const rows = notices.filter((n) => noticeFilter === '全部' || n.type === noticeFilter);
  const groups = [];
  for (const row of rows) {
    const last = groups[groups.length - 1];
    if (last && last.type === row.type) last.items.push(row);
    else groups.push({ type: row.type, items: [row] });
  }
  return `<section class="drawer notice-drawer" role="dialog" aria-modal="true" aria-labelledby="notice-title"><div class="drawer-header"><div><h2 id="notice-title">通知中心</h2><p>示例通知，按类型分组；未读 ${unreadNoticeCount()} 条</p></div><button class="icon-button" data-action="close" aria-label="关闭通知中心">${icon('close')}</button></div><div class="group-tabs notice-tabs" role="tablist" aria-label="通知筛选">${types.map((f) => `<button type="button" class="group-tab" data-flow="notice-filter" data-flow-filter="${f}" aria-selected="${noticeFilter === f}">${f}${f === '全部' && unreadNoticeCount() ? ` (${unreadNoticeCount()})` : ''}</button>`).join('')}</div><div class="drawer-content"><div class="notice-toolbar"><span class="muted">点击条目标为已读</span><button class="btn subtle" data-flow="notice-read-all" ${unreadNoticeCount() ? '' : 'disabled'}>${icon('check')}全部标为已读</button></div>${
    groups.length
      ? groups
          .map(
            (group) =>
              `<div class="notice-group"><div class="notice-group-head">${group.type}</div>${group.items
                .map(
                  (n) =>
                    `<button type="button" class="notice-item ${n.unread ? 'notice-unread' : ''}" data-flow="notice-read" data-flow-id="${n.id}"><span class="notice-dot" aria-hidden="true"></span><span class="notice-copy"><strong>${esc(n.title)}</strong><small>${esc(n.detail)}</small><small class="muted">${esc(n.time)} · ${n.type}</small></span>${n.unread ? '<span class="pill status-normal">未读</span>' : '<span class="pill">已读</span>'}</button>`,
                )
                .join('')}</div>`,
          )
          .join('')
      : '<p class="muted cal-empty-day">该类型暂无通知。</p>'
  }</div></section>`;
}

/* ---------------------------------------------------------------- 双语对照 */

const BILINGUAL_GROUPS = [
  [
    '导航与页面',
    [
      ['工作概览', 'Overview'],
      ['商品管理', 'Products'],
      ['组织与成员', 'Organization'],
      ['操作日志', 'Audit log'],
    ],
  ],
  [
    '操作按钮',
    [
      ['保存', 'Save'],
      ['保存并继续编辑', 'Save and continue editing'],
      ['新增', 'Add'],
      ['删除', 'Delete'],
      ['清除筛选', 'Clear filters'],
      ['展开全部', 'Expand all'],
    ],
  ],
  [
    '状态与角色',
    [
      ['已发布', 'Published'],
      ['待审核', 'In review'],
      ['已驳回', 'Rejected'],
      ['管理员', 'Administrator'],
      ['只读成员', 'Read-only member'],
    ],
  ],
  [
    '消息与提示',
    [
      ['操作成功', 'Operation succeeded'],
      ['浏览器未能保存偏好', 'The browser could not save the preference'],
      ['至少保留一列', 'Keep at least one column'],
      ['没有符合条件的记录', 'No matching records'],
    ],
  ],
];
let bilingualLanguage = 'zh';
export function renderBilingual() {
  const live = {
    zh: {
      title: '季度经营简报',
      status: '待审核',
      actions: ['保存', '导出 CSV', '删除'],
      hint: '更改仅保存在当前浏览器',
    },
    en: {
      title: 'Quarterly business brief',
      status: 'In review',
      actions: ['Save', 'Export CSV', 'Delete'],
      hint: 'Changes stay in this browser only',
    },
  }[bilingualLanguage];
  return (
    ui.intro('双语对照', '同一套管理界面的中英文案对照，覆盖主题自带的翻译目录。', '') +
    hint('静态演示 · Django 环境中由 i18n 目录按激活语言输出') +
    `<section class="panel"><div class="panel-head"><div><h2>实时示例</h2><p>切换语言查看同一段界面的两种文案。</p></div><div class="segmented">${['zh', 'en'].map((code) => `<button data-flow="bilingual-lang" data-flow-lang="${code}" class="${bilingualLanguage === code ? 'active' : ''}">${code === 'zh' ? '中文' : 'English'}</button>`).join('')}</div></div><div class="bilingual-live"><div class="bilingual-sample"><strong>${esc(live.title)}</strong><span class="pill ${bilingualLanguage === 'zh' ? 'status-pending' : ''}">${esc(live.status)}</span></div><div class="bilingual-actions">${live.actions.map((a) => `<span class="btn">${esc(a)}</span>`).join('')}</div><p class="muted bilingual-hint">${esc(live.hint)}</p></div></section><section class="panel"><div class="panel-head"><div><h2>文案对照表</h2><p>主题自带标签的常用译法。</p></div></div><div class="table-scroll"><table class="bilingual-table"><thead><tr><th>场景</th><th>中文</th><th>English</th></tr></thead><tbody>${BILINGUAL_GROUPS.map(([scene, pairs]) => pairs.map(([zh, en], index) => `<tr>${index === 0 ? `<td rowspan="${pairs.length}">${scene}</td>` : ''}<td>${zh}</td><td>${en}</td></tr>`).join('')).join('')}</tbody></table></div></section>`
  );
}

/* ---------------------------------------------------------------- 行内编辑 */

let inlineRows = [
  { id: 1, name: '无线充电板', stock: '42', status: '正常', note: '双十一前补货 30 件' },
  { id: 2, name: '磁吸手机壳', stock: '120', status: '正常', note: '' },
  { id: 3, name: '胡桃木收纳盘', stock: '0', status: '补货中', note: '等待工厂排产' },
  { id: 4, name: '复古帆布包', stock: '17', status: '正常', note: '' },
  { id: 5, name: '便携补光灯', stock: '-4', status: '停售', note: '演示负数校验' },
];
const INLINE_STATUSES = ['正常', '补货中', '停售'];
let inlineBaseline = structuredClone(inlineRows);
function inlineDirty(row) {
  const base = inlineBaseline.find((b) => b.id === row.id);
  return !base || base.stock !== row.stock || base.status !== row.status || base.note !== row.note;
}
function inlineError(row) {
  const value = (row.stock || '').trim();
  if (value === '' || !/^-?\d+$/.test(value) || Number(value) < 0) return '库存需为不小于 0 的整数';
  return '';
}
export function renderInline() {
  const dirtyCount = inlineRows.filter(inlineDirty).length;
  return (
    ui.intro(
      '行内编辑',
      '直接在表格里修改库存与状态，逐行保存并跟踪脏状态。',
      `<button class="btn subtle" data-flow="inline-reset">放弃全部修改</button>`,
    ) +
    hint('合成库存表 · 保存只更新本地演示数据 · 校验失败会定位到单元格') +
    `<section class="panel"><div class="panel-head"><div><h2>库存调整</h2><p>${dirtyCount ? `${dirtyCount} 行有未保存修改` : '没有未保存的修改'}</p></div><span class="pill ${dirtyCount ? 'status-pending' : ''}">${dirtyCount ? '有未保存更改' : '全部已保存'}</span></div><div class="table-scroll"><table class="inline-table"><thead><tr><th>商品</th><th>库存</th><th>状态</th><th>备注</th><th>操作</th></tr></thead><tbody>${inlineRows
      .map((row) => {
        const dirty = inlineDirty(row);
        const error = inlineError(row);
        return `<tr class="${dirty ? 'inline-row-dirty' : ''}"><td><strong>${esc(row.name)}</strong></td><td><input class="inline-input inline-stock" data-flow-inline="stock" data-flow-id="${row.id}" value="${esc(row.stock)}" inputmode="numeric" aria-label="${esc(row.name)}库存"><small class="error">${error}</small></td><td><select class="inline-input" data-flow-inline="status" data-flow-id="${row.id}" aria-label="${esc(row.name)}状态">${INLINE_STATUSES.map((s) => `<option ${s === row.status ? 'selected' : ''}>${s}</option>`).join('')}</select></td><td><input class="inline-input" data-flow-inline="note" data-flow-id="${row.id}" value="${esc(row.note)}" maxlength="40" aria-label="${esc(row.name)}备注" placeholder="补充说明…"></td><td>${dirty ? `<span class="tree-actions"><button class="btn subtle" data-flow="inline-revert" data-flow-id="${row.id}">还原</button><button class="btn primary" data-flow="inline-save" data-flow-id="${row.id}">${icon('check')}保存</button></span>` : '<span class="muted inline-saved">已保存</span>'}</td></tr>`;
      })
      .join('')}</tbody></table></div></section>`
  );
}
function inlineRevert(id) {
  const base = inlineBaseline.find((b) => b.id === id);
  const row = inlineRows.find((r) => r.id === id);
  if (base && row) Object.assign(row, { stock: base.stock, status: base.status, note: base.note });
}
function inlineSave(id) {
  const row = inlineRows.find((r) => r.id === id);
  if (!row) return;
  const error = inlineError(row);
  if (error) {
    ui.toast(`${row.name}：${error}`);
    document.querySelector(`[data-flow-inline="stock"][data-flow-id="${id}"]`)?.focus();
    return;
  }
  row.stock = row.stock.trim();
  const base = inlineBaseline.find((b) => b.id === id);
  if (base) Object.assign(base, { stock: row.stock, status: row.status, note: row.note });
  recordAudit('行内编辑', `${row.name} 库存 ${row.stock} · ${row.status}`);
  ui.toast(`${row.name} 已保存`);
}

/* ---------------------------------------------------------------- 事件分发 */

export function renderFlow(route) {
  const view = route.split('/')[0];
  if (view === 'import') return renderImport();
  if (view === 'kanban') return renderKanban();
  if (view === 'approvals') return renderApprovals();
  if (view === 'tree') return renderTree();
  if (view === 'calendar') return renderCalendar();
  if (view === 'columns') return renderColumns();
  if (view === 'recycle') return renderRecycle();
  if (view === 'bilingual') return renderBilingual();
  if (view === 'inline') return renderInline();
  return renderTasks();
}

function rerender(focus) {
  ui.renderView();
  if (focus) document.querySelector(focus)?.focus();
}
function noticeSyncDrawer() {
  const drawer = document.querySelector('.notice-drawer');
  if (drawer) {
    const subtitle = drawer.querySelector('.drawer-header p');
    if (subtitle) subtitle.textContent = `示例通知，按类型分组；未读 ${unreadNoticeCount()} 条`;
    const allTab = drawer.querySelector('[data-flow-filter="全部"]');
    if (allTab)
      allTab.textContent = `全部${unreadNoticeCount() ? ` (${unreadNoticeCount()})` : ''}`;
    const readAll = drawer.querySelector('[data-flow="notice-read-all"]');
    if (readAll) readAll.disabled = !unreadNoticeCount();
  }
  syncNoticeBadge();
}
function flowsInput(event) {
  const input = event.target.closest?.('[data-flow-inline]');
  if (!input) return false;
  const row = inlineRows.find((r) => r.id === Number(input.dataset.flowId));
  if (!row) return false;
  row[input.dataset.flowInline] = input.value;
  if (event.type === 'change') rerender();
  return true;
}

export function flowsClick(event) {
  const el = event.target.closest('[data-flow]');
  if (!el) return false;
  const action = el.dataset.flow;
  if (action === 'import-parse') {
    const raw = document.getElementById('import-raw')?.value ?? importState.raw;
    const parsed = parseImport(raw);
    if (parsed.error || !parsed.headers.length) {
      ui.toast(parsed.error || '表头为空，无法继续');
      return true;
    }
    importState.raw = raw;
    importState.headers = parsed.headers;
    importState.rows = parsed.rows;
    importState.mapping = autoMapping(parsed.headers);
    importState.step = 2;
    rerender('#import-raw');
    return true;
  }
  if (action === 'import-apply') {
    document.querySelectorAll('[data-flow-column]').forEach((select) => {
      importState.mapping[Number(select.dataset.flowColumn)] = select.value;
    });
    importState.step = 3;
    rerender();
    return true;
  }
  if (action === 'import-back') {
    importState.step = Number(el.dataset.flowStep) || 1;
    rerender();
    return true;
  }
  if (action === 'import-run') {
    importRun();
    rerender();
    return true;
  }
  if (action === 'import-restart') {
    importState.step = 1;
    importState.raw = IMPORT_SAMPLE;
    importState.result = null;
    rerender();
    return true;
  }
  if (action === 'import-skip') {
    importState.skipInvalid = el.checked;
    rerender();
    return true;
  }
  if (action === 'kanban-move') {
    const id = Number(el.dataset.flowCard);
    const card = kanbanCards.find((c) => c.id === id);
    if (card) {
      const order = KANBAN_COLUMNS.map(([key]) => key);
      moveCard(id, order[Math.min(order.indexOf(card.col) + 1, order.length - 1)]);
      rerender();
    }
    return true;
  }
  if (action === 'approval-filter') {
    approvalFilter = el.dataset.flowFilter;
    rerender();
    return true;
  }
  if (action === 'approval-open') {
    approvalDrawer(Number(el.dataset.flowId));
    return true;
  }
  if (action === 'approval-approve') {
    approvalDecide(Number(el.dataset.flowId), true);
    return true;
  }
  if (action === 'approval-reject') {
    approvalDecide(Number(el.dataset.flowId), false);
    return true;
  }
  if (action === 'approval-withdraw') {
    approvalWithdraw(Number(el.dataset.flowId));
    return true;
  }
  if (action === 'tree-toggle') {
    treeToggle(Number(el.dataset.flowId));
    rerender();
    return true;
  }
  if (action === 'tree-expand-all') {
    treeFlatten(treeNodes).forEach(({ node }) => {
      if (node.children.length) treeExpanded.add(node.id);
    });
    rerender();
    return true;
  }
  if (action === 'tree-collapse-all') {
    treeExpanded.clear();
    rerender();
    return true;
  }
  if (action === 'tree-up' || action === 'tree-down') {
    treeMove(Number(el.dataset.flowId), action === 'tree-up' ? -1 : 1);
    rerender();
    return true;
  }
  if (action === 'cal-day') {
    calendarSelected = el.dataset.flowDate;
    rerender();
    return true;
  }
  if (action === 'cal-prev' || action === 'cal-next') {
    calendarCursor = calendarShift(calendarCursor, action === 'cal-prev' ? -1 : 1);
    rerender();
    return true;
  }
  if (action === 'cal-today-btn') {
    const now = new Date();
    calendarCursor = { year: now.getFullYear(), month: now.getMonth() };
    calendarSelected = null;
    rerender();
    return true;
  }
  if (action === 'col-toggle') {
    const order = columnLoad();
    const key = el.dataset.flowKey;
    if (el.checked) {
      if (!order.includes(key)) order.push(key);
    } else {
      const index = order.indexOf(key);
      if (order.length <= 1) {
        el.checked = true;
        ui.toast('至少保留一列');
        return true;
      }
      if (index >= 0) order.splice(index, 1);
    }
    columnSave();
    rerender();
    return true;
  }
  if (action === 'col-up' || action === 'col-down') {
    const order = columnLoad();
    const index = order.indexOf(el.dataset.flowKey);
    const target = index + (action === 'col-up' ? -1 : 1);
    if (index >= 0 && target >= 0 && target < order.length) {
      [order[index], order[target]] = [order[target], order[index]];
      columnSave();
      rerender();
    }
    return true;
  }
  if (action === 'col-reset') {
    columnState = null;
    try {
      localStorage.removeItem('nova-view-columns');
    } catch {}
    columnLoad();
    rerender();
    return true;
  }
  if (action === 'recycle-delete') {
    const index = recycleLive.findIndex((x) => x.id === Number(el.dataset.flowId));
    if (index >= 0) {
      const [item] = recycleLive.splice(index, 1);
      recycleItems.unshift({
        id: item.id,
        title: item.title,
        deletedFrom: item.from,
        deletedAt: '2026-11-07',
      });
      recordAudit('移入回收站', item.title);
      rerender();
    }
    return true;
  }
  if (action === 'recycle-restore') {
    const index = recycleItems.findIndex((x) => x.id === Number(el.dataset.flowId));
    if (index >= 0) {
      const [item] = recycleItems.splice(index, 1);
      recycleLive.push({ id: item.id, title: item.title, from: item.deletedFrom });
      recordAudit('从回收站恢复', item.title);
      rerender();
      ui.toast(`「${item.title}」已恢复`);
    }
    return true;
  }
  if (action === 'recycle-purge-ask') {
    recycleAsk('purge', Number(el.dataset.flowId));
    return true;
  }
  if (action === 'recycle-clear-ask') {
    recycleAsk('clear');
    return true;
  }
  if (action === 'recycle-purge-run') {
    const index = recycleItems.findIndex((x) => x.id === Number(el.dataset.flowId));
    if (index >= 0) {
      const [item] = recycleItems.splice(index, 1);
      recordAudit('彻底删除', item.title);
    }
    ui.closeOverlay(true);
    rerender();
    ui.toast('已彻底删除');
    return true;
  }
  if (action === 'recycle-clear-run') {
    recordAudit('清空回收站', `${recycleItems.length} 项`);
    recycleItems = [];
    ui.closeOverlay(true);
    rerender();
    ui.toast('回收站已清空');
    return true;
  }
  if (action === 'notice-filter') {
    noticeFilter = el.dataset.flowFilter;
    const drawer = document.querySelector('.notice-drawer');
    if (drawer) drawer.outerHTML = renderNotificationCenter();
    return true;
  }
  if (action === 'notice-read') {
    const notice = notices.find((n) => n.id === Number(el.dataset.flowId));
    if (notice?.unread) {
      notice.unread = false;
      el.classList.remove('notice-unread');
      const pill = el.querySelector('.pill');
      if (pill) {
        pill.textContent = '已读';
        pill.classList.remove('status-normal');
      }
      noticeSyncDrawer();
    }
    return true;
  }
  if (action === 'notice-read-all') {
    notices.forEach((n) => {
      n.unread = false;
    });
    const drawer = document.querySelector('.notice-drawer');
    if (drawer) drawer.outerHTML = renderNotificationCenter();
    syncNoticeBadge();
    return true;
  }
  if (action === 'bilingual-lang') {
    bilingualLanguage = el.dataset.flowLang;
    rerender();
    return true;
  }
  if (action === 'inline-save') {
    inlineSave(Number(el.dataset.flowId));
    rerender();
    return true;
  }
  if (action === 'inline-revert') {
    inlineRevert(Number(el.dataset.flowId));
    rerender();
    return true;
  }
  if (action === 'inline-reset') {
    inlineBaseline = structuredClone(inlineRows);
    rerender();
    ui.toast('已放弃全部未保存修改');
    return true;
  }
  if (action === 'task-start' || action === 'task-pause' || action === 'task-fail') {
    const task = tasks.find((x) => x.id === Number(el.dataset.flowId));
    if (!task) return true;
    if (action === 'task-start') {
      ensureTaskTimer();
      if (task.status === 'failed' || task.percent >= 100) task.percent = 0;
      task.status = 'running';
      task.failAt = null;
    } else if (action === 'task-pause') {
      task.status = 'paused';
    } else {
      task.failAt = task.percent + 12;
    }
    rerender();
    return true;
  }
  return false;
}

export function flowsDragOver(event) {
  const column = event.target.closest?.('[data-flow-column]');
  if (column && kanbanDragId !== null) {
    event.preventDefault();
  }
}

export function flowsDrop(event) {
  const column = event.target.closest?.('[data-flow-column]');
  if (!column || kanbanDragId === null) return false;
  event.preventDefault();
  moveCard(kanbanDragId, column.dataset.flowColumn);
  kanbanDragId = null;
  rerender();
  return true;
}

export function flowsDragStart(event) {
  const card = event.target.closest?.('[data-flow-card]');
  if (!card) return false;
  kanbanDragId = Number(card.dataset.flowCard);
  if (event.dataTransfer) {
    event.dataTransfer.setData('text/plain', String(kanbanDragId));
    event.dataTransfer.effectAllowed = 'move';
  }
  return true;
}
