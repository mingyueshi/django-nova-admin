# 上游模板漂移预警

Nova 采用同名模板继承。主题覆盖和 Django 原版必然有差异，因此不能把每个 diff 都当作回归，也不能把“无文本差异”当作兼容保证。

仓库根目录的 `scripts/template_drift.py` 同时输出两份 diff：

- `*.override.diff`：当前 Django 原版与 Nova／项目覆盖的差异，供人工审查改写范围
- `*.upstream.diff`：当前 Django 原版与已审查版本的差异；发现变更或继承链中丢失所用 block 时退出 1，要求审查

审查范围包括主题 base/index/login，以及 Demo 项目 base_site/actions/fieldset/tabular。`ci/template-baselines.json` 保存 5.2.17、6.0.8、6.1.1 原版模板，许可证见 `src/nova_admin/LICENSE-DJANGO.txt`。主题自有 `nova_*` block 不被误当作上游必需 block。中文字段呈现片段仍须由集成回归覆盖。

Demo 的 `project_admin_template` 直接读取当前安装的 Django 原生 fieldset/tabular 模板，按完整内容的 SHA-256 匹配已审查的中文适配片段，不以 `django.VERSION` 的 minor 白名单决定是否渲染。5.2.17、6.0.8、6.1.1 对应三种 fieldset 和两种 tabular 签名；6.0.8 与6.1.1的 tabular 内容相同，共用一个已审查片段。每次选择都会重新核对原生内容，不缓存旧匹配；模板读取失败、未知 kind 或未知签名会抛出明确的 `TemplateSyntaxError`，包含模板路径及可用的来源/签名信息，不回退到旧片段。

升级时先查看原生差异、确认 markup、a11y、escaping、CSRF 与 Inline 行为，再更新匹配片段及 `demo/catalog/templatetags/project_admin.py` 中的签名，并运行 `tests.test_project_localization` 和核心回归。修改版本元数据而保持已审查模板不变可以继续渲染；这只消除了版本字符串造成的误拒绝，不等于新 Django 版本已获支持，包的 `Django<6.2` 边界保持不变。

在已安装目标 Django 的环境，从仓库根目录运行：

```bash
python scripts/template_drift.py --output /tmp/nova-drift-6.1.1
```

报告目录必须不存在，脚本不会覆盖旧证据或自动接受新版本。实际 diff 审查及回归通过后，维护者才可明确更新某个稳定版本基线：

```bash
python scripts/template_drift.py --record-reviewed --output /tmp/nova-reviewed-6.1.1
```

主线检查只读取官方源码，不把 main 加入包的支持区间：

```bash
git clone --depth 1 --branch main https://github.com/django/django.git /tmp/django-main
revision=$(git -C /tmp/django-main rev-parse HEAD)
python scripts/template_drift.py --django-root /tmp/django-main/django \
  --label "main@$revision" --output /tmp/nova-drift-main
```

`.github/workflows/upstream-drift.yml` 配置每周一 05:23 UTC 和手动运行，读取官方 Django main 的当次精确 SHA，保存 diff、声明依赖报告与源码回归日志。`scripts/upstream_dependencies.py` 使用固定packaging26.3读取上游`pyproject.toml`，检查Python范围、适用的基础依赖和Django导入来源；asgiref固定为3.13.0，并运行`pip check`。源码经PYTHONPATH使用时，pip不会自动校验其项目声明，故这两项检查都需保留。最终检查模板、依赖、回归三步的`outcome`，任一失败或跳过都会使预警任务失败。它不发布、不修改基线、不创建权限或秘密，也不自动扩大 `Django<6.2` 依赖边界。

2026-10-23 复核已下载的 GitHub 运行元数据及原始工件：远端 `mingyueshi/django-nova-admin` 的该工作流已实际由 `schedule` 触发，见下方2026-10-19记录。这证明调度已有真实执行，不代表告警任务一直健康。维护者仍须查看默认分支工作流、Actions 状态和通知；调度可能延迟，公开仓库长期无活动也可能被停用，不承诺即时响应未来6.2。

2026-10-03 本地实际观察官方 main `7847227a3fecde4b2a169552b84c60c6286b6025`：7 种上游模板文本与6.1.1基线相同；Python3.14.8 的完整源码实验回归运行314项，产生54个错误、2个预期跳过。错误来自 Demo 中文字段模板明确限制5.2/6.0/6.1的版本闸门及对应测试映射。没有删除闸门、跳过失败或将其记为6.2兼容；后续需审查新分支模板并补项目片段、再做正式矩阵。文本漂移与运行兼容性检查的结果必须分别解读。

