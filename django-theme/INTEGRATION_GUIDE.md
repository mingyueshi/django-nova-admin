# 宿主项目接入指南

本文件说明如何利用 Django 的公开扩展点继续建设业务后台。除 README 明确列出的主题功能外，以下能力不会因安装 Nova 自动启用，也没有暗含的新 API、权限、上传目录或认证端点。

## 多语言与中文文案

Nova 自有界面使用英文源消息与 `Nova Admin` gettext context，随 Django 当前激活语言显示；包中提供简体中文词典。英文项目不再混入 Nova 硬编码中文。宿主仍负责 `LANGUAGE_CODE`、LocaleMiddleware、语言选择入口及业务模型字段/导航配置的翻译。Demo 的业务字段与合成姓名是中文示例，不宣称整个 Demo 为双语业务系统。

不在主题词典中覆盖 Django 的通用消息。翻译目录优先级是项目/应用级，而非 CSS 外观级：在主题中覆盖“Add”“Log out”或“- Select an option -”会同时影响原生恢复及其他页面。需要统一业务中文措辞时，由宿主有意识地维护自己的 `LOCALE_PATHS`；将它视为产品文案定制，单独测试 native 模式，而不是 Nova 默认行为。参阅 [Django 翻译优先级](https://docs.djangoproject.com/en/6.1/topics/i18n/translation/#how-django-discovers-translations)。

### 可直接复制的项目配置与词典

研究包已提供完整可运行示例：`demo/locale/zh_Hans/LC_MESSAGES/django.po`、编译后的`django.mo`、`demo/catalog/forms.py`、项目模板与企业蓝/紧凑CSS。直接参考 [PROJECT_CUSTOMIZATION.md](PROJECT_CUSTOMIZATION.md)，不需要改 Django 或 Nova 安装目录。

```python
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_CODE = "zh-hans"
NOVA_ADMIN_DEFAULT_MODE = "light"
FORM_RENDERER = "catalog.forms.ProjectAdminFormRenderer"
PROJECT_ADMIN_COMPACT = False
# 合并到已有配置，保留原 context processors：
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]
# 追加 catalog.context_processors.project_admin
```

项目 `.po` 中的可复制片段如下；完整词典还覆盖 Add 的带模型名变体、group/groups、显示数量及菜单占位：

```po
msgid "- Select an option -"
msgstr "请选择"

#, python-format
msgid "Select %s to change"
msgstr "%s列表"

msgid "Add"
msgstr "新增"

msgid "Log out"
msgstr "退出登录"

msgctxt "Nova Admin"
msgid "Site overview"
msgstr "工作台"

msgctxt "Nova Admin"
msgid "Manage models and everyday work. Available content depends on your site permissions."
msgstr "管理内容数据"
```

三个已测 Django 版本的列表标题实际使用 `%s`，不能把 msgstr 单独换成 `%(verbose_name)s`。Inline 等命名消息则原样保留其 `%(verbose_name)s`、`%(name)s` 或 `%(model)s`。本次要求的消息均在 `django` 域；Inline 新增文字也由服务端写入组件数据，不能误放 `djangojs.po` 后以为已覆盖。详细核验表见项目指南。

有 GNU gettext 时在 `demo/` 执行 `PYTHONPATH=../src:. python manage.py compilemessages --locale zh_Hans`；无该工具时，先安装 `demo/requirements-localization.txt`，再执行 `python demo/compile_catalog.py`。交付已包含 `.mo`，普通启动无需先编译。

中文全角冒号由项目 Form renderer 和少量版本对应的 Admin 模板产生，保留真实 label/legend/for/id、readonly 与 Inline 语义；checkbox 动作短语及组内选项不强加冒号，英语保持原样。不是 CSS 伪元素，且不会叠加双冒号。移除项目定制时可同时移除 `LOCALE_PATHS`、renderer、项目模板与样式；只关闭 Nova 时项目文案仍是项目文案。

主题默认启用是指：**你显式安装包、加入 INSTALLED_APPS 和 context processor 后**，省略 `NOVA_ADMIN_ENABLED` 时为 True。没有安装配置时不会自行启用。此版本保留该默认以免升级突然关闭外观；显式 False 仍可完整关闭。

## 列表搜索、数字与币种

`ModelAdmin.search_fields` 决定真实可搜索字段，`search_help_text` 给出可见说明。Nova 仅在没有现有 placeholder 的可编辑搜索框上补提示，优先使用该说明；不会改变 GET、q 参数、标签、帮助文字或提交逻辑。无 JavaScript 时仍显示原生帮助文字。[Django 搜索设置](https://docs.djangoproject.com/en/6.1/ref/contrib/admin/#django.contrib.admin.ModelAdmin.search_help_text)

表格常见 `price`、`stock`、`sku` 字段及显式 `.nova-number` 内容使用等宽数字；价格/库存按末端对齐。它不推断币种，也不改数据库值。若业务确认全部为人民币，可以在自己的 ModelAdmin 添加 `@admin.display(ordering="price", description="价格（CNY）")` 方法，返回 `f"¥{obj.price:,.2f}"`；把它放入 list_display。混合币种应有独立 currency 字段，不能全站盲加 ¥。排序继续指向数值字段，导出使用原始 Decimal，而不是格式化字符串。

## 找回密码与账号安全

找回密码应由现有身份系统决定。Django 提供四个标准密码重置视图，登录页在存在 `admin_password_reset` 命名 URL 时显示入口；邮件后端、发件域名、链接域名、模板与频率限制需一起配置和验收。优先沿用已有 SSO/身份提供方，避免同时出现两套恢复路径。[官方接入说明](https://docs.djangoproject.com/en/6.1/ref/contrib/admin/#adding-a-password-reset-feature)

上线前验证：合法账号、无效账号、禁用账号、无可用密码的 SSO 账号、过期/重复令牌、邮件不可达、HTTPS 链接和防枚举响应。验证码、锁定策略、MFA、“记住我”和会话时长同属身份/风险策略；Nova 不自动添加或更改它们。本 Demo 没有重置密码端点，也不发送邮件。

## 图片/文件上传与授权媒体

Demo 的合成 static 图集只用于 list_display 样式，不是私有媒体方案。若接入 ImageField/FileField，应保留 Django ModelForm 与原生 multipart 提交；同时明确文件类型/大小、解码与重编码、随机文件名、病毒扫描、存储额度、审计、删除与备份策略。[上传机制](https://docs.djangoproject.com/en/6.1/topics/http/file-uploads/)

私有文件不能直接用公开 MEDIA_URL 暴露：下载/预览先根据宿主权限、对象归属和 queryset 检查，再由授权响应或短时签名方式交付；列表能看到对象不等于媒体自动安全。不要把不可信 SVG/HTML 作为同源可执行内容提供。对公网用户内容应考虑独立媒体域及合适的 Content-Type/Disposition。[Django 用户上传内容安全说明](https://docs.djangoproject.com/en/6.1/topics/security/#user-uploaded-content)

富文本/Markdown 编辑器属于内容输入功能：采用可信维护的集成，并在服务端按允许列表净化输出；不能只靠编辑器按钮限制 HTML。主题不会把已有普通 TextField 悄悄换成编辑器。

## 导入与导出

导出可使用原生 admin action 接收已筛选/选中的 queryset，但还需遵守宿主对象级/字段级权限，明确允许导出的列，禁止信任客户端提供任意模型/字段名。CSV 用标准 csv writer 转义逗号/引号；电子表格打开场景还要处理不可信单元格的公式注入，并限制数据量。[Admin actions](https://docs.djangoproject.com/en/6.1/ref/contrib/admin/actions/) · [CSV 输出](https://docs.djangoproject.com/en/6.1/howto/outputting-csv/)

导入应分成上传、解析/类型校验、预览差异、确认提交四步；使用已有认证和 CSRF，限制文件/行数、列允许列表、可关联对象范围与重复主键策略。提交需事务或明确的逐行失败策略，并记录操作者与结果；不建议一键覆盖生产表。导入导出库可以作为宿主依赖独立选择，Nova 不捆绑安装。

## 仪表盘、行操作与分页

可通过现有 `AdminSite.index_template` 自定义首页，再保留原生应用入口；统计必须从同一权限过滤的业务服务取得，避免给只读/受限人员显示越权汇总。卡片没有数据时显示明确空态，不能复用 Mock KPI 冒充实时数据。[AdminSite 扩展点](https://docs.djangoproject.com/en/6.1/ref/contrib/admin/#adminsite-objects)

行操作可用 `@admin.display` 与 `format_html` 生成所属 AdminSite 的原生 change/delete 链接，并逐对象调用权限 hook。删除继续使用原生确认与 CSRF POST，不能以 GET 完成操作。跳页/每页条数由 ModelAdmin/paginator 的业务容量与查询成本决定；设置有限允许值，不能信任无限 page_size。`date_hierarchy` 可按模型已有日期字段启用；新闻发布校验、缺货警示由业务规则决定，不是主题自动推断。

## 生产检查清单

在自己的生产 settings 中，逐项核对后运行 `python manage.py check --deploy --settings=你的生产配置`，不要复制 Demo settings：[官方部署清单](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/)

- DEBUG=False；正确且明确的 ALLOWED_HOSTS、CSRF_TRUSTED_ORIGINS
- 由现有秘密管理流程提供独立 SECRET_KEY；不使用 Demo 占位值
- HTTPS、安全 Session/CSRF Cookie；HSTS 根据实际域名/子域覆盖逐步配置
- 只有在可信代理明确移除外来同名请求头时，才配置代理 HTTPS 头
- 数据库/媒体/备份最小权限、限流、错误监测、审计与恢复演练
- collectstatic、缓存更新与 CSP nonce 配合；不得为主题草率放开脚本策略
- 管理员及各类受限账号分别验证列表、对象、动作、媒体和导出权限

## 浏览器与视觉定制

主题使用 CSS variables、`:is()`、`:has()`、逻辑属性和原生 details。完整增强布局要求支持这些特性的现代浏览器；`:has()` 跨浏览器基线为 2023 年 12 月。旧浏览器可能仍可使用原生表单，但本主题不承诺其完整响应式布局。应以项目目标浏览器实测，而不是把服务端版本矩阵当浏览器认证。[MDN :has()](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:has)

品牌颜色可以在主题 CSS 后加载自己的文件，覆盖 `body.nova-admin.nova-mode-light` / `.nova-mode-dark` 下的 `--button-bg`、`--button-fg`、`--default-button-bg`、`--link-fg`。保留 hover/focus/disabled/error 对应状态，并检查文字对比度。Nova 没有强制改成蓝色，也没有压缩掉可读源码；压缩/缓存属于宿主 collectstatic 工具链。

多 AdminSite 时，每个 `include(for_admin(site), namespace="唯一名称")` 使用不同命名空间，并与 `NOVA_ADMIN_URL_NAMESPACES` 映射一致；运行系统检查。默认 app namespace 相同本身并非错误，真正需要唯一的是各实例 namespace，不能依赖默认名重复挂载。

### 企业颜色和紧凑布局现成文件

`demo/catalog/static/catalog/enterprise.css` 提供浅色蓝 `#1d4ed8`、深色蓝 `#93c5fd` 及 hover/选中/按钮文字变量。通过 `admin/base_site.html` 在 Nova CSS 后加载；已有会话的明确外观选择优先于项目默认浅色。auto 使用系统明暗偏好，不重置已保存的 light/dark/native。

`enterprise-compact.css` 是实际原生布局覆盖，包含 `--nova-cell-padding`、`--nova-form-row-padding`、`--nova-control-padding-block`、`--nova-control-padding-inline`、`--nova-control-min-height`、`--nova-action-padding` 和 `--nova-section-padding`。核心还暴露行高/最小行高；完整变量默认值和触控保底见 [DENSITY_PRESETS.md](DENSITY_PRESETS.md)。Demo 以 `PROJECT_ADMIN_COMPACT=True` 加载预设，原生恢复模式不加载项目配色/密度样式。


## 可选登录验证码（0.4.0）

登录页的视觉增强自动随主题生效。0.5.0 延续桌面开放构图、手机无外层卡片；项目可覆盖 nova_admin/login_brand.html 定制桌面纯装饰，片段在900px及以下隐藏，不包含品牌宣传文案或认证控件。服务端验证码必须另外显式接入，不因添加主题而自动启用。核心安装、数据库和既有AdminSite注册不变；完整中文步骤、认证前置校验、同源刷新、回退与无障碍边界见CAPTCHA_INTEGRATION.md。已有MFA/SSO表单应保留自身逻辑，合并字段和clean守卫，不直接套用示例替换。


## 0.5.0 呈现约定

主题首页直接把有上下文的 `Site overview` 翻译作为主标题；项目词典仍可把它译成“工作台”，不再产生额外的小标题。英文 locale 保持英文标题，关闭主题后恢复上游首页标题。组件状态/分类文本与无障碍说明不是装饰标签。

当前演示的企业蓝已经由项目 `enterprise.css` 覆盖生效；核心可复用包的默认紫色仍可用于其他品牌。主原型已合并重复的主色定义，不能把源码里存在核心默认紫色误认为线上企业预设失效。字体声明只使用宿主已有字体；新增 Noto Sans SC、Source Han Sans SC、HarmonyOS Sans SC 回退不代表已在所有国产系统验证。


## 可选的真实分页接入

参见 [PAGINATION_INTEGRATION.md](PAGINATION_INTEGRATION.md)。Demo 只在商品、成员、新闻三个 ModelAdmin 显式采用该示例；每页仍默认20条，可选10/20/50/100及跳页。它不改未知项目的默认值，不改变原生权限、动作、CSRF、表单保存或查询集。宿主“显示全部”策略和无效页处理仍遵循Django。


## 0.6.0 可选扩展入口

- [BRANDING.md](BRANDING.md)：七个常用CSS令牌、NOVA_ADMIN_BRANDING安全资源配置，以及完整模板block/include清单
- [NAVIGATION_EXTENSIONS.md](NAVIGATION_EXTENSIONS.md)：收藏、常用模型、受控图标、一次调用的权限内计数；Django W001–W003自检
- [UPSTREAM_DRIFT.md](UPSTREAM_DRIFT.md)：本地差异报告、已审查版本与尚未运行的GitHub主线cron
- [CAPTCHA_INTEGRATION.md](CAPTCHA_INTEGRATION.md)：可选security extra、Axes8.3.1接入与实际边界
- 仓库 `examples/compose/README.md`：隔离的PostgreSQL/验证码/多AdminSite一条命令示例；当前无Docker运行结果

本地品牌/导航配置可直接复制 `demo/config/extensions_settings.py`，或运行 `python demo/manage.py runserver --settings=config.extensions_settings`（先按该settings执行migrate并创建自己的管理员）。该示例只在原有Demo之上启用样式/导航，不启用验证码或Axes；需要登录防护时显式使用相应settings。生产项目应逐项合并到已有设置，不替换未知配置。
