# Nova Django Admin Theme 0.6.0

本轮增加可选品牌/令牌/导航扩展、自检与上游漂移工具；核心仍无额外依赖。新的 Axes 登录桥接只在项目显式选择 security extra 与对应登录表单后启用。入口见 [BRANDING.md](BRANDING.md)、[NAVIGATION_EXTENSIONS.md](NAVIGATION_EXTENSIONS.md)、[UPSTREAM_DRIFT.md](UPSTREAM_DRIFT.md)。维护范围与本轮实际验证分别见 [COMPATIBILITY.md](COMPATIBILITY.md) 和 [TEST_REPORT.md](TEST_REPORT.md)。

核心安装仍只依赖Django。启用验证码需显式安装extra、挂载接口并迁移其独立表，见 [CAPTCHA_INTEGRATION.md](CAPTCHA_INTEGRATION.md)。原生外观/主题关闭后，已启用的验证码继续要求验证；完全卸载主题时，也要先处理已配置的login_form/login_template及可选刷新URL。

# Nova · 原生 Django Admin 可逆主题

Nova 0.6.0 是可复用的 Django Admin 主题包，直接作用于项目现有的 `AdminSite` / `ModelAdmin`。支持深色、浅色、跟随系统和 Django 原生外观，包含可选的分组 → 应用 → 模型三级导航。**这是实际运行 Django 模板、权限、表单和数据库流程的主题，不是用 React 重做的管理后台。**

## 覆盖范围与边界

- 站点首页：原生应用/模型模块、权限可见性、最近操作，增加清晰的标题层次
- 模型列表：原生搜索、排序、筛选、批量操作、分页、选择框、添加入口；Demo 增加圆形头像 / 方形商品图 / 16:9 新闻封面三种真实 image list_display 示例
- 编辑表单：原生字段布局、fieldset、只读字段、帮助文本、校验错误、保存栏
- 关联字段：ForeignKey 自动完成、关联对象入口、M2M 双栏选择器
- 内联：原生 TabularInline 行、添加/删除、管理表单、行级错误
- 其他：登录、退出、面包屑、删除确认、消息、popup、原生模式恢复
- 可选侧栏：从 `available_apps` 直接生成应用 → 模型导航；配置分组后成为分组 → 应用 → 模型三级结构。只分组原生权限允许的应用，支持键盘折叠、原生搜索、当前模型状态

核心主题没有另建站点、复制注册表、查询业务数据、改写 ModelAdmin、修改认证/CSRF/权限/查询集或替换业务表单。`admin/base.html`、`admin/index.html` 和 `admin/login.html` 使用同名继承，保留适用的 `block.super`；列表、表单、关联、内联和删除模板继续使用对应版本的 Django 原模板。登录页单独覆盖呈现区，保留原生表单字段、错误、CSRF、next 与认证语义；未启用主题时恢复上游内容。导航自有模板只消费原生 `available_apps`。显式启用的可选 CAPTCHA 会在调用认证后端前增加服务端挑战校验，独立于外观开关。

自定义导航默认关闭，Demo 显式开启。它提供真实的分组/应用/模型层级，不凭空添加“报表”“系统设置”等无后端页面。复杂自定义 Admin 模板、第三方主题、额外 JS 组件需要目标项目验证；完整无障碍认证、全浏览器认证、生产安全审计不在本次结果内。

## 0.5.1 历史矩阵（2026-10-03；0.6.0 新增结果见 TEST_REPORT.md）

| Python | Django | 核心源码及 wheel（各轮） | 可选验证码源码及 wheel（各轮） |
|---|---|---:|---:|
| 3.11.17 | 5.2.17 | 269通过 + 1预期跳过 | 22 / 22 |
| 3.12.15 | 5.2.17 | 269通过 + 1预期跳过 | 22 / 22 |
| 3.12.15 | 6.0.8 | 269通过 + 1预期跳过 | 22 / 22 |
| 3.12.15 | 6.1.1 | 269通过 + 1预期跳过 | 22 / 22 |
| 3.13.16 | 6.1.1 | 269通过 + 1预期跳过 | 22 / 22 |
| 3.14.8 | 5.2.17 | 269通过 + 1预期跳过 | 22 / 22 |
| 3.14.8 | 6.1.1 | 269通过 + 1预期跳过 | 22 / 22 |

