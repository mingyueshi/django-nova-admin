# 登录页与可选验证码接入

## 独立行布局与渐进式验证

图片与答案输入框各占一行，图片按原比例显示、宽度最多为容器宽度，答案输入框没有 4 位长度限制。`CAPTCHA_LENGTH = 6` 可配置上游随机字符生成器的长度；自定义生成器也可返回 5 位、8 位或更长的答案。

现有接入默认保持 `always`（每次验证）。图片表单与下方滑块表单均可显式启用同一套服务端策略：

```python
NOVA_ADMIN_CAPTCHA_POLICY = "progressive"  # 或 "always"
NOVA_ADMIN_CAPTCHA_FAILURE_LIMIT = 2      # 同一连接 IP 的失败提交次数
NOVA_ADMIN_CAPTCHA_WINDOW = 900           # 从首次失败开始计时，单位秒
NOVA_ADMIN_CAPTCHA_CACHE = "default"      # Django CACHES 中的别名
# 可选：项目自己的服务端异常检测，不能直接信任客户端参数。
NOVA_ADMIN_CAPTCHA_RISK_CHECK = lambda request: False
```

正常请求不渲染验证码字段，也不生成挑战。第二次失败的响应就会显示验证码；之后缺失、错误、过期的验证码先于密码认证被拒绝。正确验证码配合错误密码仍保留验证要求，成功登录清除该 IP 的失败计数；未成功时计数随窗口过期。初始触发的失败包括必填字段、密码、staff 检查及验证码失败。计数不按用户名区分，不通过验证码显隐暴露账号是否存在。换浏览器或改前端隐藏字段不会清除同一 IP 的服务端计数。

这是验证码升级策略，不是密码尝试限流。多进程／多实例必须把选定缓存配置为共享、支持原子 `add`/`incr` 的后端（例如项目已有的 Redis）；默认 LocMem 只适合单进程本地演示，进程重启会清除计数。缓存、风险回调错误会传播并拒绝本次登录，不回退到免验证。默认使用连接 `REMOTE_ADDR`，忽略转发头；共享出口可能影响多名用户，可信代理/IP 解析、独立限流、MFA、SSO 和真实替代登录仍由宿主项目配置。不要把验证码当作认证后端或锁号策略。

本地图形渐进式演示使用 `config.progressive_captcha_settings`，数据库和原图片演示相同。把下方图片演示命令的 `--settings` 替换为此配置即可；它使用 6 位字符，未创建任何预设管理员。

## Nova Slider CAPTCHA 接入

滑块复用独立的 `nova-slider-captcha` **0.3.0** 包及原生 Web Component，本次同步源码固定为 `62a93e7efc2d4f1cca0a9390627f5a821c4c742c`（不代表已发布到 PyPI）。核心主题不自动导入该包，也不强制安装图片验证码。当前源代码工作区可从 `django-nova-admin` 仓库根目录安装兄弟项目：

```bash
python -m pip install -e ./django-theme
python -m pip install -e ../django-nova-slider-captcha
cd django-theme
python demo/manage.py migrate --settings=config.slider_settings
python demo/manage.py createsuperuser --settings=config.slider_settings
python demo/manage.py runserver 127.0.0.1:8000 --settings=config.slider_settings
```

`config.slider_settings` 使用独立 `demo/slider-demo.sqlite3`，没有预设账号，默认两次失败后显示滑块。切换到每次验证可在自己的设置里使用 `NOVA_ADMIN_CAPTCHA_POLICY = "always"`。这是本机开发配置；不要直接作为生产设置。

已有项目保留自己的认证后端、中间件、AdminSite 与模型注册，只显式接入表单、模板、接口和迁移：

```python
# settings.py: 加入 nova_slider_captcha，保留 nova_admin 和原项目 apps。
INSTALLED_APPS += ["nova_slider_captcha"]

# urls.py: 挂载在现有 admin catch-all 路由之前。
from django.contrib import admin
from django.urls import include, path
from nova_admin.slider import SliderCaptchaAdminAuthenticationForm

admin.site.login_form = SliderCaptchaAdminAuthenticationForm
admin.site.login_template = "nova_admin/slider_login.html"
urlpatterns = [
    path("admin/_slider/", include("nova_slider_captcha.urls")),
    path("admin/", admin.site.urls),
]
```

