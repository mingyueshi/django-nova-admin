// Additional admin scenarios. All mutations remain in this browser.
let api,
  tab = 'forms',
  surface = 'ready',
  step = 1,
  wizard = { name: '每周内容巡检', target: '内容运营', notify: true },
  formTags = new Set(['内容运营']);
const tabs = [
  ['forms', '表单控件', 'edit'],
  ['data', '数据展示', 'layers'],
  ['feedback', '反馈与边界', 'activity'],
  ['workflow', '操作流程', 'bolt'],
  ['tokens', '视觉规范', 'grid'],
];
const initialAudit = [
  {
    id: 'LOG-1042',
    type: '修改用户',
    resource: '林知夏',
    actor: '演示管理员',
    time: '2026-10-01 09:42:18',
    status: '成功',
    detail: '更新所属团队与角色。',
  },
  {
    id: 'LOG-1041',
    type: '批量更新',
    resource: '用户 · 3 条记录',
    actor: '演示管理员',
    time: '2026-10-01 09:36:05',
    status: '成功',
    detail: '将所选演示账户状态更新为正常。',
  },
  {
    id: 'LOG-1040',
    type: '权限校验',
    resource: '系统配置',
    actor: '只读成员',
    time: '2026-10-01 09:31:26',
    status: '已拦截',
    detail: '此条目是被拒绝访问的示例，不代表本页面实施了真实鉴权。',
  },
  {
    id: 'LOG-1039',
    type: '新增记录',
    resource: '秋季内容计划',
    actor: '演示编辑',
    time: '2026-10-01 09:20:42',
    status: '成功',
    detail: '通过表单创建了一条示例内容记录。',
  },
  {
    id: 'LOG-1038',
    type: '导出演示',
    resource: '成员列表',
    actor: '演示管理员',
    time: '2026-09-30 17:56:09',
    status: '成功',
    detail: '导出当前筛选条件下的合成演示数据。',
  },
  {
    id: 'LOG-1037',
    type: '保存配置',
    resource: '通知偏好',
    actor: '演示管理员',
    time: '2026-09-30 16:08:51',
    status: '失败',
    detail: '模拟请求超时。真实项目应由服务端记录原始异常与操作者。',
  },
];
let audit,
  auditFilter = '全部结果';
function helpers() {
  return api;
}
export function initScenarios({ ui, getUser, getUsers, getView, navigate, markClean }) {
  api = Object.freeze({ ...ui, getUser, getUsers, getView, navigate, markClean });
  try {
    audit = JSON.parse(localStorage.getItem('nova-audit')) || structuredClone(initialAudit);
  } catch {
    audit = structuredClone(initialAudit);
  }
  document.addEventListener('click', onClick);
  document.addEventListener('submit', onSubmit);
  document.addEventListener('change', onChange);
}
export function addAuditEvent(type, resource, detail = '仅更新当前浏览器中的演示数据。') {
  if (!audit) return;
  const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
  audit.unshift({
    id: `LOG-${Date.now().toString().slice(-7)}`,
    type,
    resource,
    actor: '演示管理员',
    time: stamp,
    status: '成功',
    detail,
  });
  audit = audit.slice(0, 60);
  try {
    localStorage.setItem('nova-audit', JSON.stringify(audit));
  } catch {}
}
export function resetAudit() {
  audit = structuredClone(initialAudit);
  try {
    localStorage.removeItem('nova-audit');
  } catch {}
}
const field = (label, html, note = '') =>
  `<div class="field"><label>${label}</label>${html}${note ? `<small>${note}</small>` : ''}</div>`;
const panel = (title, body, cls = '') =>
  `<section class="panel lab-panel ${cls}"><div class="panel-head"><h2>${title}</h2></div>${body}</section>`;
