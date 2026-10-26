# 0.6.1 发布包历史验收与复现（2026-10-15）

本页保留 **2026-10-15 的 0.6.1 发布包历史验收清单与复现步骤**。下文的622项前端、121项主题JS、38个运行文件及其他旧数量均属于当时；“本轮”“当前”等措辞也只指该历史阶段，不能作为新发行的通用必需数量或已完成认证。

当前工作区的执行规范见[CI说明](../docs/CI_CD.md)、[CI契约源码](../scripts/ci_support.py)和[npm脚本](../package.json)，文档入口见[索引](../docs/README.md)。2026-10-26的20套件1397项前端/260项主题JS契约包含尚未提交的用户数据候选，本地独立验收及其边界见[用户数据验收记录](../docs/USER_DATA_VALIDATION_ACCEPTANCE_2026-10-26.md)；它不是发行或线上矩阵验收。

新发行必须固定自己的候选SHA，按**该SHA对应的当前契约**重新执行安装、矩阵、产物及浏览器验收，保存同一交付目录中的`REPORT.md`、`MANIFEST.json`、`SHA256SUMS`和`evidence/`。不得沿用本页旧次数、历史通过结果或未提交工作区作为新提交的证据；本轮仅说明历史边界，没有重新认证发行。公开tag、GitHub Release、PyPI上传不在本次范围内。

## 当时的必需检查（历史清单）

| 范围 | 验收要求 |
|---|---|
| Python / Django | 原有七组精确组合、核心/验证码 × 源码/wheel，共 28 个独立环境；实际版本、导入来源、安装、pip check、系统检查、迁移漂移、测试全部通过 |
| Node / npm | 22.23.3/10.9.9、24.21.0/11.19.0、26.10.0/11.19.1；各自干净安装 40 个锁定依赖；622 前端、121 主题 JS 检查；包清单/锁文件不变 |
| 可选安全集成 | CPython 3.12.15 × Django 5.2.17/6.0.8/6.1.1，固定 Axes 8.3.1、CAPTCHA 0.7.0、Pillow 12.2.0；每组 15 项检查 |
| 发布工具 | 65 项 CI/包/模板工具测试、25 项 runner 测试、23 项静态导出安全检查；CSS 预算、配色对比度、actionlint、三份 Django 模板基线检查 |
| 真实浏览器 | 下列尺寸/语言/外观、搜索 GET、总数链接、侧栏、登录、列表、表单与回退检查；实际截图和几何数据 |
| 固定源码 | 仅提交本次改动，正常推送已有远端；干净副本的完整 SHA 与构建清单一致，不用历史游离提交或未提交树代替 |
| wheel / sdist | 同一固定提交先生成 sdist，再由 sdist 构建 wheel；版本、38 个运行文件、源码/文档、MIT/Django 许可证、静态资源、METADATA、RECORD 和校验和完整 |
| 安装与复建 | 最终 wheel 和 sdist 各在新环境安装、pip check、Django check、页面冒烟；另一干净副本复建并比较包内文件 |

补充当前 Django 安全补丁 5.2.18/6.0.9/6.1.2 的 CPython 3.12.15 组合，使用独立 manifest，不修改原七组矩阵。补充范围、平台与结果均独立记录。

## Python 与 Node 复现

解释器映射、可信 wheelhouse 和完整命令见 [COMPATIBILITY.md](COMPATIBILITY.md)。所有运行目录必须是尚不存在的独立目录。先预检，再执行；不要把其它补丁解释器映射成所需精确版本。

```bash
python django-theme/scripts/test-matrix.py \
  --source /absolute/clean-checkout/django-theme \
  --interpreters /absolute/interpreters.json \
  --root /absolute/new-matrix-run \
  --wheel /absolute/artifacts/nova_django_admin_theme-0.6.1-py3-none-any.whl \
  --find-links /absolute/verified-wheelhouse \
  --no-index --with-captcha --preflight
```

去掉 `--preflight` 执行完整矩阵；也可为每个 `--cell PYTHON/DJANGO` 使用不同目录，最后按 `scripts/ci_support.py verify-reports --scope full` 汇总全部七组。源码变更后，旧轮次只保留作历史对比，不能直接填写新提交通过。