执行宿主项目的 `migrate` 和 `collectstatic`。这不需要外部服务或 API 密钥；安装包提供图片生成、数据库表、同源 CSRF 接口及资源。模板保留 Nova 品牌、深浅色及原生模式，组件支持拖动、触屏、方向键与 Enter。滑块需要 JavaScript，无脚本提示只引导到项目自己的替代验证渠道，不会绕过服务端要求。

`nova_slider_token` 隐藏字段由组件创建，模板不重复输出。模板用 `field-name="{{ widget.name }}"` 传入完整 Django 字段名，因此 `prefix="auth"` 的表单会提交 `auth-nova_slider_token`。表单用固定 `purpose="login"` 调用包的 `consume()`，先原子消费绑定当前会话、未过期的一次性凭证，再执行 Django 原生密码、active/staff 和安全 next 检查。密码错误也需要重新拼图。凭证过期、跨会话、跨用途、重用及接口 CSRF 失败均不能登录。不要把前端 `verified` 事件当作服务端授权；不要把消费校验放入之后可能回滚的外层事务。接口限流和清理沿用独立包的配置与 `prune_slider_captcha` 命令，需按项目实际数据库和部署方式验收。

已有 MFA/SSO／Axes 自定义表单需要组合现有逻辑，不直接替换；本适配器没有宣称自动提供滑块与 Axes 的补报联动。自定义 URL namespace 可继承 `NovaSliderWidget.get_context()` 改用自己接口的反向解析。组件只声明简体中文与英语文案；真实无障碍替代认证、生产数据库并发和负载需分别验收。

宿主可成对配置 `NOVA_SLIDER_ALTERNATIVE_URL` / `NOVA_SLIDER_ALTERNATIVE_LABEL`，提供真正可用的安全替代验证入口。URL 只允许上游校验通过的本站绝对路径；Nova 在组件外强制转义输出 URL 和标签，组件刷新不会移除链接。未配置时不显示入口，不会自动跳过验证。

公开 `dist/login.html` 默认展示渐进式预览，并可切换图形／滑块、每次／异常时验证及 5／6／8 位字符。预览复用原组件的交互代码，通过不同名称的本地演示子类替换网络传输，只使用合成 PNG、公开演示位置和临时模拟凭证；不发送验证或登录请求，不建立真实会话。MIT 原文件、许可证和 SHA256 位于 `dist/vendor/nova-slider-captcha/`。Django 适配器直接使用安装包，不使用这份 mock 子类。

验证命令（`django-theme` 目录）：

```bash
PYTHONPATH=src:demo:. python demo/manage.py test tests.test_captcha_policy --noinput
PYTHONPATH=src:demo:. python demo/manage.py test tests.test_captcha --settings=tests.captcha_settings --noinput
PYTHONPATH=src:demo:. python demo/manage.py test tests.test_slider --settings=tests.slider_settings --noinput
```

以下保留原图片验证码和 Axes 的接入细节及历史验证记录。

核心主题仍只依赖Django。验证码是项目显式选择的独立接入，使用本机 `django-simple-captcha==0.7.0`、`Pillow==12.2.0`，不调用第三方验证码服务。公开登录演示为客户端mock，不是真实认证。

## 本地试运行（独立Demo数据库）

在本包 `django-theme` 目录和你的虚拟环境内：

```bash
python -m pip install -e '.[captcha]'
python demo/manage.py migrate --settings=config.captcha_settings
python demo/manage.py seed_demo --settings=config.captcha_settings
python demo/manage.py createsuperuser --settings=config.captcha_settings
python demo/manage.py runserver 127.0.0.1:8000 --settings=config.captcha_settings
```

验证码Demo使用单独的 `demo/captcha-demo.sqlite3`，包内没有该数据库或预设账号。不要把此调试配置用于生产；现有项目的 `captcha` 迁移应走你自己的备份/部署流程。

## 接入自己的项目

1. 安装可选extra，在INSTALLED_APPS增加captcha，保留原AdminSite和ModelAdmin注册
2. 通过已有AdminSite的login_form/login_template挂入下方示例；已经自定义MFA/SSO表单的项目，应合并字段与clean前置校验，不直接替换原表单
3. 挂载本地图片/刷新URL，保留CSRF、中间件、认证后端和next校验；不需要API密钥
4. 验证码失败、过期、已使用或签名不对时，必须先拒绝而不调用密码认证。一次性消费以数据库受影响行数为准；数据库错误保持拒绝
5. 切回Django原生外观或关闭Nova样式不会关闭已启用验证码。若要移除验证，必须单独移除项目login_form/login_template/URL/app配置，不能把外观恢复当安全开关

