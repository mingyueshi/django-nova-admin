# 诊断整改与独立验收台账

日期：2026-10-23（Asia/Shanghai）。基线：`05c656ad4a07ccad3670bec7f0a691a8f952e132`。

实施：[增加更多暗色配色方案](codex://threads/01a166ed-0e0f-7253-a9aa-e2d6800617d8)。当前会话负责复核报告、单项派发、代码审查与独立验收。下一项仅在上一项验证通过或明确记录外部阻塞后派发。未经新指令不提交、推送、发布或部署。

| 顺序 | 项目 | 状态 | 验收要求 |
|---|---|---|---|
| 0 | 报告事实复核 | 已完成首轮 | 已纠正 R3/T1/T4/D3、历史测试混用与功能范围推断；原报告保存于本地证据目录 |
| 1 | R2 模板选择 | 本地验收通过 | 三版核心各349通过/2跳过；统筹独立重跑6.1.1及6个基线选择检查通过；不声明6.2支持 |
| 2 | R3 现有告警 | 本地说明已纠正；线上待验证 | 原始失败已定位；官方main源码下载受网络阻塞，本轮没有远端重跑 |
| 3 | R1 共享登录样式 | 本地验收通过 | 字节一致/只读检查及4项回归、1274项前端、12组合浏览器、153页导出来源检查通过 |
| 3.1 | R3b CI 前端摘要契约过期 | 本地验收通过 | 真实18套件/1274项及121项主题JS摘要通过；7类独立故障注入均拒绝；82项脚本回归通过 |
| 4 | T1 当前平台证据 | 已更新 | R2/R1/R3b实际运行于macOS ARM64；不将其拆成两组平台或冒充完整矩阵 |
| 4.1 | T2 容器/PostgreSQL | 启动超时，未验收 | 配置解析/core镜像构建完成；300秒超时后PG健康、web仅Created；应用连接/迁移/登录未跑，未重发启动 |
| 5 | T3/T4 音频、设备及辅助技术 | 未验收，边界已明示 | PATH中无Flite/SoX；未做物理真机或屏幕阅读器操作；F1–F6保留为候选需求 |

## 基线复核证据

- 远端：`https://github.com/mingyueshi/django-nova-admin.git`；本地 main 比跟踪分支多 3 个提交。未执行推送。
- 本机：macOS 27.0.1 / ARM64；Python 3.12.14、Django 6.1.1 可用；Node 24.21.0。Docker Engine 29.9.2 的 Linux ARM64 daemon 可达，只说明环境可用。
- 统筹独立执行 `npm test`：1270 项 PASS；`python3 scripts/build_icons.py --check`：320 图标、5 库登记一致；`python3 scripts/test_palette_contrast.py`：2908 个声明角色检查通过。
- [线上快速 CI](https://github.com/mingyueshi/django-nova-admin/actions/runs/38677768095)：`121a3e0`，通过；不代表本轮 HEAD。
- [线上定时预警](https://github.com/mingyueshi/django-nova-admin/actions/runs/39241104648)：2026-10-19，本仓库 `121a3e0` / Django main `11af25c0ae06c8275ebb8def8b8ca777a5660ed6`。模板状态 reviewed；335 项回归报 55 errors、2 skips（54 个版本闸门异常、1 个版本映射 KeyError）。明确为失败证据。
- 本地证据目录：`.local/diagnostic-review-20261023/`。包括原报告备份、基线 SHA、GitHub 元数据、下载的原始 artifact、前端与资源检查日志。该目录被 Git 忽略；关键结论同步到本台账。

## R2 验收记录

实施改动为 `project_admin_template` 按原生模板完整内容 SHA-256 选择已审查片段，未知类型、读取失败或未审查模板明确报错；去除测试的 minor 版本字典索引。三份 fieldset、两份 tabular 片段本身未变，支持区间仍 `<6.2`。

- 实施自测：Python 3.12.14 / Django 5.2.17、6.0.8、6.1.1，各执行351项，349通过、2跳过、0失败/错误；每版27项本地化定向检查通过。原先从错误目录发现0项的运行已保留，但不计通过。
- 统筹独立验证：同平台 Django6.1.1 完整351项（349通过、2跳过）；从 `ci/template-baselines.json` 读取原生基线，验证三版共6个选择结果均匹配，模拟6.2元数据不影响选择。源码哈希保存在 `r2-source-hashes.json`。
- 2项跳过分别为未启用的 CAPTCHA 与 security 集成占位；本轮不视作可选集成已通过。
- 新增测试覆盖未知模板、未知kind、读取失败、匹配后模板变化、真实表单/Inline与主题移除。统筹代码审查未发现阻断问题。
- 官方 main 固定 SHA 的源码拉取未完成（GitHub直连网络失败），真实 main 本地重跑与线上恢复均未验收；历史错误日志不改写。

## R1 验收记录

- 唯一来源为主题 `login.css`；`npm run sync:login-css` 显式同步预览，`npm run check:login-css` 只读检查并在漂移时非零。`npm check` 已接入该检查；没有新增依赖。
- 统筹独立运行 `npm test`：1274项 PASS（原1270 + 新4项共享CSS检查）；CSS预算通过。新增约1.3KB来自主题已有样式，预算只更新对应文件，未放宽其它文件。
- 统筹 Chromium 验证 mock/真实只读样本 × 明/暗 × 1440/390/320px，共12组合：无横向溢出、品牌/控件越界、破图或 pageerror，键盘焦点可见；真实样本保持禁用表单。已查看手机深色与桌面真实浅色截图。不是动态 Django 登录或屏幕阅读器验收。
- 新样本由现有导出器实际生成：153页校验通过，全部来源哈希与当前源码一致。HTML未变化；更新来源清单及39张随机合成验证码PNG，不以手改哈希冒充重新生成。
- Chromium自动探测 `/favicon.ico` 返回404，单列为非业务请求；不宣称所有console输出为0。功能资源、图片及脚本异常检查通过。
- 证据：`.local/diagnostic-review-20261023/r1-npm-test.log`、`r1-css-budget.json`、`r1-browser.json`、`output/playwright/r1-*.png`；实施导出记录在 `.local/r1-login-css-20261023/`。

## R3b 验收记录

CI收集器原有13套件/622项契约已更新为当前18套件/1274项；增加 `package.json` 中 npm test 顺序与套件登记的一致性检查。完整收集器仍检查runtime、安装/步骤状态、输入hash和完整报告；新增 `check-node-summaries` 明确只输出摘要契约专项，不提供完整CI回执。

- 统筹独立使用本会话实际日志：前端1274项、三版原生导航78项、列表增强32项、验证码增强11项；18组前端及121项主题JS摘要均接受。
- 统筹在临时日志副本注入缺失、重复、FAIL、数量错误、同总数挪动、未知摘要、旧配色计数，7类均拒绝。未修改真实日志。
- `python3 -m unittest discover -s scripts/tests -v`：82项通过。未触发线上CI、重装依赖或伪造安装/运行时证据。
- 证据：`.local/diagnostic-review-20261023/r3-node-independent.json`、`r3-scripts-tests.log`、`r3-node-real-logs/`。

## T2 隔离验证记录

- 隔离目录：`.local/t2-compose-20261023-kqhq7mlz/input-src`；Compose项目 `nova-local-079f0eef8f91`，只规划 `127.0.0.1:4189`。统筹独立核对188个输入文件，副本与工作区都符合输入清单；原示例未生成 `.local` 状态。
- Docker Engine29.9.2 / Linux ARM64，Compose5.6.1；真实 `config --quiet` 通过。使用原固定 Python3.12.15、PostgreSQL17.11、Django5.2.17、psycopg3.3.6，未换版本。
- 首次 `demo.py up --no-captcha --port 4189` 达300.009秒总超时，exit124。日志确认core镜像已经构建完成；超时后独立读回PG为running/healthy，web仅Created。超时原因不能仅凭此归结为应用缺陷；不得记作启动成功。
- 未运行：应用的PG连接、迁移、两站真实登录/权限/保存/重复启动、CAPTCHA构建与并发消费。未用SQLite补充成PG通过，也未自动重发up/start。
- Python基础镜像解析到 `sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70`；PostgreSQL镜像为 `sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27`。镜像获取/构建结果与应用运行验收分开记录。
- 证据：隔离目录上一级的 `input-manifest.json`、`core-up.json`、`core-up.log`；统筹目录中的 `t2-input-independent.json`、`t2-timeout-readback.json`、`t2-cleanup-independent.json`。
- 收尾独立确认：本项目容器和网络均已移除，4189端口关闭；保留唯一专用PostgreSQL卷及两份0600密钥，原示例状态未变化。未执行全局清理。后续应在当前会话继续统筹、复用同一隔离输入/卷/密钥处理T2，不换项目或秘密绕过未验收状态。

## 验收边界

尚未执行本轮完整 Python/wheel/可选依赖矩阵、生产部署、物理真机、屏幕阅读器及音频播放验收。历史发布记录不自动归属于本轮源码。线上闭环需要之后对获准提交/推送的精确 SHA 读取结果，不能用本地通过冒充。

本轮三个代码整改单项（R2、R1共享登录CSS、R3b）已独立验收；T2首轮验证因启动超时保留未验收状态。整改验收结束时尚未提交Git，原有本地3个提交保持不变。实施会话已收到本轮收尾指令；未派发F类功能扩展。

2026-10-23，用户随后授权提交本地Git，本次提交收录上述整改、重新导出的样本及诊断文档。提交前已复核7个验收源码哈希与共享登录CSS一致性；本地证据、隔离环境与密钥不纳入Git。未推送、发布或生产部署；T2未验收状态保持不变。

---

## 2026-10-24 复诊记录

### 台账整改落地独立复核

| 项 | 复核结果 | 证据 |
|---|---|---|
| R1 共享登录 CSS | 已闭环 | `npm run check:login-css` 通过，source/target SHA-256 均为 `957cbcd6…`，逐字节一致；`sync:login-css`/`test:shared-css` 命令在 package.json 中 |
| R2 模板选择 | 已落地 | `demo/catalog/templatetags/project_admin.py` 采用原生模板完整内容签名选择 |
| R3b CI 前端摘要契约 | 已落地 | `scripts/ci_support.py` 契约更新，测试数基准同步 |
| R1/R2/R3b 合入 | 已提交 | 对应 `21a56b9` 及后续提交 |

### 工作区新增未提交改动：品牌名称 + 首字母占位（替代硬编码 "N"）

范围 23 文件：后端 `branding.py`（`name` 字段 + `brand_initial()`）、`nova_tags.py`（`nova_brand` 标签）、3 个模板、`theme.css`；前端 `dist/js/branding.js`（新）、`app.js`、`login.js`、`login.html`、`styles.css`、`login-preview.css`；测试 `test_branding_tokens.py`（+65 行）、`presentation.cjs`（+13 项）、`login-demo.cjs`、`palettes.cjs`；文档/CI `BRANDING.md`、`README.md`、`CI_CD.md`、`css-budget.json`、`ci_support.py`。

- 质量：实现 + 前后端测试 + 文档 + CI 预算完整闭环，前端测试总数 1284 → 1297。
- 独立验证：`npm run check` 全通过（含新 `branding.js`）；`test:presentation` 38 项、`test:login` 44 项通过；Python/JS 语法与 lint 无错误。
- 顺带修复真实缺陷：`base_site.html` 覆盖 `branding` block 时补回 Django 原版的 `{% if user.is_anonymous %}{% include "admin/color_theme_toggle.html" %}{% endif %}`（三版基线均含该模板，5.2/6.0/6.1 均安全）。
- 发现 3 个小问题（P3，非阻塞）：
  - N1 品牌名长度前后端不一致：前端 `brandName()` 截断 64 码点，后端 `branding()["name"]` 仅 `.strip()` 无上限且进 `<title>`。
  - N2 `nova_tags.py` 跨模块导入私有 `_text`（`from nova_admin.branding import brand_initial, _text`），破坏封装。
  - N3 `base_site.html` title block 用 `{% with site_title=… %}{{ block.super }}{% endwith %}` 覆盖变量，可读性差。

状态：未提交 Git；未运行完整 Django 矩阵（branding 后端新增 `nova_brand`/`name` 字段的 3 版矩阵回归待跑）。

### 仍开放项

- T2 Docker/PostgreSQL：首轮启动 300s 超时，应用连接/迁移/登录未执行，未验收。
- T3 音频验证码：无 Flite/SoX，未验证。
- T4 真机 / 屏幕阅读器：未做操作验收。
- branding 改动的后端三版矩阵回归与提交。
