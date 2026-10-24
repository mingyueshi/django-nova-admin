# 一条命令启动本地 PostgreSQL / 多 AdminSite 示例

这是**本地集成样例，不是生产部署模板**。复用仓库里的原生 Django 模型、ModelAdmin、模板和 Nova 主题；不连接现有项目数据库，不发布后台，不提供共享账号。需要 Python 3.10+、已运行的 Docker，以及支持 `up --wait` 的 Docker Compose v2。使用 Linux、macOS 或 WSL 的普通用户终端。

在仓库根目录执行（首次构建需要访问 Docker Hub / PyPI）：

```sh
python3 examples/compose/demo.py up --create-superuser
```

该命令生成仅本机保存的随机密钥，构建镜像，启动专用 PostgreSQL，等待健康检查，运行迁移、加入少量合成记录，然后由 **Django 自己交互式询问**用户名、邮箱和密码。密码不回显，不写入启动参数、配置或日志；数据库只保存 Django 的密码哈希。无需使用真实姓名、邮箱或重复使用其它服务的密码。没有默认用户名或密码。取消账号创建不会删除已启动的服务。

- 主站点：http://127.0.0.1:8000/admin/ ，保留已有注册的商品、分类、标签、成年会员合成资料、新闻以及 Django 用户/组
- 仓库站点：http://127.0.0.1:8000/warehouse/ ，只显式注册商品、分类和标签，复用原 ModelAdmin 类，并生成各站点独立的实例
- 两个站点共享本样例的数据库、用户、会话和模型权限。它们是两个管理入口，**不是租户隔离、独立认证域或不同权限策略**。可用用户管理页创建限制权限的 staff；样例不自动授予业务权限

已有账号时重启无需再次创建：

```sh
python3 examples/compose/demo.py up
```

也可以先仅启动服务，再明确创建账号：

```sh
python3 examples/compose/demo.py up
python3 examples/compose/demo.py createsuperuser
```

## 可选验证码

```sh
python3 examples/compose/demo.py up --captcha --create-superuser
```

`--captcha` 同时选择镜像构建 extra 和运行时 app/form/URL 配置，安装 `django-simple-captcha==0.7.0` / `Pillow==12.2.0` 并迁移验证码表。主站和仓库站都要求验证码；只挂载一组共享图片/刷新地址，避免上游全局 URL 名称重复。没有外部验证码服务、API key 或自动音频能力。

开关保存在本地，后续 `up` / `logs` / `down` 使用同一选择。已有账号时不要重复传 `--create-superuser`。需要关闭本例的认证验证码时显式运行：

```sh
python3 examples/compose/demo.py up --no-captcha
```

这会重建无验证码的镜像并移除本例的验证码登录配置，保留数据库。**切回 Django 原生外观不会关闭验证码**。不要把样式开关当认证安全开关。此 Compose 例不自动启用 Axes / SSO / MFA；安全工具的独立示例见 [验证码集成说明](../../django-theme/CAPTCHA_INTEGRATION.md)。

## 隔离、密钥和重复启动

- 仅将 web 的 8000 端口发布到 `127.0.0.1`；PostgreSQL 没有宿主端口。容器内 runserver 的 `0.0.0.0` 只用于接收 Docker 转发，不改变宿主的回环绑定
- 项目名由本例所在绝对路径的摘要生成，卷和网络沿用 Compose 的项目隔离规则；没有固定 container_name、共享 external 卷或真实数据库地址。另一个检出目录用另一个项目；同机并行需指定不同端口：`up --port 8001`
- `examples/compose/.local/` 权限为 700；其中 `postgres_password` 和 `django_secret_key` 使用 Python `secrets` 生成，权限为 600，重复启动复用。它们被 Git 和 Docker build context 排除，不会拷进镜像。请保护本地目录；Compose file secrets 是文件挂载，**不是加密保险库**
- web 使用宿主普通用户的 UID/GID，以读取 owner-only 的挂载文件；PostgreSQL 使用官方镜像的初始化/降权流程。不要用 sudo 运行启动器，或改宽密钥权限解决 UID 问题；rootless Docker / 用户命名空间映射需要单独验证
- 配置仅接收 `NOVA_DJANGO_SECRET_KEY_FILE` / `NOVA_POSTGRES_PASSWORD_FILE` 的路径，不把密钥明文放进 Compose 环境或构建参数。可以在首次启动前用自己的本地秘密管理流程创建这两个 owner-only 文件（单行、至少 32 字符）；不要粘贴真实凭据进文档、仓库或 shell 历史
- PostgreSQL 初始化变量只对空数据目录生效。不要在保留卷时删除/替换密码文件，替换文件不会修改数据库角色密码；已初始化的样例缺少文件时启动器会拒绝生成替代密码。恢复原文件后再启动
- `down` 保留数据库卷、账号和密钥。移动目录会改变项目摘要，请先在旧位置停机，记录原项目/卷，再按 Docker 的备份迁移流程处理；不要把改路径当数据库迁移
- 启动器不修改 Docker 配置，不安装 daemon，不执行全局清理，不删除卷。启动失败可先用 `logs` 查看；保留现场与密钥后修复原因，再重复 `up`

