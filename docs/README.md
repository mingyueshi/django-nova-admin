# 文档索引

[返回项目首页](../README.md) · [原生 Django 主题文档](../django-theme/README.md)

本目录收纳仓库级专题指南、规划和历史验收记录。文档保留各自的日期、固定提交和覆盖边界；历史通过记录不能代替当前提交的验证。

2026-10-29 的滑块固定来源更新、Nova 登录校验顺序及本地验证见[本次同步记录](SLIDER_SYNC_2026-10-29.md)。下方 2026-10-26 的状态摘要保留其历史范围。

## 当前状态与阅读入口（2026-10-26）

本地 `main@df48494` 的最后提交仅新增诊断复核文档，产品基线为 `c6e3484`。当前用户数据六文件候选已完成本地独立验收，**尚未提交或推送，未触发线上 CI**：Node 24.21.0 / npm 11.19.0 下 20 套件、1,397 项前端检查及 62 项 CI 适配器测试通过，另有真实 Chrome 桌面/窄视口、表单、刷新、CSV 和失败恢复证据。详见 [用户数据独立验收](USER_DATA_VALIDATION_ACCEPTANCE_2026-10-26.md)。

历史音频、排序和导航分支已依次合入主线，最终合并 `cbc1624` 是当前 HEAD 的祖先；2026-10-24 的 [快速 CI 40099609587](https://github.com/mingyueshi/django-nova-admin/actions/runs/40099609587) 与 [完整 CI 40100316363](https://github.com/mingyueshi/django-nova-admin/actions/runs/40100316363) 已独立验收，当时前端 1,322 项、主题 JS 260 项通过。它们不覆盖当前未提交候选。

[分阶段进度](DIAGNOSTIC_PROGRESS.md) 保留 T2 Docker/PostgreSQL、T3 音频生成/原生播放及后续异常边界的本地验收。T4 仅为用户在真实 iPhone Safari / VoiceOver 上回报并被接受的无 CAPTCHA core 登录与导航最小范围。人工音频听辨继续跳过未验收；其他设备/读屏组合、可选验证码真机流程，以及当前候选的发行和生产部署仍未验收。

最新问题按 [2026-10-26 诊断报告](DIAGNOSIS_2026-10-26.md) → [诊断复核](DIAGNOSIS_2026-10-26_REVIEW.md) → [用户数据独立验收](USER_DATA_VALIDATION_ACCEPTANCE_2026-10-26.md) 阅读。各阶段的旧计数、未合入或未实测描述保留为历史记录；仓库现状以本页和[项目首页](../README.md)的日期化摘要为准。

## 图表与分析指南

| 文档 | 内容 |
|---|---|
| [CHARTS.md](CHARTS.md) | 手写 SVG 统计分析、数据口径与接入 |
| [CHART_LIBRARIES.md](CHART_LIBRARIES.md) | ECharts、Chart.js、uPlot 的场景、资源和许可 |
| [ANALYSIS_LAB.md](ANALYSIS_LAB.md) | 联动筛选、下钻与模拟实时刷新 |

## 开发、兼容与交付

| 文档 | 内容 |
|---|---|
| [CI_CD.md](CI_CD.md) | CI 门禁、产物校验与历史接入记录；当前候选状态见页首 |
| [NODE_COMPATIBILITY.md](NODE_COMPATIBILITY.md) | Node/npm 精确组合和维护范围 |
| [REFACTOR_NOTES.md](REFACTOR_NOTES.md) | 预览模块整理与接口边界记录 |
| [DELIVERY.md](DELIVERY.md) | 历史源码包交付及发行说明入口 |

## 功能规划与进度

| 文档 | 内容 |
|---|---|
| [FEATURE_ROADMAP.md](FEATURE_ROADMAP.md) | 功能候选、范围和验收标准 |
| [FEATURE_PROGRESS.md](FEATURE_PROGRESS.md) | 分批实施与独立验收台账 |

## 诊断与验收记录

| 文档 | 内容 |
|---|---|
| [DIAGNOSIS_2026-10-26.md](DIAGNOSIS_2026-10-26.md) | 新诊断报告；采纳范围和事实修正需结合下方复核 |
| [DIAGNOSIS_2026-10-26_REVIEW.md](DIAGNOSIS_2026-10-26_REVIEW.md) | 逐项复核、已复现问题、现有能力与推进顺序 |
| [USER_DATA_VALIDATION_ACCEPTANCE_2026-10-26.md](USER_DATA_VALIDATION_ACCEPTANCE_2026-10-26.md) | 未提交用户数据候选的冻结哈希、本地独立测试及 Chrome 验收 |
| [DIAGNOSTIC_REPORT.md](DIAGNOSTIC_REPORT.md) | 诊断结论、优先级和未覆盖边界 |
| [DIAGNOSTIC_PROGRESS.md](DIAGNOSTIC_PROGRESS.md) | T2/T3/T4 分阶段验收、固定提交和 CI 历史证据索引 |
| [QA.md](QA.md) | 静态预览的历史测试与浏览器验收 |

## 就地维护的文档

- [django-theme/README.md](../django-theme/README.md)：独立主题包的接入、兼容和发行文档；该目录的 README、CHANGELOG、LICENSE 及其他包文档保留原位。
- [examples/compose/README.md](../examples/compose/README.md)：隔离 Compose 示例的使用与验收记录。
- [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) 和 [LICENSE](../LICENSE)：仓库第三方声明与项目许可。
