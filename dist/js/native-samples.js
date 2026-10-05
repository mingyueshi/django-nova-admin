const nativePages = [
  ['index', '工作台'],
  ['changelist', '商品图片列表'],
  ['members', '成员头像列表'],
  ['news', '新闻封面列表'],
  ['changeform', '关联字段与 Inline'],
  ['validation-error', '原生校验错误'],
  ['delete-confirm', '原生删除确认'],
  ['login', '登录页面'],
];
let look = 'light',
  density = 'comfortable',
  page = 'changeform',
  api;
function sampleMode() {
  return look === 'native' ? 'native' : density === 'compact' ? 'compact-' + look : look;
}
export function selectNativeComparison(currentView, currentRoute) {
  look = 'native';
  page =
    currentView === 'overview'
      ? 'index'
      : currentView === 'catalog' && currentRoute.startsWith('catalog/edit/')
        ? 'changeform'
        : ['catalog', 'users'].includes(currentView)
          ? 'changelist'
          : 'index';
}
export function initNativeSamples(a) {
  api = a;
  document.addEventListener('change', (e) => {
    if (e.target.id === 'native-page') page = e.target.value;
    else if (e.target.id === 'native-look') look = e.target.value;
    else if (e.target.id === 'native-density') density = e.target.value;
    else return;
    document.getElementById('native-density').disabled = look === 'native';
    const url = `./native-admin/${sampleMode()}/${page}.html`;
    document.getElementById('native-preview').src = url;
    document.getElementById('native-open').href = url;
  });
}
export function renderNativeSamples() {
  return (
    api.intro(
      '原生 Django，真正的模板',
      '对照原生结构，验证主题覆盖的边界。',
      '<a class="btn primary" href="./login.html">体验登录页 ↗</a>',
    ) +
    `<div class="compatibility-strip"><div>${api.icon('check')}<strong>真实集成验证</strong></div><span>Django 5.2.17 LTS</span><span>Django 6.0.8</span><span>Django 6.1.1</span><small>主题 0.6.0 · Python 3.11–3.14 · 已测7组精确组合</small></div><section class="panel native-sample-panel"><div class="native-sample-toolbar"><div><h2>Django 6.1.1 渲染样本</h2><p>从真实 Admin 视图、模板与合成数据库生成</p></div><div class="native-sample-controls"><label>页面<select id="native-page">${nativePages.map(([id, label]) => `<option value="${id}" ${page === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label>外观<select id="native-look"><option value="dark" ${look === 'dark' ? 'selected' : ''}>企业蓝 · 深色</option><option value="light" ${look === 'light' ? 'selected' : ''}>企业蓝 · 浅色</option><option value="auto" ${look === 'auto' ? 'selected' : ''}>跟随系统</option><option value="native" ${look === 'native' ? 'selected' : ''}>Django 原生</option></select></label><label>密度<select id="native-density" ${look === 'native' ? 'disabled' : ''}><option value="comfortable" ${density === 'comfortable' ? 'selected' : ''}>标准</option><option value="compact" ${density === 'compact' ? 'selected' : ''}>紧凑</option></select></label><a id="native-open" class="btn" href="./native-admin/${sampleMode()}/${page}.html" target="_blank" rel="noopener">独立查看 ↗</a></div></div><div class="native-readonly-note">${api.icon('shield')}项目预设含中文词典、真实全角冒号、企业蓝和密度覆盖。只读快照：已移除表单提交、认证、远程请求和脚本。自动完成接口、Inline 提交与安全校验已做服务端集成测试；此快照不执行前端增强脚本。</div><iframe id="native-preview" class="native-preview" title="真实 Django Admin 模板只读样本" src="./native-admin/${sampleMode()}/${page}.html" sandbox="allow-same-origin"></iframe></section><div class="integration-boundaries"><section><h3>保留原生能力</h3><p>原有 AdminSite、ModelAdmin 注册、权限、CSRF、模型表单、列表筛选、批量动作与操作日志继续由 Django 处理。主题只增强外观与导航。</p><p><a class="text-link" href="./navigation-lab/zh-hans-dark.html" target="_blank" rel="noopener">收藏、常用模型与移动导航样例 ↗</a></p></section><section><h3>项目定制与恢复</h3><p><a class="text-link" href="./extensions.html" target="_blank" rel="noopener">设计令牌、品牌配置与扩展指南 ↗</a></p><p>默认浅色、企业蓝、中文措辞和紧凑覆盖均来自 Demo 项目配置，通用主题保留原始默认。</p><p>真实主题支持会话级原生模式；也可关闭或移除主题应用，恢复 Django 自带外观；项目词典和标签定制可单独移除。这里的“Django 原生”快照用于对照。</p></section><section><h3>仍需项目级验收</h3><p>本轮仅验证集成说明中的7组Python/Django组合，不代表全部交叉组合、其它平台或第三方Admin插件。界面演示不连接生产数据库。</p></section></div>`
  );
}