七组精确组合共28次独立运行，Django系统检查、迁移漂移检查和pip check均通过。核心的唯一跳过项是未安装captcha时的明确占位；可选套件没有跳过。wheel实际从各自site-packages导入，27个运行文件与源码逐字节一致。

这不是整个 Python × Django 笛卡尔积。测试平台仅为Linux x86-64标准GIL CPython；其它补丁、操作系统、CPU、free-threaded构建与第三方Admin插件不因此视为已验证。完整边界、官方维护日期和复现命令见 [COMPATIBILITY.md](COMPATIBILITY.md)，实际执行记录见 [TEST_REPORT.md](TEST_REPORT.md)。

最低安装声明仍为 `requires-python >=3.10`，Django区间仍为 `Django>=5.2.17,<6.2`；Python3.10已EOL，仅保留历史安装边界，当前维护目标从3.11开始。此前0.5.0在Python3.12.14的三分支结果保留为历史证据，不冒充当前安全补丁结果。

已检查 6.1 的真实模板变化：面包屑从 `div` 改为 `ol`、字段标签/错误布局变更、`object-tools` 移到 `titles-and-tools`、列表筛选器移入表单容器。CSS 匹配对应结构，未用旧版整页模板覆盖新版。主题资源支持可选 `csp_nonce` 上下文，但 CSP 策略本身仍由宿主项目负责。

## 运行 Demo

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r requirements-test.txt
python demo/manage.py migrate
python demo/manage.py seed_demo
python demo/manage.py createsuperuser
python demo/manage.py runserver 127.0.0.1:8000
```

访问 `http://127.0.0.1:8000/admin/`，使用你刚创建的管理员。没有默认账号、共享密码、免登录入口。本地研究包附带可重复运行的 `seed_demo`，预置合成分类、标签、商品、会员头像与新闻封面，不创建登录账号、不会覆盖已有样例的修改。也可跳过种子，自行先建立分类和标签，再创建商品；可测试分类自动完成、标签多选、规格内联、字段分组、只读更新时间、批量上架、分页与删除确认。

Demo 模型只是接入示例，不需要复制进你的业务项目。`0002` 增加可选分类 FK、标签 M2M；`0003` 增加默认为 False 的精选推荐 BooleanField。`0004` 新增可选商品图片 key、会员资料和新闻两个轻量示例模型。均为保留原商品的增量迁移；从上一版 Demo 升级需运行 `migrate`。会员资料不是认证账号，新闻示例不是 CMS 或发布服务。

`demo/config/settings.py` 只供本地演示：SQLite、DEBUG、本地示例密钥。不能直接用于生产。生产仍须自行配置真实密钥、HTTPS、ALLOWED_HOSTS、安全 Cookie、数据库备份、关闭 DEBUG 和静态资源部署。

## 接入已有项目

### 1. 安装本地包

```bash
python -m pip install /path/to/nova-admin/django-theme
```

也可安装本地构建的 wheel。该包没有发布到公共 PyPI，不能假设直接通过包名安装即可获得它。

### 2. 启用模板与上下文

```python
INSTALLED_APPS = [
    "nova_admin",  # 必须在 django.contrib.admin 之前
    "django.contrib.admin",
    # 保留其余现有应用
]
```

在现有 DjangoTemplates 的 `OPTIONS.context_processors` 中增加：

```python
"nova_admin.context_processors.theme"
```

保留项目已有的 request/auth/messages 上下文处理器及 Session、Authentication、CSRF、Message 中间件。没有主题上下文处理器时模板安全退回原生内容，不会报空配置错误。

```python
NOVA_ADMIN_ENABLED = True
NOVA_ADMIN_DEFAULT_MODE = "dark"  # dark / light / native
NOVA_ADMIN_NAVIGATION = True     # 默认 False；显式选择分组侧栏
```

