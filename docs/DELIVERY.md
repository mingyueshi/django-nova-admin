# NOVA Admin 交付说明 · 2026-10-05

本页保留 10 月 5 日导入交付的历史记录。当前官方仓库为 `mingyueshi/django-nova-admin`，主题 `0.6.1` 的新发行准备见 [发行与升级说明](../django-theme/RELEASING.md) 和 [实际验证](../django-theme/RELEASE_VALIDATION.md)；下方版本、来源和次数不作为本次发行包的结果。

## 版本与来源

- 交互预览：1.8.0；Django 主题：0.6.0
- 已核准云端源码提交：5175ea0084378dce63dafb46cebe0f0065e88eb7，2026-10-03
- 本次交付保持全部运行代码不变；更新下载交付说明和本地秘密忽略规则
- 最新源码仓库：https://github.com/mingyueshi/nova-admin
- 新仓库采用当前源码快照，未携带原发布环境绑定或旧 Git 历史

## 内容和使用

- dist/ 就是完整静态前端源码，无需 React/Vue 构建，运行方式见 README.md
- django-theme/ 包含真实主题、Django Demo、测试、翻译和集成说明
- examples/compose/ 是 PostgreSQL、验证码与多 AdminSite 的独立开发示例
- ci/ 与 .github/workflows/ 包含快速/完整验证、手动候选产物及上游漂移检查
- ZIP 另带 django-theme/dist/nova_django_admin_theme-0.6.0-py3-none-any.whl，可在独立测试环境安装；Git 仓库可直接安装主题源码
- ZIP 解压后先运行 python3 scripts/verify_package.py 校验，再按 README.md 启动
- 生产接入先确认宿主 Django/Python 版本，保留现有认证、验证码、CSRF、权限以及原生回退；不要直接使用 Demo 设置部署生产

## 本次重新验证

- 最新源码与已发布版本来源精确匹配，运行代码未改
- Node 24.19.0、已存在的相同 jsdom 26.1.0：全部 540 项前端 DOM 测试和 JS 语法检查通过
- 主题搜索增强 8 项、验证码 JS 11 项通过
- CI/CSS/模板工具 43 项、矩阵 runner 25 项、Compose 启动器 11 项通过
- CSS 体积预算通过；wheel 的 37 个运行文件与源码逐字节一致，METADATA 版本及全部 RECORD 校验通过
- 对全部交付文件进行秘密/禁止文件检查，ZIP 完整性与解压后 manifest 校验通过

## 本次验证限制

- 环境中断后无法完成全新 npm/PyPI 依赖安装，本次未重跑 Prettier、Django 后端、依赖完整安装或完整 Python/Node 版本矩阵；上述现有依赖验证不等同于全新安装测试
- 主题导航 JS 用例依赖真实 Django 模板生成，本环境未安装 Django，所以本次未重跑该组；不计入通过数
- 历史完整版本矩阵和浏览器验收以 django-theme/TEST_REPORT.md 中 2026-10-03 记录为准；不冒充本次重新执行
- Docker/PostgreSQL、Flite/SoX 音频、旧 admin-honeypot、Django 6.2 未新增支持或验证
- 本次没有重新部署公开站或生产项目，没有配置新凭据、软件包发布或启用候选发布开关

## 安全与完整性

包内不包含 .git、.openai、真实 .env、数据库、node_modules、虚拟环境、缓存、运行日志或开发机凭据。演示和测试占位 SECRET_KEY、合成数据是源码中明确标记的非生产值。Compose 密钥在用户本机运行时随机生成。

ZIP 的 PACKAGE_MANIFEST.json 记录所有其他交付文件 SHA-256；清单自身不自引用。wheel 为本次从相同运行源码重建，ZIP 时间戳不同会使其整体 SHA 与历史 wheel 不同。