```sh
python3 examples/compose/demo.py config       # Docker Compose 解析校验，不展示密钥内容
python3 examples/compose/demo.py status
python3 examples/compose/demo.py logs
python3 examples/compose/demo.py check
python3 examples/compose/demo.py down         # 停止当前目录对应的项目，保留数据卷
```

`config` / `check` 不代表完成生产安全验证。主程序健康探针只检查 HTTP 开始服务；不是数据库故障监控。样例只加 2 个商品、1 个合成成年会员、1 条新闻及关联，按固定标识 `get_or_create`；不会覆盖已有值、恢复被删关系或创建认证用户。已有 SQLite 示例和它的 `seed_demo` 限制保持原样。

## 版本、可复现性和官方依据

默认选择 Python `3.12.15-slim-bookworm`、PostgreSQL `17.11-bookworm`、Django `5.2.17`、Psycopg binary `3.3.6`。Python / PostgreSQL tag 在 2026-10-03 对照 [Python 官方镜像](https://hub.docker.com/_/python) 和 [PostgreSQL 官方镜像](https://hub.docker.com/_/postgres)核对；[Psycopg 官方安装说明](https://www.psycopg.org/psycopg3/docs/basic/install.html)与 [3.3.6 发布记录](https://pypi.org/project/psycopg/3.3.6/)说明 binary extra。

这固定了所选版本标签，**不是 immutable image lock / 完整传递依赖 lock / 可重复构建证明**。未拉取镜像，因此没有编造 digest。需要冻结镜像时，由使用者在自己的 Docker 主机读取并审核真实 manifest digest：

```sh
docker buildx imagetools inspect python:3.12.15-slim-bookworm
docker buildx imagetools inspect postgres:17.11-bookworm
```

将审核后的完整引用分别通过 `NOVA_PYTHON_IMAGE`、`NOVA_POSTGRES_IMAGE` 提供给启动器；例如引用格式为 `python:3.12.15-slim-bookworm@sha256:<已验证的真实digest>`。不要复制占位符，不要无计划更改 PostgreSQL 主版本；17 的卷位置与 18+ 不同。冻结 digest 后也要主动评估安全更新，参见 [Docker 版本与 digest 固定说明](https://docs.docker.com/build/building/best-practices/#pin-base-image-versions)。镜像/依赖升级后重新做下方真实容器验收。

文件 secrets、健康检查启动顺序分别遵循 [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/) 与 [启动依赖文档](https://docs.docker.com/compose/how-tos/startup-order/)。PostgreSQL `_FILE`、初始化、卷目录行为参见上面的官方镜像说明；`pg_isready` 只报告连接状态，见 [PostgreSQL 文档](https://www.postgresql.org/docs/17/app-pg-isready.html)。

## 验证记录与未验证范围

2026-10-03 的首次验证环境没有 `docker` 可执行文件，当时**没有执行镜像构建、docker compose config、容器启动、PostgreSQL 迁移或 PostgreSQL 验证码并发测试**，也没有为此安装 Docker。以下保留当时的结果；SQLite 检查不代替 PostgreSQL 验收。

已验证（2026-10-03）：

- 启动器 11 项标准库测试：秘密唯一性/复用/权限、符号链接拒绝、已初始化后丢密钥拒绝、项目隔离、选项持久化、明确交互创建账号、无 Docker 时无写入、停机保留卷
- 5 项 YAML 静态隔离检查（PyYAML 6.0.3）：仅 loopback 暴露、项目卷/网络、file secrets、健康依赖、build context 排除；这不等价于真实 Compose 解析
- Python 3.12.15 / Django 5.2.17 下真实 Django + SQLite 集成检查，core 8/8、CAPTCHA 8/8：原生注册、独立 ModelAdmin、权限、站点 URL/主题返回边界、CSRF、原生外观中的验证码及认证前拒绝、幂等合成种子

在已有相应依赖的 Python 环境中复现：

```sh
python3 examples/compose/test_launcher.py
python3 examples/compose/test_configuration.py  # 需要测试工具 PyYAML
python3 examples/compose/verify.py             # 需要 Django 与源码
python3 examples/compose/verify.py --captcha   # 另需主题 captcha extra
```

### 2026-10-24 本机容器验收

本次运行验收绑定源码 `243effb0569591f2732831a0650cac99c9f8e704` 及其 222 份隔离输入，随后仅补充本文记录。环境为 macOS ARM64 宿主上的 Docker Desktop **Linux ARM64 容器**，web 只绑定 `127.0.0.1:4189`，PostgreSQL 没有宿主端口映射。逐项独立复核与脱敏回执索引见[统筹验收台账](../../DIAGNOSTIC_PROGRESS.md)。

| 组件 | 实际验证版本 |
| --- | --- |
| Docker Engine / Compose | 29.9.2 / 5.6.1 |
| 宿主启动器 Python | 3.12.14 |
| 容器 Python | 3.12.15（`3.12.15-slim-bookworm`） |
| Django | 5.2.17 |
| PostgreSQL | 17.11（`17.11-bookworm`，Debian 17.11-1.pgdg12+2） |
| psycopg binary | 3.3.6 |
| django-simple-captcha / Pillow | 0.7.0 / 12.2.0 |

早期“未拉取镜像”的描述属于 2026-10-03 记录。本次已实际构建镜像；Python 基础镜像沿用 `sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70`，PostgreSQL 沿用 `sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27`。这些版本与摘要限定本次环境，未形成完整传递依赖锁定。

本机已验收：

- core 与 CAPTCHA 两种镜像分别完成构建、`pip check`、Compose 配置校验及健康启动；实际 PostgreSQL 认证连接、迁移与合成种子读回通过，无待迁移。
- `/admin/`、`/warehouse/` 均完成真实桌面浏览器登录和退出、只读 staff 权限拒绝、分类自动补全、标签多选、规格 inline 与表单保存；Nova 与 Django 原生外观均有实际工作流。有效 CSRF 可以保存，缺失 CSRF 被拒绝；两站主题表单的跨站 `next` 均回到请求站点。
- CAPTCHA extra 实际安装并迁移；两站图片生成与 UI 刷新、刷新 POST/CSRF 校验、旧挑战拒绝、错误答案不登录及正确答案登录通过。`CAPTCHA_TEST_MODE=False`、`CAPTCHA_GET_FROM_POOL=False`，使用真实合成挑战，答案和密码未输出到回执。
- 真实 PostgreSQL 的两条独立连接同时读到同一挑战后，仅一方成功提交消费；外层事务回滚恢复挑战，随后提交消费后重放被拒绝。真实行锁超时异常向调用方传播，认证入口与后端均未被调用；正向对照实际调用认证后端并通过。仅处理本阶段新建挑战，没有清空验证码表。
- 原始完整 `demo.py up` 重复启动，以及 `down` 后从同一保留卷 `up` 均通过。两件已编辑商品的字段、关系和规格、4 个合成账号的原密码及权限保持一致，种子未覆盖哨兵；原卷、密钥与 options 保留。最终收尾只移除本项目容器和网络、关闭 4189，未操作无关资源。

2026-10-23 首次一体启动达到 300.009 秒外层超时，该总预算包含镜像下载、构建和启动；日志停在 web Starting，事后 web 仍为 Created。随后将构建和启动分开计时，完成上述运行闭环。分步成功没有确定首次启动未完成的底层原因，也没有证明应用或 Docker 存在故障；历史超时及核对脚本失败回执保留，最终结果以逐项独立复核为准。未修改运行代码或放宽启动器默认健康等待超时。

本次范围为上述版本和本机容器环境。T3 音频生成/播放、T4 物理真机与屏幕阅读器、完整 CI、完整 Python/wheel/可选依赖矩阵及生产部署/安全验收均未覆盖；本次没有运行新的完整矩阵。更换宿主、镜像或依赖、数据库及认证配置后，需要在目标环境重新验收。

本例使用 `DEBUG=True`、Django development server、HTTP 和 PostgreSQL 初始化管理员角色，没有生产 TLS、最小数据库角色、备份/恢复、限流、MFA/SSO、审计、验证码清理调度、可访问替代认证或生产 CSP 配置。它不承诺公开托管、全浏览器/无障碍认证或生产安全审计；生产项目应采用自己的已审核部署与认证流程。
