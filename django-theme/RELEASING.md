# 0.6.1 发行与升级说明

本版使用 PEP 440 正式版本号 `0.6.1`，将 `0.6.0` 后已合入官方主分支的布局、过滤器折叠、宽表控制与配色更新整理为兼容修订。没有新的破坏性配置变更或主题数据库迁移，因此采用补丁版本。正式版本号不等于 1.0 稳定性承诺；现有 Alpha 成熟度分类继续保留。

准备起点是官方 `main` 的 `f4f07b8da3ce9ddbfd69819f11705fd9bb8ca610`。2026-10-15 通过 GitHub 接口核实：没有 tags 或 Releases；该起点的快速 CI 已通过。本次只交付发行包和仓库改动，不创建发行标签、公开 Release，不上传 PyPI，也不启用或手动触发新发行流程。任何下游项目的私有 rc/local 版本均须独立比较，不将其定制合入公版。

## 安装与升级

核心依赖保持 `Django>=5.2.17,<6.2`、`Python>=3.10`。Python 3.10 只保留历史安装边界，维护测试从 3.11 开始；Django 6.x 自身要求 Python>=3.12。使用目标 Django 分支的当前安全补丁，并单独验证宿主及第三方插件；元数据区间不等于每种组合都已测试。当前补丁与本次实际覆盖见 [COMPATIBILITY.md](COMPATIBILITY.md) 和 [RELEASE_VALIDATION.md](RELEASE_VALIDATION.md)。

1. 保存现有依赖锁、主题版本、静态资源以及项目覆盖模板/CSS。若使用 vendored 或私有版本，先按文件比较官方包与本地改动，保留有意的定制；不要直接覆盖目录。
2. 在新的测试环境核验发行目录的 `SHA256SUMS`，安装提供的 wheel，并使用宿主的原有依赖约束。例如 `python -m pip install --upgrade /path/to/nova_django_admin_theme-0.6.1-py3-none-any.whl`。离线安装需预先提供全部依赖，不能以 `--no-deps` 隐藏缺失依赖。
3. 保留 `INSTALLED_APPS` 中 Nova 位于 Django admin 之前的顺序、已有 context processor、URL 命名空间和认证/验证码配置。配色设置保持可选，参见 [PALETTE_PRESETS_ZH.md](PALETTE_PRESETS_ZH.md)。没有新增必填配置。
4. 执行宿主原有 `check`、必要测试、`collectstatic` 和静态缓存更新流程。确认登录、权限、CSRF、搜索/排序/过滤、列表编辑、批量操作、过滤器折叠、宽表键盘/拖动和手机布局，再按宿主流程部署。
5. 主题没有模型或 migration，本次无需数据库迁移，也无需导入 Demo。已有可选 CAPTCHA/Axes 的依赖、迁移和认证约束仍由宿主原有升级流程管理；不要使用本包 Demo 设置或种子替代生产配置。

过滤器折叠使用当前浏览器会话中按模型路径保存的偏好；未启用 JavaScript 时保留原生列表操作。宽表交互需在运行中的 Django 后台验证，只读静态样本不会运行脚本。

发行核查确认 Django 在 `max-width: 1024px` 使用 `nowrap`/零宽度结果计数，与 Nova 控件尺寸冲突。本版在同一响应式范围允许搜索行换行、结果计数占独立整行、按钮保持自身高度；不改宿主模板、GET 参数、查询或列表动作。真实 Chromium 检查覆盖 320/375/390/414/768/1024/1025/1280px、中英文、浅色/深色；特别保留 768px 修复前后的截图与几何数据。检查方法及平台限制见 [RELEASE_ACCEPTANCE.md](RELEASE_ACCEPTANCE.md)。

Django 5.2 的原生 tabular inline 尚无内层 `.wrapper`；本版在该结构上启用局部横向滚动，避免宽内联表格撑开手机页面。Django 6.x 保留原有 wrapper，普通字段组不增加裁切；字段、管理表单和动态添加行的语义保持原生。

## 回退

优先使用现有“Django 原生”外观，或设置 `NOVA_ADMIN_ENABLED = False` 恢复原生呈现。已经显式启用的验证码仍然执行。需要回滚包时，重新安装先前固定的可信 wheel/源码和依赖锁，再重新收集静态资源并更新缓存；没有主题数据迁移需要回滚。完全卸载前按接入指南处理 context processor、URL 和可选 login form/template，不能只卸载依赖包。

## 固定源码构建与核验

在干净、已提交的官方源码工作副本，从仓库根目录运行。输出必须在源码之外且尚不存在：

```bash
python -m pip install --require-hashes --no-deps --only-binary=:all: -r ci/requirements-tools.txt
python scripts/ci_artifacts.py build --directory /path/to/new-artifacts --commit FULL_SOURCE_SHA
python scripts/ci_artifacts.py verify --directory /path/to/new-artifacts --commit FULL_SOURCE_SHA
```

构建工具默认先生成 sdist，再从该 sdist 构建 wheel；沿用 `setuptools.build_meta`，固定 `SOURCE_DATE_EPOCH` 为源码提交时间。`MANIFEST.json` schema 2 绑定完整源码 SHA、版本、每个发行文件的大小和 SHA-256、全部运行文件、sdist 源码/文档和静态资源哈希；`SHA256SUMS` 覆盖 wheel、sdist 和独立的 `nova-static.tar.gz`。清单本身不自引用；校验和不构成签名或供应链证明，也不承诺 sdist 压缩字节逐次相同。

wheel 仅安装 `nova_admin` 运行文件，包含模板、CSS/JS、PO/MO、Django BSD 许可证和项目 MIT 许可证；不安装 Demo、数据库或测试。sdist 另含可运行的合成 Demo、测试、测试脚本、全部主题 Markdown 指南和许可证。静态预览单独归档，不进入 Python 运行包。包内容核验拒绝遗漏、额外运行文件、路径穿越、符号链接和重复归档成员。

对最终 wheel 做新的隔离环境安装、`pip check`、实际导入来源检查、Django 系统/迁移漂移和核心/可选测试。按 [兼容矩阵](COMPATIBILITY.md) 运行维护矩阵，记录所有失败和未执行项；任何局部矩阵都不得标为完整通过。最终产物 SHA、SHA-256、命令、退出状态与测试报告保存在发行交付目录；结果报告如另有仓库提交，需明确区分构建源码提交和报告提交。

现有 main push 仅触发只读 CI 及检查产物上传；`release-candidate.yml` 仅手动触发、默认关闭，要求实际 `theme-v<VERSION>` ref 和保护环境，且本身不发布。推送前再次检查远端差异，禁止顺带推送 tags。本次不配置凭据、权限、候选开关或任何下游项目。
