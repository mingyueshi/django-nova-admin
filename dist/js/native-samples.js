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
const palettePages = ['index', 'changelist', 'login'];
const palettes = [
  ['default', '默认配色'],
  ['teal', '医疗青'],
  ['indigo', '专业靛'],
  ['violet', '文教紫'],
  ['terracotta', '零售陶'],
  ['graphite', '石墨黑'],
  ['midnight', '午夜蓝'],
  ['forest', '松林绿'],
  ['amber', '暖琥珀'],
  ['ocean', '深海青'],
  ['slate', '雾岩灰'],
  ['plum', '暮梅紫'],
  ['coffee', '摩卡棕'],
];
let palette = 'default',
  representativePage = 'index',
  representativeLook = 'light';
let look = 'light',
  density = 'comfortable',
  page = 'changeform',
  api;
function samplePage() {
  return palette === 'default' ? page : representativePage;
}
function sampleLook() {
  return palette === 'default' ? look : representativeLook;
}
function sampleMode() {
  if (palette !== 'default') return `palette-${palette}-${sampleLook()}`;
  return look === 'native' ? 'native' : density === 'compact' ? 'compact-' + look : look;
}
export function selectNativeComparison(currentView, currentRoute) {
  palette = 'default';
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
    if (e.target.id === 'native-palette') {
      if (palette === 'default' && e.target.value !== 'default') {
        representativePage = palettePages.includes(page) ? page : 'index';
        representativeLook = ['light', 'dark'].includes(look) ? look : 'light';
      }
      palette = e.target.value;
    } else if (e.target.id === 'native-page') {
      if (palette === 'default') page = e.target.value;
      else representativePage = e.target.value;
    } else if (e.target.id === 'native-look') {
      if (palette === 'default') look = e.target.value;
      else representativeLook = e.target.value;
    } else if (e.target.id === 'native-density') density = e.target.value;
    else return;
    const representative = palette !== 'default';
    for (const option of document.getElementById('native-page').options) {
      option.disabled = representative && !palettePages.includes(option.value);
    }
    document.getElementById('native-page').value = samplePage();
    for (const option of document.getElementById('native-look').options) {
      option.disabled = representative && !['light', 'dark'].includes(option.value);
    }
    document.getElementById('native-look').value = sampleLook();
    document.getElementById('native-density').disabled = look === 'native' || representative;
    document.getElementById('native-density').value = representative ? 'comfortable' : density;
    const url = `./native-admin/${sampleMode()}/${samplePage()}.html`;
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
    `<div class="compatibility-strip"><div>${api.icon('check')}<strong>真实集成验证</strong></div><span>Django 5.2.17 LTS</span><span>Django 6.0.8</span><span>Django 6.1.1</span><small>主题 0.6.0 · 历史兼容基线：Python 3.11–3.14，共7组精确组合</small></div><section class="panel native-sample-panel"><div class="native-sample-toolbar"><div><h2>Django 6.1.1 渲染样本</h2><p>Python 3.12.14 · 从真实 Admin 视图、模板与合成数据库生成</p></div><div class="native-sample-controls"><label>配色<select id="native-palette">${palettes.map(([id, label]) => `<option value="${id}" ${palette === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label>页面<select id="native-page">${nativePages.map(([id, label]) => `<option value="${id}" ${samplePage() === id ? 'selected' : ''} ${palette !== 'default' && !palettePages.includes(id) ? 'disabled' : ''}>${label}</option>`).join('')}</select></label><label>外观<select id="native-look"><option value="dark" ${sampleLook() === 'dark' ? 'selected' : ''}>深色</option><option value="light" ${sampleLook() === 'light' ? 'selected' : ''}>浅色</option><option value="auto" ${sampleLook() === 'auto' ? 'selected' : ''} ${palette !== 'default' ? 'disabled' : ''}>跟随系统</option><option value="native" ${sampleLook() === 'native' ? 'selected' : ''} ${palette !== 'default' ? 'disabled' : ''}>Django 原生</option></select></label><label>密度<select id="native-density" ${look === 'native' || palette !== 'default' ? 'disabled' : ''}><option value="comfortable" ${density === 'comfortable' || palette !== 'default' ? 'selected' : ''}>标准</option><option value="compact" ${density === 'compact' && palette === 'default' ? 'selected' : ''}>紧凑</option></select></label><a id="native-open" class="btn" href="./native-admin/${sampleMode()}/${samplePage()}.html" target="_blank" rel="noopener">独立查看 ↗</a></div></div><div class="native-readonly-note">${api.icon('shield')}项目默认保留 56 个页面样本和 1 个目录页；包含医疗青、专业靛、文教紫、零售陶、石墨黑、午夜蓝、松林绿、暖琥珀、深海青、雾岩灰、暮梅紫和摩卡棕，另含 72 个代表页，仅工作台、商品列表、登录页的浅色／深色与标准密度。切回项目默认会恢复之前的页面、外观和密度。只读快照：已移除表单提交、认证、远程请求和脚本。自动完成接口、Inline 提交与安全校验已做服务端集成测试；此快照不执行前端增强脚本。</div><iframe id="native-preview" class="native-preview" title="真实 Django Admin 模板只读样本" src="./native-admin/${sampleMode()}/${samplePage()}.html" sandbox="allow-same-origin"></iframe></section><div class="integration-boundaries"><section><h3>保留原生能力</h3><p>原有 AdminSite、ModelAdmin 注册、权限、CSRF、模型表单、列表筛选、批量动作与操作日志继续由 Django 处理。主题只增强外观与导航。</p><p><a class="text-link" href="./navigation-lab/zh-hans-dark.html" target="_blank" rel="noopener">收藏、常用模型与移动导航样例 ↗</a></p></section><section><h3>项目定制与恢复</h3><p><a class="text-link" href="./extensions.html" target="_blank" rel="noopener">设计令牌、品牌配置与扩展指南 ↗</a></p><p>默认浅色、企业蓝、中文措辞和紧凑覆盖均来自 Demo 项目配置，通用主题保留原始默认。</p><p>真实主题支持会话级原生模式；也可关闭或移除主题应用，恢复 Django 自带外观；项目词典和标签定制可单独移除。这里的“Django 原生”快照用于对照。</p></section><section><h3>仍需项目级验收</h3><p>7组兼容组合属于历史基线。本轮新增配色的验证范围见配色接入与验收说明；历史配色曾在 Python 3.12.14 配合 Django 6.1.1 实测，不代表重测全部历史组合、其它平台或第三方 Admin 插件。界面演示不连接生产数据库。</p></section></div>`
  );
}
