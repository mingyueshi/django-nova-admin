# 图标演示与开源图标接入

静态预览进入“开发与集成 → 图标演示”（`/#icons`），或从组件预览的“图标演示”按钮进入。可切换图标库、搜索中英文名称及业务关键词、按11类场景分类，每页48个图标，并调整16/20/24/32/48px尺寸和1–2.5px轮廓线宽。选择图标后可查看按钮/标签组合、复制代码或下载原始SVG；窄屏选择后会移到用法区。复制API不可用时提供可选中的只读文本。

## 已交付的精选集

| 图标库 | 固定来源版本 | 本地数量 | 许可及来源 |
| --- | --- | --- | --- |
| Lucide | lucide-static 1.61.0 | 64个轮廓图标 | [ISC与派生自Feather部分的MIT许可](https://lucide.dev/license) |
| Tabler Icons | @tabler/icons 3.49.0 | 64个轮廓图标 | [MIT](https://github.com/tabler/tabler-icons/blob/main/LICENSE) |
| Heroicons | heroicons 2.2.0 | 64个24px轮廓图标 | [MIT](https://github.com/tailwindlabs/heroicons/blob/master/LICENSE) |
| Iconoir | iconoir 7.12.1 | 64个regular轮廓图标 | [MIT](https://github.com/iconoir-icons/iconoir/blob/main/LICENSE) |
| Bootstrap Icons | bootstrap-icons 1.13.2 | 64个16px原生填充路径图标 | [MIT](https://github.com/twbs/icons/blob/main/LICENSE) |

这是320个常用图标的本地精选集，不是五个上游完整图标库。原有72个名称保持兼容。原始SVG、原始许可证与来源版本/压缩包完整性/逐文件SHA-256记录位于 `dist/assets/icons/`；Lucide完整LICENSE同时保留其Feather派生图标的MIT条款。Django运行包包含同一精选集及 `nova_admin/licenses/` 中的完整许可。复用、修改或分发时按对应许可保留版权和许可文本。

不需要远程CDN、运行时下载、图标字体、额外Node服务或前端框架。图标使用 `currentColor`，可随现有16套配色及明暗模式切换。来源名称固定，JavaScript、模板和导航使用同一命名空间，例如 `lucide:search`、`tabler:search`、`heroicons:magnifying-glass`、`iconoir:search`、`bootstrap:search`。


## 后台场景覆盖

| 场景 | 代表图标与搜索词 |
| --- | --- |
| 导航 | 首页、侧栏菜单、前进、展开 |
| 用户与权限 | 用户、角色、权限、锁定、密钥令牌 |
| 操作与文件 | 搜索、增删改、上传导入、下载导出、复制、预览、链接接口 |
| 状态与反馈 | 成功、警告、通知、收藏 |
| 订单支付 | 商品、信用卡、发票、退款、钱包、银行财务 |
| 库存物流 | 库存包裹、物流配送、仓库门店、扫码、二维码 |
| 审核与工单 | 日程、审批、任务待办、客服工单、认证、等待处理 |
| 数据报表 | 柱状图、饼图、趋势、表格、筛选、分析报告 |
| 消息协作 | 邮件、会话评论、电话、客服帮助 |
| 内容媒体 | 图片、视频、站点语言、位置地址 |
| 系统运维 | 设置、云服务、数据库、服务器、磁盘、CPU、网络、终端日志 |

各库每种场景均有精选，原生名称和形状以对应上游为准，部分业务概念使用通用图形表达。中文业务词与英文名称可组合图标库/分类筛选。例如“审批”“退费”“备份”“API”“令牌”可直接检索。所有结果按业务概念交错排列，便于对比五库样式；分页切换后将焦点移至目录标题，搜索或换库会回到第一页。

填充图标的用法与轮廓图标一致：

```django
{% load nova_tags %}
{% nova_icon "bootstrap:credit-card" size=16 %}
{% nova_icon "iconoir:delivery-truck" size=20 label="发货" %}
```

## JavaScript

```js
import { icon } from './js/icons.js';

const svg = icon('lucide:search', '', {
  size: 24,
  strokeWidth: 2,
  label: '搜索',
});
```

将返回内容放入图标容器。这个接口仅从随包的固定图标表选择内容，不接受原始SVG。现有 `icon('search')`、`icon('users')` 等内置调用继续兼容；未知名称仍回退为原有网格图标。轮廓SVG默认保留原库线宽；Bootstrap使用原始16×16坐标和currentColor填充，忽略线宽参数，避免给填充路径额外描边。可选线宽范围1–3，尺寸只接受16/20/24/32/48。对应CSS尺寸类在静态预览样式中交付。

```html
<button type="button" aria-label="搜索用户">
  <!-- 在此渲染 icon('lucide:search')，省略 label 作为装饰 -->
</button>
```

有明确文字标签的按钮可使用默认装饰图标；独立图标的按钮本身应有可访问名称。`label`会输出转义后的 `role="img"` / `aria-label`；不传label时使用 `aria-hidden="true"`，不为每个装饰图形重复朗读。

## Django 模板

```django
{% load nova_tags %}
{% nova_icon "lucide:search" size=24 stroke_width=2 label="搜索" %}

<button type="submit">
  {% nova_icon "tabler:download" size=16 %}
  导出
</button>
```

模板标签在服务器渲染本地SVG，不依赖JavaScript。未知或非法名称不输出SVG；label经Django转义。非法尺寸回退20px；非法线宽回退原库值。这个辅助标签不自动加载Nova样式，因此不要在原生关闭模式下额外引入主题资源。

## Django 导航配置

```python
NOVA_ADMIN_NAV_ICONS = {
    "catalog": "tabler:folder",
    "catalog.product": "lucide:shopping-bag",
    "catalog.newsitem": "heroicons:document-text",
}
```

只修饰已有权限过滤后的AdminSite菜单。旧的 `box`、`folder`、`users` 等名称继续可用。未知值忽略；图标名称不能创建新链接、扩大权限或输入HTML。已有 `NOVA_ADMIN_NAV_ICON_PROVIDER` 也可返回这些固定名称，调用频率和权限边界不变。`manage.py check` 接受320个命名空间名称与原有9个内置名称。

## 离线重建与扩展

```sh
python scripts/build_icons.py --check
python scripts/build_icons.py
```

默认从已交付的原始SVG与manifest生成 `dist/js/open-icons.js`、`nova_admin/icons.json` 和运行包许可证；`--check`仅校验，不写文件，也不访问网络。构建器校验来源哈希、受审查的16/24单位viewBox、currentColor轮廓或填充路径及受控SVG元素/属性；拒绝脚本、事件属性、远程引用和越界文件路径。

添加图标时，从相同或明确升级后的官方版本挑选资源，保留许可证，审核并更新manifest中的来源路径与哈希，并显式更新manifest中的总数、各库数量、预览名称及测试。重新生成两份注册表，运行前端、Django、资源一致性与浏览器检查；不要把未经审查的上传SVG直接写入注册表。上游完整使用方式见 [Lucide](https://lucide.dev/guide/lucide)、[Tabler](https://docs.tabler.io/icons)、[Heroicons](https://github.com/tailwindlabs/heroicons#basic-usage)、[Iconoir](https://github.com/iconoir-icons/iconoir#basic-usage)、[Bootstrap Icons](https://icons.getbootstrap.com/#usage)。

## 首轮72图标验证记录（2026-10-23，扩充前）

- Node 24.21.0 / npm 11.19.0：完整 `npm test` 796项检查通过，含91项新增图标检查及原有165项配色检查。共享VM测试加载器改为一次链接完整模块图，以覆盖新的共享传递依赖。
- Python 3.12.14 / Django 6.1.1：源码342项测试，340通过、2项可选集成预期跳过；脚本单测95项通过。离线资源与生成注册表一致性校验通过。
- 本地wheel在独立环境安装后，图标与导航扩展27项测试通过；72个图标记录和三份原始许可与源码一致。当前wheel为本地候选，未上传或发布。
- 153个Django只读导出HTML通过23项导出安全测试，无跳过；导出附带三份图标许可，脚本、实时接口、外部请求和可提交表单均为0。
- Chromium 39项检查通过：72个SVG均有可见几何形状，覆盖三库与中英文搜索、分类、五种尺寸、四种线宽、四类代码示例、原始SVG下载和本地许可。下载结果SHA-256与上游原始文件一致。剪贴板成功/拒绝使用浏览器API模拟，未读写用户系统剪贴板；这不等于所有系统的原生剪贴板验收。
- 浅/深色桌面及1920/1440/1024/768/390/320px检查通过；窄屏选中后用法区可见且获得焦点。已查看桌面和手机截图，检查范围内无横向溢出、脚本异常、失败资源或远程图标请求。桌面内嵌浏览器初次命中了旧模块缓存，随后用独立localhost预览地址确认新页面载入。
- 2908项既有不透明配色角色检查和CSS预算通过；未重新执行完整运行时矩阵、生产部署、真实Django登录交互或所有第三方宿主验收。本轮改动未提交、推送或发布。


## 扩充至320图标的本地验证（2026-10-23）

- 5库各64个图标，保留原有72个名称；320份原始SVG与5份完整许可通过离线SHA-256校验，JavaScript与Django注册表一致。
- 完整 `npm test` 1066项通过，其中361项图标检查；覆盖分页遍历全部320个名称、筛选回到第一页、中文业务词、填充样式和代码示例。CSS预算通过。
- Python 3.12.14 / Django 6.1.1：源码343项测试，341通过、2项可选集成预期跳过；根脚本71项、Django脚本25项通过。额外使用独立Django runner运行7项seed回归，通过。首次误用标准unittest发现脚本入口时未建立Django测试库，出现7项缺表错误，已按脚本入口重跑；不将该错误调用计入通过。
- 本地wheel重新构建并在独立环境安装，图标与导航28项测试通过；确认导入来自已安装包，320条记录和5份原始许可与源码一致。
- 重新导出的153个HTML通过资源/来源清单校验与23项导出安全测试，无跳过；5份许可随导出保留，icons.json纳入源码哈希。首次生成触发“源文件在导出期间改变”保护后，待编辑与测试结束再生成，通过。导出无脚本、实时接口、外部请求或可提交表单。
- Chromium 80项检查通过，320个SVG逐页均有可见几何形状；覆盖5库、11类场景、中英文和业务关键词搜索、分页、5种尺寸、4种线宽、4类代码、下载、许可和窄屏焦点。Iconoir/Bootstrap下载SVG的SHA-256与固定上游原件一致；剪贴板成功/拒绝使用模拟API。
- 浅/深色桌面及1920/1440/1024/768/390/320px无横向溢出，检查范围内无页面脚本错误、失败资源或外部请求；已查看桌面和手机截图，内嵌浏览器已刷新确认展示5库与320图标。
- 本轮未重新执行完整Python/Django支持矩阵或第三方宿主验收。改动与wheel均为本地候选，未提交、推送、部署或发布。