### 可选三级导航配置

只对当前 `AdminSite` 已提供的权限过滤列表进行分组：

```python
NOVA_ADMIN_NAV_GROUPS = [
    {"label": "业务管理", "apps": ["catalog"]},
    {"label": "系统管理", "apps": ["auth"]},
]
```

`apps` 填 Django 的 `app_label`，不填模型名或自定义 URL。Demo 的显示路径为“业务管理 → 商品示例 → 商品 / 商品分类 / 商品标签”。应用名称仍来自 AppConfig，模型名称仍来自原生 Admin。

- 未配置或空列表：保持应用 → 模型两级导航
- 未知应用、无权限应用、没有可见模型的应用：不加入任何分组
- 空组、无可见成员的组、无效配置项：不渲染标题，不泄露其模型
- 同一应用出现多次：仅首次有效分组生效，不重复展示
- 可见但未配置分组的应用：自动出现在“其他应用”，避免导航丢失
- 分组不会产生查询、修改 available_apps、复制注册表或改变权限
- 搜索模型时自动展开匹配分组与应用；清空后恢复各层原展开状态
- native、全局关闭、popup 和站点侧栏关闭均不会渲染该分组导航

### 3. 可选外观切换端点

在原有 `admin.site.urls` 之前挂载，不创建第二个站点：

```python
from django.contrib import admin
from django.urls import include, path
from nova_admin.urls import for_admin

urlpatterns = [
    path("admin/_theme/", include(for_admin(admin.site))),
    path("admin/", admin.site.urls),
]
```

原有 `admin.py` 注册、`ModelAdmin`、站点属性保持原样。主题不要求导入 Demo。省略端点时仍能用配置设定外观，模板不会显示无效切换控件。

切换只接受 CSRF 保护的 POST，使用该 **同一个站点** 的 `admin_view` 检查登录和权限；偏好保存在 Django 会话内。`next` 仅允许该站点 URL 前缀下的本地规范路径，拒绝外链、协议相对 URL、反斜线和路径穿越。不能把 `HTTP Referer` 当作可信返回地址。

### 4. 多 AdminSite

如果项目原来就有多个站点，可以分别挂载端点，并显式映射命名空间；不要为了主题另建站点或复制注册表。

```python
urlpatterns = [
    path("operations/_theme/", include(for_admin(operations_site), namespace="operations_theme")),
    path("operations/", operations_site.urls),
    path("audit/_theme/", include(for_admin(audit_site), namespace="audit_theme")),
    path("audit/", audit_site.urls),
]
NOVA_ADMIN_URL_NAMESPACES = {
    "operations": "operations_theme",  # 键为现有 AdminSite.name
    "audit": "audit_theme",
}
```

未配置的站点不会错误链接到另一个站点的切换端点。每个端点使用所属站点的权限与重定向范围。同一 Django 会话内的外观偏好是共享的，并非按站点单独储存。默认映射是 `{"admin": "nova_admin"}`。原生 `enable_nav_sidebar=False` 与 popup 隐藏规则仍被尊重。

### 5. 静态资源与 CSP

```bash
python manage.py collectstatic
```

包中有一份作用域 CSS、仅补搜索提示的小型渐进增强 JS，以及可选导航 JS。Django 自己的表单/自动完成/内联/选择器脚本继续由 Django 加载。自定义 JS 不发请求、不改变权限或表单提交。导航支持分组/应用/模型搜索及按站点、用户隔离的折叠偏好；清空搜索恢复各层原展开状态。搜索提示只读取已有可见帮助文字，不改变字段值。

全部 CSS 选择器以 `body.nova-admin` 为作用域。外观切到 native 时不加载主题 CSS/JS、不注入分组导航。CSP 若使用 Django 6.x nonce 上下文，会为主题 link/script 同样输出经过转义的 nonce；没有 nonce 时不输出该属性。与项目自己的严格 CSP/静态域配置仍需联合验证。

