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
| 4.1 | T2 容器/PostgreSQL | 2026-10-24 本地已独立验收并清理 | core/CAPTCHA真实构建、PG连接/迁移、双站业务、并发/回滚、完整启动器重复up及原卷down/up通过；历史首次300秒超时保留，收尾见本页末 |
| 5 | T3 音频验证码 | 正常配置本地生成/原生播放已独立验收；上游异常边界保留 | 临时容器Flite/SoX真实生成、双站原生/无JS播放、刷新与登录回归通过；过期音频200、进程超时/失败残留未修复，见本页T3记录 |
| 6 | T4 设备及辅助技术 | 未验收 | 未做物理真机、屏幕阅读器或人工听辨；其他浏览器未测；F1–F6仍为候选需求 |

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

尚未执行本轮完整 Python/wheel/可选依赖矩阵、生产部署、物理真机、屏幕阅读器及人工听辨。T3正常配置下的本地生成/原生播放已在2026-10-24单独验收，异常路径仍保留。历史发布记录不自动归属于本轮源码。线上闭环需要之后对获准提交/推送的精确 SHA 读取结果，不能用本地通过冒充。

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

### 复诊当时的工作区改动：品牌名称 + 首字母占位（替代硬编码 "N"）

以下为当时记录；品牌修复随后已随CP1提交至`4f58b35`。2026-10-24本次Git收口复核确认：N1已统一64码点上限，N2已改用公开的`normalize_brand_name`，N3已改为明确的title模板；不再列为当前未处理项。后续验收记录见`FEATURE_PROGRESS.md`。

范围 23 文件：后端 `branding.py`（`name` 字段 + `brand_initial()`）、`nova_tags.py`（`nova_brand` 标签）、3 个模板、`theme.css`；前端 `dist/js/branding.js`（新）、`app.js`、`login.js`、`login.html`、`styles.css`、`login-preview.css`；测试 `test_branding_tokens.py`（+65 行）、`presentation.cjs`（+13 项）、`login-demo.cjs`、`palettes.cjs`；文档/CI `BRANDING.md`、`README.md`、`CI_CD.md`、`css-budget.json`、`ci_support.py`。

- 质量：实现 + 前后端测试 + 文档 + CI 预算完整闭环，前端测试总数 1284 → 1297。
- 独立验证：`npm run check` 全通过（含新 `branding.js`）；`test:presentation` 38 项、`test:login` 44 项通过；Python/JS 语法与 lint 无错误。
- 顺带修复真实缺陷：`base_site.html` 覆盖 `branding` block 时补回 Django 原版的 `{% if user.is_anonymous %}{% include "admin/color_theme_toggle.html" %}{% endif %}`（三版基线均含该模板，5.2/6.0/6.1 均安全）。
- 发现 3 个小问题（P3，非阻塞）：
  - N1 品牌名长度前后端不一致：前端 `brandName()` 截断 64 码点，后端 `branding()["name"]` 仅 `.strip()` 无上限且进 `<title>`。
  - N2 `nova_tags.py` 跨模块导入私有 `_text`（`from nova_admin.branding import brand_initial, _text`），破坏封装。
  - N3 `base_site.html` title block 用 `{% with site_title=… %}{{ block.super }}{% endwith %}` 覆盖变量，可读性差。

状态：未提交 Git；未运行完整 Django 矩阵（branding 后端新增 `nova_brand`/`name` 字段的 3 版矩阵回归待跑）。

### 复诊当时的开放项

- T2 Docker/PostgreSQL：首轮启动 300s 超时，应用连接/迁移/登录未执行，未验收。
- T3 音频验证码：无 Flite/SoX，未验证。
- T4 真机 / 屏幕阅读器：未做操作验收。
- branding 改动的后端三版矩阵回归与提交。

### 2026-10-24 Git收口时的剩余事项

- T2 Docker/PostgreSQL应用连接、迁移、登录等链路仍未验收；保留原隔离输入、卷与密钥，不把构建完成记成应用通过。
- T3音频验证码、T4物理真机/屏幕阅读器仍未验收。
- R3真实Django main回归与精确提交的线上CI闭环仍待完成；本轮完整Python/wheel/可选依赖矩阵未运行。
- 品牌修复与CP1已在`4f58b35`提交；PR1/NM1/PF1本地独立验收完成并纳入本次用户授权的Git提交。其余功能建议仍为后续候选，详见`FEATURE_ROADMAP.md`与`FEATURE_PROGRESS.md`。本次未推送、发布或部署。

## 2026-10-24 T2 继续验证

用户要求先处理T2，保持原实施会话执行、当前会话逐项独立验收。基线为`243effb0569591f2732831a0650cac99c9f8e704`；不因继续验证自动提交、推送、发布或部署。

