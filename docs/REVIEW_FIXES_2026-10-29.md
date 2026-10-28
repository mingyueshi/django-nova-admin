# 2026-10-29 问题核实与修复

本次针对用户提供的清单核实当前源码。以下验证在本地提交前执行，未推送、部署或触发远端 Actions。清单低危部分按实际列出的 23 条逐项记录。

## 高危与中危

高危修复位置：H1 为 `django-theme/src/nova_admin/captcha.py:157`（公开音频请求
可重复启动进程，影响登录服务可用性）；H2 为 `.github/workflows/ci.yml:229`
和 `django-theme/scripts/test-security.py:72`（此前 CI 无法证明真实 Slider 登录路径未回归）。

| 项目 | 核实结果与处理 |
|---|---|
| H1 音频放大 | 确认。`captcha.py` 在生成前用缓存原子计数；默认每挑战 6 次、每连接 IP 20 次、窗口 60 秒。超限返回无缓存的 429 和 Retry-After，计数存储失败返回 503，均不启动工具。失败的生成也占预算。保留挑战消费保护、Range 和独立文件所有权。多 worker 需共享且支持原子 add/incr 的缓存，LocMem 仅限制本进程。 |
| H2 Slider CI 空缺 | 确认。`test-matrix.json` 新增 slider/security profile；安全 job 从固定公开提交 `62a93e7efc2d4f1cca0a9390627f5a821c4c742c` 和 SHA-256 校验的源包构建 provider wheel。独立安装环境执行真实登录、重放、purpose、跨会话、CSRF 和策略用例，缺 provider、零用例、跳过或失败均拒绝通过。 |
| M1 多站点回跳 | 确认嵌套实例会错站。preference 根据当前 URL 的外层实例命名空间构造站点 index，并传入 current_app/request.urlconf；增加嵌套站点和外层实例命名空间不同、AdminSite.name 相同的两实例回归。根层直接重复同一 namespace 本身会触发 Django urls.W005，不能仅靠 current_app 区分，仍须为挂载配置可区分的实例命名空间。 |
| M2 裸 demo | 固定密钥与无连接限制属实。改为环境密钥或每进程随机临时密钥，并在请求进入应用前拒绝非回环连接，不信任 Host/转发头。Compose 明确沿用密钥文件及回环端口发布。原描述“能伪造 session cookie”不适用于默认数据库 session 后端（[Django session 说明](https://docs.djangoproject.com/en/5.2/topics/http/sessions/#configuring-the-session-engine)）；但公开密钥仍不应保留。 |
| M3 输入名称 | 未复现。支持的 django-simple-captcha 0.7.0 的 BaseCaptchaTextInput.id_for_label() 已返回答案输入的 `_1` ID；现有登录测试实际断言 `label[for=id_captcha_1]`、帮助说明和可见字段。保留上游实现，避免重复覆盖破坏 id_prefix。 |
| M4 打印观察器 | 确认。仅观察影响可见性/排除规则的属性和结构变更，以 requestAnimationFrame 合批；等待下一帧期间立即清除旧可见性快照，避免 print CSS 显露此前隐藏内容。增加无关属性忽略、跨回调合批、打印抢先发生的回归。 |
| M5 extras | 确认集成版本限制过严；并非每个宿主都必然冲突。公开 extras 改为兼容范围：captcha >=0.7,<0.8、Pillow >=12.2,<13、Axes >=8.3,<9；测试矩阵仍保留精确版本。 |
| M6 忽略项 | 部分已解决：根 .gitignore 原本已有 .mimosa/、.video_agent/。补充 .DS_Store、根 tmp/、output/ 和 demo/staticfiles/。 |
| M7 review 存档 | 有意存档，保留。`docs/REFACTOR_NOTES.md` 明确引用两份 patch 作为离线审阅差异，`docs/QA.md` 引用同一材料。删除当前文件也不会缩小既有 Git 历史。 |
| M8 交互测试 | 确认。实际是 31 个断言；改为每例创建和 finally 关闭 app、显式准备自身数据、失败后继续报告其他例，可通过名称筛选单跑。 |

## 低危逐项处理

| 项目 | 处理 |
|---|---|
| L1 策略 incr 最后一层过期 | 所有过期重试改为有界循环；反复竞态时本响应升级显示验证码，不再抛 ValueError。真实缓存故障继续拒绝登录。 |
| L2 脏计数值 | 非非负整数按 0 处理并移除脏条目，缓存操作本身失败仍传播；增加字符串、None、负值、bool 回归。 |
| L3 kill 后无限 wait | 最终 reap 有 0.2 秒超时，并关闭输出管道；无法承诺立即回收处于内核不可中断 IO 的进程。 |
| L4 多模板引擎漏报 | 每个 DjangoTemplates 引擎都检查 theme context processor，增加多引擎回归。 |
| L5 navigation 空节点 | 三处标题查询改为可选访问和空字符串回退；DOM 套件增加缺标题/字段的局部 markup 检查。 |
| L6 裸 button | 通过 form.elements 的实际 type 属性识别 submit，包含缺省 type 及关联表单按钮；增加刷新锁定回归。 |
| L7 next 依赖 request processor | theme processor 直接输出 get_full_path()，模板消费该值；移除 request processor 后仍保留查询参数的回归通过。 |
| L8 多余 navigation.js | 与其他导航脚本一致，要求 has_permission 且非 popup；nonce 测试使用实际授权上下文。 |
| L9 options.json 未知键 | 拒绝非 object、缺键和未知键，均走已有 ValueError 干净报错路径；增加 launcher 回归。 |
| L10 icons 的 JS 模板字面量 | 内嵌 JSON 将反引号和 `${` 编码为 JSON unicode 转义；加入数据完整性回归，现有 320 图标无额外生成差异。 |
| L11 RECORD/构建暂存 | RECORD 每行先校验 3 字段；暂存复制排除 staticfiles 与 .DS_Store。 |
| L12 wheel JS 路径变动 | 缺失资产转换为包含 Django 版本及具体路径的 ValueError；路径仍是需要显式复核的上游契约。 |
| L13 对比度 JSON 契约 | 同时捕获 OSError，缺文件仍输出结构化失败 JSON。 |
| L14 PYTHONPATH | 在示例自身路径后追加已有 PYTHONPATH。 |
| L15 批量上架时间 | queryset.update() 显式写入 updated_at=timezone.now()；原生 action 测试核验时间推进。 |
| L16 security 测试库 | 默认每进程独立 TemporaryDirectory，保留环境指定路径；矩阵按 profile/版本继续独立指定测试库。 |
| L17 本地 build 漂移 | 旧 build 移入忽略的 `.local/audit-fixes-20261029/stale-build/`，重新从 sdist 构建并核对 wheel 与源码。 |
| L18 asgiref 双源 | 将 main 实验覆盖集中到 manifest 的 upstream profile，并在 workflow/文档解释它为何不同于受支持版本。 |
| L19 CI 重复版本清单 | 安全依赖和各 Django 下载列表从矩阵配置生成。 |
| L20 full 仅发行阶段 | PR/push 保留 quick 的既有取舍，增加每周二 05:23 UTC 的 full。只有配置变更，尚未观察到该定时运行。 |
| L21 Python 3.10 声明 | 补充分类器，quick/full 均加入 3.10.20 / Django 5.2.17；本地实际验证源码和 wheel。 |
| L22 npm 版本解析 | 提取唯一完整语义版本行，忽略前后警告；零个或多个版本行拒绝通过。 |
| L23 测试数量 tripwire | 在 CI_CD.md 明确新增测试需同步成功摘要和数量。同时实跑发现导航原有 123 项与旧 108 契约不符，修正为实际值；加上打印/CAPTCHA 回归后主题 JS 共 278 项。 |

## 验证范围

本地证据在忽略目录 `.local/audit-fixes-20261029/`；安装包矩阵使用 `/tmp/nova-security-audit-20261029/`，Python 3.10 核心矩阵使用 `/tmp/nova-audit-py310-20261029/`。本地 Python 为 3.12.14 / 3.10.20，不能冒充 workflow 指定的 3.12.15 等全部运行时已经执行。

| 验证 | 结果 |
|---|---|
| Django 6.1.1 核心源码 / 安装 wheel | 各 436 项，3 项为未启用可选集成的预期跳过 |
| CAPTCHA + 策略源码 / 安装 wheel | 各 76 项通过，含合成可执行文件、并发、超时和清理 |
| Slider + 策略源码 / Axes 源码 | 31 / 16 项通过 |
| 三版 Django 的安全安装包矩阵 | 6 个隔离环境均通过：每版 Axes 16 项、Slider + 策略 31 项 |
| Python 3.10.20 / Django 5.2.17 | 核心源码和 wheel 均通过，含依赖、来源、check、迁移检查与测试 |
| npm test | 20 套件、1,398 项通过，31 个交互例亦可单跑 |
| 主题 JS + 真实摘要契约 | 278 项通过，使用三版官方 Django wheel 中校验过的 sidebar/filter 脚本 |
| CI 适配器 / 矩阵 runner / Compose launcher | 103 / 25 / 12 项通过 |
| Compose Django/SQLite | 8 项通过（启用 CAPTCHA）；未启动 Docker/PostgreSQL |
| Compose 配置检查 | 5 项通过 |
| 构建 / 静态检查 | wheel/sdist 与源码一致，63 个运行时文件和 215 个源包文件；图标一致性、对比度、actionlint、git diff --check 通过 |

最终交付 wheel 的运行时逐字节等于上述受测 wheel；最后一次重建仅更新 README 等包内说明，比较结果保存在 `delivery-artifacts.json`。构建时工作区尚未提交，因此未绕过发行构建的 clean-checkout/SHA 门禁，也未将本地构建称为发行候选。

人工音频听辨、真实浏览器布局/设备/读屏、Linux 全矩阵和生产部署不属于这些本地自动化结果。

## 提交前边界复核

无需为以下已知前提追加代码修复：音频限流需要宿主正确配置连接真实对端地址和共享原子缓存；裸 demo 的临时随机密钥用于单进程预览，多 worker 必须显式提供一致的环境密钥。不要通过直接信任任意转发头或恢复公开固定密钥来消除这些部署前提。

本地验证不能代替 Actions 的实际运行。推送后需检查首次 security job 的 Slider/Axes 结果；每周 full 的触发时间为周二 05:23 UTC，尚未观察到该定时事件。提交应完整包含 `demo/config/local_demo.py`、`tests/test_demo_boundary.py`（均位于 `django-theme/` 内）和本记录三个新增文件。