## 原生控件与列表状态

- 单选保留真实 `<select>` 的键盘操作与系统弹出菜单，统一圆角、留白、自绘箭头、焦点与禁用状态；不伪造可搜索下拉。多选列表与 Select2 隐藏源字段不套单选箭头样式
- 自动完成继续使用 Django 自带 Select2，覆盖搜索框、选项高亮/已选/不可选/无结果、多选标签、打开/焦点/错误/禁用状态。服务端查询、分页与权限仍完全归 Django 所有；静态导出不执行 Select2
- 数字输入保留原生 number、step/min/max、键盘步进和系统微调按钮，仅规范尺寸、数字对齐与一层外部焦点，不拦截滚轮或键盘，不引入第二组自定义加减按钮
- 布尔只读显示保留 Django 图标及原有 True/False/None 替代文本；装饰不会变成可点击控件。列表状态用带原文的视觉徽章，仍支持原生排序和状态筛选
- 需要开关外观时，业务项目自行给已有 CheckboxInput 增加 class `nova-switch` 和可访问名称；主题不会自动改变全站复选框。选行、全选、内联删除、权限复选框均维持原生外观。强制颜色模式退回平台复选框/下拉
- Demo 的“精选推荐”是实际 BooleanField，原生 `list_editable = ["featured"]` 提交、CSRF、权限、整组校验和审计日志都继续有效。**切换只改变待保存表单，必须点击原生保存才写入数据库**；没有自动保存请求。只读用户看到不可编辑的布尔图标，native 外观则退回普通复选框

Demo 列表额外用同名继承的 result_list 小块显示“点击保存后生效”提示；它只存在于 Demo，并保留 block.super。只读用户没有这个编辑提示。主题运行时包仍没有列表模板覆盖。

这些是 CSS 状态与 TestClient/DOM 回归覆盖，不等于浏览器端自动完成或完整无障碍认证。业务项目的现有 ModelAdmin 不会被主题修改；Demo 的字段和方法仅是接入示例。


## 原生图片列示例

Demo 使用同一个 `ModelAdmin.list_display` 输出三种业务图片：会员头像 44×44 圆形、商品图片 60×60 方形、新闻封面 96×54 横向。名称、排序、搜索、筛选、分页、批量操作与现有商品内联 / `list_editable` 都继续由 Django 负责；没有替换 changelist 模板或在主题中查询业务数据。

- 文件只来自 `demo/catalog/static/catalog/demo-media/` 的三张本地 WebP 合成图集，共约 694 KB；头像均为虚构成年人，商品无品牌，新闻场景为虚构。每张 3 列×2 行，用 CSS 显示独立格子，不使用外链
- 记录只存允许列表 `"0"`–`"5"` 的 key 或空值，不接收 URL、文件路径或上传。模型表单拒绝非法 key；即使数据库被写入非法值也显示占位，不会生成外部图片请求。跨域 `STATIC_URL` 在该安全示例中也会退回占位
- `format_html` 转义姓名、标题、alt 和链接；图片保留 `alt`、`loading="lazy"`、`decoding="async"` 与宽高。容器固定尺寸；缺图显示“暂无”，请求失败保留背景占位 / 原生替代文本，不依赖 `onerror` 或自定义 JS
- 缩略图链接到所属 `AdminSite` 已有的对象 change view，保留原查询条件；读权限用户只能阅读，写入继续受原生权限与 CSRF 保护。没有新的图片预览端点或认证旁路
- 图片列调用现有对象权限 hook；记录级列表可见性仍须由宿主 `ModelAdmin.get_queryset()` 正确限制。测试覆盖无模型权限、隐藏 queryset 记录和对象级拒绝。图集本身是公开静态合成资源，**不是私有媒体授权或上传系统的示例**
- native / 全局关闭 / 移除主题后，仍保留业务图片列和 Demo 自有的裁切尺寸 CSS；Nova 的主题 / 导航 CSS 和 JS 则完整移除。原生 Django 表格、文字和对象链接不变

