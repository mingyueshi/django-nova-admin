# CI/CD 接入与验证

## 当前状态与已合并阶段（2026-10-26）

音频、排序、导航分支已依次合入主线，最终合并 `cbc1624` 是当前本地 `main@df48494` 的祖先。`df48494` 仅新增诊断复核文档，产品基线为 `c6e3484`；统筹 2026-10-26 的 `git ls-remote` 只读回执显示远端 `main` 仍为 `c6e3484`。以下历史运行均绑定各自提交，不属于当前文档或未提交候选的验证。

| 已合并阶段 | 主线提交与实际运行 | 独立最终回执（本地忽略目录） |
|---|---|---|
| M1 音频及上游门禁 | `80911703`：[quick 40094522627](https://github.com/mingyueshi/django-nova-admin/actions/runs/40094522627)、[手动上游 40095089612](https://github.com/mingyueshi/django-nova-admin/actions/runs/40095089612) 通过并独立验收 | `.local/branch-merge-review-20261024/audio/M1-final-independent-acceptance.json` |
| M2 排序 | `993764a`：[quick 40096067713](https://github.com/mingyueshi/django-nova-admin/actions/runs/40096067713) 通过并独立验收 | `.local/branch-merge-review-20261024/sorting/M2-final-independent-acceptance.json` |
| M3 导航 | `cbc1624`：[quick 40099609587](https://github.com/mingyueshi/django-nova-admin/actions/runs/40099609587) 8/8 jobs、8 artifacts；[full 40100316363](https://github.com/mingyueshi/django-nova-admin/actions/runs/40100316363) 14/14 jobs、14 artifacts，通过并独立验收 | `.local/branch-merge-review-20261024/navigation/M3-final-independent-acceptance.json` |

M3 当时的 Node 契约为 **19 套件、1,322 项前端、260 项主题 JS**；full 覆盖 7 组 Python/Django、28 个源码/wheel 环境、3 组 Node 和三版 Axes。统筹 2026-10-26 再次只读核对 quick/full 的 jobs 全部 success、工件均绑定 `cbc1624`，手动上游的 jobs success 且工件绑定 `80911703`。读回证据在 `.local/docs-status-review-20261026/online-readback.json`、`upstream-readback.json`；它们不替代此前对工件内容和源码的独立验收。

当前工作区另有已本地独立验收、**尚未提交的六文件用户数据候选**：Node 24.21.0 / npm 11.19.0 下 20 套件、1,397 项前端及 62 项 CI 适配器测试通过，实施运行主题 JS 260 项通过，双方来源和真实 Chrome 范围见 [用户数据独立验收](USER_DATA_VALIDATION_ACCEPTANCE_2026-10-26.md)。没有为该候选重装依赖、重跑完整 Python/wheel 矩阵或触发线上 CI；本轮文档也没有触发验证运行。

主线手动上游已验证，不等于观察到定时 cron 事件；实验预警不扩大 `Django<6.2` 支持声明。人工音频听辨继续跳过未验收；T4 仅接受用户真实 iPhone Safari / VoiceOver 的无 CAPTCHA core 登录与导航最小范围。其他设备/读屏组合、可选验证码真机流程，以及当前候选的发行与生产部署仍未验收。更多入口见 [文档索引](README.md)。

### 历史接入与特性分支合入前状态

以下两段保留当时的接入与验收背景；其中默认分支“尚未合入”等结论仅指当时，后续合并以页首记录为准。

本仓库提供 GitHub Actions 配置和本地可复现的执行入口。以下正文中的云端接入过程保留为最初交付背景；2026-10-15 已核实实际官方仓库为 `mingyueshi/django-nova-admin`，`main@f4f07b8da3ce9ddbfd69819f11705fd9bb8ca610` 的 [快速 CI 运行](https://github.com/mingyueshi/django-nova-admin/actions/runs/38528050393) 已通过。该历史运行不代替新发行提交的验证。未代为配置分支保护、审批环境、凭据或生产发布。

2026-10-24 合入前验收（历史）：已推送的特性分支 `codex/audio-listening-validation`，固定候选 `ef58c7d7a72ac6e8fd881fc182acc129d3d34f15` 的完整矩阵和线上手动上游预警均已由原实施会话执行、统筹会话独立验收。最近核验的远端默认分支仍为 `main@ee532041276d217e1576de12fdb8c821550fe900`；候选尚未合入，不能据此宣称默认分支的定时预警已恢复。本文本次补记属于验收后文档，不是 `ef58c7d` 已运行 CI 的输入。

`0.6.1` 的构建清单升级为 schema 2：在原 wheel/静态产物之外增加 sdist，并从 sdist 构建 wheel；增加源码/文档、许可证与运行时版本核验。现有下载/复核入口跟随同一源码脚本，不增加发布流程。详见 [发行与升级说明](../django-theme/RELEASING.md)。

## 流程入口

| 入口 | 范围 | 输出 |
|---|---|---|
| PR或main/master分支push | 快速矩阵 | 检查结果、wheel、静态产物与可追溯报告 |
| 手动运行Nova CI，scope=full | 完整矩阵 | 七组Python/Django与三组Node的精确结果 |
| 手动运行Nova release candidate | 默认关闭；版本标签、完整CI、审批环境 | 已验证候选产物；不调用软件仓库或生产部署接口 |
| 每周一05:23 UTC或手动运行Nova upstream warning | 官方Django main当次精确SHA的独立预警 | revision、模板diff、声明依赖报告、核心源码回归日志 |

文件：`.github/workflows/ci.yml`、`.github/workflows/release-candidate.yml`、`.github/workflows/upstream-drift.yml`。静态演示本身没有Node构建步骤；这里的静态产物是校验后打包的`dist/`，不会启动Django后台，也不带数据库、环境、源码ZIP或依赖目录。

### 主线预警

`Nova upstream warning`使用Ubuntu24.04/Python3.14.8，固定asgiref3.13.0及packaging26.3等核心辅助工具。模板检查后，`scripts/upstream_dependencies.py`核对官方源码`pyproject.toml`中的Python范围、适用基础依赖与实际Django导入来源，保存`dependencies.json`，再运行`pip check`及核心源码回归。PYTHONPATH源码没有安装发行版元数据，pip check不能代替该声明检查。三个实验步骤保留`continue-on-error`以收集证据，最终按它们的`outcome`统一判定：仅全部success通过，失败或跳过都会使独立预警失败；工件在失败时也保留。

线上验证前的本地阶段记录：2026-10-24固定官方main `0e128d524d0a7c55a955570d6e5da983ac6ce6c7`的A/B/C已由双方验收：7模板/8覆盖无漂移；依赖门禁及95项脚本测试通过；双方macOS ARM64/Python3.12.14核心各424项、421通过、3可选集成跳过。统筹actionlint1.7.12全部3份workflow通过，最终shell五种outcome验证通过。测试在Nova `67e1e5a`加3文件候选上执行，内容已逐文件核对与`9707224`一致；该阶段未宣称提交后重跑、工作流规定运行时、远端CI或完整矩阵通过。后续真实线上结果见下方验收记录；历史失败与下载阻塞保留在[上游预警记录](../django-theme/UPSTREAM_DRIFT.md)。该入口不发布、不接受新基线、不扩大`Django<6.2`支持范围。

### 快速PR矩阵

- Python3.11.17 / Django5.2.17：核心源码与wheel
- Python3.12.15 / Django6.0.8：核心源码与wheel
- Python3.14.8 / Django6.1.1：核心源码、核心wheel、可选验证码源码、可选验证码wheel
- Node24.21.0 / npm11.19.0：当前工作区契约要求20套件、1397项前端检查，以及260项主题JS检查（导航108、导航命令面板25、外观披露与三版原生筛选脚本24、changelist增强38、当前页打印24、当前响应消息26、CAPTCHA增强15）

这里描述工作区源码的执行规范；20/1397 契约包含未提交的用户数据套件，不是该候选的线上运行结果。按固定 SHA 已执行的旧计数分别保留在相应历史验收段落。

共8个Python隔离运行，不等同完整28个。稳定汇总检查名为`Nova CI gate`；将其设为必需检查前，先在实际GitHub仓库确认显示名称。它会对失败、跳过、取消和缺报告作失败处理，不会因为汇总job被跳过而误放行。

### 完整矩阵

Python/Django从既有`django-theme/scripts/test-matrix.json`读取以下七组，各执行核心/可选验证码 × 源码/wheel，共28个隔离环境：

| Python | Django |
|---|---|
| 3.11.17 | 5.2.17 |
| 3.12.15 | 5.2.17 / 6.0.8 / 6.1.1 |
| 3.13.16 | 6.1.1 |
| 3.14.8 | 5.2.17 / 6.1.1 |

Node独立跑22.23.3/npm10.9.9、24.21.0/npm11.19.0、26.10.0/npm11.19.1。Node26在2026-10-03仍是Current，仅表示精确版本已测。没有把Node与Python做全笛卡尔组合。两类矩阵各最多2个并行job；每个Pythonjob内部串行。工作流显式选择bash以启用失败传播；汇总器输出文件与展示分开，失败不会被管道末端的成功状态覆盖。

## 2026-10-24 特性分支线上验收（合入前历史）

本节保留 `ef58c7d` 阶段的原始失败、1298/230 等旧计数及当时未合入的事实；文中“当前”等措辞只指该阶段。后续主线合并、19/1322/260 与当前未提交的 20/1397/260 分别见页首，不能相互替换。

原五份 R3 本地验收文档已提交为 `57e19a474534e988c5efde11a4668aa743583b84`。随后由原实施会话逐项执行下列线上运行，统筹会话分别独立读取原始日志、下载工件并核对 GitHub 摘要、源码身份及报告；通过一项后再推进下一项。两次失败保留为原始结果。

| 运行 | Nova 候选 | 实际结果及后续处理 |
|---|---|---|
| [首次 quick #40074862570](https://github.com/mingyueshi/django-nova-admin/actions/runs/40074862570) | `57e19a4` | 失败：sdist 已包含 JSON 测试夹具，但独立源码契约遗漏该类型。修复与正负回归独立接受后，提交 `93fd274`；保留源码逐字节校验和多余文件拒绝保护。 |
| [quick #40075349271](https://github.com/mingyueshi/django-nova-admin/actions/runs/40075349271) | `93fd274` | 通过：3组 Python/Django、8个源码/wheel变体、1个Node版本及快速范围Axes集成；统筹独立验收通过。 |
| [首次 full #40075868053](https://github.com/mingyueshi/django-nova-admin/actions/runs/40075868053) | `93fd274` | 失败：Node26/JSDOM 对受控存储 getter 的异常传播使测试收到 `ReferenceError`，原断言预期 `SecurityError`。仅修测试 harness，保留严格拒绝前置、原生中断及表单/披露检查；独立验证及变异对照通过后提交 `ef58c7d`。 |
| [最终 full #40077039814](https://github.com/mingyueshi/django-nova-admin/actions/runs/40077039814) | `ef58c7d` | 通过：14个jobs、14份artifacts；7组Python/Django×核心/验证码×源码/wheel，共28环境，3个Node版本及3版Axes集成；最终门禁通过并独立验收。 |
| [手动上游预警 #40078003051](https://github.com/mingyueshi/django-nova-admin/actions/runs/40078003051) | `ef58c7d` | 通过：实际Ubuntu24.04.5/Python3.14.8，检出官方Django main `0e128d524d0a7c55a955570d6e5da983ac6ce6c7`；模板、依赖、源码回归三步的实际outcome均为success，统筹独立验收。 |

最终 full 在同一 `ef58c7d` 上覆盖全部 quick 场景，按统筹派发没有对该提交另行重复 quick。核心14个环境各运行424项，421通过、3项未启用的CAPTCHA/security/slider占位跳过；验证码14个环境各57项全通过、无跳过。Axes在Django5.2.17、6.0.8、6.1.1上各16项通过、无跳过。三个Node/npm精确版本均各通过1298项前端与230项主题JS检查。历史PF1阶段的226项主题JS/验证码11项仍是当时结果；当前230/15不覆盖那些记录。

线上上游预警的7种模板、8个覆盖目标均为reviewed，文本漂移及丢失继承block均为0；声明依赖满足、Django导入来源为检出的官方源码，`pip check`通过。原始日志最终环境值为`DRIFT=success`、`DEPENDENCIES=success`、`SMOKE=success`；源码回归运行424项、421通过、3项可选集成跳过。上游SHA来自本次`revision.txt`和检出日志，并经官方commit/tree核对；没有用历史固定值替代本次观测。

实施证据保存在本地忽略目录 `.local/ci-full-20261024/`，统筹独立证据另存 `.local/ci-full-review-20261024/`：

| 验收项 | 原实施回执（相对实施证据目录） | 统筹独立回执（相对独立证据目录） |
|---|---|---|
| quick | `attempt-2/CI-1-quick-final.json` | `quick-independent-acceptance.json` |
| 最终full | `full-rerun/CI-2-full-final.json` | `full-independent-acceptance.json` |
| 线上上游预警 | `upstream/CI-3-upstream-final.json` | `upstream-independent-acceptance.json` |

首次quick失败保存在实施目录的`CI-1-failed-run-receipt.json`，首次full失败保存在`full/CI-2-full-first-run-final.json`；两次修复的独立接受记录分别为统筹目录的`CI-1-fix-accepted.json`、`CI-2-fix-accepted.json`。完整日志、工件ZIP、摘要与输入快照随各回执保留，不以最终成功改写失败。

上述成功仅绑定已推送的特性分支固定候选。默认分支尚未合入，定时预警恢复仍待合入后的精确版本核验；`Django<6.2`支持范围不扩张。人工音频听辨继续跳过且未验收，真机/读屏与生产范围不扩大；本轮没有合并、发布或部署。本文新增内容是验收后的记录，不作为已完成CI的输入，也未因此重跑验证。

## 检查与产物

1. 从可信固定SHA运行官方Actions，使用ubuntu-24.04；精确选择运行时
2. 用带SHA-256的`ci/requirements-tools.txt`安装固定构建工具；单测CI适配脚本与原矩阵runner；actionlint1.7.12校验工作流，下载二进制亦核官方SHA
3. 验证已有真实Django静态样本的惰性表单、CSP与导出清单，再从干净commit构建wheel与静态文件
4. 每个Python组合下载同一个wheel，重新核验内容、版本、commit、全部主题运行文件和wheel RECORD；每种安装模式使用新的venv、测试数据库与导入来源检查
5. 核心环境没有captcha/Pillow。可选环境固定依赖；唯一无官方wheel的django-ranged-response0.2.0从固定官方sdist校验后，用固定工具离线构建。它只作为测试支持产物，不混入主题wheel或候选交付包
6. 每个Node版本独立npm ci，启用engine-strict，保留原lock及integrity；检查实际npm、全部40个包版本和依赖树，执行格式、语法及交互回归。导航脚本从三个固定Django官方wheel按SHA提取，不需要安装三个Django运行时
7. 汇总器验证每个必需组合、步骤状态、源码/wheel、可选配置、commit、wheel哈希及Node锁哈希。快速结果不能冒充完整结果

构建目录含主题 wheel、sdist、`nova-static.tar.gz`、`MANIFEST.json` 和 `SHA256SUMS`。清单保存 commit、主题/预览版本、每个产物的字节数与 SHA，以及逐文件静态/主题/源码和文档哈希。包内容拒绝路径穿越、符号链接、重复成员和非预期文件。

上传/下载Actions使用自己的artifact digest，并在下载时设置`digest-mismatch: error`。随后再做上述项目级校验。普通SHA清单属于完整性校验，不是签名证明或供应链证明；本实现未申请OIDC或创建attestation权限。

构建产物按实际artifact ID传递，候选job重试不会用新的run_attempt猜测一个不存在的旧产物名。每个逻辑测试组合在同一运行内保留最新成功报告，重跑时仅覆盖该组合报告；旧job日志仍在GitHub运行记录中。汇总必须先看到当前依赖job成功，再检查报告。失败日志另行保留，不会作为通过证据；只上传允许的日志与摘要，排除venv、缓存、测试数据库和harness。

## 安全默认值

- 所有工作流只声明`contents: read`；checkout不持久化凭据
- PR使用`pull_request`，不使用`pull_request_target`、特权`workflow_run`或secrets继承
- 没有token、环境secret、id-token、包发布或部署权限配置；不要把凭据写入仓库
- 不启用依赖缓存；setup-node明确关闭自动包管理缓存，setup-python不设置cache。依赖仍由锁文件/精确版本控制
- 发布候选仅手动触发，不因push、标签创建或PR自动发布；默认仓库变量未开启时立即失败并说明接入步骤
- fork PR仍运行不可信代码，应使用GitHub托管隔离runner；不要直接换成可访问生产网络或秘密的self-hosted runner
- 官方Actions全部固定完整commit SHA。升级时同时核对官方来源、action输入/输出和本地验证，不能只把SHA换成浮动标签

Actions自身目前使用Node24运行时，这与被测试的Node22/24/26无关。若将来使用自托管runner，需要满足官方Actions要求并单独评估；本模板建议GitHub托管ubuntu-24.04。actionlint本轮执行语法/表达式检查，未宣称同时运行ShellCheck或pyflakes。

## 接入自己的GitHub仓库

这些设置需要仓库所有者按自己的权限和计划完成；当前没有代为创建或配置：

1. 将源码迁入你选定的GitHub仓库，提交工作流到默认分支；如默认分支不是main/master，调整push分支列表
2. 启用Actions并检查首次快速CI；为实际显示的汇总检查配置分支保护，评估公共/私人仓库的运行分钟数和存储成本
3. 需要候选交付时，先创建`nova-candidate`环境，配置内置required reviewers、避免自行审批的规则和允许的`theme-v*`标签；确认你的GitHub套餐支持并且规则生效
4. 环境使用`deployment: false`，保留内置审批/等待规则而不创建部署记录。自定义GitHub App部署保护规则不适用于该选项。仅在YAML中写环境名不会自动配置审批；不要把默认新建的无保护环境当作已安全配置
5. 审批环境核实后，显式将仓库变量`NOVA_ENABLE_RELEASE_CANDIDATE`设为字符串`true`
6. 由维护者创建与主题版本完全相符的标签，例如当前`theme-v0.6.1`，在该真实标签ref上手动dispatch候选工作流。它核验GITHUB_REF与主题版本，不接收可代替真实ref的任意标签输入
7. 完整CI通过并完成审批后，下载`nova-approved-candidate-<commit>-<attempt>`。其中`candidate/`包含原始已测产物，旁边的`validation.json`说明完整覆盖范围；没有重建未经验证的新wheel

如将来要发布PyPI、GitHub Release、对象存储或生产服务器，先明确目标、权限、凭据管理和回滚策略，再增加独立受审批发布job。现有流程停在候选交付边界，没有占位的真实发布命令，也不会更改本演示站分享权限。

## 本地运行同一入口

在独立工作副本中使用已验证Python3.12.15和Node24.21.0，先安装固定构建/检查工具。所有输出路径放在源码外的新目录；不要把现有项目数据目录当作输出。

```bash
python -m pip install --require-hashes --no-deps --only-binary=:all: -r ci/requirements-tools.txt
python -m unittest discover -s scripts/tests -v
python -m unittest discover -s django-theme/scripts/tests -v
python scripts/ci_support.py plan --scope quick
python scripts/ci_support.py plan --scope full
python django-theme/scripts/test_export_safety.py --export-dir dist/native-admin
python django-theme/scripts/export_admin_samples.py --check dist/native-admin
```

提交待验收修改后，用完整commit SHA构建并验证；脏工作区会被拒绝，避免产物假称来自其它commit：

```bash
python scripts/ci_artifacts.py build --directory /path/to/new-artifact --commit FULL_COMMIT_SHA
python scripts/ci_artifacts.py verify --directory /path/to/new-artifact --commit FULL_COMMIT_SHA
```

Python隔离矩阵沿用[运行时说明](../django-theme/COMPATIBILITY.md)中的test-matrix.py入口，传入上一步同一wheel。Node入口为`node scripts/ci_node.mjs --node 24.21.0 --npm 11.19.0 --logs /path/to/new-node-logs --sidebars /path/to/verified-sidebars`；sidebars先用`ci_support.py sidebars`从固定官方Django wheel生成。工作流文件保留各命令的完整顺序，供接入时核对。

维护时在ci/matrix.json和既有Python矩阵中同步精确版本；新增或删减前端测试时，同步ci_support.py中的测试数量契约，避免完整套件被意外少跑。不要仅放宽断言来掩盖缺失的分组。

`ci_support.py` 按套件身份、精确数量和执行顺序核对20条成功摘要，前端合计1397项，主题JS合计260项；总PASS数相同不能补偿缺套件、挪动数量、重复、失败、未知摘要或顺序变化。脚本适配器回归同时检查 `package.json` 的 `test` 链必须依次执行 `format:check`、`check` 及契约登记的 `test:*` 脚本，且脚本定义存在；新增测试未登记会使检查失败。完整Node收集仍要求真实运行时、所有必需步骤成功和当前package/lock输入哈希，专项摘要校验不会替代这些条件。

仅需要复核已有真实日志时，可将完整输出保留为 `frontend.log`、`navigation.log`、`enhancements.log`、`captcha.log`，执行只读专项：

```bash
python scripts/ci_support.py check-node-summaries --logs /path/to/real-suite-logs
```

它与完整 `collect-node` 复用同一严格摘要检查，返回 `kind=node-suite-contract` 并明确声明不证明安装、运行时或CI步骤；该种记录不能被 `verify-reports` 当作完整Node报告接纳。不得为让 `collect-node` 通过而编造未执行的 `install`、`runtime.json` 或 `steps.json`。本地专项通过也不表示线上CI已经重跑。

最初的本地接入验证未覆盖GitHub线上Actions；后续特性分支及主线固定提交的真实线上结果分别见历史段落和页首证据索引。当前未提交候选与本轮文档没有线上重跑结果。分支保护、环境审批、账单额度与第三方生产目标仍未作为本轮验收范围；当前演示站没有新增虚构的绿色CI徽章。

## 官方参考

- [GitHub工作流语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [安全使用Actions](https://docs.github.com/en/actions/reference/security/secure-use)
- [手动触发与真实ref](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)
- [环境与审批配置](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [不创建部署记录的环境](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments#using-environments-without-deployments)
- [actionlint1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12)


## 0.6.0 新增维护门槛

- `ci.yml` 构建阶段执行 `scripts/css_budget.py`；各稳定 Django cell 在回归后检查已审查模板基线，失败时上传差异文件
- 独立 security job 使用 Python3.12.15 的已构建 wheel，快速范围测试 Django6.1.1，完整范围再含5.2.17/6.0.8；Axes 为独立可选安装，不与7组核心/验证码矩阵做笛卡尔扩张。security job 失败/跳过也使最终 gate 失败
- `upstream-drift.yml` 为每周一05:23 UTC及手动主线预警。固定Actions SHA，只读官方Django main当次SHA、保存差异/声明依赖报告/实验回归日志，最终按三步outcome拒绝失败或跳过；不发布、不接受新基线、不扩大包版本上界
- 主线源码的 `tests` 包会与本主题测试目录同名，工作流把本主题目录放在 PYTHONPATH 首位，并在 django-theme 目录执行；输出必须实际运行至少一项测试，不能把零测试当通过
- 此段最初为源码交付的维护门槛；当前实际仓库与已核实的历史快速 CI 运行见本文开头。Docker/Psycopg/真实 PostgreSQL 不在本次本地发行矩阵中，详见 Compose 示例的明确验收边界