浏览器的“换一张”通过同源CSRF POST消费旧码后生成新码，错误时锁住提交并提示重载。不启用JS时仍可正常服务端登录；重载生成新码，但旧码会保留到过期或被使用。令牌是签名的随机数据库标识，不含答案，也不绑定具体浏览器身份。

## 无障碍与部署边界

- 可操作标签、错误关联、键盘刷新、状态播报已经实现；图片答案不放在alt/HTML/JavaScript中
- 历史云环境缺少Flite/SoX，当时仅验证条件链接。2026-10-24已在独立本机容器中验收真实音频生成、双站原生/键盘/无JS播放，并依次独立验收T3-4过期保护、T3-5共享超时/稳定503、T3-6资源清理/大小限制；默认音频仍关闭，主机未安装工具。应使用 `nova_admin.captcha_urls`，原来直接挂载 `captcha.urls` 的项目需显式迁移。人工听辨、真机/读屏、其他浏览器、线上CI、完整安装矩阵及生产未验收；直接子进程、OS拒删等真实边界保留。配置和完整范围见下方[Accessibility and audio](#accessibility-and-audio)
- 项目仍需提供可用的无障碍认证或支持流程；帮助文字/链接本身不实现替代认证。图形和音频验证码都不能单独作为WCAG 2.2登录合规证明
- PostgreSQL/MySQL、生产负载、读写路由、外层事务/回滚、限流、MFA/SSO及清理策略需项目单独验收。原有事务回滚可能恢复被删挑战；不要跨请求复用表单校验结果
- 不公开测试库、动态令牌或提交端点。导出的真实样本只保留合成PNG和禁用表单

以下是具体接口、工作原理与英文参考。

## 可选 django-axes 联动（本地示例）

只安装验证码不会带来请求限流。另一个独立 extra 使用
`django-axes==8.3.1`，由 Axes 负责计数、持久化、封锁与冷却；Nova 不实现认证后端或限流器。

```bash
python -m pip install -e '.[security]'
python demo/manage.py migrate --settings=config.security_settings
python demo/manage.py createsuperuser --settings=config.security_settings
python demo/manage.py runserver 127.0.0.1:8000 --settings=config.security_settings
```

该配置使用单独的 `demo/security-demo.sqlite3`，没有默认账号；不自动启用到核心主题或普通Demo。
`config.security_settings` 是本地示例，不是生产安全配置。

- 同一连接 IP 累计5次失败后，登录返回不包含账号信息的429；冷却15分钟，封锁期间尝试不延长固定冷却；成功登录清除匹配的失败记录
- `AxesCaptchaAdminAuthenticationForm` 为验证码/必填字段失败、非staff拒绝补发一次Django标准 `user_login_failed` 信号；正常错误密码由Django报告，不重复计数。验证码错误仍不会调用密码认证后端
- `AxesStandaloneBackend` 位于原认证后端之前，`AxesMiddleware` 最后；自定义MFA/SSO项目需合并表单行为并保留自己的后端，不能直接照抄替换
- Axes后端和认证信号作用于配置的整个Django认证栈；本例的验证码表单补报只用于Admin。还有其他登录入口的项目必须统一评估范围、失败策略和日志脱敏
- Axes官方 `axes_dispatch` 包装同一AdminSite的登录、图片/音频、Nova刷新路径，已封锁IP无法通过GET产生新挑战。安全示例不挂载上游不消费旧码的GET刷新接口
- IP读取只信任连接的 `REMOTE_ADDR`，忽略用户可伪造的 `X-Forwarded-For`。反向代理/容器后面直接照搬会把多名用户视为同一IP；可信代理与IP解析必须由项目按真实部署配置和测试
- 密码、验证码答案/令牌、CSRF值在Axes请求载荷日志中被遮盖。Axes仍保存用户名、IP等审计字段；这是有访问控制的安全数据，不是匿名日志。示例验证普通staff无日志查看权限，授予Django原生查看权限后才能访问

这只是登录失败频率控制。未封锁前的登录GET、图片与刷新请求次数、分布式攻击、共享出口误封及生产吞吐仍需网关/WAF等成熟请求限流与运维策略；本例没有宣称解决这些问题。

### 账号枚举边界

真实测试比较了未知账号、错误密码、inactive和非staff账号的HTTP状态和非字段错误文本，它们一致；验证码错误不查询密码后端，封锁响应不回显账号。
这不是恒定耗时证明，也不是完整的防枚举保证：页面会正常回填提交的用户名，认证后端、响应时间、密码重置、SSO、其他接口及项目自定义错误仍需分别检查。

### admin-honeypot 共存边界

2026-10-03查验[原包PyPI](https://pypi.org/project/django-admin-honeypot/)仍为
1.1.0（2018-05-14），只声明Django1.11/2.0；没有证据支持本项目Django5.2/6.0/6.1，故没有安装、启用或承诺该包兼容。

若项目已有自行维护并验证的实现，真实AdminSite与诱捕入口应使用不同路径和namespace，保留真实站点的 `admin:login`，诱捕使用独立的 `admin_honeypot`，不要让诱捕表单执行真实认证或复用真实验证码。
本例仅以明确标记的路由哨兵验证：诱捕namespace不会覆盖真实AdminSite、不会调用密码后端或写真实登录失败记录；这不等于运行过django-admin-honeypot。
诱捕日志、告警接收方、密码脱敏和留存必须另外审查；本交付没有开启邮件或外部告警。

### 安全联动复现

```bash
export PYTHONPATH="$PWD/src:$PWD/demo:$PWD"
python demo/manage.py test tests.test_security_interop --settings=tests.security_settings --noinput
```

测试使用隔离合成SQLite库；并行运行时为 `NOVA_SECURITY_TEST_DB` 配置各自路径。
Axes8.3.1的官方声明包含Django5.2/6.0，未包含6.1；本项目自己的6.1集成测试不替代上游支持承诺。

2026-10-03本轮源码集成实测（Python3.12.15，Axes8.3.1，验证码0.7.0/Pillow12.2.0）：

| Django | Axes联动 | 原验证码回归 | 核心配置隔离 |
| --- | --- | --- | --- |
| 5.2.17 | 15/15通过 | 22/22通过 | 可选套件正常跳过 |
| 6.0.8 | 15/15通过 | 22/22通过 | 可选套件正常跳过 |
| 6.1.1 | 15/15通过（本地验证） | 22/22通过 | 可选套件正常跳过 |

覆盖验证码/必填字段/密码/非staff计数不重复、封锁后不执行密码认证或生成挑战、固定冷却与恢复、成功重置、错误文本/状态一致、CSRF、日志脱敏、可信IP边界、原生日志权限以及路径namespace隔离。
该表不代表生产负载、所有Python版本、真实admin-honeypot或音频运行验证。

---

# Optional server-side login CAPTCHA

NOVA's default installation still requires **Django only**. Login CAPTCHA is an
explicit project integration using `django-simple-captcha==0.7.0` and
`Pillow==12.2.0` (with FreeType support). The upstream package also depends on
`django-ranged-response==0.2.0`. No external CAPTCHA service, tracking SDK,
secret API key, new user account, or replacement AdminSite is used.

## Install and opt in on your existing AdminSite

Install the optional extra in your project's environment:

```sh
python -m pip install -e '.[captcha]'  # From this source package's django-theme directory
```

Keep `nova_admin` before `django.contrib.admin` in `INSTALLED_APPS`; add
`captcha` to that list. Review and run the upstream application's migrations
using your normal deployment process:

```sh
python manage.py migrate captcha
```

Set the two supported public attributes on **the same AdminSite your project
already uses**. Keep its model registrations, auth backends, middleware and
URL mount unchanged:

```python
from django.contrib import admin
from django.urls import include, path
from nova_admin.captcha import CaptchaAdminAuthenticationForm, captcha_refresh

admin.site.login_form = CaptchaAdminAuthenticationForm
admin.site.login_template = 'nova_admin/captcha_login.html'

urlpatterns = [
    path('admin/_captcha/refresh/', captcha_refresh, name='nova-captcha-refresh'),
    path('admin/_captcha/', include('nova_admin.captcha_urls')),
    # Your existing Nova preference route, if enabled, goes here.
    path('admin/', admin.site.urls),
]
```

This example is deliberately explicit. NOVA never mutates `admin.site` merely
by importing its theme app. In a custom AdminSite, assign the same attributes on
your existing site instance. If your project already has a custom login form,
merge the CAPTCHA field and the `clean()` guard into that form while preserving
its existing superclass, fields and authentication checks; do not silently
replace a custom MFA/SSO form with this example. Custom URL namespaces require
subclassing `NovaCaptchaTextInput.refresh_url_name` and configuring the field to
use that widget. Upstream image/audio names are the global names shown above;
use one shared `nova_admin.captcha_urls` mount per project. This explicit optional
mount keeps upstream URL names and replaces only the audio callback with Nova's
live-challenge guard. Existing projects mounting `captcha.urls` must change that
include to receive the guard; installing/upgrading Nova does not rewrite host
URL configurations. Do not mount a second unguarded audio route alongside it.

The optional template extends `admin/login.html`, preserving native login CSS,
`form.media`, and the native version's CSP rendering. Its content uses NOVA's
login partial so the CAPTCHA remains required and visible in light, dark,
native, and `NOVA_ADMIN_ENABLED=False` modes. Functional CAPTCHA assets remain
loaded in native mode; the decorative login background does not. The CAPTCHA
script and stylesheet honor NOVA's escaped `csp_nonce` helper on Django 5.2,
6.0 and 6.1. This does not configure or relax the project's CSP.

## Authentication and token behavior

The project still uses Django's native `AdminAuthenticationForm`, LoginView,
CSRF middleware, staff/active checks, auth backend selection and validated
`next` redirect. A wrong CAPTCHA must not invoke an authentication backend:
Django calls form-level `clean()` even after field errors, so the provided form
returns before `super().clean()` when the CAPTCHA field is invalid.

The challenge and answer stay in upstream `CaptchaStore` on the server. The
browser receives only an image, optional upstream audio, and a signed opaque DB
identifier. The signed identifier contains **no challenge text or answer** and
is not stored in a session or cookie by this integration. Tokens are bearer
challenges, not bound to a person or browser session. They expire according to
the database timestamp (`CAPTCHA_TIMEOUT`, upstream default five minutes).
Signed-key validation is scoped to this integration's signing salt; an unsigned
upstream key cannot authenticate through this form.

Upstream 0.7.0 checks a row, deletes it, then compares the answer without
requiring a successful delete. Two simultaneous readers could both accept it.
`SingleUseCaptchaField` retains upstream challenge/image generation and Django
field validation but replaces this acceptance step with a small adapter:

1. Read from the database selected by Django's write router
2. Delete that row by primary key and challenge key
3. Accept only if the DB reports exactly one `CaptchaStore` row deleted, the
   expiration has not passed, and the answer matches

A second reader must lose the deletion and cannot reach authentication. Wrong
and blank answers also consume a supplied valid key. A failed password/staff
check consumes its already-validated CAPTCHA. The next form render gets a fresh
challenge and an empty answer field. Missing, malformed, expired, tampered and
already-used keys are rejected. `CAPTCHA_TEST_MODE=True` and shared
`CAPTCHA_GET_FROM_POOL=True` are explicitly refused by this adapter.

The adapter depends on ordinary transactional database DELETE/affected-row
semantics. DB errors fail closed and propagate; this integration does not turn
an unavailable/locked database into a successful sign-in. SQLite shared-memory
concurrent writes can produce a table-lock error. File-backed SQLite concurrent
claims are tested, but PostgreSQL/MySQL, unusual routers/replication,
`ATOMIC_REQUESTS`/custom surrounding transactions, and production load require
project-specific verification. It is an at-most-once **successful claim**;
a surrounding transaction later rolling back can restore a deleted challenge.
Do not reuse this form's validation result across requests or outside the normal
login flow.

## Refresh, JavaScript and cleanup

The `New image` button performs a same-origin CSRF-protected POST to NOVA's
refresh endpoint. A valid signed old token must win deletion before exactly one
replacement is generated. An expired row can be refreshed while it still
exists. A missing/consumed/cleaned row returns 409 and asks the user to reload.
Upstream's unrelated GET refresh endpoint is still mounted by
`nova_admin.captcha_urls`, preserving the ordinary integration's exposure;
it generates unsigned keys and does **not** invalidate previous keys. The NOVA
widget never uses it, and those unsigned keys do not pass this login field.
The Axes demo continues to omit that GET endpoint and wraps all retained CAPTCHA
callbacks, including protected audio, with its existing lockout decorator.

While refreshing, submit is blocked, the answer is cleared, and repeated
click/keyboard activation issues one request. The image is preloaded before
submission is reenabled. HTTP, CSRF, image and timeout failures keep submission
blocked with a visible live-region message. A failed image retains the new
opaque key so another refresh can replace it. Navigation invalidates late
responses; restoring the form from the browser's back-forward cache reloads it.
With JavaScript disabled, ordinary server-validated login still works. Reloading
the page creates a fresh challenge but does not immediately invalidate the old
one; the old challenge expires normally or is consumed if submitted.

Unused challenges require regular upstream cleanup (`python manage.py
captcha_clean`) under the project's own operations policy. This task did not
create a production schedule, change security settings, or migrate a real DB.
The separate opt-in security example above delegates login-failure lockout to
Axes. Request-volume limits, abuse monitoring, production policy, MFA and SSO
remain the project's responsibility; CAPTCHA is not a substitute for them.

## Accessibility and audio

The field has a real label linked to its visible answer input, error/help
associations, keyboard-operable refresh, status announcements, error focus and
visible focus rings. It includes project-controlled alternative-sign-in guidance:

```python
NOVA_ADMIN_CAPTCHA_HELP_TEXT = 'Contact our support team for an alternative sign-in method.'
NOVA_ADMIN_CAPTCHA_SUPPORT_URL = '/help/sign-in/'  # Optional trusted project URL.
```

Provide and test a genuinely usable alternative authentication/support flow.
The guidance does not itself implement such a flow. Image recognition can remain
a barrier, and these features are **not a WCAG conformance claim**.

The earlier cloud validation had no Flite/SoX and checked conditional audio-link
markup only. On 2026-10-24, normal audio generation and native browser playback
were independently verified in a separate local Linux ARM64 Docker environment:
Python 3.12.15, Django 5.2.17, PostgreSQL 17.11, django-simple-captcha 0.7.0,
Pillow 12.2.0, Flite 2.2-5 and SoX 14.4.2+git20190427-3.5. Tools were installed
only in a temporary container layer; the host was not modified. That fixture is
test infrastructure, not a distributed deployment example. Evidence and scope
are indexed in the [diagnostic ledger](../docs/DIAGNOSTIC_PROGRESS.md).

Audio remains **disabled by default**, including in the Compose example.
Projects that provision and verify the executables, Flite voice/libraries and
SoX WAV support can explicitly configure paths such as:

```python
CAPTCHA_FLITE_PATH = '/usr/bin/flite'
CAPTCHA_SOX_PATH = '/usr/bin/sox'
CAPTCHA_TEST_MODE = False
CAPTCHA_GET_FROM_POOL = False
NOVA_ADMIN_CAPTCHA_AUDIO_TIMEOUT = 10  # One shared budget in seconds.
```

Debian's `flite`, `sox` and `libsox-fmt-base` packages supplied the tested pipeline.
SoX synthesizes brown noise during each request; no external noise file is
required. Flite-only output was byte-identical across repeated requests in the
tested case, so leaving SoX unconfigured is not the recommended configuration.

When audio is configured, the widget renders a labelled native
`<audio controls preload="none">` without autoplay and an explicit download
fallback. Both admin sites were exercised in desktop Chromium with actual
native controls, including keyboard Space and JavaScript disabled: playback
advanced through `playing`/`timeupdate` to `ended`. WAV attachment and Range
semantics are retained; the player fetches it as media, while the fallback
downloads it. No browser speech synthesis or plaintext answer injection is used.

With JavaScript enabled, starting a refresh pauses the player, removes its old
source and disables the old download link. A successful response exposes the
new audio only after its replacement image is ready, with the new signed form
key, image and audio synchronized. It does not resume playback automatically.
Failure keeps the media cleared and login blocked, including a lost response
after the server has consumed the old challenge. Without JavaScript, initial
native playback and the download fallback work; reload for a fresh challenge.
Listening does not consume a challenge. Form validation and CSRF-protected
refresh do; a fresh audio request for the consumed key returns 410. Previously
downloaded or buffered bytes cannot be revoked by deleting a database row.

The shared Nova audio entry validates a 40-character lowercase hexadecimal key
and checks `expiration > now` on the write database before generation. Missing,
consumed, expired and exact-deadline challenges return 410 without invoking the
audio generator. A second write-database check rejects challenges that expire
or are consumed during generation. That rejected response and its underlying
ranged-response file are closed before returning 410. Successful audio and 410
responses are not cached; valid WAV, attachment and Range responses
are preserved. Audio remains unavailable when Flite is unconfigured. This guard
does not consume or prune rows and does not mutate third-party URL patterns.

Since the 2026-10-29 hardening, generation requests are limited to **6 per
challenge and 20 per connection IP within 60 seconds**, including failed
generation attempts. Exceeding either limit returns an uncached **429** with
`Retry-After`; a cache failure returns **503** without launching speech tools.
Configure positive integer `NOVA_ADMIN_CAPTCHA_AUDIO_KEY_LIMIT`,
`NOVA_ADMIN_CAPTCHA_AUDIO_IP_LIMIT`, and `NOVA_ADMIN_CAPTCHA_AUDIO_WINDOW` to tune
these budgets. `NOVA_ADMIN_CAPTCHA_AUDIO_CACHE` selects the cache alias (default
`default`). Multiple workers/instances must use a shared cache with atomic
`add`/`incr`; LocMem applies the limits separately in each process. Only
`REMOTE_ADDR` is used, so trusted proxy configuration remains the host's
responsibility. These audio budgets do not replace login/image/refresh limits.

The protected entry uses Nova's local Flite/SoX generator. It reads the challenge
from the write database and retains character spelling, mathematical operators,
optional SoX brown noise, PCM WAV and Range/download behavior. All subprocesses
run without a shell, check their exit status and share a single monotonic
deadline. `NOVA_ADMIN_CAPTCHA_AUDIO_TIMEOUT` defaults to 10 seconds and must be a
positive finite number (booleans are rejected). Invalid budgets launch no tool.
Each later stage receives only the remaining time, including when prior stages
succeeded. Missing executables, nonzero exits, timeouts and unusable WAV output
produce an empty, uncached 503; tool arguments, output, challenge and temporary
paths are not returned or logged. A later valid configuration can generate audio
for the same still-live challenge, since failures do not consume it.

Nova's subprocess runner kills and waits for the direct child on timeout or
interruption, and also closes its output pipe.
The final reap waits at most 0.2 seconds: a child stuck in uninterruptible kernel
IO may remain pending after SIGKILL, but cannot indefinitely hold this request.
Configured executables must be trusted; this is not a supervisor for arbitrary
descendant processes. OS process creation itself cannot be interrupted by that
timeout. Shared-timeout/failure handling passed T3-5 independent local acceptance;
the following resource hardening passed separate T3-6 independent local acceptance.

Each generation owns one private 0700 directory; cleanup never scans or deletes
another request's directory. Explicit `finally` cleanup also runs on
`KeyboardInterrupt`/`SystemExit`. Cleanup failures close any already-created
response/file and make one bounded retry on that exact owned directory before
propagating the failure. Persistent OS deletion denial may retain that restricted
directory; this cannot be guaranteed away by GC or an application retry.

Only the SoX sample-rate output is captured: at most 128 bytes are accepted, and
overflow terminates/reaps the direct child. Other stdout and all stderr go to
the null device. Intermediate regular files are checked against a 2 MiB limit
after each writing stage. WAV reads accept at most 2 MiB, validate RIFF length,
uncompressed PCM frame size and full frame availability, and reject empty,
invalid, truncated or oversized output with uncached 503. Copy blocks are at
most 64 KiB. These are per-output/read limits, not an absolute bound on aggregate
process memory or disk: a tool can write before its stage finishes, concurrent
requests have separate allocations, and the example's private 32 MiB tmpfs is
an environment-specific bound. Tools must remain trusted executables.

Nova's own ranged response closes its underlying file explicitly on
`response.close()`, stream exhaustion, iterator close and stream exceptions;
call `response.close()` when abandoning an unread or partial response. Generated
files also close if response construction, directory cleanup or the post-generation
DB check fails or is interrupted. These paths do not depend on garbage collection.
Audio remains disabled by default. T3-4, T3-5 and T3-6 were independently accepted
in that order in the local Linux ARM64 container. With GC disabled and responses
retained, normal/partial/Range closes and same-key concurrency kept file descriptors
stable and preserved another request's sentinel. Injected creation/copy/response,
cleanup, stream and postcheck failures released owned files; oversized tool/WAV
output was rejected. Evidence and historical failures remain in the diagnostic
ledger. Physical devices, assistive technology, human intelligibility, other
browsers, complete installation matrices, online CI and production remain
separate acceptance work. Persistent OS deletion denial retains the explicit
restricted-directory boundary described above.

**Retained upstream baseline and remaining scope:**

- The original upstream-only mount returned audio 200 for expired-but-stored
  challenges in the retained baseline. Hosts still mounting raw `captcha.urls`
  retain that behavior until they migrate to the protected Nova entry above.
- The retained upstream-only baseline had no explicit subprocess timeout or
  exit-code checking; missing/failing SoX left a source WAV. Those historical
  observations are preserved and do not describe Nova's new local generator.
- Raw ranged-response 0.2.0 does not forward `response.close()` to its underlying
  file, as observed in the preserved baseline. Nova now owns that file explicitly;
  T3-6 separately verifies normal/partial streaming, failures and interruption.

This result covers local normal configuration and the playback UI fix, not
production readiness or complete authentication accessibility. Human listening
and intelligibility, physical devices, screen readers, other browsers and online
CI were not exercised. The narrow 320/375px viewport checks do not replace T4
device/assistive-technology acceptance or a WCAG assessment. Keep a usable
project-owned alternative sign-in flow.

## Isolated demo and tests

The base demo remains CAPTCHA-free. Use `--settings=config.captcha_settings` to
opt in; that settings module uses a separate `captcha-demo.sqlite3` local demo
DB. Only synthetic test migrations/accounts were created during verification.
No seeded credentials or database files are distributed.

```sh
export PYTHONPATH="$PWD/src:$PWD/demo:$PWD"
python demo/manage.py test tests.test_captcha --settings=tests.captcha_settings --noinput
node scripts/test-captcha.mjs
```

`tests.captcha_settings` gives the concurrent-connection test a dedicated
file-backed synthetic SQLite DB that Django creates/destroys. Parallel runners
must set different `NOVA_CAPTCHA_TEST_DB` paths. The JavaScript suite uses the
project's existing `jsdom` development dependency. The standard Django-only
`test tests` suite skips the optional module when `captcha` is not installed as
an app; importing the core theme does not import Pillow or CAPTCHA.

Local worker verification: Python 3.12.14, Django 6.1.1, django-simple-captcha
0.7.0, Pillow 12.2.0, django-ranged-response 0.2.0. Tests cover real PNG rendering,
server rejection/auth short-circuit, staff/inactive/password/next/CSRF behavior,
replay and concurrent claims, refresh invalidation, errors, native/disabled
presentation, conditional audio markup, form media/CSP, and JS asynchronous
failures/repetition/navigation. Browser layout and other version/source/wheel
matrix results are reported separately by the combined release verification.

## Primary references

- [django-simple-captcha 0.7.0 package and dependencies](https://pypi.org/project/django-simple-captcha/0.7.0/)
- [Upstream installation and form usage](https://django-simple-captcha.readthedocs.io/en/latest/usage.html)
- [Upstream settings, widget rendering and audio prerequisites](https://django-simple-captcha.readthedocs.io/en/latest/advanced.html)
- [Django AdminSite login_form and login_template](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.AdminSite.login_form)
- [django-axes 8.3.1 fixed package and declared framework versions](https://pypi.org/project/django-axes/8.3.1/)
- [Axes installation: backend order, middleware and migrations](https://django-axes.readthedocs.io/en/stable/2_installation.html)
- [Axes configuration and lockout policy](https://django-axes.readthedocs.io/en/stable/4_configuration.html)
- [Pinned Axes backend and signal behavior reviewed for the bridge](https://github.com/jazzband/django-axes/blob/8.3.1/axes/backends.py)
- [Original django-admin-honeypot package metadata](https://pypi.org/project/django-admin-honeypot/)

The atomic adapter was reviewed against the installed, pinned 0.7.0 source,
not inferred from the library's feature list. Reassess it before upgrading that
extra. The optional Axes bridge is likewise version-specific and must be
reassessed when Axes, the project's authentication stack or lockout policy changes.
