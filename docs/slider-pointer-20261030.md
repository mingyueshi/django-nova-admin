# 静态演示滑块手柄命中区域修复

用户报告可见手柄拖不动、箭头不跟手。云端已在 v42 修复，本仓库从 main `10000fb62b6b675a2f606977138b4054fd3f1915` 精确回同步该补丁；两份文件 SHA-256 均与云端提供值一致，见[来源](evidence/slider-pointer-20261030/source.json)。本地不发布 Site，不改变两站生产。

根因是 CSS 选择器：原组件在 `nova-slider` 上声明 19 个宿主变量及明暗规则，演示子类 `nova-slider-demo` 只桥接 5 个，缺少 48px 手柄尺寸、手柄背景、成功/失败状态和 fallback。JS 类继承不会继承另一个标签的 CSS 选择器。缺失尺寸使轨道和透明 range 命中区小于可见手柄，手柄下半会命中 meta，left 的 calc 也失效；事件本身已加载。

在自有 `dist/login-preview.css` 完整镜像供应商 host prelude，仅替换标签名。供应商 JS/CSS、manifest 及 Django 运行包均未改，新增 DOM 契约回归防止遗漏主机规则；登录套件 48 项、完整 npm 1401 项、CI 支持 105 项和 CSS 预算检查通过。

[真实浏览器指针记录](evidence/slider-pointer-20261030/preview-pointer.json)有 76 条断言：浅/深色 × 1280/390/320px，手柄 20%/50%/85% 高度真实鼠标拖动，elementFromPoint 命中 range、拼图与箭头同步、每次释放仅一次校验、取消重开、下半手柄完成合成登录。共 18 次错误拖动和 6 次正确鼠标拖动。另使用 Chromium CDP 模拟触摸，确认取消不校验、移动同步、释放一次校验并完成演示；这不是物理手机或 Safari 真机验收。

[实际 Django 模板记录](evidence/slider-pointer-20261030/admin-template-pointer.json)另 47 条断言通过：模板、Hen、CSGO 的真实登录模板配本地假响应，从可见手柄下半做真实鼠标拖动后各恰好一次预验证及原生登录。它们使用原始 `nova-slider` 标签，原主机变量已生效，没有发现同一 CSS 缺口，故不更新两站后台 wheel，也不修改 CSGO 仓库。

证据：[桌面拖动](evidence/slider-pointer-20261030/light-desktop-drag.png)、[320px 深色拖动](evidence/slider-pointer-20261030/dark-mobile-drag.png)、[模拟触摸拖动](evidence/slider-pointer-20261030/emulated-touch-drag.png)。所有页面/接口均为本地合成演示，未操作真实账户或真实 CAPTCHA。

复跑：先用 `python3 -m http.server 4173 --bind 127.0.0.1 --directory dist` 提供预览，再运行 `node scripts/check-login-pointer.cjs /path/to/playwright-cli http://127.0.0.1:4173/login.html`。需要已安装可用的 Playwright CLI/浏览器；脚本只打开并关闭自己创建的会话。截图输出到已忽略的 `output/playwright/`。
