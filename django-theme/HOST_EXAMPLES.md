# 五个可复制的宿主集成示例

每次选择一个配置运行。五个配置各用一个本地 SQLite 数据库，共用 Demo 的回环访问限制。示例代码在源码仓库及源码分发包的 `demo/` 目录中。

## 启动

在 `django-theme/` 目录、Python 3.12 虚拟环境中执行。将第二行的配置名换成下表中的任一项。

```sh
python -m pip install -e .
export DJANGO_SETTINGS_MODULE=config.audit_settings
python demo/manage.py migrate
python demo/manage.py createsuperuser
python demo/manage.py runserver 127.0.0.1:8000
```

| 配置 | 启动前准备 | 浏览器入口 |
|---|---|---|
| `config.audit_settings` | 通过后台新增或修改一条标签，产生第一条原生日志 | 后台首页 → 管理 → 日志条目，或 `/admin/admin/logentry/` |
| `config.reset_settings` | 创建管理员时填写邮箱 | `/admin/login/` → 找回登录凭据 |
| `config.import_settings` | 迁移后运行 `python demo/manage.py seed_demo` | 商品列表 → 导入库存 CSV |
| `config.media_settings` | 迁移前运行 `python -m pip install 'Pillow>=12.2,<13'` | `/admin/private_media/attachment/` → 增加私有图片 |
| `config.mfa_settings` | 迁移前运行 `python -m pip install -e '.[security]'`。创建管理员后按下文绑定验证器 | `/admin/login/` → 验证器或一次性恢复码 |