- T2-1A只读复诊已派发；统筹独立确认原项目无容器/网络、4189无监听，原专用卷和两份0600密钥仍在，原示例未生成本地状态。证据：`.local/t2-review-20261024/preflight.json`。
- 后续依次为：当前源码输入核对与一次有界core启动 → PostgreSQL迁移、双站登录/权限/保存 → CAPTCHA构建与真实并发/回滚 → 重复启动、卷持久化和清理。每步通过后才派发下一步；不将健康检查、SQLite或历史结果代替对应验收。
- 当前状态仍为T2未验收；历史300秒超时记录保留。实际根因须以复诊与新运行证据确认，不先假定为应用缺陷。

### T2-1A / T2-1B：复诊与core启动已独立验收

- 历史输入188份均符合旧清单；按当前提交最小同步25改、34新，共222份输入，原卷、密钥和options保留。统筹独立比对全部输入及本次复诊前后的密钥哈希一致；历史没有密钥内容哈希，不声称跨日身份已由哈希证明。
- 旧300秒上限包含镜像解析/获取、构建与启动。日志中Python元数据83.8秒、基础镜像148.9秒，按时间近似估算PG启动时只余约4秒。底层web Starting未完成原因不能仅据此确诊。
- 本次固定原镜像digest，core单次构建39.271秒、单次无构建/无拉取启动12.179秒，均退出0。未修改应用代码，未自动重试；旧超时仍为失败记录。
- 统筹直接检查运行容器：Python3.12.15 / Django5.2.17 / psycopg3.3.6 / PostgreSQL17.11，认证SQL连接成功、0待迁移、2合成商品/1会员/1新闻、当时0用户；容器内222份输入全部匹配。db/web均healthy，web仅绑定127.0.0.1:4189，数据库无宿主端口；无密钥被COPY进源码目录。
- 真实Chromium打开admin登录页正常，favicon自动请求404单列。证据：`.local/t2-review-20261024/input-sync-independent.json`、`core-independent.json`；实施构建/启动回执在`.local/t2-continue-20261024/`。T2-2双站业务流程已派发，整项T2仍未关闭。

### T2-2：双站业务流程已独立验收

- 统筹使用独立随机合成超级用户，在真实Chromium分别登录warehouse/admin并保存KEYBOARD；实际分类自动补全、标签、多字段及inline保存有效。另用独立view_product-only账号分别登录两站，列表/只读详情200，无保存/新增入口，直接新增、携带有效CSRF的修改POST及分类访问均403。
- 两站缺CSRF请求拒绝，偏好携带另一站next仍返回当前站；core阶段两站没有CAPTCHA入口。浏览器0pageerror，预期403/favicon404单列，不当成所有网络请求成功。
- 直接PG读回统筹持久化哨兵：名称“T2 统筹持久化哨兵 20261024”、价格101.25、库存37、分类1、原标签和规格值“统筹标准款”。截图已目视检查。证据：`core-anonymous.json`、`core-save.log`、`core-workflow.log`、`sentinel-before-restart.json`。实施仅编辑ORGANIZER，两会话数据分开。
- 统筹准备时一次点到排序表头、一次使用当前CLI不支持的network命令，均非验收用例；后续以明确的表单步骤和读回结果完成验证，不计入通过数。T2-3A CAPTCHA构建/登录已派发，整项T2仍未关闭。

### T2-3A / T2-3B：CAPTCHA与PostgreSQL边界独立验收

- CAPTCHA单次构建48.648秒、单次启动9.922秒，均退出0；仍为原项目/卷/密钥。实际django-simple-captcha0.7.0、Pillow12.2.0，测试模式/挑战池关闭。统筹重新检查222输入、认证SQL、0待迁移、4个合成账号与既有数据。
- 统筹真实Chromium在admin/warehouse各验证：图片200、UI刷新200、刷新GET405、缺CSRF403、旧挑战刷新409、错误答案不登录且消费挑战、正确答案登录302并消费挑战、退出登录。读取的是本地合成挑战答案，未启用测试绕过。首次统筹脚本误用图片CSS选择器超时，失败记录保留；修正为实际data-captcha-image后才完成验收。
- 统筹独立PG脚本5个场景通过：两个实际backend PID同步读同一行只有一方成功消费；外层事务回滚恢复挑战，之后可正常提交；一方删除后回滚、竞争方等待后成功提交；数据库删除异常向上传播且认证后端零调用；错误答案消费挑战且认证后端零调用。仅创建/清理本脚本挑战，未清全表。事务回滚恢复数据是记录下来的数据库契约，不宣称挑战删除可以跨外层回滚持久化。
- 证据：`.local/t2-review-20261024/captcha-runtime-independent.json`、`captcha-browser-independent.json`、`pg-captcha-independent.json`。实施方回执与统筹结果分别保留。重复启动、down/up持久化和最终清理尚待验证，整项T2仍未关闭。