业务项目可以参考 `demo/catalog/media.py` 与三个 Admin 类接入自己的 `list_display`，保留自己的权限和 queryset。`catalog/demo-media.css` 只控制示例图片几何尺寸，Nova runtime wheel 仅增加相应的可选配色 / 焦点样式，不含 Demo 模型、图片或媒体后端。采用私有上传时应另行实现经过授权的媒体访问，不能照搬公开 static 图集。

真实 Django Demo 的图片入口是对象详情；公开只读导出仅保留已有对应静态样本的链接，其他链接禁用，不提供在线图片预览或真实修改能力。

## 三条恢复路径

1. 当前用户选“Django 原生”：立即卸载 Nova CSS/导航，留下一个普通外观控件以便切回；保留会话偏好
2. `NOVA_ADMIN_ENABLED = False`：全站原生模板内容，不显示主题控件，偏好端点返回 404
3. 完全卸载：从 INSTALLED_APPS、上下文处理器和 urls 中移除 Nova 配置，再卸载包；不需要迁移业务数据或重新注册模型

主题没有数据库表或迁移。剩余的会话键 `nova_admin_mode` 不参与业务逻辑，可随会话自然过期。原生模式仍由 Django 自己的主题切换负责系统深浅色。

## 重复验证与构建

```bash
# 已安装本包的当前环境
python demo/manage.py test tests -v 2
python demo/manage.py check
python demo/manage.py makemigrations --check --dry-run

# 多 Python 精确矩阵：控制脚本需要 Python >=3.11
# 完整参数、解释器映射、独立输出目录见 COMPATIBILITY.md

# 打包
python -m pip install build
python -m build
```

矩阵脚本先核对每个解释器的真实微版本，再在明确指定的全新目录按 Python / Django / core或captcha / source或wheel 隔离执行。默认串行；日志与结果保留每组实际版本、安装来源和退出状态。`PYTHON` 只选择控制脚本的解释器，不再替代全部目标；`NOVA_MATRIX_LOGS` 已由独立运行目录中的分组日志代替。它不会下载运行时、复用未知环境或触碰 Demo 数据库。用法见 [COMPATIBILITY.md](COMPATIBILITY.md)。

当前核心套件发现270项，其中269项执行、1项是未启用可选验证码时的明确占位；可选验证码另有22项独立测试。套件保留项目中文、模板、auto、密度和分页覆盖；核心默认测试与项目默认浅色隔离。原有覆盖包括：真实 CRUD POST、FK/M2M 保存、内联新增/删除/校验与事务保持、无效关联、只读字段、自动完成权限与分页、批量发布/删除确认/日志、列表分页、CSRF、匿名/非 staff/只读拒绝、popup、三种恢复方式、两站点命名空间与自定义 has_permission、导航权限、nonce 属性转义、三级分组的过滤/去重/不泄露与布局回归。多项测试内部对 dark/light/native 分别执行。

## 真实模板静态样本（可选产物）

```bash
python -m pip install beautifulsoup4==4.15.0
PYTHONPATH=src:demo:. python scripts/export_admin_samples.py
```

`exported-admin-samples/index.html` 为样本入口，包含 light/dark/auto 三种外观的标准与紧凑版本，加上 native 原生外观，每种各八页，共 56 页（另加入口）。由 Django 6.1.1 的真实 TestClient 响应生成，使用独立内存数据库和纯虚构数据，不连接外部服务，也不读取本地业务数据库。

对外呈现必须标记“真实 Django 模板渲染样本 · 只读”：它不是在线 Django 服务。保留原生表单标签、ID与类名以保持响应式布局；移除所有提交/关联属性、字段name、隐藏字段、脚本、CSRF/会话数据、密码字段和在线端点。全部控件禁用，严格CSP设置 form-action none，禁止任何功能性提交；只允许样本之间的相对链接。JS 依赖的自动完成/M2M 交互不能在静态样本工作。`manifest.json` 记录源版本、哈希和消毒验证结果；必须连同 `static/` 整体复制，不能把模板包作为公开下载附件。

