# 品牌与 CSS tokens

Nova 的品牌层只负责外观。原生 `AdminSite`、权限、表单、CSRF、URL 和已保存的外观选择仍由现有逻辑处理。默认不增加页脚、图片或永久说明文字；未配置品牌时，登录页保留宽屏留白和手机无卡片边框的布局。

## 四个颜色变量换品牌

主题依次加载 `nova_admin/theme.css`、`nova_admin/tokens.css`。项目样式放在它们之后；不要修改安装包里的 CSS。下面四个变量同时覆盖主按钮、保存按钮、链接和焦点色，自动模式也会使用对应的明暗值：

```css
/* static/project/brand.css */
body.nova-admin {
  --nova-brand-light: #1d4ed8;
  --nova-brand-light-hover: #1e40af;
  --nova-brand-dark: #93c5fd;
  --nova-brand-dark-hover: #bfdbfe;
}
```

变量在同一个 `body.nova-admin` 上定义即可，无需复制三组模式选择器。原生 Django 变量（如 `--button-bg`、`--link-fg`、`--accent`）由 `tokens.css` 映射。通用包的四个品牌变量默认不赋值，映射中的每个角色都有原来的精确颜色作为回退，所以未配置时主色、链接色与绿色保存按钮保持原样。

四色接口不自动推算中性色、危险操作色、选中背景和图表色。品牌规范要求这些区域也变化时，在项目 CSS 里覆盖对应的 Django 角色变量，并分别检查浅色、深色和自动模式。通用包的对象工具按钮仍使用原有中性色。Demo 的 `enterprise.css` 使用同样四个变量，并保留企业蓝选中背景和对象工具映射；不要同时复制旧版的硬编码覆盖层。

将文件加到项目已有的 `templates/admin/base_site.html` 中：

```django
{% extends "admin/base_site.html" %}
{% load static nova_tags %}
{% block extrastyle %}
  {{ block.super }}
  {% if nova_admin_active %}
    <link rel="stylesheet" href="{% static 'project/brand.css' %}" {% nova_nonce %}>
  {% endif %}
{% endblock %}
```

如使用本仓库 Demo，把项目覆盖链接放在 `catalog/enterprise.css` 和可选的 `catalog/enterprise-compact.css` 之后。`TEMPLATES[0]["DIRS"]` 中的宿主模板优先；`nova_admin` 仍放在 `django.contrib.admin` 前面。保留原有 context processors，并加入 `nova_admin.context_processors.theme`。

## 三个几何变量

```css
body.nova-admin {
  --nova-density: .9; /* 1 为默认；原生表格/表单/控件的垂直密度 */
  --nova-spacing: .95; /* 1 为默认；控件横向留白与主内容/页头外边距 */
  --nova-radius: 10px; /* 默认 12px；面板及相关的小圆角随之变化 */
}
```

建议先在密度和留白 `.8`–`1.2` 范围内微调；值须是有效的无单位正数，圆角须是非负 CSS 长度。它们是项目开发者控制的 CSS，不接收用户输入。圆形状态标识、胶囊标签和开关保持其语义形状。手机及粗指针的 44px 控件触控下限、原生勾选框的 24px 下限不随密度缩小。登录输入框和提交按钮保持 48px 下限，手机登录页也不会因为密度预设变成带边框的卡片。

更细的覆写仍可使用 `--nova-cell-padding`、`--nova-form-row-padding`、`--nova-control-padding-block`、`--nova-control-padding-inline`、`--nova-control-min-height`、`--nova-action-padding`、`--nova-section-padding` 和 `--nova-row-line-height`。它们在 tokens 之后声明时优先，详见 [DENSITY_PRESETS.md](DENSITY_PRESETS.md)。Demo 紧凑预设保留原有 7px 表格垂直留白、32px 桌面控件等基线，同时接受密度与留白乘数。不要覆写内部的 `--nova-touch-min`。

圆角衍生值为 `--nova-control-radius`（12px 基线时为 7px）、`--nova-action-radius`（8px）、`--nova-small-radius`（6px）、`--nova-login-radius`（9px）；也可以分别覆盖。

## 声明式品牌设置

### 后台名称与自动 Logo