### T2-4：重复启动与原卷恢复已独立验收

- 原始`demo.py up`重复运行一次，2.015秒退出0；`demo.py down`一次3.727秒退出0。统筹独立确认容器/网络已移除、4189关闭、原卷及0600密钥保留后，才派发原始`demo.py up`从原卷恢复，11.982秒退出0。每一步单次执行，失败或结果不明不自动重发。
- 统筹分别在重复up和down/up后直接读取PG，与独立基线完整比较：2商品的名称/价格/库存/分类/标签/inline、4账号的身份/权限/密码哈希均不变；卷名及创建时间、本次复诊后的密钥哈希不变，0待迁移，容器内222输入仍匹配。主题实际安装在site-packages的61份资源也与源码逐字节一致。
- 恢复后，统筹真实Chromium用原测试账号密码及新的真实验证码重新登录，在admin和warehouse两站读回KEYBOARD哨兵全部正确，0pageerror，随后正常退出并关闭统筹浏览器。证据：`repeat-up-independent.json`、`down-independent.json`、`restored-persistence-independent.json`、`restored-runtime-independent.json`、`restart-browser-independent.json`、`installed-package-independent.json`。
- 实施额外提供实际PG行锁超时`55P03`、认证入口/后端零调用及正向认证对照；统筹审阅脚本和回执，其自己的异常路径检查使用显式DatabaseError注入，两个证据来源不混同。全部新挑战仅按所属ID清理。
- 本次没有发现需要修改应用代码的缺陷；通过将构建和启动分开计时补齐运行证据，未放宽产品默认超时。T2本机Linux ARM64容器运行闭环已接受。T3音频、T4真机/读屏、完整CI/安装矩阵及生产部署仍不在本轮结论内。

### T2最终收口

最终单次`demo.py down`用时3.617秒、退出0。统筹独立确认本项目容器/网络为空、4189关闭，同一专用卷保留、两份0600密钥哈希未变、原示例未生成`.local`；两个临时凭证/答案桥端口60319/61609无监听且原PID均不存在，双方临时浏览器已关闭。专用卷、密钥、合成账号与证据保留供后续复查，没有全局清理。证据：`final-cleanup-independent.json`、`final-helpers-independent.json`。

T2已完成本地独立验收并关闭。源码运行基线为`243effb`，验收时仅更新诊断/功能状态和Compose验证文档，未新增应用代码改动，也未提交、推送、发布或部署。用户随后授权提交Git，本次提交收录这四份文档；未推送、发布或部署。当前会话继续统筹的下一未验收项为T3音频；T4真机/读屏、R3线上CI及完整矩阵仍保留。汇总回执：`.local/t2-review-20261024/verification.json`。

## 2026-10-24 T3：正常配置本地音频生成/原生播放验收

### 隔离基线与原行为

- 用户要求T2提交后继续下一项；T2四份文档已提交为`b4e636ce933d821ef53e0dbf61d7942e49c670ea`，未推送。T3从该提交另建222份tracked输入，项目`nova-t3-audio-20261024`、回环4193、新库`nova_audio_t3`、独立卷和新0600密钥；T2项目/卷/密钥/账号/哨兵及历史证据未复用或改写，原`examples/compose/.local`仍不存在。
- 主机没有安装Flite/SoX。工具只装入临时Docker层，实际为Flite/libflite1 2.2-5、SoX/libsox3/libsox-fmt-base 14.4.2+git20190427-3.5；容器Python3.12.15、Django5.2.17、PG17.11、psycopg3.3.6、captcha0.7.0、Pillow12.2.0，TEST_MODE/POOL均False。首次独立构建104.037秒、启动11.527秒，均单次退出0。
- 两站真实HTTP生成有效WAV，样本为2秒/8kHz/16bit/mono、PCM非零；同挑战两次完整GET摘要不同，GET不消费。实际CSRF刷新200、旧音频410、新音频200。原UI的真实Chromium点击只触发下载，页面不变且audio元素为0，不能记作播放通过。
- 原输入、临时overlay和baseline镜像标识均保留。实施证据`.local/t3-audio-20261024/`，统筹独立证据`.local/t3-review-20261024/runtime-baseline.json`、`audio-http-baseline.json`、`original-ui-baseline.json`。

### 单项播放体验修复与独立复验

