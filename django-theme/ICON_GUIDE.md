# Nova 业务图标接入指南

Nova 提供 **98 个本地内建线性图标**，覆盖导航、用户、组织、商品、交易、内容、运营、数据、动作和状态。Django 主题与静态预览共用同一清单；不引入图标字体、整库 JavaScript、CDN、网络字体或额外运行依赖。

可视化入口：运行 `npm run dev` 后打开 `/icons.html`（源文件为 `dist/icons.html`），或从“项目扩展 → 浏览业务图标”进入。目录支持中文用途、英文名称、分类交叉筛选和深浅色。该页是公开合成参考，不是后台业务模块；不会上传搜索词或连接管理服务。

## 1. 应用与模型导航

```python
NOVA_ADMIN_NAVIGATION = True
NOVA_ADMIN_NAV_ICONS = {
    "catalog": "store",           # 原生 AppConfig.label
    "catalog.product": "box",     # app_label + 小写模型名
    "catalog.category": "tag",
    "sales": "briefcase",
    "sales.order": "receipt",
    "sales.shipment": "truck",
    "content.article": "newspaper",
    "support.ticket": "headphones",
    "auth.user": "users",
    "auth.group": "shield",
}
```

- 键必须是现有 `app_label` 或 `app_label.model_name`；模型部分使用小写。不要填应用显示名、模型中文名、类导入路径或 URL。
- 仅装饰当前 AdminSite 已给出的、经过权限过滤的导航；配置不能注册模型、创建链接、授予权限或绕过对象级权限。无需在 ModelAdmin 或 AppConfig 上增加自定义属性。
- 应用与模型分别选择图标，模型不会自动继承应用图标，也不会根据名称推测业务语义。上例中的 `sales`、`support` 等只有你的项目真实存在时才会出现。
- 默认配置是 `{}`，完全保留原来无图标的导航。未配置、未知名称、空值或非字符串值都省略导航图标，不影响原链接和文字；`manage.py check` 用 `nova_admin.W003` 提示错误配置。旧有九个名称全部保留。
- 常用和收藏入口复用相同模型图标。没有列表目的地的原生标签不会被变为可点击图标。分组标题继续由导航配置负责，本轮未增加分组图标设置。
- 图标仅表达视觉分类，不替代权限判断、状态文字、说明或确认操作。

### 可选批量提供器

```python
NOVA_ADMIN_NAV_ICON_PROVIDER = "project.admin_navigation.icons"

# project/admin_navigation.py
# 每次导航渲染只调用一次；available_apps 是已过滤可见列表的隔离副本。
def icons(request, available_apps):
    return {"sales": "briefcase", "sales.order": "receipt"}
```

提供器中的同名键优先于固定设置；没有返回的键继续使用固定设置。显式返回空值或无效名称会隐藏该键图标。返回的值仍只能选择本指南中的名称，不能插入 SVG/HTML。默认和固定配置不查询业务数据库；提供器的业务成本与数据范围由宿主负责。提供器失败不会阻断导航，也不会把异常内容放进页面。与徽标、收藏结合的完整规则见 [NAVIGATION_EXTENSIONS.md](NAVIGATION_EXTENSIONS.md)。

## 2. 在项目模板复用图标

```django
{% load nova_tags %}
<button type="submit">{% nova_icon "save" %} 保存</button>
<span>{% nova_icon "check-circle" %} 已完成</span>
{% nova_icon "receipt" css_class="project-order-icon" size=24 %}
{% nova_icon "info" label="该数据来自缓存" %}
<button type="button" aria-label="刷新列表">{% nova_icon "refresh" %}</button>
```

标签签名：`nova_icon name css_class="" label="" size=16`。

- 默认生成装饰性 `aria-hidden="true"` SVG，不重复朗读旁边的文字；没有键盘焦点。
- 对确实独立承载信息的图标，传入纯文本 `label`，得到 `role="img"` 和 `aria-label`。图标按钮的可访问名称应写在按钮本身。
- 尺寸接受 12–64 的整数，其他值回到 16；颜色继承 `currentColor`。额外 CSS 可调整垂直对齐，例如 `.project-order-icon { vertical-align: middle; }`。
- `css_class` 仅接受 ASCII 字母/下划线开头、后续字母数字/下划线/连字符的类名，空格分隔；每个最多 64 字符、总输入最多 256 字符。无效片段被移除，不支持任意属性或内联样式。
- 通用标签遇到未知名称会显示中性 `grid`，避免控件空缺；这与导航配置“无效即省略”的兼容行为不同。
- 即使字符串被项目标记为 safe，`label` 仍按纯文本转义。路径、事件属性、HTML、远程资源和模板路径都不是可配置参数。

Python 可通过 `nova_admin.icons.ICON_NAMES`、`ICON_CATEGORIES`、`ICON_CATALOG`、`ICON_PATHS` 只读查看内建目录；`get_icon_path(name, fallback=None)` 只返回目录内路径，默认无匹配返回 `None`。旧的 `nova_admin.navigation.ICON_PATHS` 导入继续兼容。

