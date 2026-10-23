# NOVA Admin

版本：交互预览 **1.8.0** / 原生 Django 主题 **0.6.1** · 2026-10-23

本轮新增设计令牌与品牌配置、权限内的收藏/常用模型/图标/计数、自检警告、上游漂移预警、隔离 Compose 示例和可选 Axes 接入。入口见 [品牌指南](django-theme/BRANDING.md)、[导航扩展](django-theme/NAVIGATION_EXTENSIONS.md)、[模板漂移](django-theme/UPSTREAM_DRIFT.md)、[Compose](examples/compose/README.md)、[验证码与安全工具](django-theme/CAPTCHA_INTEGRATION.md)。公开演示只承载合成预览与只读样本。官方源码见 [GitHub 仓库](https://github.com/mingyueshi/django-nova-admin)。历史源码包交付记录见 [DELIVERY.md](DELIVERY.md)，当前版本与验证范围见 [发行验证](django-theme/RELEASE_VALIDATION.md) 和 [CI 说明](CI_CD.md)。

既有 7 组 Python/Django 精确组合和 3 组 Node 工具链继续保留，新增验证与未实测边界见 [本轮报告](django-theme/TEST_REPORT.md)。Docker/PostgreSQL 运行、音频、旧 admin-honeypot 仍未实测。GitHub 工作流配置随源码提供，实际运行状态以仓库 Actions 为准，生产部署与候选发布开关未自动启用。

## 先选择要研究的部分

| 目录 | 用途 | 数据与交互 |
|---|---|---|
| `dist/` | 完整的 HTML/CSS/JS 交互预览源码，未压缩、无需构建 | 浏览器本地 mock 数据；没有真实权限或业务 API |
| `django-theme/src/nova_admin/` | 可安装、可恢复原生的 Django Admin 主题 | 使用原来的 AdminSite、ModelAdmin、认证、权限、CSRF、表单和动作 |
| `django-theme/demo/` | 可运行 Django 项目与图片列示例 | 本地 SQLite，由你创建管理员；真实增删改及关系字段流程 |
| `dist/native-admin/` | 真实 Django 6.1.1 渲染的 56 页＋96 个配色代表页＋入口 | 明暗/自动、标准/紧凑与原生外观，完全只读；脚本、认证及提交能力已经移除 |
| `tests/` | 交互预览的 1284 项前端检查 | Node/jsdom，不代表浏览器视觉或真机认证 |
| `django-theme/tests/` | 核心、可选验证码和 Axes 独立测试 | 精确补丁版本测试，详情见验证报告 |

`dist/` 就是前端源码，**不存在缺失的 React/Vue 工程或构建步骤**。本包没有 Python/Node 环境或依赖缓存；首次安装依赖需要访问官方 PyPI/npm。原始 PNG 图集、截图、数据库、浏览器数据、日志和发布配置没有打包。三份约 694 KB 的 WebP 是各演示入口的本地资源，不依赖外链。

## 1. 最快查看交互预览

在解压后的 `nova-admin` 目录运行（Windows 可将 `python3` 改为 `py`）：

```bash
python3 -m http.server 4173 --bind 127.0.0.1 --directory dist
```

浏览器打开：

- `http://127.0.0.1:4173/`：工作台
- `http://127.0.0.1:4173/#analytics`：统计分析与8类交互图表
- `http://127.0.0.1:4173/#charts`：ECharts / Chart.js / uPlot开源图表实验室
- `http://127.0.0.1:4173/#analysis`：经营、转化与运维的图表联动、三级下钻、模拟实时刷新
- `http://127.0.0.1:4173/#users`：头像列表
- `http://127.0.0.1:4173/#catalog`：商品图列表与复杂编辑表单
- `http://127.0.0.1:4173/#news`：新闻封面列表
- `http://127.0.0.1:4173/#components`：组件与状态
- `http://127.0.0.1:4173/#native-samples`：真实模板只读对照
- `http://127.0.0.1:4173/responsive.html`：390–2560 CSS 像素 iframe 检查

请通过 HTTP 打开，不要双击 HTML 使用 `file://`，否则 ES modules 会受到浏览器限制。修改源文件后刷新即可。模拟数据保存在当前浏览器的 localStorage；演示内的重置功能可以恢复合成数据。所有“权限”“保存失败”“状态开关”仅用于交互演示，不能作为生产权限实现。

## 2. 运行真正的 Django Admin

推荐 **Python 3.12.15**。以下使用已验证的 Django 6.1.1：

```bash
cd django-theme
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r requirements-test.txt
python demo/manage.py migrate
python demo/manage.py seed_demo
python demo/manage.py createsuperuser
python demo/manage.py runserver 127.0.0.1:8000
```

Windows PowerShell 的建环境与激活命令改为：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果不想改变 PowerShell 执行策略，可以不激活，直接使用 `.\.venv\Scripts\python.exe` 替代后续的 `python`。

打开 `http://127.0.0.1:8000/admin/`，使用刚创建的账号。**没有预设账号、共享密码或免登录入口**。`seed_demo` 只生成虚构业务资料与图片示例，不创建认证用户；可重复执行且保留已有样例的修改。图片选择使用内置图集 key，不接受用户上传或外部 URL。数据库在首次 migrate 时生成，包内没有数据库。

种子命令仅允许 DEBUG=True + SQLite；使用稳定 SKU、会员编号和保留的新闻 ID 900001–900007。若相同标识已存在，会保留该记录及其关系；删除或更改标识后重跑可能重新创建示例。它不用于生产数据迁移。

Demo 设置为 DEBUG、本机地址和显式的本地演示用占位签名值，仅用于研究；它不是部署配置。不要把 Demo 的 settings 直接用于生产。主题自己的 `src/nova_admin` 不含业务数据、账号或配置密钥。

若研究 5.2 或 6.0，在独立环境中安装相应版本，例如：

```bash
python -m pip install -e . "Django==5.2.17"
# 或 Django==6.0.8
```

不要再安装固定6.1.1的 `requirements-test.txt` 来覆盖该环境。实际验证为Python3.11.17×5.2.17；3.12.15×5.2.17/6.0.8/6.1.1；3.13.16×6.1.1；3.14.8×5.2.17/6.1.1，共七组。依赖区间仍为 `Django>=5.2.17,<6.2`，最低安装元数据仍为Python3.10；3.10已EOL，不进入当前维护矩阵。其它交叉组合、平台、补丁或第三方插件需单独验收。

## 3. 安装到自己的 Django 项目

建议先在独立分支与测试数据库验收。从项目根目录安装本包中的主题源码（路径换成自己的解压位置）：

```bash
python -m pip install -e /path/to/nova-admin/django-theme
```

也可自行在主题目录用 `python -m build --wheel` 构建wheel安装。wheel只包含主题运行资源，不包含Demo模型、图片或测试。研究修改时优先editable源码安装。

1. `INSTALLED_APPS` 中把 `nova_admin` 放在 `django.contrib.admin` 前
2. 在现有模板 context processors 中增加 `nova_admin.context_processors.theme`，保留原有处理器
3. 设置 `NOVA_ADMIN_ENABLED = True`；企业示例推荐 `NOVA_ADMIN_DEFAULT_MODE = "light"`
4. 若需要用户切换外观，在现有 `admin.site.urls` 之前挂载 `nova_admin.urls.for_admin(admin.site)` 的端点
5. 按项目原有静态资源流程运行 `collectstatic`

完整可复制配置、三级导航、多个 AdminSite、CSP、图片列和原生控件说明见 `django-theme/README.md`。**无需导入 Demo 模型、复制注册表或重写现有 ModelAdmin**。

## 4. 恢复 Django 原生

- 当前会话：外观菜单选择“Django 原生”，卸载 Nova 主题样式与分组导航
- 全站：设置 `NOVA_ADMIN_ENABLED = False`，不显示主题控件
- 完全卸载：先移除 `INSTALLED_APPS`、context processor 和 URL 中的 Nova 配置，再卸载包

主题没有数据库迁移，也不需要重新注册业务模型。Demo 的图片列属于业务示例，在原生模式仍保留；其最小图片尺寸 CSS 不属于 Nova 主题外观。

## 5. 从哪些文件改起

- 整体设计：`dist/styles.css`；真实主题：`django-theme/src/nova_admin/static/nova_admin/`
- 导航/面包屑：`dist/js/navigation.js`；真实主题的导航模板与 context processor
- 商品关联与 Inline：`dist/js/catalog.js`；真实 Demo 的 `catalog/admin.py`、`models.py`
- 图片预览/缺图/失败：`dist/js/media.js`；新闻：`dist/js/news.js`
- 真正的安全图片列：`django-theme/demo/catalog/media.py` 与 `admin.py`
- 数字/选择框：`dist/js/controls.js` 与作用域 CSS；Django 继续使用原生控件 / Select2
- 原生开关：Demo 的 `featured` 是原生 `list_editable`，必须点击“保存”才写入；Mock 开关本地即时保存

## 6. 运行检查

私人源码包首次解压可以先核对文件完整性（网站仓库未打包时不含该manifest）：

```bash
python3 scripts/verify_package.py
```

前端开发/测试推荐 **Node.js 24.21.0 + npm 11.19.0**；22.23.3 LTS与26.10.0 Current亦已独立验证。依赖的历史技术门槛仍为Node 18，18/20已EOL且不列为维护推荐；项目未新增engines限制。查看静态预览或运行真实Django主题不需要Node。在项目根目录运行：

```bash
npm ci
npm test
```

真实 Django（在已安装主题的虚拟环境内、`django-theme` 目录）：

```bash
python demo/manage.py check
python demo/manage.py makemigrations --check --dry-run
python demo/manage.py test tests -v 2
python scripts/test_seed_demo.py
node scripts/test-navigation.mjs
# 多 Python 精确矩阵的解释器映射与完整参数见
# django-theme/COMPATIBILITY.md（从主题目录执行脚本）
```

本轮及历史执行记录见 `django-theme/TEST_REPORT.md`。服务端 TestClient、DOM/CSS 契约与浏览器视觉验收分别记录，不能互相替代。先前实际浏览器多尺寸检查使用 iframe，不是物理手机测试。

## 授权与素材

原创代码遵循根目录 `LICENSE` 的 MIT 条款；Django/Select2 静态资源的许可证保留于 `dist/native-admin/`。合成图片由本次演示生成，为虚构成年人、无品牌产品与虚构场景，没有私人照片或第三方图片热链；见 `THIRD_PARTY_NOTICES.md`。


## 1.4.1 / 0.2.1 首批整改

主题已修复自有文案国际化、可选URL反解、导航搜索/状态、Inline名称、搜索提示及数字/对比度细节。见 `django-theme/CHANGELOG.md`、`REVIEW_RESPONSE.md` 与 `INTEGRATION_GUIDE.md`。新版是云端基线，不包含或覆盖你本地的研究改动。

## 1.4.2 / 0.2.2 交互恢复与手机导航

真实主题新增手机宽度下的导航展开入口，继续使用权限过滤后的同一菜单；Escape、搜索清空、焦点返回和桌面折叠偏好各自保持。无 JavaScript 时菜单直接显示；切回 Django 原生或关闭 Nova 导航时不加载这段增强。

交互预览修复了三类列表的地址/筛选状态、列表开关与编辑表单的并发覆盖、重复提交、超出安全整数范围的库存、禁用选项组，以及图片连续失败后的重试和嵌套预览恢复。图片预览内的“图片状态演示”可反复验证失败与恢复，只使用随包本地素材。

新增 36 项前端恢复回归，原有 98 项检查保持不变。该轮更新继续以云端基线为准，未读取或合并你本地的研究改动。具体运行结果与浏览器检查见 `QA.md` 与 `django-theme/TEST_REPORT.md`。

## 1.5.0 / 0.3.0 企业中文预设

首次访问采用浅色企业蓝；已保存的手动明暗/自动选择优先。项目级中文词典、真实全角冒号与紧凑CSS已经落在可运行Demo中，完整配置和来源见 `django-theme/PROJECT_CUSTOMIZATION.md`，密度变量见 `django-theme/DENSITY_PRESETS.md`。中文标点在真实模板/表单层处理；checkbox动作短语和组内选项保留原语义，英文界面文案不受中文词典影响。

`#native-samples` 可独立选择外观与标准/紧凑密度，对比真实Django只读渲染；原生模式移除Nova及企业配色/密度，项目文案仍保留。彻底移除项目中文策略的步骤也在项目指南中。


## 1.5.1 / 0.3.0 静态原型技术债治理

本轮只整理前端原型，原生 Django 主题与企业中文预设保持 0.3.0。按顺序完成固定版本 Prettier、三种列表共用 collection 工厂、缩小模块与应用状态/持久化的接口。没有新增业务功能或改变界面设计。具体提交、接口边界、保留的差异与验证方法见 [REFACTOR_NOTES.md](REFACTOR_NOTES.md)。

```bash
npm ci
npm run format:check
npm test
# 编辑 dist/js 后统一格式
npm run format
```

格式化仅覆盖自有 `dist/js/*.js`，排除 Django、第三方脚本与只读导出；不会自动重排 HTML 模板字符串。前端测试 222 项，含 68 项针对列表与接口边界的回归，以及 7 项商品批量发布旧标签缺陷的修复检查。该旧 bug 以第四个独立提交修复，不混入三步行为保持的结论。Django 三个精确版本的 241 项源码/安装验证属于上一版已完成记录，本轮以运行源码、样本和 wheel 的字节不变校验保留该基线，没有将它计作新增运行。


## 1.6.0 / 0.4.0 登录页与可选验证码

当前登录演示已支持图形／拼图滑块、每次验证／异常后验证，以及 5／6／8 位字符对比。图片与输入框各占一行；真实 Django 表单支持服务端失败升级策略，滑块接入独立 `nova-slider-captcha` 0.2.0 包并先消费一次性凭证再认证。预览仍为本地 mock。配置与兄弟项目安装方法见 [登录验证码接入](django-theme/CAPTCHA_INTEGRATION.md)。

- `dist/login.html`：独立登录交互演示，企业浅蓝/深色/自动、几何背景、手机单栏。只使用预填的虚构账号，不输入真实密码
- `#login-preview` 和 `#native-samples` 提供入口，`responsive.html` 可检查不同宽度
- 演示有图形刷新、文字替代、错误/过期、提交失败、重复/中断提交；所有校验都在浏览器本地，不建立真实会话
- 真正的Django可选extra使用 `django-simple-captcha==0.7.0`、`Pillow==12.2.0` 本机生成和服务端校验。默认核心安装仍只有Django；详见 [验证码接入](django-theme/CAPTCHA_INTEGRATION.md)
- 实际模板样本中的验证码是隔离数据库生成的静态PNG，已移除密钥、提交和执行脚本；查看交互请使用独立演示或本地Django项目

可选Django试运行使用单独的Demo设置和数据库：

```bash
cd django-theme
python -m pip install -e '.[captcha]'
python demo/manage.py migrate --settings=config.captcha_settings
python demo/manage.py createsuperuser --settings=config.captcha_settings
python demo/manage.py runserver 127.0.0.1:8000 --settings=config.captcha_settings
```

包内没有管理员账号或数据库。核心主题、验证码接入和项目的安全策略相互独立：切回原生外观不会关闭已启用验证码。听读需要项目配置真实Flite/SoX；本轮未安装或验证音频生成/播放。生产限流、MFA、数据库负载和无障碍替代认证仍需项目验收。


## 1.6.1 / 0.4.1 登录页精简

登录页改为单一聚焦卡片，只保留品牌、账号密码、验证码与登录主操作。移除双栏宣传文案、大标题、标签和重复页脚，以轻量背景环线和光影保留设计感。公开预览保留一句虚构账号提示，测试账号与失败/过期控制收进“帮助与演示”；真实 Django 的替代登录帮助按需展开，认证错误始终直接显示。验证码服务端、CSRF 与原生外观恢复逻辑不变。


## 1.6.2 / 0.4.2 双端登录布局

桌面采用宽幅开放构图：纯视觉品牌图形与适中宽度表单互相平衡，取消小浮卡，不增加宣传文案。900px及以下使用独立单列布局，删除外层边框、圆角、面板背景和阴影，表单直接融入页面；输入控件边界与触控间距保留。Django真实模板和公开mock使用同一登录样式，验证码、认证与CSRF逻辑未变。

共享登录布局 CSS 以 `django-theme/src/nova_admin/static/nova_admin/login.css` 为唯一来源；`dist/login.css` 是其逐字节副本，修改来源文件后运行：

```sh
npm run sync:login-css
npm run check:login-css
```

同步命令只在有差异时更新副本。`--check`（即 `node scripts/sync-login-css.cjs --check`）只读取并比较字节，副本缺失或漂移时非零退出，不创建或改写文件。现有 `npm check`、`npm test` 和调用它们的前端 CI 都执行该检查，CI 不自动修复漂移。`npm run test:shared-css` 在临时目录注入漂移，验证检查不写入、显式同步和缺失副本等行为；没有新增依赖。

共享 CSS 不要求两种页面具有相同 DOM 或相同功能：`login-preview.css` 提供 mock 的基础变量、预览工具及演示控件，浏览器内的模拟校验不能代表真实认证；真实 Django 仍保留原生表单、权限与 CSRF。`dist/native-admin/*/login.html` 来自真实模板渲染后经过安全净化的只读样本，输入/提交均禁用，只能检查布局、品牌与仍可聚焦的链接/摘要，不能用来验收登录或输入框键盘行为。它们通过现有导出器重新生成，不能手工改写来源清单中的 SHA。


## 1.7.0 / 0.5.0 中文呈现与分页

- 主标题直接呈现，不再默认添加装饰性英文或中文 eyebrow；真实状态、分类和必要的模拟数据说明保留
- 中文字体采用系统现有字体回退，不下载或捆绑新字体；实际字形仍取决于目标系统安装的字体
- 搜索提示在 macOS 显示 ⌘ K、其他平台显示 Ctrl K；键盘处理仍支持两种组合
- 浅色错误文字统一深红，按实际浅底计算对比度；暗色语义不变
- 中文展示为 99.2%、124ms、¥299.00；数字输入值、数据库 Decimal 和英文翻译不做全局替换
- 用户、商品和新闻列表默认每页10条，可选10/20/50/100；页码与条数进入URL，支持返回、前进和重载。改变页容量保留选中记录并回第一页；改变筛选清除选择；非法跳页就地提示、超范围页码夹到有效末页
- 新访客的商品和新闻各有24条合成记录，复用合法本地图片。已保存的浏览器修改继续保留，若想查看完整新种子，可自行使用“恢复演示初始状态”

这不是把前端分页连接到生产后端。原生项目级分页示例、允许值和接入边界见主题指南。

## 0.6.1 主题发布包

官方主线的布局、过滤器折叠、宽表操作与配色更新现整理为主题 `0.6.1`，预览包仍为 `1.8.0`。版本规则、安装升级、无迁移与回退步骤见 [发行说明](django-theme/RELEASING.md)，实际测试和覆盖边界见 [发行验证](django-theme/RELEASE_VALIDATION.md)。交付源码绑定的 wheel/sdist 与静态归档，不代表已发布到 PyPI 或公开 Release。

## CI/CD

GitHub Actions 包含 PR/主分支快速矩阵、手动完整矩阵、源码绑定的 wheel/sdist/静态产物，以及默认关闭的手动审批候选交付。官方仓库已运行快速 CI；本次发行提交的实际验证单独记录，没有自动包发布或生产部署。配置与边界见 [CI/CD接入说明](CI_CD.md)。

## 独立配色预设

系统设置顶部提供16张可点击色卡，每张展示缩略工作台、背景/侧栏/面板/强调/文字五种色点与场景说明。色卡随浅色、深色或系统自动外观同步显示真实配色；点击立即应用、标记“使用中”并保存偏好，另有独立的默认配色恢复按钮。下拉选择、刷新恢复、跨窗口和登录页同步继续可用。

系统设置与登录预览可选择医疗青、专业靛、文教紫、零售陶、石墨黑、午夜蓝、松林绿、暖琥珀、深海青、雾岩灰、暮梅紫、摩卡棕、冰川蓝、胭脂红、苔原绿、极夜黑；行业名称仅为演示定位，不是行业标准。十二套暗色表面方案在深色或系统深色下同时调整页面、侧栏、卡片与表单底色；松林绿使用森林绿底色与薄荷绿强调色，暖琥珀使用暖棕底色与琥珀强调色。深海青适合监控运维，雾岩灰适合密集表格，暮梅紫适合内容审稿，摩卡棕适合夜间阅读；冰川蓝适合科技工作台，胭脂红适合品牌运营，苔原绿适合项目管理，极夜黑适合低干扰办公。这些是选色建议。配色与浅色、深色、跟随系统、原生恢复分开。默认仍为企业蓝，通用 Django 包默认仍为紫色主色和绿色保存按钮。

静态预览仅用独立 `nova-palette` 保存偏好，首屏、跨页与同源窗口恢复；存储不可用时可继续当页使用。不会清除 `nova-theme` 或业务数据。Django 使用受 CSRF 保护的独立 session 偏好，配置和宿主覆盖见 [中文配色接入与验收说明](django-theme/PALETTE_PRESETS_ZH.md)。

新样式为两份手写 token 样式表，没有 CSS 编译依赖或整套主题复制。成功、警告、危险的状态语义保留。`python scripts/test_palette_contrast.py` 量测新色彩的明确不透明角色；这不等于浏览器视觉或整站无障碍认证。

## 图标演示与开源图标

“开发与集成 → 图标演示”（`/#icons`）提供Lucide、Tabler、Heroicons、Iconoir、Bootstrap Icons共320个图标的本地精选集，每库64个，覆盖11类后台场景。支持中英文和业务关键词搜索、分类、分页、尺寸和轮廓线宽预览、JavaScript/Django/导航配置/SVG示例、复制代码及下载原始SVG。现有内置图标接口保持兼容；Django可通过 `{% nova_icon "lucide:search" %}` 或导航图标配置使用同一名称。完整许可、资源来源与接入步骤见 [图标指南](django-theme/ICONS.md) 和 [第三方声明](THIRD_PARTY_NOTICES.md)。


## 统计图表与数据演示

“统计分析”（`/#analytics`）新增趋势折线/面积、订单堆叠/分组柱状、渠道环形/饼图、商品排行、转化漏斗、时段热力图、订单与客单价散点图、目标进度共8类图表。支持7/30/90天和渠道联动筛选、三种趋势指标、上期对比、图例开关、键盘/触摸读数、目标设置、明细表及精确CSV导出，并提供无数据和全零状态。图表使用本地SVG和固定合成数据。功能、口径、源码接入与验证范围见 [CHARTS.md](CHARTS.md)。


## 开源图表库

新增“开源图表实验室”（`/#charts`），实际接入Apache ECharts 6.1.0、Chart.js 4.6.1和uPlot 1.6.32，覆盖17类后台统计场景、28组库与场景组合。支持本地按需加载、筛选、原生图例/提示/缩放、运维模拟回放、PNG/CSV导出和JavaScript/Django用法。完整资源来源、许可、范围及宿主接入方式见 [开源图表指南](CHART_LIBRARIES.md)。

新增“联动分析工作台”（`/#analysis`），提供经营收入、用户转化、服务监控三类场景。排行点击联动图表/指标/明细，双击或按钮逐层下钻，时间滑块联动统计区间；支持3/5/10秒模拟刷新、暂停、失败重试、保留最后成功快照、CSV完整范围导出。数据均为独立模拟样本，未新增真实统计API。数据口径、生命周期、源码与接入结构见 [联动分析指南](ANALYSIS_LAB.md)。

## 原生列表排序

运行 Django Demo 后进入「商品」列表，展开排序说明。列名链接按 Django 规则排序并提升为首要排序，箭头只切换该列方向，× 移除该列；数字表示多列优先级。搜索、筛选及分页容量参数由原生链接保留，图片列和选择框列不添加排序控件。关闭 JavaScript 或切换为 Django 原生外观后仍可使用原生排序链接。

本次复用 `codex/changelist-sorting-ui-20261015` 中 `2dde2c6`、`fe99ecf` 的排序增强和回归测试，以最小差异适配当前 main，未整合旧分支中的其他文件。`dist/native-admin` 仍是既有只读快照，完整排序交互请在运行中的 Demo 核验。