```bash
python scripts/ci_support.py sidebars \
  --wheelhouse /absolute/verified-wheelhouse --output /absolute/new-sidebars
node scripts/ci_node.mjs --node 24.21.0 --npm 11.19.0 \
  --logs /absolute/new-node-logs --sidebars /absolute/new-sidebars
```

另外两组各在独立源码副本中运行对应的真实 Node/npm。主题 JS 的 121 项是三版导航 78 项、列表增强 32 项、验证码 11 项；不能用两版导航的 95 项替代。

## 搜索与页面浏览器复现

2026-10-15 的首次真实浏览器测量证明：旧修复覆盖手机，但 768px 计数宽度仍为 0，中文按钮高度约 139px。Django 的相关规则从 `max-width: 1024px` 开始，因此修复扩展到相同范围。初轮自动检查未断言平板的计数宽度，人工审阅判为未通过；修正后必须重测，不沿用初轮“passed”字段。

1. 按 README 用本次 wheel 启动独立合成 Demo、独立 SQLite 和测试管理员。建立一条名称含 `Layout` 的商品以及其它商品。请求 `/admin/catalog/product/?q=Layout`，确认真实存在 `#changelist-search .quiet`。
2. 在 Chromium 实际渲染 320×812、375×812、390×844、414×896、768×1024、1024×900、1025×900、1280×900；覆盖 `zh-hans`/英文及 Nova 浅色/深色。不能只检查未过滤列表或 HTTP 200。
3. 保存搜索输入、按钮、结果计数及父行的 `getBoundingClientRect()`。所有尺寸要求计数宽度大于 0、按钮不被计数拉高、页面 `scrollWidth <= clientWidth`；1024px 及以下还要求计数位于输入和按钮下方、占父行全宽、短计数不超过两行。1025px/1280px 检查桌面规则。
4. 实际按 Enter 和点击按钮提交 GET，核对 `q` 和结果；点击总数链接后应清除查询并恢复全部商品。过滤器折叠不改变输入值；手机侧栏能展开、Escape 关闭并恢复焦点；桌面侧栏可折叠。
5. 对 Django 5.2/6.0/6.1 的最终安装包分别检查：5.2 无 `.wrapper` 的内联表格必须在自身容器滚动，页面不可被撑宽；填入原行后添加内联行，原值应保留。检查 390/1280px 的首页、完整列表和包含关联控件/内联/保存栏的表单。检查中英文浅/深色登录页；用触摸上下文验证 390px 菜单。`native` 与 `NOVA_ADMIN_ENABLED=False` 不加载 Nova CSS，原生 GET 保留。
6. 表单另覆盖 320/768/1024/1025px，检查 Django 5.2/6.0 的自动完成、双栏选择器和关联按钮不造成页面横向溢出；实际选择/移除标签、添加内联后原值保持。
7. 保存截图、浏览器版本、页面异常和资源失败记录。首次预检发现的缺陷、修复前截图与最终通过截图分别保存；最终安装包还需页面冒烟。

```bash
playwright-cli -s=nova-release-qa open "$NOVA_QA_URL" --headed
playwright-cli -s=nova-release-qa resize 390 844
playwright-cli -s=nova-release-qa snapshot
playwright-cli -s=nova-release-qa screenshot --filename output/playwright/search-390.png
```

完整执行脚本和 JSON 几何数据随交付 `evidence/browser-*.js`、`evidence/browser-*-result.json` 提供。它们使用独立本地站点；运行时替换 URL 并先登录自己的测试管理员。

## 证据边界

本轮实测平台为 macOS ARM64、标准 GIL CPython，以及真实 Chromium 的桌面/手机视口与触摸模拟。浏览器启动、实际导航和截图均必须成功才可填写通过。该证据不等于真实 iOS/Safari/Android 设备认证、Windows/Linux 重跑、free-threaded CPython、生产部署、第三方业务插件或无障碍认证。Docker/PostgreSQL 和可选音频 Flite/SoX 仍需使用它们的目标宿主单独验收；不缩小原安装/支持声明，也不把这些未运行项写成通过。
