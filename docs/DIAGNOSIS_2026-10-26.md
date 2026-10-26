# NOVA Admin 项目诊断报告

- 日期：2026-10-26
- 诊断对象：交互预览 **1.8.0** / 原生 Django 主题 **0.6.1**（git main @ c2c06ce，工作区干净）
- 诊断方式：只读分析，未修改任何源代码
- 范围：`django-theme/`（Python 包与 Demo）、`dist/`（前端预览）、`scripts/`、`tests/`、`ci/` 与 `.github/workflows/`、`docs/`

---

## 0. 总体评价

这是一个**工程投入极不均匀、但底子很好的项目**。

**高于社区平均的部分**：安全与供应链纪律达到资深水准——GitHub Actions 全部 pin 到 commit SHA 并带 actionlint + sha256 校验；构建工具 `--require-hashes` 安装；CSRF 用 `enforce_csrf_checks=True` 真实测试；开放重定向防护（`preferences.safe_admin_return`）拒绝绝对 URL、百分号穿越、反斜杠与控制字符，属教科书级实现；验证码链路有签名 token、`constant_time_compare`、原子消费；模板层 0 处 `|safe` 滥用；第三方许可合规完备（ECharts/Chart.js/uPlot/五套图标库逐一收录 LICENSE）。全仓 0 处 TODO/FIXME/HACK、无裸异常捕获。

**完全缺位的部分**：Python 端与前端均无 lint、无 mypy、无依赖漏洞扫描（pip-audit/npm audit/CodeQL）、无视觉回归测试——这四项"行业底线"设施一项都没有。

---

## 1. 需要改进的问题（按优先级排序）

### 1.1 工程化缺位（影响面最大）

| # | 问题 | 证据 |
|---|------|------|
| 1 | **双端零 lint**：Python 无 ruff/flake8/isort；前端无 ESLint，仅 `prettier --check` + 27 个文件逐一 `node --check` 语法检查 | `django-theme/pyproject.toml` 无任何 lint 工具段；`package.json:9` |
| 2 | **零依赖漏洞扫描**：SHA pin 只保证"没被换"，不保证"没漏洞"。ci.yml 里名为 `security` 的 job 实际是 Optional Axes 互操作测试 | `.github/workflows/ci.yml:227-228`；全仓无 pip-audit/npm audit/CodeQL/Dependabot |
| 3 | **无类型检查**：`django-theme` 是要发 PyPI 的包，src/nova_admin 无 mypy 配置（.gitignore 已预留 `.mypy_cache/`） | `.gitignore` vs 实际无 mypy |
| 4 | **CI 对测试数量的硬编码校验极脆弱**：`ci_support.py` 的 FRONTEND_SUMMARIES 硬编码 19 个前端套件的精确通过总数（如 `'pagination': 'TOTAL 254 pagination checks passed'`），每增删一个测试必须同步改 dict 否则 CI 挂。根因是自造 `console.log('PASS')` 计数 harness | `scripts/ci_support.py:18-38` |

### 1.2 前端结构性债务

| # | 问题 | 证据 |
|---|------|------|
| 5 | **native-admin 41 个变体目录整体复制**：~52,643 行 HTML，light 与 dark 的 changelist.html 546 行仅 18 行差异（title、body class、导航高亮）；`dist/native-admin/static/` 与 `dist/navigation-lab/static/` 各持一份 base.css(1,385 行)/theme.css(1,251 行)/responsive.css(857 行)。一处修改需同步 41+ 处且无测试保护 | `dist/native/*/changelist.html` vs `dist/native/dark/changelist.html` |
| 6 | **零视觉回归测试**：484 个用例 / 1,452 个 assert 全部是 jsdom 行为断言；全仓 grep `puppeteer|playwright|screenshot|pixelmatch` 零命中。41 个视觉变体的正确性全靠人工 | `tests/*.cjs` |
| 7 | **app.js 1,230 行单体编排层**：路由、渲染、表单校验、CSV 导出、命令面板、主题切换混杂；`userResults()` 为单行 2,000+ 字符巨型模板函数。主题切换逻辑在 app.js / login.js / extensions-guide.js / preferences-init.js **4 处重复实现**（各自读写 `nova-theme`）。chart-lab.js(521 行) 与 analysis-lab.js(594 行) 的 mount/dispose/theme 帧管理骨架平行复制 | `dist/js/app.js`；`dist/js/chart-lab.js` vs `dist/js/analysis-lab.js` |
| 8 | **innerHTML 转义不一致**：有统一 `esc()`（app.js:56-61）且 CSV 导出有公式注入防护（app.js:700），但 `table()`/`userResults()` 中 `u.role`/`u.team`/`u.joined` 裸插值，数据源为可篡改的 localStorage | `dist/js/app.js`；`dist/js/catalog.js` 等 34 处 innerHTML |
| 9 | **styles.css 90.7KB / 261 行超长行**：prettier 只覆盖 `dist/js/*.js`，CSS 不在格式化范围 | `dist/styles.css` |
| 10 | **localStorage 键随路径增殖**：`nova.preview.navigation.v2.<pathname>` 按部署路径动态生成，路径变化产生永久孤儿键，无清理或版本迁移 | `dist/js/navigation.js` |