打开 [本机后台](http://127.0.0.1:8000/admin/)。切换配置后，重新迁移、创建该示例的账号并启动对应进程。会话和密码重置令牌使用当前进程的 Demo 密钥；需要跨重启使用时，通过环境变量提供自己的 `DJANGO_SECRET_KEY`。

## 审计查看器

复制 [后台注册类](demo/host_audit/admin.py)，在宿主的 AdminSite 注册 Django 的 `LogEntry`。示例读取既有日志，提供操作者、动作和时间筛选以及只读详情。授予 staff 账号 `admin.view_logentry` 后，可查看**整个站点**的日志，包括已删除对象的名称。租户级审计需要宿主提供日志查询范围。

验证时先以操作者身份修改一条标签，再以审计员身份按操作者和“修改”筛选，打开该条详情。撤销查看权限后，直接访问详情也会被拒绝。超级管理员在此查看器中同样只能读取。

## 密码重置

把[四条命名路由](demo/config/reset_urls.py)放在宿主 AdminSite 的通配路由前，合并[邮件后端与登录地址配置](demo/config/reset_settings.py)。请求重置后，从运行开发服务器的终端取得邮件链接，设置新密码并从完成页返回后台登录。

示例沿用 Django 的本地账号资格规则，所有激活且有可用密码的匹配账号均可收信。输入格式正确的未知、停用或仅使用外部身份认证的账号邮箱时，页面给出相同的跳转和提示。重复或过期链接显示失效。自动测试使用内存邮箱。生产宿主负责受信任的 HTTPS 链接域名、发件配置、投递监控和频率限制；同步投递仍可能产生响应时延差异。[Django 密码重置](https://docs.djangoproject.com/en/5.2/topics/auth/default/#django.contrib.auth.views.PasswordResetView)

## 商品库存 CSV 导入

复制 [stock_import 应用](demo/stock_import/)及其迁移，把 [ProductAdmin](demo/catalog/admin.py) 中的 `import_urls(self)` 和 `can_import(request, self)` 接到宿主的商品列表及[工具栏](demo/catalog/templates/admin/catalog/product/change_list.html)。字段为唯一 `sku` 和可编辑的 `stock`，库存、预览表及 Admin 日志使用同一数据库。普通操作员需要 `catalog.change_product` 和 `stock_import.import_stock`。宿主应把自己的对象与库存字段授权规则接到 `editable()`。

运行种子命令后，将以下内容保存为 UTF-8 CSV 文件并上传。

```csv
sku,stock
NOVA-DEMO-KEYBOARD,27
NOVA-DEMO-STAND,6
```

1. 上传。固定两列表头，最多 256 KiB、500 条数据，接受 UTF-8 BOM。
2. 校验。逐行显示重复 SKU、无效库存或不可操作的商品。重复 SKU 的所有行都标错。可以下载经公式防护处理的错误 CSV，修正后重新上传。也可以明确选择跳过错误行。
3. 预览。核对有效行的 SKU、原库存、新库存及跳过数量。预览绑定操作者和 AdminSite，15 分钟有效，下一次上传会清理过期预览。
4. 确认。服务端重新检查权限、商品版本与库存，在同一事务内更新选定行并写入原生商品历史。任一行发生冲突，整批回滚。重复提交同一预览只返回已有结果。

可在另一标签页修改其中一条商品，再确认旧预览，验证两条都没有被旧值覆盖。宿主部署时也应在接收请求的网关设置上传体积上限。

## 私有图片

复制 [private_media 应用](demo/private_media/)并按[配置示例](demo/config/media_settings.py)指定私有存储目录。普通 staff 需要 `private_media.add_attachment` 上传，需要 `private_media.view_attachment` 查看自己的附件；超级管理员可查看全部。宿主可以在 `get_queryset()` 和对象权限钩子中接入自己的归属规则。

上传一张 PNG 或 JPEG，在列表或详情中分别打开“预览”和“下载”。两条路由每次请求都会校验权限。撤销查看权限后，原链接返回 404。文件限制为 2 MiB、400 万像素，服务端只保存重新解码并编码的静态 PNG，拒绝 SVG、HTML 和动画。目录位于仓库的 `.local/nova-private-media/`，由授权视图读取。部署时将目录置于 Web 服务器公开映射之外。[合成图集](demo/catalog/media.py)继续服务于公开静态列表配图。

## MFA 与会话

复制 [宿主表单、AdminSite 和绑定命令](demo/host_mfa/)，合并 [MFA 设置](demo/config/mfa_settings.py)和[登录路由](demo/config/mfa_urls.py)。继续使用已有 Axes 与 CAPTCHA 路由。后台授权同时要求 staff 身份和已验证的设备。该示例每种方式使用一个已确认设备。[django-otp 的认证与授权](https://django-otp-official.readthedocs.io/en/stable/auth.html)

在可信本地终端为刚创建的管理员绑定验证器，将以下 `myadmin` 替换为账号名。

```sh
export DJANGO_SETTINGS_MODULE=config.mfa_settings
python demo/manage.py enroll_totp myadmin
python demo/manage.py addstatictoken myadmin
```

第一条管理命令提供手动录入密钥，输入当前动态码验证成功后才保存设备。第二条命令生成一次性恢复码，应离线保存。使用下一周期的动态码、密码及图形验证码登录。设备遗失时，选择“一次性恢复码”登录，由获授权的管理员撤销旧设备，再重新绑定；恢复码用过即失效。耗尽恢复码时，可由宿主运维核实身份后在可信终端补发。

本例的普通登录使用浏览器会话 Cookie，服务端会话期限为 8 小时；勾选“记住这次登录”时设置 7 天持久 Cookie。两项时长均在宿主配置中。关闭浏览器时的实际 Cookie 清理还受浏览器会话恢复设置影响。可验证同一动态码无法二次登录、错误第二因素计入 Axes 锁定、撤销设备后既有后台会话失去访问权。

## 独立验收

在 `django-theme/` 目录执行以下命令。复验全部示例需安装 `.[security]` 和 `requirements-test.txt`。每条命令使用测试数据库。

```sh
python demo/manage.py test host_audit.acceptance --settings=config.audit_settings
python demo/manage.py test tests.test_host_reset --pythonpath . --settings=config.reset_settings
python demo/manage.py test stock_import.acceptance --settings=config.import_settings
python demo/manage.py test private_media.acceptance --settings=config.media_settings
python demo/manage.py test host_mfa.acceptance --settings=config.mfa_settings
```