2026-10-19 GitHub [Nova upstream warning #39241104648](https://github.com/mingyueshi/django-nova-admin/actions/runs/39241104648) 的实际 schedule 运行：本仓库 SHA `121a3e0856c1352359347460c1f5076f06f9dca1`，官方 Django main `11af25c0ae06c8275ebb8def8b8ca777a5660ed6`。工件中的模板报告为 `reviewed`（参考6.1.1）；原始 `tests.log` 运行335项，结果为 `errors=55, skipped=2`，其中54个错误是 `Unsupported project admin template version or kind`，另1个是版本映射 `KeyError: (6, 2)`。最终告警任务失败。这份较新的失败证据与10月3日记录一并保留，未被后续本地修复或元数据模拟测试覆盖成“通过”。

2026-10-23 R2 本地修复将上述两个版本映射改为已审查模板内容匹配，新增已知模板逐一选择、模拟6.2版本元数据、未知模板/未知kind诊断及真实表单回归。这里的6.2测试仅修改版本元数据并保留当前安装的原生模板；没有据此宣称真实6.2支持，也没有重写这两次历史main回归结果。

本次在 macOS ARM64、CPython3.12.14 下分别使用实际安装的 Django5.2.17、6.0.8、6.1.1 运行源码核心回归，每个环境执行351项：349项通过、2项可选CAPTCHA/安全集成跳过，失败和错误均为0；其中每个环境的27项项目本地化测试全部通过。另将3个已审查发行版的6组原生模板与对应片段逐一核对。该结果不是声明矩阵中的Python3.12.15测试、完整wheel/extra矩阵或真实6.2/main重新验收。

## 2026-10-24 固定 main 的本地结果

R3本次固定官方main `0e128d524d0a7c55a955570d6e5da983ac6ce6c7`，官方归档SHA256为`fe372e3c84ded7c7601fbb6ad891d6904d3d94321e7c34ac87ae2d5718a1522e`；7089个blob重建Git tree与官方提交匹配。10月23日的源码下载阻塞保留为历史，本次已取得并独立核对完整归档。实施与统筹分别使用自己的输入副本、上游解包和venv完成：

- A：7种上游模板、8个覆盖目标均为reviewed，文本漂移/丢失继承block为0；没有执行`--record-reviewed`，6.1.1参考基线未改。
- B：原asgiref3.12.1可完成真实Django setup和ASGI/WSGI导入，但不满足官方`asgiref>=3.13`；新门禁对旧pin exit1、3.13.0 exit0，错误来源同样被拒。新旧环境的pip check均通过，说明它不能单独发现PYTHONPATH源码的声明不匹配。新增10项专项和全部95项脚本测试通过。统筹独立运行最终shell的5组outcome，仅全success返回0；actionlint1.7.12对全部3份workflow exit0。
- C：双方macOS ARM64 / CPython3.12.14实际运行`python demo/manage.py test tests --noinput`，各424项、421通过、3跳过、exit0。3项跳过为未启用CAPTCHA、security、slider集成的占位，不计为可选集成通过。Nova tests优先，Django确实来自固定官方源码，未安装发行版替代或修改版本元数据；输入、上游源码和模板基线前后哈希不变。

本地官方归档放在Nova仓库内部时，设置进程级`GIT_CEILING_DIRECTORIES`为归档源码根目录的父目录，避免Django版本工具向上发现Nova的`.git`而混入其提交日期；上游真实`VERSION`仍为`VersionTuple(6, 2, 0, "alpha", 0)`。这项归档隔离不替代源码SHA和树的核验。

测试在Nova `67e1e5a`加B的3文件候选上执行，内容已逐文件核对与`9707224`一致；未宣称提交后重跑。实施A/B/C回执在`.local/r3-main-20261024/`，独立回执在`.local/r3-main-review-20261024/`；原始核心日志分别是`r3-c-implementation/core-tests.log`与`core-tests.log`。详细顺序见[诊断验收台账](../DIAGNOSTIC_PROGRESS.md)。10月3日/19日失败不重写；工作流Ubuntu24.04/Python3.14.8、远端CI及完整Python/wheel/可选依赖矩阵未跑，`Django<6.2`支持边界保持不变。

参考：[Django 模板覆盖](https://docs.djangoproject.com/en/dev/howto/overriding-templates/)、[Django 发布过程](https://docs.djangoproject.com/en/dev/internals/release-process/)、[GitHub schedule 限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