### 1.3 Python 包与发布质量

| # | 问题 | 证据 |
|---|------|------|
| 11 | **包测试与 demo 项目强耦合**：45 个测试必须经 `python demo/manage.py test tests` 运行，`tests/test_theme.py:12` 直接 `from catalog.admin import ProductAdmin`；tests/ 还混入 9 个非测试 settings/urls 模块。包无法在隔离环境独立验证发布物 | `django-theme/tests/` |
| 12 | **可选依赖声明不完整**：`src/nova_admin/slider.py:11` 导入 `nova_slider_captcha`，但 pyproject 无 `slider` extra、requirements-test.txt 未列，`tests/test_slider.py` 默认整文件 skip——该模块在默认 CI 中是零覆盖死代码 | `django-theme/pyproject.toml` |
| 13 | **未声明的传递依赖**：`src/nova_admin/captcha.py:25` 直接 `from ranged_response import RangedFileResponse`，`django-ranged-response` 不在任何 extras 中，仅靠上游 simple-captcha 传递解析（test-matrix.json 固定 0.2.0），上游换依赖即断链 | `django-theme/src/nova_admin/captcha.py` |
| 14 | **元数据不一致**：`requires-python >= 3.10`（3.10 已 EOL 且从未验证），classifiers 与测试矩阵最低均为 3.11.17；`Development Status :: 3 - Alpha` 与 0.6.1 版本号及文档成熟度不符 | `django-theme/pyproject.toml:10,14` |
| 15 | **视图逻辑散落**：preference 视图写在 `urls.py:16-33`；`captcha.py`（204 行）同时承担表单字段、widget、两个视图、工具函数四种职责，无统一 views 模块；`navigation.py:72-73` 与 `:83-84` 两段几乎相同的 icon 装饰三元表达式重复 | `django-theme/src/nova_admin/` |

### 1.4 仓库卫生

| # | 问题 | 证据 |
|---|------|------|
| 16 | **过程性文档污染**：`docs/DIAGNOSTIC_PROGRESS.md`（312 行）含私有 `codex://threads/...` 会话链接；`docs/REFACTOR_NOTES.md` 标题仍是 1.5.1 时期、正文写着"主题版本仍为 0.3.0"（已过时两个版本）；`review/` 入库了评审截图 PNG、patch。合计约 800+ 行一次性记录，34 个 md 可瘦身到 ~25 个 | `docs/`、`review/` |
| 17 | **双轨版本无同步约束**：release-candidate.yml 只校验 tag 与 pyproject 版本一致，完全不管 package.json 的 1.8.0；README 首行版本号手工维护；预览轨无 CHANGELOG（历史散落在 README"本轮"叙述与 docs 中）；`ci_artifacts.py` 仅分别记录并回读，非同步约束 | `.github/workflows/release-candidate.yml:37-39` |
| 18 | **根目录 997 个 tracked 文件中 dist/ 占 697 个（70%）**：这是"无构建、dist 即交付物"的设计决定，但 icons.json（238KB）全量随 Python 包分发、ECharts（1.12MB）未按需裁剪使 wheel/预览体积偏大 | `git ls-files` 统计 |
| 19 | **demo 工程碎片化**：`demo/config/` 15 个模块靠 `from .X import *  # noqa: F403` 链式继承，变量来源需逐层追踪；`demo/templates/project_admin/` 存放导出样本 HTML（fieldset_52.html 等），位置语义混乱 | `django-theme/demo/` |

