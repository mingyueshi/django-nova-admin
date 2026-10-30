# 登录提交后弹出验证码

参考 `nova-account-vue` main `cab11ef` 的 `useAuthFlow.loadChallenge()`、`verifyChallenge()`、`cancel()` 与原生 `NovaDialog`：先校验凭据，再弹出安全验证，通过后继续登录。Nova 的图片验证码和滑块模板、静态登录交互预览均同步；服务端策略、CSRF、认证、权限、验证码一次性消费和限流未改动。

基础字段错误留在登录页。弹窗取消/Esc/外部 close、重置、页面离开和凭据修改会中止本次待提交；迟到响应不能续提。滑块首次打开才挂载，关闭后重开重新取挑战；真实宿主适配器仍须在最终 submit 重核 proof 与期限。图片验证码保留无脚本内联表单；旧浏览器保留内联交互。

本轮验证环境为本地 Python 3.12.14、Django 6.1.1、Node 24.21.0 和 Chromium。基线 `7c9eff945cc4d8ce28366790304eb8574a115531`，受测运行文件逐项绑定于[哈希记录](evidence/login-captcha-modal-20261030/tested-runtime-sha256.json)。源码提交和下游精确 wheel 来源由 Git 历史及下游来源记录标识，版本仍为 0.6.1 源码快照，未发布 PyPI。

- 完整 `npm test` 通过，包含静态登录预览 47 项。
- `node --test django-theme/scripts/test-captcha-dialog.mjs`：16 项通过；旧图片增强 16 项通过。
- Django 核心：436 项运行、3 项可选集成跳过；单独滑块 23 项、图片验证码/策略 77 项通过。首次将原生登录测试与滑块测试混跑触发共享 AdminSite 状态干扰，按仓库既有独立配置分别复跑通过。
- CI 支持脚本单测和 CSS 体积检查按项目解释器运行。系统 Python 3.9 缺 `tomllib` 的尝试不计通过。
- [实际模板浏览器检查](evidence/login-captcha-modal-20261030/browser-checks.json)：38 条通过，三项目均有凭据 Enter、空字段、Esc、焦点返回、320px、一次预验证和一次原生登录；图片验证码答案 Enter 通过。
- [静态预览浏览器检查](evidence/login-captcha-modal-20261030/preview-browser.json)：6 条通过，含图片验证码答案 Enter 与 320px 布局。

[桌面弹窗截图](evidence/login-captcha-modal-20261030/template-desktop.png)与[手机图片验证码截图](evidence/login-captcha-modal-20261030/preview-image-mobile.png)仅含合成数据。浏览器以实际模板渲染和本地假响应测试 UI/请求次数；后端测试使用临时数据校验认证和防护，未使用真实账户、未自动完成真实 CAPTCHA，未访问生产登录。第一次 Chromium 沙箱启动失败，后续经正常工具审批在本机启动成功。

人工验收重点：部署后分别确认正常登录与失败触发验证码；点击/Enter 弹出、手动拖动后自动登录、Esc/关闭再开、过期/失败重试和手机键盘。此次仅提交推送，不部署。
