# 代码与素材说明

## 原创部分

NOVA 前端预览、Django 主题、Demo、测试及打包辅助代码按根目录 `LICENSE`（MIT）提供。依赖包的授权仍由对应项目决定。

## 本地合成图片

`avatars-sheet.webp`、`products-sheet.webp`、`covers-sheet.webp` 是为本演示生成的 AI 合成图集，不是图库下载或私人图片。头像是虚构成年人，商品没有品牌标识，新闻场景不代表真实新闻事件。原图只做同尺寸 WebP 转码；单格裁切由 CSS 完成。作为本演示的一部分，可以用于本地研究和修改；不声称存在真实人物肖像授权、真实商品背书、素材独占性或对第三方权利的额外保证。

每张为 3 列 × 2 行：

- 头像：1536 × 1024，六个虚构成人肖像
- 商品：1536 × 1024，键盘、收纳盒、背包、便笺本、支架、收纳包
- 封面：2048 × 768，美术馆、共享办公室、湖泊、工作坊、绿色出行、展览

前端、真实 Demo、只读模板样本分别保留本地资源副本，便于各自独立运行。没有外部图片服务、跟踪像素或媒体 API。

## Django 与 Select2

`dist/native-admin/` 中的 Django 样式与图标保留 `DJANGO-LICENSE.txt`（BSD 3-Clause）；Nova 保留 `NOVA-LICENSE.txt`；Select2 CSS 附带 `static/admin/css/vendor/select2/LICENSE-SELECT2.md`（MIT）。更多组件来源见同目录 `THIRD_PARTY_NOTICES.txt`。原生 Django JavaScript 未进入只读样本；运行中的真实 Django 从已安装的官方 Django 包加载自身资源。

## 仅用于开发的依赖

jsdom 26.1.0（MIT）及其依赖通过 `package-lock.json` 锁定并由 npm 安装，不内嵌 node_modules。Django、beautifulsoup4、build 和构建依赖从官方 Python 包源安装，不内嵌解释器或虚拟环境。完整依赖许可证以安装包为准。

## 项目级 Admin 模板定制（0.3.0）

`django-theme/demo/templates/project_admin/` 中的字段集和 tabular inline 模板来自已测试的 Django 5.2.17、6.0.8、6.1.1，仅调整项目标签渲染入口；按原 Django BSD 3-Clause 许可分发。完整许可证位于该目录的 `DJANGO_LICENSE.txt`。版本选择、上游来源与升级核对说明见 `django-theme/PROJECT_CUSTOMIZATION.md`。这些项目模板不属于通用 Nova wheel 的运行资源。


登录模板内容部分改编自Django原生admin/login.html，BSD 3-Clause完整许可随主题运行包置于nova_admin/LICENSE-DJANGO.txt。可选验证码依赖django-simple-captcha0.7.0（MIT）/Pillow12.2.0；依赖由官方PyPI安装，不把其库源代码、字体或系统音频工具打入本包。静态验证码图片由隔离合成数据库在本地生成，无真实账号、服务令牌或第三方请求。

## 开源图标精选集

本项目收录320个上游原始SVG：Lucide（lucide-static 1.61.0，64个，ISC及Feather派生部分的MIT）、Tabler Icons（@tabler/icons 3.49.0，64个，MIT）、Heroicons（heroicons 2.2.0，64个24px轮廓图标，MIT）、Iconoir（iconoir 7.12.1，64个regular轮廓图标，MIT）、Bootstrap Icons（bootstrap-icons 1.13.2，64个16px原生填充路径图标，MIT）。这些图标不属于NOVA原创路径，依照各自的许可分发。

- Lucide与Feather完整原始许可：`dist/assets/icons/lucide/LICENSE.txt`、`nova_admin/licenses/lucide.txt`。
- Tabler原始许可：`dist/assets/icons/tabler/LICENSE.txt`、`nova_admin/licenses/tabler.txt`。
- Heroicons原始许可：`dist/assets/icons/heroicons/LICENSE.txt`、`nova_admin/licenses/heroicons.txt`。
- [Iconoir原始许可](https://github.com/iconoir-icons/iconoir/blob/main/LICENSE)：`dist/assets/icons/iconoir/LICENSE.txt`、`nova_admin/licenses/iconoir.txt`。
- [Bootstrap Icons原始许可](https://github.com/twbs/icons/blob/main/LICENSE)：`dist/assets/icons/bootstrap/LICENSE.txt`、`nova_admin/licenses/bootstrap.txt`。

原始来源、固定版本、发布包完整性与逐SVG文件SHA-256见 `dist/assets/icons/manifest.json`；SVG几何仅转成受控本地注册表。静态演示和Django使用同一精选集，运行时不访问CDN或远程图标服务。只读Django导出同时保留 `ICON-LICENSES/`。使用与重建说明见 [图标指南](django-theme/ICONS.md)。


## 开源图表运行库

`dist/vendor/charts/` 保留以下官方npm发布文件及未修改的许可文本，按当前场景选择在本地加载：

- [Apache ECharts](https://github.com/apache/echarts) 6.1.0：Apache-2.0，完整 `echarts/LICENSE`、`echarts/NOTICE`、d3的 `echarts/LICENSE-d3`；内嵌zrender 6.1.0的BSD 3-Clause许可见 `echarts/LICENSE-zrender.txt`，tslib 2.3.0的许可与版权见 `echarts/LICENSE-tslib.txt`、`echarts/tslib-CopyrightNotice.txt`。
- [Chart.js](https://github.com/chartjs/Chart.js) 4.6.1：MIT，见 `chartjs/LICENSE.md`；其UMD文件标明内嵌@kurkle/color 0.3.2，对应原始MIT许可见 `chartjs/LICENSE-color.md`。
- [uPlot](https://github.com/leeoniya/uPlot) 1.6.32：MIT，见 `uplot/LICENSE`。原始JS和CSS一起保留。

固定版本的发布包URL、SHA-512完整性及逐文件SHA-256见 `dist/vendor/charts/manifest.json`，可用 `node scripts/check-chart-assets.cjs` 离线校验。没有修改上游运行库、重新压缩它们或向通用Django主题运行包自动注入图表依赖。NOVA编写的适配器和合成数据仍按项目MIT许可提供；第三方图表库按上述各自许可分发。