---

## 2. 建议新增的功能

### 2.1 Django 主题端（对宿主项目最有价值）

1. **全局 ⌘K 命令面板 / 跨模型搜索**：预览已有（`dist/js/navigation.js`），Django 端可做成视图 + 模板标签，按权限过滤、一键跳转任意模型 changelist。这是 Unfold/Grappelli/Jazzband 系竞品的核心卖点，也是本主题最大的差异化机会。
2. **变更历史字段级 diff**：admin 自带 LogEntry 只有"改了什么对象"，字段级高亮对比（旧值 → 新值）是运营/审核高频刚需。
3. **审计日志可选 extra**：who/when/what/where，与现有 axes 桥接同模式（宿主显式 opt-in，核心零依赖）。
4. **未保存离开警告 / changeform 草稿自动暂存**：长表单的表单保护，纯前端可做（预览端已有类似模式）。
5. **Excel/PDF 导出**：CSV 已有（含公式注入防护），补全格式，可参考 django-import-export 集成模式做成可选 extra。
6. **changelist 列宽/列显隐记忆**：布局偏好存 session，与现有 mode/palette 偏好体系（CSRF + frozenset 白名单）完全同构。
7. **MFA / 无障碍替代认证**：README 自己承认"生产限流、MFA、无障碍替代认证仍需项目验收"，可并入 `security` extra。
8. **暗色模式下的图片/媒体反色策略**：暗色 admin 下白色截图刺眼是常见痛点，可提供 per-model 或全局配置。

### 2.2 前端预览端

9. **视觉回归 CI**：Playwright 截图对比，与 native-admin 变体模板化（问题 5）天然配套，一次建设同时消除两个最大风险。
10. **`responsive.html` 风格收敛**：当前是硬编码颜色 + 2 处内联 onclick 的孤岛，与全仓 CSP 友好、token 化风格不一致。
11. **测试 harness 迁移到 `node:test`**：19 个 .cjs 各自复制 `check/wait/tick/route` 样板（约 150-250 行重复），迁移后获得失败摘要、机器可读报告、并整体删除 ci_support.py 的硬编码 dict（问题 4）。

### 2.3 生态与发布

12. **PyPI 正式发布 + mkdocs-material 文档站**：0.6.1 已具备发布质量，Alpha 标记是自我设限；34 个 md 正好可作为文档站素材池（瘦身同步进行）。
13. **共享 login.css 做成可安装资源**：`sync-login-css.cjs` 单源同步机制已验证，可评估发布为可安装静态资源包。
14. **Django 官方生态联动**：向 django-packages / awesome-django 提交条目，获取真实用户反馈驱动路线图。

---

## 3. 已知风险边界（README 自认，属已知而非新发现）

Docker/PostgreSQL 运行、音频验证码（Flite/SoX 未安装验证）、旧 admin-honeypot、物理真机测试均未实测。`dist/native-admin/` 是只读快照，登录/输入行为不能据此验收。浏览器视觉检查使用 iframe，不是真机。

---

## 4. 建议行动顺序

1. **第一周（半天成本级）**：ruff（Python）+ ESLint flat config（前端）+ pip-audit/npm audit 步骤进 ci.yml；修正 pyproject 元数据（requires-python、Development Status）。
2. **第二步（消除最大组合风险）**：native-admin 41 变体模板化生成（复用 build_icons.py 模式）+ Playwright 视觉回归。
3. **第三步**：包测试与 demo 解耦（独立 tests 项目或 tox/pytest 布局）；补 slider extra 与 ranged-response 显式声明。
4. **第四步**：app.js 按视图域拆分、抽公共 theme.js；测试 harness 迁 node:test，删 FRONTEND_SUMMARIES 硬编码。
5. **持续**：文档瘦身（移除过程性记录）、双轨版本一致性检查脚本、然后考虑 PyPI 正式发布。

---

*本报告为只读诊断，未修改任何源代码。三路探索证据（文件路径、行数、代码片段）已在生成时逐一核对。*