不提供图片 Logo 时，页头与登录页装饰会从后台名称自动取标识：英文取大写首字母，中文保留首个汉字，数字开头取首个数字，跳过空白和标点；全部为符号的名称显示 `?`。例如 `Atlas Admin` → `A`、`星河管理后台` → `星`，不需要为每个项目制作图片，也不会固定显示 `N`。

最小配置只有名称：

```python
NOVA_ADMIN_BRANDING = {"name": "星河管理后台"}
```

`name` 统一当前 Nova 外观的页头名称、浏览器站点标题和自动 Logo。配置了有效 `logo` 图片时，页头优先显示图片；图片路径校验不通过时回退到自动标识。`favicon` 和 `login_background` 仍是独立的可选图片设置，不自动生成。

未设置 `name` 时，直接使用**当前 AdminSite** 的 `site_header`；它为空时再回退到 `site_title` 或 Django 的默认管理名称。不会把其他 AdminSite 的名称带过来，也不会修改已有 site 实例。要让恢复原生外观后也使用同一名称，优先使用 Django 原有配置：

```python
from django.contrib import admin

admin.site.site_header = "星河管理后台"
admin.site.site_title = "星河管理后台"
# 不配置 logo 即自动生成“星”。已有自定义 AdminSite 在自己的实例上设置。
```

名称是纯文本；即使传入 `mark_safe()` 字符串，也不会作为 HTML 解释。字母标识在页头对辅助技术隐藏，相邻名称链接提供完整名称，避免重复朗读。原生模式、关闭主题或省略主题 context processor 时，仍恢复项目自己的 Django 品牌内容。

本地静态预览可在“设置 → 后台与工作空间 → 后台名称”中保存名称；侧栏和登录页共用此浏览器偏好。已打开的登录页会随同源其他窗口的更改更新名称，不清空正在填写的账号、密码或验证码。此设置只影响预览，不写入真实 Django 配置。

### 图片与其他品牌资源

```python
NOVA_ADMIN_BRANDING = {
    "name": "Example 管理后台",  # 可选；省略时沿用当前 AdminSite.site_header
    "logo": "project/brand.svg",
    "logo_alt": "",  # 相邻站点标题已表达品牌；必要时再填写不同的信息
    "favicon": "project/favicon.svg",
    "login_background": "project/login.webp",
    "footer": "Example 内部管理平台",
}
```

所有字段可省略。`site_header`、`site_title` 仍可设置在已有 `AdminSite` 上；`name` 只是 Nova 展示层的统一覆盖，图片 Logo 不替换名称文字。图片应放在宿主自己控制的 static 目录，并经过正常的 `collectstatic` 流程：

- `logo`：页头图片，最大 160×36px，保留纵横比，与原生站点标题链接一起显示
- `logo_alt`：纯文本替代文字，默认空值避免与相邻标题重复朗读
- `favicon`：图标链接，支持 ICO 以及下面的常规图片格式
- `login_background`：桌面登录页左侧装饰区的背景图片，裁切填满原有装饰区；手机和强制颜色模式隐藏，避免影响表单对比度及原有布局
- `footer`：后台及登录页页脚纯文本；默认没有页脚内容。即使传入 `mark_safe()` 字符串也会转义

图片允许 SVG、PNG、JPEG/JPG、GIF、WebP、AVIF；配置只能是由英文字母、数字、`_`、`-`、`.`、`/` 组成的相对 static 路径。不接受完整 URL、绝对路径、`..`/`.` 路径段、重复斜线、反斜线、编码路径、查询参数、片段、HTML 或任意 CSS。SVG 必须是宿主审核过的静态文件，不能把用户上传的文件当作品牌资源。

Django 的 static storage 负责生成最终 URL，支持普通本地 static 与 manifest 哈希文件名。最终地址也必须是同源绝对路径；CDN/远程 `STATIC_URL`、带签名查询的 storage URL、非法路径和找不到的 manifest 项会隐藏对应的可选图片，其他字段继续生效。普通 static storage 不验证文件是否实际存在，发布时应检查静态资源请求没有 404。要使用经审核的远程资源或富文本，宿主应明确编写模板并负责自己的域名许可、CSP 和转义；设置接口本身没有“允许任意 HTML”的开关。

品牌图片通过 `img`/`link` 加载，没有由设置生成的内联样式或脚本。已有 `nova_nonce` 同时用于新 tokens 样式链接，沿用 Django 6.x 的 CSP nonce；Django 5.2 无需引入 6.x 模板标签。部署自己的 CSP 时，需要允许实际 static 来源的 `style-src` 和 `img-src`。

