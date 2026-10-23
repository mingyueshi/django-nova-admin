# 开源图表库支持与使用演示

从统计分析页的“开源图表演示”或“开发与集成 → 开源图表”进入 `/#charts`。页面使用真实图表库渲染，提供库切换、场景选择、业务筛选、运维窗口、空/零状态、原始配置、数据明细、PNG与CSV下载，以及JavaScript和Django模板接入示例。原有 `/#analytics` 的8类本地SVG图表继续可用。

新增 `/#analysis` [联动分析工作台](ANALYSIS_LAB.md)：使用本地ECharts演示跨图筛选、三级下钻、时间区间联动和带失败重试的模拟实时刷新，覆盖经营、转化和服务监控。

## 已接入的固定版本

| 图表库 | 版本 | 许可 | 已接入范围 |
| --- | --- | --- | --- |
| [Apache ECharts](https://echarts.apache.org/handbook/en/get-started/) | 6.1.0 | Apache-2.0，完整NOTICE及子组件许可随附 | 17类场景 |
| [Chart.js](https://www.chartjs.org/docs/latest/) | 4.6.1 | MIT | 7类常规报表 |
| [uPlot](https://github.com/leeoniya/uPlot/tree/master/docs) | 1.6.32 | MIT | 4类运维时序 |

原始发布文件和许可保存在 `dist/vendor/charts/`，浏览器按当前选择加载本地脚本，运行时不访问CDN或第三方数据服务。npm原始压缩包的URL、版本、SHA-512完整性与逐文件SHA-256记录在同目录的 `manifest.json`。ECharts保留LICENSE、NOTICE、d3、zrender 6.1.0与tslib 2.3.0的相关许可；Chart.js分发文件标明内嵌 `@kurkle/color 0.3.2`，对应版本的原始MIT许可一起保留。

```sh
node scripts/check-chart-assets.cjs
```

该命令只读取本地文件并核对哈希，不下载资源。第三方uPlot CSS保留原件，不纳入手写CSS预算；自己的 `chart-lab.css` 单独记录预算。静态打包器只为4个已审核的上游无扩展名许可路径增加例外，其余文件类型与路径规则继续执行。

## 场景与支持范围

| 场景 | ECharts | Chart.js | uPlot |
| --- | --- | --- | --- |
| 支付金额趋势 / 折线面积 | 已接入 | 已接入 | — |
| 新客与复购 / 堆叠柱状 | 已接入 | 已接入 | — |
| 渠道贡献 / 环形图 | 已接入 | 已接入 | — |
| 金额与订单 / 双轴组合 | 已接入 | 已接入 | — |
| 支付转化 / 漏斗 | 已接入 | — | — |
| 商品收入 / 矩形树图 | 已接入 | — | — |
| 渠道转化画像 / 雷达 | 已接入 | 已接入 | — |
| 星期与时段 / 热力图 | 已接入 | — | — |
| 渠道与商品 / 桑基流向 | 已接入 | — | — |
| 订单与客单价 / 散点气泡 | 已接入 | 已接入 | — |
| 收支结余 / 瀑布浮动柱 | 已接入 | 已接入 | — |
| 接口响应分布 / 箱线 | 已接入 | — | — |
| 支付目标 / 仪表盘 | 已接入 | — | — |
| P95/P99延迟 | 已接入 | — | 已接入 |
| CPU与内存使用率 | 已接入 | — | 已接入 |
| 吞吐量与错误率 | 已接入 | — | 已接入 |
| 任务队列积压 | 已接入 | — | 已接入 |

每个库只展示本次已接入的场景，不把未实现的类型替换成其他图。此表是本演示的范围，不是三个上游库完整能力清单；切换库时优先保留共同场景。

## 数据口径与交互

经营数据复用统计分析页的固定合成数据，支持7/30/90天及渠道过滤。图表、代码、明细和CSV共享同一份场景数据。

- 原始金额以整数分聚合，转为元后传给图表；双轴组合将金额和订单分到不同单位的坐标轴。
- 雷达各轴使用0–100%的比例，说明中明确各自分母。
- 桑基图按商品金额结构分配各渠道收入，保留每个渠道流出总额；不是逐笔订单归因。
- 瀑布图使用模拟成本与费用比例，末列是模拟结余，不是实际利润核算。
- 箱线图是独立接口基准的合成五数概括，时间/渠道筛选不作用于这组数据。
- 运维图是独立的北京时间合成样本，1/6/24小时窗口分别使用60/180/288个点。播放每1.5秒推进1分钟，窗口大小不变；暂停、切换筛选或离开路由会停止计时，不进行实时接口轮询。
- 空数据不初始化图表；零值在没有可定义的占比、分布或客单价时显示说明。PNG在图表渲染完成后才可下载。
- ECharts提供原生图例、提示与时序dataZoom；Chart.js提供原生图例与提示；uPlot提供原生选择缩放、图例读数与setData更新。重置缩放使用对应库的公开API。
- PNG由当前实际实例导出，Canvas图补上当前主题背景；uPlot的PNG是Canvas绘图区，不包含DOM图例。CSV有UTF-8 BOM、CRLF和标准引号转义，数值型负数保留为数值。图例隐藏或缩放只改变呈现，CSV仍导出完整当前筛选数据。

主题、配色及容器尺寸变化会更新或重建图表。路由切换先销毁旧实例并断开ResizeObserver；异步加载完成时检查请求代次和容器，避免把迟到结果绘制到其他页面。加载失败提供重试；剪贴板不可用时提供可选择的手动复制文本。

## 源码与JavaScript用法

- `dist/js/chart-lab-data.js`：库/场景目录、`createChartExample()`及`chartExampleCsv()`。
- `dist/js/chart-lab-options.js`：`buildEChartsOption()`、`buildChartJsConfig()`、`buildUPlotOptions()`，同一数据转为原生配置。
- `dist/js/chart-lab.js`：按需加载、挂载/销毁、尺寸与主题更新、回放、代码和下载。
- `dist/chart-lab.css`：实验室界面样式。

页面中的“JavaScript”标签给出当前数据、主题、脚本路径、容器、适配器调用及销毁方式；“原始配置”展示同一次构建的实际选项，uPlot函数以JavaScript保留，不伪装为JSON。“数据”标签提供可解析的场景对象。

## Django宿主中的可选接入

这轮图表资源属于静态预览，没有自动加入通用 `nova_admin` wheel，也没有新增Django统计API。要在宿主项目使用，可把资源复制到宿主静态目录，例如：

```sh
mkdir -p your_app/static/nova_charts/js
cp -R dist/vendor your_app/static/nova_charts/
cp dist/js/chart-lab-options.js your_app/static/nova_charts/js/
```

在页面选好库与场景，复制“Django”示例到项目模板。示例使用 `{% static %}` 加载本地资源，用 `json_script` 传递服务端的 `chart_data`；数据对象的结构见“数据”标签。宿主视图须先校验登录状态、模型权限、组织范围及指标口径，再从数据库聚合对应结构。不要直接把外部内容拼成脚本，也不要把静态演示数组当作生产统计。

运行 `collectstatic` 后，确认静态路径、CSP、实际容器尺寸、页面销毁和下载策略。ECharts容器必须有明确高度；Chart.js在有高度的父容器内使用canvas；uPlot同时需要随附CSS。原始许可、NOTICE及子组件许可应随资源保留。上游用法见 [ECharts导入](https://echarts.apache.org/handbook/en/basics/import/)、[Chart.js集成](https://www.chartjs.org/docs/latest/getting-started/integration.html)、[uPlot文档](https://github.com/leeoniya/uPlot/tree/master/docs)。

## 本地校验

```sh
npm run test:chart-libraries
npm test
node scripts/check-chart-assets.cjs
python3 scripts/css_budget.py
python3 -m unittest discover -s scripts/tests
```


本轮本地验证（2026-10-23）：

- Node 24.21.0 / npm 11.19.0：完整 `npm test` 1207项通过，含77项图表库检查；覆盖原生配置、数据守恒、单位与双轴、代码、CSV、空/零状态、回放、销毁和复制失败降级。Node/jsdom使用轻量API替身验证生命周期，实际第三方库渲染另由浏览器检查。
- Chromium逐一完成28组库/场景实际渲染，检查Canvas可见内容；另有76项浏览器交互检查通过，覆盖原生ECharts图例和dataZoom、Chart.js图例、uPlot时序回放、主题/配色、导出、失败重试及离开路由清理。
- 另用真实uPlot实例验证鼠标拖选缩放：6小时窗口缩至约3小时，重置后恢复6小时；离开路由调用原生destroy，绘图根节点断开。
- 三库在1920/1440/1024/768/390/320px检查范围内无页面横向溢出，Canvas及uPlot图例在自己的容器内；已查看桌面、手机及原生PNG截图。主题切换和ResizeObserver是异步更新，检查等待更新完成后再比对。
- ECharts热力图168行、Chart.js雷达5行、uPlot吞吐180行的浏览器CSV下载逐行等于当前数据对象，UTF-8 BOM正确；另核对瀑布CSV的负金额未变成文本。三库PNG实际下载并通过文件解码与尺寸检查。320px统计页的新增入口和页面宽度检查通过。
- 76项浏览器检查范围内无非预期脚本异常、失败资源或远程请求。首次加载故障单独在临时标签中模拟并验证重试，没有把预期拦截请求计作正常资源通过。剪贴板成功/拒绝使用模拟API，没有读写用户系统剪贴板。
- 根脚本74项通过，包含原始许可文件名打包与CSS预算的回归；3个图表库及3个内嵌依赖共13份源文件的版本/字节/哈希一致。最终676个静态文件的本地打包/解包往返一致，包含全部14个vendor目录文件（含清单）。CSS预算与diff空白检查通过。

证据限于本地静态前端与Chromium；没有重新执行完整浏览器/Python/Django支持矩阵，也不代表真实监控或Django统计接口验收。通用Django运行包未改动，本轮未提交、推送、部署或发布。
