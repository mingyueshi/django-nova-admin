# 项目级分页：每页条数与跳页

这是由宿主明确选择的示例，不是安装 Nova 后自动生效的全局行为。Demo 只在商品、成员、新闻三个 ModelAdmin 启用；分类、标签、认证模型及其他 AdminSite 保留原配置。

## 复制与启用

1. 将 `demo/catalog/pagination.py` 复制到自己的应用，保留或明确审查有限的 `PAGE_SIZES = (10, 20, 50, 100)`
2. 将 `demo/templates/project_admin/pagination_change_list.html` 放入项目模板目录，将 `demo/catalog/static/catalog/pagination.css` 放入项目静态目录。搬移文件时同步模板中的 CSS 路径
3. 在原来的 ModelAdmin 上显式添加 mixin，并选择允许的默认容量，例如：

```python
from .pagination import BoundedPaginationAdminMixin

class ProductAdmin(BoundedPaginationAdminMixin, ExistingProductAdmin):
    list_per_page = 20
```

替换现有注册所用的类，不要重复注册同一模型。默认100也属于允许值；示例不会按请求修改共享 ModelAdmin 实例。如果项目默认值不在允许集合中，显式接入时会报配置错误，要求宿主自行确定容量。

已有 `change_list_template` 时，将示例的分页块及外部 GET 表单合并进去，或让现有模型模板继承分页模板，并继续显式指定现有模型模板。Demo 的商品模板采用后一种方式，保留列表开关的保存说明；不要丢弃项目模板。两个 `block.super` 保留原生分页、条数统计、“显示全部”、列表编辑保存、动作 POST 与 CSRF。页码/条数 GET 表单位于原生 POST 表单之外，控件通过 `form` 属性关联，无需 JavaScript，不会嵌套表单或误触批量动作。

控件使用英文 gettext 源消息及 `Nova pagination` context，Demo 的项目中文词典已给出译文。复制对应条目后运行现有 `demo/compile_catalog.py`，或用 GNU gettext 的 `compilemessages`；不要修改 Django 安装目录。手机控件触控高度至少44px，数值控件字号16px；原生外观也保留可用的项目级分页控件。

## 请求和状态边界

- `_nova_page_size` 仅接受单个 `10`、`20`、`50`、`100`。缺失、重复、非支持值、带符号、空格、Unicode数字或无界值均回到这个 ModelAdmin 的默认容量
- 改变容量通过 GET 提交，省略 `p` 回第一页，保留其他合法查询参数及其多值，包括搜索、排序、过滤、popup 与 facets
- 跳页使用 Django 原生从1起算的 `p`。非规范值、重复值、零、负数或超过9位的数字回第一页；有效正整数超过多页结果范围时沿用原生拒绝流程，重定向到 `?e=1`。原生这个错误路径也会丢弃被拒请求的其他查询参数。空列表、单页列表显示第1页，不展示跳页输入
- 保留参数名 `_nova_page_size`。它只从 ORM 查询条件中移除，仍随原生导航链接保留；其他查询参数继续经过 Django 原有查找校验
- “显示全部”仍由宿主的 `all` 与 `list_max_show_all` 决定，因此宿主允许时可能显示超过100条。有限容量约束针对分页，不能误称数据暴露的全局上限。显示全部时控件变为“返回分页”链接
- 页码 GET 表单不接收动作名称、选中行、`select_across`、CSRF token 或列表编辑数据。翻页时未保存编辑及选中行遵循原生行为；这个示例不跨请求持久化选择，也不增加后台状态存储
- 权限、查询集范围、搜索过滤、排序、动作、`select_across`、CSRF 与列表 formset 保存仍由原生 Admin 处理。宿主自定义 ChangeList 会与 mixin 组合；已有 `get_results()` / `get_filters_params()` 改写时要在目标项目重新验收

可交互原型的分页是另一套浏览器本地演示：它支持跨页保留选择、按 URL 恢复和越界夹页，不应把这些前端表现视为真实 Django 的后端行为。

## 恢复与验证

移除三个 ModelAdmin 上的 mixin 及对应模板选择即可恢复此前分页。只关闭 Nova 外观时，宿主明确启用的分页仍可使用；移除 `nova_admin` 也不会让此示例依赖失效。自定义项目应保留自己的测试和分页容量策略。

已验证精确版本为 Django 5.2.17、6.0.8、6.1.1。新增20项测试通过真实 Admin GET/POST 端点覆盖容量白名单、恶意/重复参数、各页边界、搜索过滤排序、多值查询、自定义权限查询集与 ChangeList、原生普通 ModelAdmin、显示全部、选中/全结果动作、权限和CSRF、列表保存、控件表单归属、中英文、明暗/原生/主题关闭。

在 `django-theme` 内，以已安装相应依赖的 Python 执行：

```bash
PYTHONPATH="$PWD/src:$PWD/demo:$PWD" python demo/manage.py test tests.test_pagination_example --verbosity 2
```

测试使用隔离测试数据库；它不迁移或修改项目正式数据库。合并后仍需运行整套集成测试。公开的真实模板样本已移除提交能力，只有本地运行 Demo 才是真实后端。

## 官方扩展点

- [ModelAdmin.get_changelist](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/#django.contrib.admin.ModelAdmin.get_changelist)
- [list_per_page 与 list_max_show_all](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_per_page)
- [ModelAdmin.get_paginator](https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.get_paginator)
- [Paginator 无效页处理](https://docs.djangoproject.com/en/6.0/ref/paginator/)

原生 `p` 从1起算及 `?e=1` 处理也已对照三个精确版本的已安装源码和实际请求验证。
