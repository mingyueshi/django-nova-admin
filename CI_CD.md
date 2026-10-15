# CI/CD 接入与验证

本仓库提供 GitHub Actions 配置和本地可复现的执行入口。以下正文中的云端接入过程保留为最初交付背景；2026-10-15 已核实实际官方仓库为 `mingyueshi/django-nova-admin`，`main@f4f07b8da3ce9ddbfd69819f11705fd9bb8ca610` 的 [快速 CI 运行](https://github.com/mingyueshi/django-nova-admin/actions/runs/38528050393) 已通过。该历史运行不代替新发行提交的验证。未代为配置分支保护、审批环境、凭据或生产发布。

`0.6.1` 的构建清单升级为 schema 2：在原 wheel/静态产物之外增加 sdist，并从 sdist 构建 wheel；增加源码/文档、许可证与运行时版本核验。现有下载/复核入口跟随同一源码脚本，不增加发布流程。详见 [发行与升级说明](django-theme/RELEASING.md)。

## 两条流程

| 入口 | 范围 | 输出 |
|---|---|---|
| PR或main/master分支push | 快速矩阵 | 检查结果、wheel、静态产物与可追溯报告 |
| 手动运行Nova CI，scope=full | 完整矩阵 | 七组Python/Django与三组Node的精确结果 |
| 手动运行Nova release candidate | 默认关闭；版本标签、完整CI、审批环境 | 已验证候选产物；不调用软件仓库或生产部署接口 |

文件：`.github/workflows/ci.yml`、`.github/workflows/release-candidate.yml`。静态演示本身没有Node构建步骤；这里的静态产物是校验后打包的`dist/`，不会启动Django后台，也不带数据库、环境、源码ZIP或依赖目录。

### 快速PR矩阵

- Python3.11.17 / Django5.2.17：核心源码与wheel
- Python3.12.15 / Django6.0.8：核心源码与wheel
- Python3.14.8 / Django6.1.1：核心源码、核心wheel、可选验证码源码、可选验证码wheel
- Node24.21.0 / npm11.19.0：完整540项前端DOM及97项主题JS检查

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
6. 由维护者创建与主题版本完全相符的标签，例如当前`theme-v0.6.0`，在该真实标签ref上手动dispatch候选工作流。它核验GITHUB_REF与主题版本，不接收可代替真实ref的任意标签输入
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

Python隔离矩阵沿用[运行时说明](django-theme/COMPATIBILITY.md)中的test-matrix.py入口，传入上一步同一wheel。Node入口为`node scripts/ci_node.mjs --node 24.21.0 --npm 11.19.0 --logs /path/to/new-node-logs --sidebars /path/to/verified-sidebars`；sidebars先用`ci_support.py sidebars`从固定官方Django wheel生成。工作流文件保留各命令的完整顺序，供接入时核对。

维护时在ci/matrix.json和既有Python矩阵中同步精确版本；新增或删减前端测试时，同步ci_support.py中的测试数量契约，避免完整套件被意外少跑。不要仅放宽断言来掩盖缺失的分组。

本轮验证不代表GitHub线上Actions、权限、环境审批、账单额度或第三方生产目标已测试。当前在线站点仅补充接入说明，不显示虚构的绿色CI徽章。

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
- `upstream-drift.yml` 为每周一05:23 UTC及手动主线预警。固定Actions SHA，只读官方Django main当次SHA、保存差异与实验回归日志；不发布、不接受新基线、不扩大包版本上界
- 主线源码的 `tests` 包会与本主题测试目录同名，工作流把本主题目录放在 PYTHONPATH 首位，并在 django-theme 目录执行；输出必须实际运行至少一项测试，不能把零测试当通过
- 此段最初为源码交付的维护门槛；当前实际仓库与已核实的历史快速 CI 运行见本文开头。Docker/Psycopg/真实 PostgreSQL 不在本次本地发行矩阵中，详见 Compose 示例的明确验收边界
