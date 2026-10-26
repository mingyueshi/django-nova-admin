# 2026-10-26 滑块 0.3.0 同步验证

本次基于 Nova Admin `f4f15eea7e3966a462f405d46ca65b5f38ca2b8a`，同步 slider `62a93e7efc2d4f1cca0a9390627f5a821c4c742c`。两处缺口仅涉及自定义 widget 的 prefix 字段绑定和已配置替代入口；未修改认证、CSRF、用途或单次消费逻辑。

## 修改

- `slider_widget.html` 以 `widget.name` 输出 `field-name`，由组件生成唯一隐藏字段；带 `auth` 前缀时提交 `auth-nova_slider_token`。
- 组件外输出 `widget.alternative`，URL/标签均使用 `force_escape`；未配置和非法全局 URL 不输出链接。
- vendored JS/CSS 与固定上游提交逐字节一致，保留 MIT 许可证，manifest 记录 0.3.0、完整提交和 SHA-256。没有既有 vendor 同步脚本，本次从固定 Git 对象提取并以已有登录测试核验。
- DemoSlider 传输仍完全模拟；合成几何 `320 × 160`、拼块宽 `44` 满足新版组件校验；公开演示不会建立 Django 会话。

## 本次执行结果

环境为 macOS arm64、Python 3.13.12、Node 24.21.0、npm 11.19.0、Pillow 12.2.0。每个 Django 版本使用独立临时环境；核心源码与 wheel 均实际运行，wheel 导入路径核对为 site-packages。

| 检查 | Django 6.1.1 | Django 5.2.17 |
| --- | --- | --- |
| 核心源码 | 428 项，3 跳过 | 428 项，3 跳过 |
| 核心安装 wheel | 428 项，3 跳过 | 428 项，3 跳过 |
| slider + 策略源码 | 29 通过 | 29 通过 |
| slider + 策略安装 wheel | 29 通过 | 29 通过 |

- `npm test`：1398 项通过，含新增组件原生 FormData prefix 提交；登录演示 45 项通过，vendor 哈希通过。
- 图形验证码增强：15 项通过。
- 新增 Django 回归涵盖渲染、完整前缀登录与证明消费、重用拒绝、错误字段名拒绝、双语替代入口、无配置、危险 URL 和 SafeString/属性转义。
- 核心命令：`PYTHONPATH=src:demo:. python -m django test tests --settings=config.settings --noinput`；安装 wheel 时移除 `src`。
- 集成命令：安装固定 slider 后，`PYTHONPATH=src:demo:. python -m django test tests.test_slider tests.test_captcha_policy --settings=tests.slider_settings --noinput`；安装 wheel 时移除 `src`。

## 真实 Chrome 检查与边界

通过本机静态预览与隔离 SQLite Django 服务检查桌面/390px 手机布局、0.3.0 图片解码、单一隐藏字段、prefix 名称、组件外替代链接跳转、英文 locale/键盘提示、中文 locale、刷新、缺少证明提交拒绝，以及渐进策略静态模拟登录成功。手机页面无横向溢出；两个页面未发现浏览器 error/warn。Chrome 自动翻译会改写英文可见文字，英文原始语义另以 locale 属性、键盘 ARIA 提示及 Django 渲染测试核对。

真实浏览器没有完成滑块解题后的成功认证；该流程的真实发题、验证、表单 POST、会话建立和重放拒绝由 Django client 回归覆盖，组件键盘验证与 FormData 由 jsdom 覆盖。未宣称触屏硬件、辅助技术、生产数据库或完整 Python 矩阵已测。

## 发布边界

原 Sites 项目和 public audience 已核对，源码只读打开并保留配置。收到凭据审批暂停后未进行站点编辑、source push、save 或 deploy；原站仍需获准后发布。未创建替代站；未发布 PyPI、未部署任何业务生产系统。