function labButton(label, action, primary = false) {
  return `<button type="button" class="btn ${primary ? 'primary' : ''}" data-lab="${action}">${label}</button>`;
}
export function renderComponentLab() {
  const { icon } = helpers();
  return `<div class="lab-tabbar" role="tablist" aria-label="组件分类">${tabs.map(([id, title, i]) => `<button class="lab-tab ${tab === id ? 'active' : ''}" role="tab" aria-selected="${tab === id}" data-lab-tab="${id}">${icon(i)}${title}</button>`).join('')}</div><div class="lab-context"><span>${{ 'forms': '从输入到提交，把常见的表单情况走一遍。', 'data': '详情、进度、折叠信息和不同密度的数据展示。', 'feedback': '真正切换加载、空、失败和禁止访问的界面状态。', 'workflow': '多步骤任务、批量操作与确认流程。', 'tokens': '复用同一套设计变量，保持跨页面的一致性。' }[tab]}</span><span class="pill">交互演示</span></div><div class="lab-grid">${{ forms: forms, data: dataShowcase, feedback: feedback, workflow: workflow, tokens: tokens }[tab]()}</div>`;
}
function forms() {
  const { icon } = helpers();
  return (
    panel(
      '内容编辑表单',
      `<form id="lab-content-form" class="lab-body" novalidate><div class="field"><label for="lab-title">内容标题 <span class="required">*</span></label><input id="lab-title" name="title" maxlength="40" placeholder="例如：十月产品更新计划" aria-describedby="lab-title-error"><small id="lab-title-error">至少 4 个字符，最多 40 个字符</small></div><div class="field-row"><div class="field"><label for="lab-category">内容分类</label><select data-searchable id="lab-category" name="category"><option>产品更新</option><option>运营公告</option><option>帮助文档</option></select></div><div class="field"><label for="lab-date">计划日期</label><input type="date" id="lab-date" name="date" value="2026-10-15"></div></div><div class="field"><label for="lab-summary">内容摘要</label><textarea id="lab-summary" name="summary" rows="3" maxlength="160" placeholder="补充一段简短说明…"></textarea><small>选填 · 最多 160 个字符</small></div><fieldset class="radio-field"><legend>发布范围</legend><label><input type="radio" name="visibility" value="团队可见" checked> 团队可见</label><label><input type="radio" name="visibility" value="仅管理员"> 仅管理员</label></fieldset><label class="check-label"><input class="checkbox" type="checkbox" name="confirm" id="lab-confirm">我已检查上述演示内容</label><small class="error" id="lab-form-error" role="status"></small><div class="lab-form-actions"><button type="reset" class="btn">清空重填</button><button type="submit" class="btn primary">${icon('check')}提交演示</button></div><div id="lab-form-result" aria-live="polite"></div></form>`,
    ) +
    panel(
      '更多输入形态',
      `<div class="lab-body"><div class="field-row"><div class="field"><label for="lab-quantity">数量</label><input type="number" id="lab-quantity" min="1" max="100" value="12"><small>支持键盘增减，范围 1–100</small></div><div class="field"><label for="lab-readonly">只读编号</label><input id="lab-readonly" value="CONTENT-2026-001" readonly><small>只读字段可选中复制</small></div></div><div class="field"><label for="lab-disabled">停用字段</label><input id="lab-disabled" disabled value="该字段当前不可编辑"></div><div class="field"><label>协作标签（可多选）</label><div class="tag-picker">${['内容运营', '产品设计', '研发中心', '客户服务'].map((t) => `<button type="button" class="tag-choice ${formTags.has(t) ? 'selected' : ''}" data-tag="${t}" aria-pressed="${formTags.has(t)}">${formTags.has(t) ? icon('check') : icon('plus')}${t}</button>`).join('')}</div><small id="tag-summary">已选 ${formTags.size} 项，至少保留一个标签</small></div><div class="field"><label for="lab-range">列表每页数量</label><div class="range-row"><input id="lab-range" type="range" min="10" max="50" step="10" value="20"><output id="lab-range-value">20 条</output></div></div><button type="button" class="toggle" role="switch" aria-checked="true" data-action="sample-toggle"><span>接收变更提醒<small>仅演示控件状态，不订阅消息</small></span><span class="toggle-track"></span></button></div>`,
    )
  );
}
function dataShowcase() {
  const { icon, getUser, getUsers, person } = helpers();
  const u = getUser();
  return (
    panel(
      '成员详情卡',
      `<div class="lab-body"><div class="profile-showcase"><span class="avatar violet">${u.name.slice(-2)}</span><h3>${u.name}</h3><p>${u.email}</p><span class="pill role-admin">${u.role}</span></div><div class="mini-stats"><div><strong>24</strong><span>内容记录</span></div><div><strong>12</strong><span>本周操作</span></div><div><strong>98%</strong><span>资料完成度</span></div></div><div class="lab-form-actions"><button class="btn primary" data-detail="${u.id}">${icon('book')}查看完整详情</button><button class="btn" data-edit="${u.id}">${icon('edit')}编辑资料</button></div></div>`,
    ) +
    panel(
      '进度与资源',
      `<div class="lab-body"><div class="progress-row"><div><strong>资料完整度</strong><span>84%</span></div><progress max="100" value="84">84%</progress><small>还差 2 项内容，即可完成配置</small></div><div class="progress-row mint"><div><strong>团队任务</strong><span>18 / 24</span></div><progress max="24" value="18">75%</progress><small>示例进度，仅用于展示组件</small></div><div class="progress-row peach"><div><strong>资源容量</strong><span>7.2 GB / 10 GB</span></div><progress max="100" value="72">72%</progress></div><details class="disclosure" open><summary>什么情况下显示进度？</summary><p>用于导入、生成、资料完整度等有明确完成目标的工作。无法测量进度时，应显示不确定的加载状态。</p></details><details class="disclosure"><summary>查看关联信息</summary><p>支持多层详情信息的按需展开，避免让表格横向堆积过多字段。</p></details></div>`,
    ) +
    panel(
      '表格密度',
      `<div class="lab-body"><div class="segmented density-control"><button data-density="comfortable" class="active">舒适</button><button data-density="compact">紧凑</button></div><div class="table-scroll"><table id="density-table"><thead><tr><th>成员</th><th>角色</th><th>状态</th></tr></thead><tbody>${getUsers(
        3,
      )
        .map(
          (u) =>
            `<tr><td>${person(u)}</td><td>${u.role}</td><td><span class="pill dot status-normal">正常</span></td></tr>`,
        )
        .join('')}</tbody></table></div></div>`,
      'lab-span-2',
    )
  );
}
function feedback() {
  const { icon } = helpers();
  return (
    panel(
      '边界状态切换',
      `<div class="lab-body"><div class="state-control">${[
        ['ready', '正常'],
        ['loading', '加载中'],
        ['empty', '空数据'],
        ['error', '请求失败'],
        ['forbidden', '无权限'],
      ]
        .map(
          ([id, label]) =>
            `<button class="chip ${surface === id ? 'active' : ''}" data-surface="${id}">${label}</button>`,
        )
        .join(
          '',
        )}</div><div id="state-surface" class="state-surface" aria-live="polite">${surfaceContent()}</div></div>`,
      'lab-span-2',
    ) +
    panel(
      '行内提示',
      `<div class="lab-body alert-stack">${[
        ['info', 'circle', '信息提示', '演示数据只保存在当前浏览器。'],
        ['success', 'check', '操作成功', '表单已通过验证，可以继续下一步。'],
        ['warning', 'circle', '需要留意', '更改角色前，请检查关联的权限范围。'],
        ['error', 'close', '请求失败', '未保存的内容仍然保留，你可以重试。'],
      ]
        .map(
          ([type, i, title, desc]) =>
            `<div class="alert alert-${type}">${icon(i)}<div><strong>${title}</strong><p>${desc}</p></div><button class="icon-button" data-dismiss-alert aria-label="关闭${title}">${icon('close')}</button></div>`,
        )
        .join('')}</div>`,
    ) +
    panel(
      '轻提示与确认',
      `<div class="lab-body"><p class="lab-copy">每个反馈都对应一个清楚的结果，危险操作保留明确的二次确认。</p><div class="button-cluster">${labButton('成功提示', 'toast-success')}${labButton('错误提示', 'toast-error')}${labButton('普通提示', 'toast-info')}${labButton('查看操作确认', 'confirm')}</div><div class="notice" style="margin-top:24px">${icon('circle')}这组示例不会发送邮件、删除真实数据或修改实际权限。</div></div>`,
    )
  );
}
function surfaceContent() {
  const { icon } = helpers();
  if (surface === 'loading')
    return `<div class="skeleton-list" aria-label="正在加载演示数据">${[1, 2, 3].map(() => `<div><span class="skeleton skeleton-avatar"></span><span class="skeleton skeleton-line"></span><span class="skeleton skeleton-tag"></span></div>`).join('')}<p>正在加载… ${labButton('取消加载', 'cancel-load')}</p></div>`;
  if (surface === 'ready')
    return `<div class="success-surface">${icon('check')}<h3>数据已准备就绪</h3><p>共有 24 条演示记录可供查看</p><button class="btn primary" data-lab="go-users">进入用户列表 ${icon('arrow')}</button></div>`;
  let info = {
    empty: ['layers', '这里还没有记录', '修改筛选条件，或从一条新记录开始。', '清除筛选并重试'],
    error: [
      'activity',
      '暂时无法加载数据',
      '网络请求失败示例。已有输入保留，不必重新开始。',
      '重新加载',
    ],
    forbidden: [
      'shield',
      '当前角色无法查看此内容',
      '这是无权限状态的视觉演示，真实访问控制由 Django 服务端执行。',
      '返回可访问页面',
    ],
  }[surface];
  return `<div class="boundary-state ${surface}">${icon(info[0])}<h3>${info[1]}</h3><p>${info[2]}</p>${labButton(info[3], surface === 'forbidden' ? 'go-users' : 'retry', true)}</div>`;
}
function workflow() {
  return (
    panel(
      '多步骤任务',
      `<div class="lab-body"><div class="stepper">${['基本信息', '执行选项', '确认内容'].map((n, i) => `<div class="${i + 1 === step ? 'active' : i + 1 < step ? 'complete' : ''}"><span>${i + 1 < step ? '✓' : i + 1}</span><strong>${n}</strong></div>`).join('')}</div><form id="wizard-form" novalidate>${step === 1 ? `<div class="field"><label for="wizard-name">演示任务名称</label><input id="wizard-name" name="name" value="${api.esc(wizard.name)}" maxlength="40"><small id="wizard-error">名称至少 4 个字符</small></div><div class="field"><label for="wizard-target">负责团队</label><select id="wizard-target" name="target">${['内容运营', '产品设计', '研发中心'].map((n) => `<option ${n === wizard.target ? 'selected' : ''}>${n}</option>`).join('')}</select></div>` : step === 2 ? `<div class="option-card"><h3>执行方式</h3><p>当前演示为一次性模拟任务，不会建立真实计划或后台作业。</p></div><label class="check-label"><input class="checkbox" id="wizard-notify" type="checkbox" ${wizard.notify ? 'checked' : ''}>完成后展示一条本地通知</label>` : `<dl class="detail-list"><div><dt>任务名称</dt><dd>${api.esc(wizard.name)}</dd></div><div><dt>负责团队</dt><dd>${wizard.target}</dd></div><div><dt>执行方式</dt><dd>立即模拟 · 不连接服务器</dd></div><div><dt>完成通知</dt><dd>${wizard.notify ? '开启' : '关闭'}</dd></div></dl>`}<div class="lab-form-actions">${step > 1 ? labButton('上一步', 'wizard-back') : ''}<button class="btn primary" type="submit">${step === 3 ? '运行演示任务' : '下一步'} ${api.icon('arrow')}</button></div><div id="wizard-result" aria-live="polite"></div></form></div>`,
    ) +
    panel(
      '批量操作规则',
      `<div class="lab-body"><div class="option-card"><h3>选择 → 检查 → 执行</h3><p>用户列表支持跨页选择，清楚标识选中数量；停用前展示确认；操作后保留本地日志。</p></div><ul class="checklist"><li>${api.icon('check')}当前页全选与单行选择</li><li>${api.icon('check')}筛选结果与空列表</li><li>${api.icon('check')}批量动作确认与结果提示</li><li>${api.icon('check')}详情入口和操作记录追踪</li></ul><div class="button-cluster">${labButton('体验用户批量操作', 'go-users', true)}${labButton('查看操作日志', 'go-audit')}</div></div>`,
    )
  );
}
function tokens() {
  return (
    panel(
      '语义颜色',
      `<div class="lab-body"><div class="swatch-grid">${[
        ['--accent', '主要操作'],
        ['--mint', '成功 / 正常'],
        ['--blue', '信息提示'],
        ['--peach', '警告 / 注意'],
        ['--danger', '危险 / 错误'],
        ['--muted', '次要信息'],
      ]
        .map(
          ([v, l]) =>
            `<div><i style="background:var(${v})"></i><strong>${l}</strong><small>${v}</small></div>`,
        )
        .join('')}</div></div>`,
    ) +
    panel(
      '字体与层级',
      `<div class="lab-body type-scale"><div><strong style="font-size:28px">页面标题</strong><span>28 / Semibold</span></div><div><strong style="font-size:20px">区域标题</strong><span>20 / Semibold</span></div><div><strong style="font-size:16px">模块标题</strong><span>16 / Medium</span></div><div><span style="font-size:14px">正文与表单内容</span><span>14 / Regular</span></div><div><span style="font-size:12px">说明、元信息与辅助标签</span><span>12 / Regular</span></div></div>`,
    ) +
    panel(
      '按钮完整状态',
      `<div class="lab-body"><div class="button-cluster">${api.button('主要操作', 'sample-success', 'primary', 'plus')}${api.button('次要操作', 'sample-toast', '', 'edit')}${api.button('轻量操作', 'sample-toast', 'subtle')}<button class="btn danger" data-lab="confirm">危险操作</button><button class="btn" disabled>不可用</button><button class="btn primary" disabled><span class="spinner"></span>处理中</button></div><p class="lab-copy" style="margin-top:20px">悬停、按压、键盘焦点和停用状态使用同一组设计变量。深浅主题会同时切换组件语义色。</p></div>`,
      'lab-span-2',
    )
  );
}
export function renderAudit() {
  const { icon, button } = helpers();
  let rows = audit.filter((a) => auditFilter === '全部结果' || a.status === auditFilter);
  return `<div class="notice">${icon('history')}当前为本地操作轨迹，含初始示例。真实审计日志必须由 Django 在服务端可靠记录。</div><section class="panel"><div class="user-toolbar"><div><h2>最近操作</h2><p class="lab-copy">本次演示中的新增、编辑、批量操作会追加到这里</p></div><span class="spacer"></span><select id="audit-filter" aria-label="按操作结果筛选">${['全部结果', '成功', '已拦截', '失败'].map((s) => `<option ${s === auditFilter ? 'selected' : ''}>${s}</option>`).join('')}</select></div><div class="table-scroll"><table class="audit-table"><thead><tr><th>操作</th><th>关联资源</th><th>操作者</th><th>结果</th><th>发生时间</th><th>详情</th></tr></thead><tbody>${rows.map((a) => `<tr><td><strong>${a.type}</strong><small class="audit-id">${a.id}</small></td><td>${api.esc(a.resource)}</td><td>${a.actor}</td><td><span class="pill ${a.status === '成功' ? 'status-normal' : a.status === '失败' ? 'status-error' : 'status-pending'}">${a.status}</span></td><td class="muted">${a.time}</td><td><button class="icon-button" data-audit-id="${a.id}" aria-label="查看 ${a.id}">${icon('chevron')}</button></td></tr>`).join('')}</tbody></table></div><div class="table-footer"><span>共 ${rows.length} 条记录 · 最多保留最近 60 条本地操作</span><span>全部为演示数据</span></div></section>`;
}
function detailDrawer(id) {
  const { getUser, esc, icon, openOverlay, person } = helpers();
  let u = getUser(id);
  if (!u) return;
  openOverlay(
    `<section class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title"><div class="drawer-header"><div><h2 id="drawer-title">成员详情</h2><p>演示资料 · 不连接真实账户</p></div><button class="icon-button" data-action="close" aria-label="关闭详情">${icon('close')}</button></div><div class="drawer-content"><div class="detail-profile">${person(u)}<span class="pill ${u.status === '正常' ? 'status-normal' : ''}">${u.status}</span></div><dl class="detail-list"><div><dt>成员编号</dt><dd>NOVA-${String(u.id).padStart(4, '0')}</dd></div><div><dt>所属团队</dt><dd>${u.team}</dd></div><div><dt>角色</dt><dd>${u.role}</dd></div><div><dt>加入时间</dt><dd>${u.joined}</dd></div><div><dt>电子邮箱</dt><dd>${esc(u.email)}</dd></div></dl><h3 style="margin-top:28px">最近活动 · 示例</h3><div class="timeline"><div><i></i><strong>资料已更新</strong><p>完善团队信息</p><small>2026-10-01 09:42</small></div><div><i></i><strong>角色已分配</strong><p>${u.role} · ${u.team}</p><small>${u.joined}</small></div><div><i></i><strong>加入工作空间</strong><p>演示账户创建成功</p><small>${u.joined}</small></div></div></div><div class="drawer-footer"><button class="btn" data-action="close">关闭</button><button class="btn primary" data-edit="${u.id}">${icon('edit')}编辑资料</button></div></section>`,
  );
}
function auditDrawer(id) {
  let a = audit.find((a) => a.id === id);
  if (!a) return;
  api.openOverlay(
    `<section class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title"><div class="drawer-header"><div><h2 id="drawer-title">操作详情</h2></div><button class="icon-button" data-action="close" aria-label="关闭操作详情">${api.icon('close')}</button></div><div class="drawer-content"><span class="pill ${a.status === '成功' ? 'status-normal' : 'status-pending'}">${a.status}</span><dl class="detail-list"><div><dt>事件编号</dt><dd>${a.id}</dd></div><div><dt>操作类型</dt><dd>${a.type}</dd></div><div><dt>关联资源</dt><dd>${api.esc(a.resource)}</dd></div><div><dt>操作者</dt><dd>${a.actor}</dd></div><div><dt>记录时间</dt><dd>${a.time}</dd></div></dl><h3 style="margin-top:25px">事件说明</h3><p class="lab-copy">${api.esc(a.detail)}</p><div class="notice" style="margin-top:25px">${api.icon('circle')}这是浏览器端演示记录，不能作为真实安全审计证据。</div></div><div class="drawer-footer"><button class="btn primary" data-action="close">完成</button></div></section>`,
  );
}
function onClick(e) {
  let t = e.target.closest('[data-lab-tab]');
  if (t) {
    tab = t.dataset.labTab;
    api.renderView();
    return;
  }
  let tag = e.target.closest('[data-tag]');
  if (tag) {
    if (formTags.has(tag.dataset.tag)) {
      if (formTags.size === 1) {
        api.toast('至少保留一个协作标签');
        return;
      }
      formTags.delete(tag.dataset.tag);
    } else formTags.add(tag.dataset.tag);
    tag.classList.toggle('selected', formTags.has(tag.dataset.tag));
    tag.setAttribute('aria-pressed', formTags.has(tag.dataset.tag));
    tag.innerHTML = api.icon(formTags.has(tag.dataset.tag) ? 'check' : 'plus') + tag.dataset.tag;
    document.querySelector('#tag-summary').textContent =
      `已选 ${formTags.size} 项，至少保留一个标签`;
    return;
  }
  let s = e.target.closest('[data-surface]');
  if (s) {
    surface = s.dataset.surface;
    api.renderView();
    return;
  }
  let a = e.target.closest('[data-dismiss-alert]');
  if (a) {
    a.closest('.alert').remove();
    return;
  }
  let d = e.target.closest('[data-detail]');
  if (d) {
    detailDrawer(Number(d.dataset.detail));
    return;
  }
  let au = e.target.closest('[data-audit-id]');
  if (au) {
    auditDrawer(au.dataset.auditId);
    return;
  }
  let density = e.target.closest('[data-density]');
  if (density) {
    document
      .querySelector('#density-table')
      .classList.toggle('compact', density.dataset.density === 'compact');
    document
      .querySelectorAll('[data-density]')
      .forEach((b) => b.classList.toggle('active', b === density));
    return;
  }
  let l = e.target.closest('[data-lab]');
  if (!l) return;
  let action = l.dataset.lab;
  if (action === 'go-users') return api.navigate('users');
  if (action === 'go-audit') return api.navigate('audit');
  if (action === 'cancel-load') {
    surface = 'empty';
    api.renderView();
    return;
  }
  if (action === 'retry') {
    surface = 'loading';
    api.renderView();
    setTimeout(() => {
      surface = 'ready';
      if (api.getView() === 'components' && tab === 'feedback') api.renderView();
    }, 900);
    return;
  }
  if (action === 'wizard-back') {
    step = Math.max(1, step - 1);
    api.renderView();
    return;
  }
  if (action.startsWith('toast-'))
    return api.toast(
      {
        success: '演示操作已成功完成',
        error: '保存失败示例，输入内容已保留',
        info: '这是一条普通的信息提示',
      }[action.slice(6)],
      action.slice(6),
    );
  if (action === 'confirm')
    return api.confirmDialog(
      '确认执行此演示操作？',
      '这是操作确认示例。只显示本地反馈，不会删除数据或改变实际权限。',
      'sample-confirm',
      '确认执行',
    );
}
function onChange(e) {
  if (e.target.id === 'audit-filter') {
    auditFilter = e.target.value;
    api.renderView();
  }
  if (e.target.id === 'lab-range')
    document.querySelector('#lab-range-value').textContent = e.target.value + ' 条';
}
function onSubmit(e) {
  if (e.target.id === 'lab-content-form') {
    e.preventDefault();
    const f = new FormData(e.target),
      title = f.get('title').trim();
    document.querySelector('#lab-title-error').className = title.length < 4 ? 'error' : '';
    document.querySelector('#lab-title-error').textContent =
      title.length < 4 ? '标题至少需要 4 个字符' : '至少 4 个字符，最多 40 个字符';
    document.querySelector('#lab-title').setAttribute('aria-invalid', title.length < 4);
    document.querySelector('#lab-form-error').textContent = !f.get('confirm')
      ? '请先确认已检查演示内容'
      : '';
    if (title.length < 4 || !f.get('confirm')) return;
    document.querySelector('#lab-form-result').innerHTML =
      `<div class="alert alert-success">${api.icon('check')}<div><strong>演示表单提交成功</strong><p>${api.esc(title)} · ${f.get('category')} · ${f.get('visibility')}</p></div></div>`;
    api.markClean?.();
    addAuditEvent('提交演示表单', title);
    api.toast('演示内容已通过校验，没有上传到服务器');
  }
  if (e.target.id === 'wizard-form') {
    e.preventDefault();
    if (step === 1) {
      let name = document.querySelector('#wizard-name').value.trim();
      if (name.length < 4) {
        document.querySelector('#wizard-error').textContent = '任务名称至少 4 个字符';
        document.querySelector('#wizard-error').className = 'error';
        return;
      }
      wizard.name = name;
      wizard.target = document.querySelector('#wizard-target').value;
    }
    if (step === 2) wizard.notify = document.querySelector('#wizard-notify').checked;
    if (step < 3) {
      step++;
      api.renderView();
      return;
    }
    let b = e.target.querySelector('button[type=submit]');
    b.disabled = true;
    b.innerHTML = '<span class="spinner"></span>正在运行';
    setTimeout(() => {
      api.markClean?.();
      addAuditEvent('模拟任务', wizard.name, '一次性本地演示已完成，未创建后台作业。');
      let result = document.querySelector('#wizard-result');
      if (result)
        result.innerHTML = `<div class="alert alert-success">${api.icon('check')}<div><strong>演示任务已完成</strong><p>结果已写入本地操作日志，没有建立后台计划。</p></div></div>`;
      if (b.isConnected) {
        b.disabled = false;
        b.innerHTML = '再次运行演示';
      }
      if (wizard.notify) api.toast('演示任务执行完成');
    }, 700);
  }
}
