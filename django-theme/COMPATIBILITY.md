# Python / Django 兼容范围

发行核查更新于 2026-10-15。本页区分上游允许的组合、历史实际执行的精确组合和本次发行验证；安装元数据不是“所有组合都已通过”的承诺。`0.6.1` 的实际结果与未运行范围见 [RELEASE_VALIDATION.md](RELEASE_VALIDATION.md)。

前端开发/测试的Node矩阵独立维护，见 [Node兼容说明](https://github.com/mingyueshi/django-nova-admin/blob/main/NODE_COMPATIBILITY.md)。它不与以下Python/Django组合做无意义的全笛卡尔乘积；主题运行不依赖Node服务。

## 上游维护范围

| Django 分支 | 官方 Python 范围 | 2026-10-15 官方最新补丁 | Django 安全维护截止 |
|---|---|---|---|
| 5.2 LTS | 3.10–3.14；3.14 从 Django 5.2.8 起支持 | 5.2.18 | 2028-04 |
| 6.0 | 3.12–3.14 | 6.0.9 | 2027-04 |
| 6.1 | 3.12–3.14 | 6.1.2 | 2027-12 |

仓库既有精确维护矩阵固定 Python 3.11.17、3.12.15、3.13.16、3.14.8 和 Django 5.2.17、6.0.8、6.1.1；这是回归基线，不是“当前最新补丁”清单。本次在任务专用目录取得并核验四个精确 CPython，重新运行源码与 wheel 验证；实际执行结果和产物绑定见 RELEASE_VALIDATION.md 及随包 REPORT.md。Python 3.11、3.12、3.13、3.14 的计划安全维护截止分别为 2027-10、2028-10、2029-10、2030-10。使用每条分支最新安全补丁，不把旧补丁的历史测试替代当前补丁验收。Python 3.15 已发布，但 Django 的上述官方 Python 表未列入它，本版不新增支持或已测声明。

Python 3.10 已于 2026-10-01 EOL，Django 4.2 已于 2026-04-07 EOL。它们不进入本轮默认维护矩阵。现有 `requires-python >=3.10` 继续保留，避免仅因文档扩充就改变已发布包的最低安装门槛；它只表示历史安装边界。已有 3.10 客户应单独安排升级，不能把这个元数据解释为继续获得 Python 上游安全维护。主题的 Django 依赖仍为 `Django>=5.2.17,<6.2`。

## 历史精确验证矩阵（0.5.1，2026-10-03）

以下七组是历史 `0.5.1` 的隔离环境结果：核心源码、核心 wheel、可选验证码源码和可选验证码 wheel；每组核心各269项通过加1项预期跳过，验证码各22项通过。`0.6.0` 后续扩展次数见 TEST_REPORT.md。这些结果均不自动归属于 `0.6.1` 发行包：

| Python | Django | 选择原因 | 历史结果 |
|---|---|---|---|
| 3.11.17 | 5.2.17 | 最低仍维护 Python / LTS 边界 | 四种运行全部通过 |
| 3.12.15 | 5.2.17 | 原 LTS 基线更新安全补丁 | 四种运行全部通过 |
| 3.12.15 | 6.0.8 | Django 6.0 的最低 Python 边界 | 四种运行全部通过 |
| 3.12.15 | 6.1.1 | Django 6.1 的最低 Python 边界 | 四种运行全部通过 |
| 3.13.16 | 6.1.1 | 中间 Python 分支 | 四种运行全部通过 |
| 3.14.8 | 5.2.17 | LTS 的最高 Python 边界 | 四种运行全部通过 |
| 3.14.8 | 6.1.1 | 最新已列入上游支持的 Python 边界 | 四种运行全部通过 |

此前 Python 3.12.14 × Django 5.2.17 / 6.0.8 / 6.1.1 的验证是保留的历史结果。它不等于本轮当前补丁结果。当前七组也不代表整个 Python × Django 笛卡尔积：例如 3.13 × 5.2、3.13 × 6.0、3.14 × 6.0 虽在上游范围内，本轮并未选择，须单独验证后才能增加“已测”标记。

## 历史运行时与可选依赖

上述历史运行时为标准 GIL CPython、Linux x86-64，由 Astral 的 python-build-standalone 20261001 预编译，通过固定 uv 0.12.22 安装到任务专用目录。上游语言实现为 CPython，二进制供应方为 Astral。历史记录保留下载 URL、预期摘要与实际版本。`0.6.1` 本轮使用同一供应方的 macOS ARM64 标准 GIL CPython，记录官方元数据摘要、下载摘要和真实版本；没有更换系统 Python。

核心主题只依赖 Django。可选验证码继续固定 `django-simple-captcha==0.7.0`、`Pillow==12.2.0`；其依赖 `django-ranged-response==0.2.0` 在矩阵中固定。Pillow 12.2.0 提供本轮各 CPython 的官方 PyPI wheel，无需为扩大 Python 覆盖而无关升级。验证码需要图像生成与 FreeType，不能仅凭 import 成功就认为集成通过。

历史矩阵不覆盖 PyPy、free-threaded CPython、Windows、macOS、ARM64、Python 3.15、未来 Django 或其它补丁。当前发行验证即便包含其中某个平台，也只覆盖明确列出的组合。第三方 Admin 插件、你的业务 ModelAdmin、生产数据库或部署设置仍需单独验证。

## 复现七组矩阵

控制脚本使用 Python 3.11+，先自行安装上表四个精确 CPython，再准备解释器映射文件（路径替换为你自己的绝对路径）：

```json
{
  "3.11.17": "/path/to/cpython-3.11.17/bin/python3",
  "3.12.15": "/path/to/cpython-3.12.15/bin/python3",
  "3.13.16": "/path/to/cpython-3.13.16/bin/python3",
  "3.14.8": "/path/to/cpython-3.14.8/bin/python3"
}
```

从 `django-theme` 目录运行：

```bash
python -m pip install build
python -m build --wheel

bash scripts/test-matrix.sh \
  --root /tmp/nova-matrix-new-run \
  --wheel /absolute/path/nova_django_admin_theme-0.6.1-py3-none-any.whl \
  --interpreters /absolute/path/interpreters.json \
  --with-captcha \
  --find-links /absolute/path/wheelhouse \
  --preflight
```

先加 `--preflight` 核对所有输入和真实解释器版本，确认后去掉它执行；预检不创建环境。输出目录必须是源码树外**尚不存在**的路径，脚本拒绝重用已有目录。重跑用新的目录，日志保留于各自目录，不把失败或中断的运行混入最终结果。

默认执行七组的核心源码和 wheel；`--with-captcha` 再增加对应的可选集成，合计28个独立环境。每个环境固定应用与测试依赖、执行 `pip check`、校验导入来源、检查 Django 系统和迁移漂移，再执行相应测试。核心环境没有 Pillow / captcha；wheel 模式断言从自己的 site-packages 加载主题，源码目录不会加入其导入路径。数据库为内存 SQLite，验证码并发测试使用该环境内的独立临时测试文件，避免碰 Demo 数据库。

依赖精确值在 `scripts/test-matrix.json`，默认使用官方 PyPI、`--no-deps --only-binary=:all:`，不自动解析新传递依赖或构建源码包。`django-ranged-response==0.2.0` 上游只有 sdist：可在单独构建环境先运行 `python -m pip wheel --no-deps django-ranged-response==0.2.0 --wheel-dir /absolute/path/wheelhouse`，核对官方源码 SHA-256 `f71fff352a37316b9bead717fc76e4ddd6c9b99c4680cdf4783b9755af1cf985` 并保留构建依赖版本，再把此本地 wheelhouse 显式传入。源码入口和摘要见 [PyPI 文件页](https://pypi.org/project/django-ranged-response/0.2.0/#files)。本轮实际使用固定 setuptools84.0.0 / wheel0.48.0 的独立构建环境、`--no-index --no-deps --no-build-isolation`，由已校验的源码包离线构建。

`--find-links` 只接受本地目录；加 `--no-index` 才是完全离线依赖安装，此时必须准备所有选定 Python 对应的完整 wheel 集合，包括各 ABI 的 Pillow。提供的本地包需由维护者确认来源；脚本的安装报告记录选择的文件与摘要，不把任意本地文件当作已验证官方来源。虚拟环境自带 pip 的版本也会记录，但不声称整个操作系统或所有构建工具逐字节可复现。

`--cell 3.12.15/6.1.1` 可限定单组，`--mode source` / `wheel` 可限定方式；子集结果不会标为完整矩阵。`PYTHON` 仅选择控制脚本解释器；`NOVA_MATRIX_ROOT` 可指定新的运行目录，旧 `NOVA_MATRIX_LOGS` 已改为运行目录内分组日志。控制脚本本身的25项无网络检查用 `python3 -I -B scripts/tests/test_matrix_runner.py` 执行，不混入 Django 核心套件。

失败结果和未执行步骤都保留在 `results.json` 与每组日志中；失败返回非零退出码。单独的种子命令、静态导出、安全消毒和浏览器检查不计入这28次 Django 套件，需按对应说明另外执行。

## 官方依据

- [Django 支持版本与截止日期](https://www.djangoproject.com/download/#supported-versions)
- [Django / Python 兼容表](https://docs.djangoproject.com/en/6.1/faq/install/#what-python-version-can-i-use-with-django)
- [Python 分支生命周期](https://devguide.python.org/versions/)
- [2026-10-01 Python 安全发布](https://blog.python.org/2026/10/python-31022-31117/)
- [Astral uv 0.12.22 发布](https://github.com/astral-sh/uv/releases/tag/0.12.22)
- [Astral Python 20261001 发布](https://github.com/astral-sh/python-build-standalone/releases/tag/20261001)
- [固定 Python 下载元数据及摘要](https://raw.githubusercontent.com/astral-sh/uv/0.12.22/crates/uv-python/download-metadata.json)
- [Pillow 12.2.0 官方文件](https://pypi.org/project/pillow/12.2.0/#files)
- [django-simple-captcha 0.7.0 变更说明](https://django-simple-captcha.readthedocs.io/en/latest/changes.html#version-0-7-0)
