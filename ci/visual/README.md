# 外观与语言验收

`run.sh` 在锁定摘要的 Linux ARM64 Playwright 镜像中启动 Chromium 和真实 Django AdminSite。测试使用 SQLite 内存数据库、四条固定商品、打包字体、1280 × 800 视口和 1 倍像素密度。测试服务器仅在容器内监听回环地址。

## 运行

在仓库根目录用 Python 3.12+、npm 和 Docker 执行以下命令。

```sh
python -m pip install --target output/visual/python --require-hashes --only-binary=:all: -r ci/visual/requirements.txt
npm ci --prefix ci/visual --ignore-scripts --no-audit --no-fund
ci/visual/run.sh
NOVA_VISUAL_SCOPE=full ci/visual/run.sh
```

PR 选择项目默认和医疗青两组。全量任务使用项目默认和全部 25 套命名配色。每组均组合标准 / 紧凑密度与明 / 暗外观，分别访问登录页、登录后的商品列表和提交无效商品后的校验页，共 24 或 312 张基线。全量 PNG 约 48 MiB。浏览器等待字体与图片解码完成后截图。比较采用 Playwright 感知色差阈值 0.02，超过阈值的差异像素容许数为零。CSS 体积预算仍独立运行。

失败时在 `output/visual/results/` 查看同名的 expected、actual 和 diff 图。GitHub Actions 将失败现场保存七天。确认有意的页面改动后，可以按配色重建并检查图片改动。

```sh
NOVA_VISUAL_SCOPE=full ci/visual/run.sh matrix -g '^.*teal-' --update-snapshots=all
NOVA_VISUAL_SCOPE=full ci/visual/run.sh
```

Django 模板、浏览器、字体或架构升级可能影响所有基线。升级渲染环境时应同时更新依赖锁、镜像摘要及经复核的基线。

## 浏览器覆盖

- 配色编辑器遍历所有预设与两种外观，验证色值输入、对比度失败反馈、完整预设和编辑差量。将导出的 CSS 加载到真实后台，检查显式与自动模式的实际颜色。
- 高对比度检查登录输入、边框、按钮、表单错误、面包屑、删除操作和标题的计算颜色，也覆盖系统强制颜色和键盘焦点。普通文本按 7:1、大文本按 4.5:1 验收，控件边界按 3:1 验收。[增强文字对比度](https://www.w3.org/WAI/WCAG22/Understanding/contrast-enhanced.html) · [非文本对比度](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
- 阿拉伯语用例执行移动导航、命令面板、焦点返回、外观提交、列显隐、批量勾选、键盘与拖动调整列宽、固定列、横向滚动、排序、分页、打印表、表单分段与内联、混排 SKU、消息和仪表板图表。Markdown、图形验证码及滑块弹窗使用测试宿主；滑块覆盖 Nova 包装层及服务不可用回退。第三方验证服务有独立的集成测试。

## 新增语言

1. 在主题包的 `locale/<locale>/LC_MESSAGES/` 添加上下文 PO 和对应的 MO。在 [语言样例](../../django-theme/tests/locales.json) 登记语言代码、方向、日期/数字、外观标签、键盘说明，以及覆盖该语言每个复数类别的数量和译文。仓库的阿拉伯语目录位于 `django-theme/tests/locale/`，用于六类复数和 RTL 的验收。
2. 用 `PYTHONPATH=output/visual/python python django-theme/demo/compile_catalog.py --po PATH` 编译，再加 `--check` 检查提交的 MO。编译器检查复数索引、百分号和具名花括号占位符。
3. 运行 Django 的 `tests.test_theme_i18n` 和 `ci/visual/run.sh interaction`。语言目录清单与登记项必须一致，随包发布的语言还会检查主题消息覆盖。每种登记语言都经过运行时查词、格式化、320px 下的长文案/工具面板约束和键盘说明检查；RTL 组件操作另有浏览器用例。