宽屏主体使用可用宽度，不再有1680px外层上限；表单字段保留独立阅读宽度。手机5–7列表格保留44rem，8列及以上54rem且商品名称单元格至少140px，额外宽度只在.results内部滚动。该范围由CSS契约测试约束；浏览器实际尺寸验收另行记录。

主表单中未增强的原生多选fallback使用min(24rem,100%)阅读宽度；只针对主fieldset，排除Select2隐藏源、Django已初始化的.filtered及.selector内控件，不改变Inline或双栏/堆叠多选增强组件。
若有related-widget-wrapper，同样只对直系未增强多选的包装器设置min(24rem,100%)，内层列表按flex分配剩余宽度，关联加号固定34px并同排保留；避免包装器按短选项文字缩合。此范围在初始化为.selector后立即不再匹配。


## 0.2.2 移动导航

可选导航在宽度不超过 767px 时提供「导航菜单」原位展开按钮，复用同一个原生权限过滤后的菜单。按钮与菜单状态同步，Esc 先清空已有筛选，再收起并把焦点送回按钮；窗口旋转或缩放时保留可见焦点。移动展开不修改桌面侧栏偏好，也不创建遮罩、焦点锁或 inert 状态。没有 JavaScript 时移动菜单保持可读；Django 原生模式及自定义导航关闭时不加入该按钮。新增文案使用 Nova Admin gettext context，提供英文和简体中文。

导航交互样例也保留该入口；所有样例链接仍只跳到本页说明，不执行管理操作。版本断言从 0.2.1 明确更新为 0.2.2；历史报告保持原验证日期和结果，新的浏览器验收与矩阵结果另行记录。

## 0.2.1 报告整改

详见 [CHANGELOG.md](CHANGELOG.md)、[REVIEW_RESPONSE.md](REVIEW_RESPONSE.md) 与 [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)。Nova 自有文案随 Django 激活语言显示；没有修改上游全局译文，中文 Demo 业务字段仍为中文示例。显式加入应用和 context processor 是 opt-in 接入，NOVA_ADMIN_ENABLED 省略时仍默认 True。

导航仅在 Nova 模式接管它自己生成的搜索输入：Django 的匿名模型筛选事件无卸载 API，因此初始化时用等价克隆建立单一事件归属，保留值/标签/ARIA/焦点与选择区；Django 总侧栏开关不变。提前绑定到该 Nova 搜索输入的第三方监听器不属于兼容承诺，请使用项目级验收。偏好不参与权限；渲染菜单仍来自原生 available_apps。

Node 交互回归需要先在研究包根目录运行 npm ci。随后激活 Django 环境，在本目录执行 `node scripts/test-navigation.mjs` 与 `node scripts/test-enhancements.mjs`；前者可通过 PYTHON 指定已安装 Django 的解释器，或传入一个/多个官方 nav_sidebar.js 路径。

## 0.3.0 企业项目预设

完整可复制项目词典、中文全角冒号、默认浅色与企业蓝见 [PROJECT_CUSTOMIZATION.md](PROJECT_CUSTOMIZATION.md)。真实密度变量与自动外观见 [DENSITY_PRESETS.md](DENSITY_PRESETS.md)。这些项目文案/模板不包含在通用主题 wheel 中；研究包提供完整 Demo 与源文件。旧会话保存的选择继续优先，不会被浅色默认强制覆盖。项目中文定制与 Nova 外观恢复互相独立。

### Palette presets

Appearance and color are independently selectable. Keep “Project default” for
unchanged project branding, or choose 医疗青 / 专业靛 / 文教紫 / 零售陶 / 石墨黑 / 午夜蓝.
Graphite and Midnight include distinct dark backgrounds, panels and controls;
use dark or system-following appearance to enable those surfaces. See
[PALETTE_PRESETS.md](PALETTE_PRESETS.md) for session validation, compatibility,
CSS override order, and tests.

中文接入、验证边界和人工验收重点见 [PALETTE_PRESETS_ZH.md](PALETTE_PRESETS_ZH.md)。