## 可覆盖的模板和区块

只修改展示时优先用上面的设置和 CSS，避免复制完整 Django 模板。

| 扩展点 | 所属模板 | 用途 |
| --- | --- | --- |
| `nova_styles` | `admin/base.html` | Nova 两个 CSS 链接；增加项目样式通常用标准 `extrastyle` + `block.super` |
| `nova_favicon` | `admin/base.html` | 图标链接 |
| `nova_footer` | `admin/base.html` | 品牌页脚，默认包含 `nova_admin/brand_footer.html` |
| `nova_branding` | `admin/base_site.html` | 页头名称与图片／自动首字标识；原生模式恢复上游内容 |
| `nova_login_content` | `admin/login.html` | 登录内容包装；替换时必须保留原生认证表单、错误、CSRF 与 next 字段 |
| `nova_login_art` | `nova_admin/login_brand.html` | 左侧装饰区域；通过覆盖/继承这个被 include 的模板修改 |

`nova_admin/brand_header.html`、`nova_admin/brand_footer.html`、`nova_admin/login_brand.html` 都可以在宿主 `TEMPLATES[0]["DIRS"]` 中同名覆盖。注意：include 的模板有自己的块作用域，不能在 `admin/login.html` 的子模板中直接覆盖 `nova_login_art`。可在项目的同名 `nova_admin/login_brand.html` 中 `{% extends "nova_admin/login_brand.html" %}` 再覆盖该块。

上述 Nova 块的默认入口均位于 `nova_admin_active` 条件内。宿主如果覆盖 Django 的标准 `branding`、`extrahead`、`footer` 等块，也应保留自己的 `nova_admin_active` 边界。普通变量仍默认转义；只有经过审核、手写的项目模板才能有意加入富文本结构。不要对设置、请求数据或上传内容使用 `safe`。

## 外观选择与对比度

品牌不会改动已保存的 `dark`、`light`、`auto` 或 `native` 选择。`NOVA_ADMIN_DEFAULT_MODE` 只影响没有有效偏好的会话。选择 native、关闭 `NOVA_ADMIN_ENABLED`、移除主题应用或省略 context processor 后，不加载 tokens 或品牌资源，也不输出品牌页脚，恢复原生 Django 内容。

每次换色应检查正文/次要文字/链接在所有实际表面上的对比度，以及按钮文字、悬停态、焦点、错误、禁用态和选中态。正文和按钮通常至少需要 4.5:1；自定义图像不能削弱文字或焦点可见性。示例企业蓝的白字主按钮为 6.70:1、白字悬停按钮为 8.72:1；通用深色按钮的 `#0b1020` 文字搭配 `#93c5fd` 为 10.50:1。这些值只验证所列配色，不代表任意自定义主题自动满足可访问性。

## 手写 CSS 与体积

运行时直接发布手写 CSS，没有 Sass、Tailwind、CSS-in-JS、Node 或前端构建依赖。CSS token 变更只需项目正常的静态资源发布与缓存更新。当前仓库仍保留可读源文件，不提供没有源码映射的压缩副本。宿主确实需要 minify 时，应同时生成并发布对应 sourcemap，保留 `sourceMappingURL` 和原始源码，不允许把无 sourcemap 的压缩 CSS 当作唯一维护源。

以下为早期交付的历史体积基线；当前体积和预算见仓库 `ci/css-budget.json`。该历史基线中，通用包 CSS 的原始体积合计为 71,385 bytes；分别 gzip（mtime=0）后合计 14,941 bytes。组成：`theme.css` 58,854 / 11,232、`tokens.css` 3,263 / 793、`login.css` 7,382 / 2,160、`captcha.css` 1,886 / 756（原始 / gzip bytes）。前两项用于普通后台；login 与 CAPTCHA 只在相应页面按需加载。这是源码基线，不包含 Django 自带样式、项目企业蓝覆盖或图片，后续修改应重测并说明差异。

`tests/test_branding_tokens.py` 覆盖路径与 storage 输出验证、HTML/属性转义、缺失配置回退、native/关闭恢复、登录表单完整性、CSP 链接、自动深色映射和精确默认颜色回退。真实项目仍需浏览器检查长标题、图片比例、手机布局、对比度及所有模式的静态资源加载。