- 仅增加带可访问名称的原生`audio controls preload="none"`和明确下载备用入口，不自动播放。刷新开始立即pause、删除src并隐藏旧媒体/下载入口；新key保留用于恢复，只有新图准备好后才同步新image/audio；失败不继续播放已消费的旧码。下载新增文案补齐中文po/mo，样式仅加宽度/hidden规则。未改音频后端、上游依赖或正式Compose默认音频设置。
- 候选基于`b4e636c`未提交差量，内容标识`c15d49273175c2eeaa5a05c7151d3ca450d3426ce4b70c4489d8e2f44e550c22`；222份候选输入中8份变化，另2份CI汇总契约联动11→15。候选镜像`nova-t3-audio-20261024-web:candidate-c15d49273175`单次构建49.305秒、启动9.635秒退出0；实际222输入和61安装资源匹配。正式文档在运行验收后更新，没有将文档差量冒充重新构建的候选。
- 实施用鼠标点击、统筹用键盘Space分别完成两站真实原生控件播放，均读回playing/timeupdate/ended及currentTime推进至2秒、无autoplay、HTTP206、无下载误触；双方另验证无JS两站原生键盘播放，下载备用入口有效。刷新挂起时旧音频即paused/hidden/src删除；真实刷新200后新音频可播，旧URL410；真实消费后模拟503响应丢失也保持媒体清空和登录锁定。320/375px无横向溢出，截图已目视检查，0pageerror；注入的预期503网络错误单列。
- 实施相关单测：15项JS、45项Django5.2.17验证码/i18n（宿主Python3.12.14）、56项CI汇总契约通过；msgfmt检查和原CSS预算通过（captcha.css 2011 bytes / gzip769）。统筹独立重跑15JS、45项Django6.1.1（宿主Python3.12.14）和56项契约，并完成实际图像/刷新/错误拒绝/成功登录/单次消费回归。没有运行完整Python/wheel矩阵或线上CI。
- 核对脚本失败保留：默认Django Client的testserver不在临时web的ALLOWED_HOSTS中，原辅助GET400且尚未发POST；指定真实Host后使用新挑战完成检查。无JS下page.waitForFunction页面内轮询超时，改用Playwright外部等待/显式evaluate读回后才通过；不改应用、不将第一次失败写成通过。临时候选runner曾在Docker调用前比较错输入路径，修正runner后才首次执行config/build/up；不是镜像或应用失败。
- 独立证据：`runtime-candidate.json`、`player-candidate-independent.json`、`nojs-candidate-independent.json`、`login-candidate-independent.json`、`unit-tests-independent.json`。实施候选清单/回执、浏览器日志、初次失败均在`.local/t3-audio-20261024/`保留；双方结果分开。

### 未修复边界及范围

- **过期但仍存行**：上游音频仅按hashkey查询，仍能200；表单过期验证拒绝并消费后才410。这与已消费行直接410不是同一测试，不宣称到期音频已拒绝。
- **工具与临时资源异常**：上游subprocess没有显式timeout/check。缺Flite/SoX路径会异常，非零退出会404或异常；缺少/失败SoX在本次独立脚本中留下1个源WAV。正常与并发两个GET的命名临时文件为0；FD在响应close及对象释放/GC的生命周期分别记录，未承诺全部异常/流中断收尾可靠。仅清自己新建挑战及case目录，未清验证码全表。故障设置只在独立docker-exec Python进程覆盖，没有破坏正在验证的web配置或可执行文件。
- **未配SoX**：真实Flite-only能生成，但同挑战重复字节相同，不作为推荐配置。SoX棕噪声现场生成，无外部噪声文件；不同摘要也不等于完整抗识别攻击证明。
- 仅接受正常配置下的本地生成与页面播放修复；生产启用前须处理上述已观察边界。默认音频仍不启用，临时fixture不作为正式交付示例。T4物理真机/屏幕阅读器、人工听辨、其他浏览器、线上CI/完整矩阵及生产验收均未覆盖，不宣称全安全或无障碍全通过。

### T3本次收尾

原生播放器修复及正常配置下的本地生成/播放已获统筹独立验收；上游异常边界保留，不将T3记为全安全或无障碍全通过。实施已关闭自有nova-t3-audio浏览器，没有启动T3凭证/答案桥。对同一T3项目执行单次有界compose down（120秒上限、无-v），3.490秒退出0。统筹独立确认T3和T2容器/网络均空、4193/4189关闭，两项目各自原卷Name/CreatedAt保留、四份0600密钥哈希与对应前基线一致，原examples/compose/.local仍不存在，Playwright列表为空；10份受测代码未再变化。证据：`.local/t3-audio-20261024/final-down.json/log`及`.local/t3-review-20261024/cleanup-independent.json`。

本次新增应用修复仅为页面播放器/刷新生命周期，相关测试、数量契约、本地化与本轮文档同步更新。验收时未提交Git、推送、发布、部署或触发线上CI；未继续T4，也未处置已保留的过期音频/工具异常/资源收尾边界。最终实施回执：`.local/t3-audio-20261024/T3-final-verification.json`。统筹已核对文档并独立确认清理。用户随后授权提交Git及继续逐项处理T3剩余边界，本次提交收录已验收的14份改动；未推送、发布或部署。