## 3. 静态前端复用

```javascript
import { icon, iconCatalog, iconCategories } from './js/icons.js';
const decoration = icon('receipt', 'project-order-icon');
```

保留既有 `icon(name, cls = '')` 签名。返回的 SVG 默认仅作装饰，名称无效时回退 `grid`；调用方负责按钮/链接的可见文本或可访问名称。类名规则与模板标签一致。原型属性名（例如 `constructor`、`__proto__`）不是图标，不能读出原型内容；不支持传入自定义 SVG。公开分类和目录对象只读。

## 4. 完整名称目录

名称区分大小写，统一使用下面的小写英文与连字符。中文是建议用途，可以结合项目上下文复用；不存在某个业务后台不代表需新建它。

### 导航与界面

- `grid`：应用总览
- `home`：首页
- `folder`：应用分组
- `layers`：分层菜单
- `menu`：菜单
- `search`：搜索
- `settings`：设置
- `sun`：浅色
- `moon`：深色
- `arrow`：前往
- `up`：向上
- `down`：展开
- `chevron`：进入
- `more`：更多
- `star`：收藏

### 用户与组织

- `users`：团队
- `user`：用户
- `user-plus`：新增成员
- `building`：组织
- `briefcase`：业务
- `id-card`：身份资料
- `shield`：权限
- `key`：凭据
- `lock`：锁定
- `unlock`：解锁

### 商品与交易

- `box`：商品
- `tag`：分类标签
- `cart`：购物车
- `store`：门店
- `receipt`：订单票据
- `credit-card`：支付
- `wallet`：钱包
- `currency`：金额
- `truck`：物流
- `warehouse`：仓库
- `barcode`：条码
- `gift`：优惠礼品

### 内容与媒体

- `file`：文档
- `book`：知识库
- `image`：图片
- `video`：视频
- `music`：音频
- `newspaper`：资讯
- `message`：评论
- `mail`：邮件
- `clipboard`：表单
- `archive`：归档
- `bookmark`：书签
- `globe`：站点

### 运营与流程

- `bell`：通知
- `calendar`：日程
- `clock`：待办时间
- `map-pin`：地点
- `map`：区域
- `flag`：目标
- `workflow`：审批流程
- `list-checks`：任务清单
- `headphones`：客服
- `wrench`：工单
- `history`：历史记录

### 数据与技术

- `chart`：报表
- `trend`：趋势
- `activity`：监控
- `database`：数据库
- `server`：服务
- `table`：数据表
- `pie-chart`：统计
- `code`：接口代码
- `terminal`：终端
- `cloud`：云服务
- `cpu`：设备
- `bolt`：自动化

### 通用操作

- `plus`：新增
- `minus`：减少
- `edit`：编辑
- `trash`：删除
- `copy`：复制
- `save`：保存
- `download`：导出
- `upload`：导入
- `refresh`：刷新
- `filter`：筛选
- `link`：关联
- `external-link`：外部入口
- `eye`：查看
- `eye-off`：隐藏
- `print`：打印
- `logout`：退出

### 状态与反馈

- `check`：确认
- `close`：关闭
- `check-circle`：成功
- `alert-triangle`：警告
- `x-circle`：失败
- `help-circle`：帮助
- `info`：信息
- `circle`：提示
- `pause`：暂停
- `play`：运行

## 5. 维护、安全与验证

权威清单为 `src/nova_admin/icons.json`，随 wheel 打包。内容只包含名称、中文用途、分类和 SVG path 的 `d` 数据。已有内建路径沿用，新业务线稿为项目内手写补充，按项目 MIT 许可提供；没有新引入第三方图标包或授权字体。整体素材/依赖边界见仓库根目录 `THIRD_PARTY_NOTICES.md`。

维护者新增或调整路径后，在仓库根目录执行：

```bash
python scripts/sync_icons.py
python scripts/sync_icons.py --check
npm run test:icons
```

`sync_icons.py` 检查名称唯一性、分类和纯路径字符白名单，然后生成 `dist/js/icons-data.js`；不要直接编辑生成文件。生成数据和 Python 目录的一致性也由 JavaScript 测试逐项核对。路径清单是受版本控制的开发者资产，不是可由用户上传或替换的设置。

Django 环境执行：

```bash
cd django-theme
python demo/manage.py test tests.test_icons tests.test_icon_geometry tests.test_navigation_extensions tests.test_checks
```

几何回归测试独立保留扩充前的SVG元素，逐段比较相对/隐式命令解析后的绝对坐标，并检查所有图标的直线、Bezier曲线、椭圆弧真实边界和描边余量，防止合并多个path时移动子路径原点。

新增测试覆盖目录一致性、名称/属性注入、受信路径、safe-string 转义、无效配置回退、模板可访问语义、模型权限范围、不改原链接、提供器覆盖、中文目录与筛选交互。CSS 和屏幕阅读器仍需结合宿主项目验证；状态图标不替代业务状态真值，图库存在不表示新增对应业务能力。
