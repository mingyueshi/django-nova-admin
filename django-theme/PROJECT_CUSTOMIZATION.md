# 企业后台：宿主项目定制

本文件说明 `demo/` 的可运行配置。通用 Nova 包继续只提供外观与导航能力；企业蓝、默认浅色、紧凑预设和中文措辞由宿主项目显式选择。没有修改 Django 安装目录或上游词典。

## 直接使用本示例

在仓库根目录运行；使用已安装本项目和 Django 的 Python 环境：

```bash
python -m pip install -e . -r requirements-test.txt
PYTHONPATH=src:demo:. python demo/manage.py check
PYTHONPATH=src:demo:. python demo/manage.py test tests.test_project_localization
```

示例的实际设置位于 `demo/config/settings.py`：

```python
LANGUAGE_CODE = "zh-hans"
USE_I18N = True
LOCALE_PATHS = [BASE_DIR / "locale"]
FORM_RENDERER = "catalog.forms.ProjectAdminFormRenderer"
NOVA_ADMIN_ENABLED = True
NOVA_ADMIN_DEFAULT_MODE = "light"
PROJECT_ADMIN_COMPACT = False

# 项目模板优先；nova_admin 仍在 django.contrib.admin 之前。
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]
# 保留现有 context_processors，并添加下面两个：
# "nova_admin.context_processors.theme"
# "catalog.context_processors.project_admin"
```

这不是将 `NOVA_ADMIN_DEFAULT_MODE` 的库默认值改为 light。示例首次访问默认浅色，已有会话明确选择 dark、light、auto 或 native 时仍使用该选择。设置 `PROJECT_ADMIN_COMPACT=True` 可在任一 Nova 模式上叠加紧凑布局。

示例固定默认中文；如果宿主需要根据用户语言选择翻译，可按 Django 文档配置 `LocaleMiddleware`，放在 `SessionMiddleware` 之后、`CommonMiddleware` 之前。测试使用 `translation.override()` 验证当前语言。项目自定义的业务模型名和演示数据本来就是中文，切换英语不会替宿主翻译这些字面量。

## 项目词典及真实消息 ID

`demo/locale/zh_Hans/LC_MESSAGES/django.po` 和编译的 `django.mo` 一起交付。项目 `LOCALE_PATHS` 目录的翻译优先于应用目录；因此这里的通用文案会同时影响 Nova 和 Django 原生模式。这是有意的产品文案定制。

已逐一核对安装的 Django 5.2.17、6.0.8、6.1.1 中的 `contrib/admin/views/main.py`、`options.py`、`helpers.py`、admin 模板、auth 模型和翻译目录：

| 页面/控件 | 实际 msgid | 项目中文 |
| --- | --- | --- |
| 空白选择项 | `- Select an option -` | 请选择 |
| 可修改列表标题 | `Select %s to change` | `%s列表` |
| 只读列表标题 | `Select %s to view` | `%s列表` |
| 应用列表新增链接 | `Add` | 新增 |
| ModelAdmin 新增页标题 | `Add %s` | `新增%s` |
| 列表工具/新增页面包屑 | `Add %(name)s` | `新增%(name)s` |
| inline 新增文案 | `Add another %(verbose_name)s` | `新增%(verbose_name)s` |
| 关联对象新增链接提示 | `Add another %(model)s` | `新增%(model)s` |
| 退出按钮 | `Log out` | 退出登录 |
| Group 单数/复数模型名 | `group` / `groups` | 用户组 |
| 分面统计开关 | `Show counts` | 显示数量 |
| 菜单搜索占位 | `Start typing to filter…` | 搜索菜单… |
| 首页眉题 | `Site overview`，context=`Nova Admin` | 工作台 |
| 首页说明 | `Manage models and everyday work. Available content depends on your site permissions.`，context=`Nova Admin` | 管理内容数据 |

用户所需的“`%(verbose_name)s列表`”最终显示为“商品列表”；这三个 Django 版本的列表标题源消息实际都使用位置占位符 `%s`，所以词典也保留 `%s`，不会把它改成不兼容的命名占位符。`group` 和 `groups` 是两个独立 gettext ID，不是一个 `msgid_plural`。中文复数头是 `nplurals=1; plural=0;`；没有覆盖的原生复数消息继续使用 Django 自己的翻译。Nova 两条文案保留上下文，不影响同名无上下文消息。

Django 6.1 的默认选择项使用上述可翻译消息；5.2/6.0 使用不可翻译的字面量 `---------`。`ProjectAdminFormRenderer` 只在中文、且空 value 的选项仍为已知默认占位文案时，将其显示为同一条 gettext 翻译。选项 value、selected、attrs、校验和宿主自定义占位文案不变。没有修改 `BLANK_CHOICE_DASH`、`BLANK_CHOICE_LABEL` 或全局字段类。

## 编译，不修改上游

已安装 GNU gettext 时，从 `demo/` 编译项目目录：

```bash
cd demo
PYTHONPATH=../src:. python manage.py compilemessages --locale zh_Hans
```

没有 GNU gettext 时，使用有版本锁定依赖的有界编译脚本。它只读取/写入本项目这一个目录，并检查模糊项、缺失翻译和 `%` 占位符是否匹配：

```bash
python -m pip install -r demo/requirements-localization.txt
python demo/compile_catalog.py
python demo/compile_catalog.py --check
```

两种方式都生成标准 GNU `.mo` 文件。不要在 Django 的 `site-packages` 或 Nova 的 `src/nova_admin/locale/` 中编辑通用文案；不要把项目翻译并入可复用主题包。修改词典后重启应用进程，以清除已加载的翻译缓存。

## 真实标签末尾的全角冒号

标签不是 CSS 伪元素，也没有客户端字符串替换：

- `demo/catalog/forms.py` 的项目 `FORM_RENDERER` 在 Django 选好 `<label>`/`<legend>`、`for`、`id` 和 class 后，把中文数据字段标签末尾统一成一个 `：`，包含普通字段、登录字段与 stacked inline
- checkbox 是“勾选某动作”的短语，保留 Django 故意省略后缀的语义，不强行追加冒号；checkbox 仍在 label 前面，保留 `vCheckboxLabel`、原 input、name、id 和原生提交语义；单选/多选控件内部各选项的文字也不追加冒号
- readonly helper 不走 BoundField renderer，所以项目模板 tag 复制当前 helper 和 form，再使用 Django 原生 `label_tag()` 渲染；不会修改实际表单对象
- tabular inline 的列标题通过项目 filter 使用同一标点规则；表单集管理字段、删除复选框、错误消息和权限条件来自原生模板
- 已有 `:` 或 `：` 会归一化，防止 `::`、`:：` 和 `：：`；原有 escaping/safe 状态保持一致，普通标签中的 HTML 继续转义
- 英语及其他语言直接保留 Django 标签与文案行为

项目只覆盖 `admin/includes/fieldset.html`、`admin/edit_inline/tabular.html`、`admin/actions.html` 与 `admin/base_site.html`。字段集和 tabular 的版本模板在 `demo/templates/project_admin/`；5.2、6.0、6.1 分别保持其原生结构、help/error 顺序及 fieldset/legend 无障碍语义。附有 Django 的 BSD 许可证。测试将这些窄改动模板与当前安装版本原文核对；升级 Django 时应重新核对并运行测试。

## 蓝色及密度，按加载顺序覆盖

`demo/templates/admin/base_site.html` 通过同名模板继承并保留 `block.super`，实际加载顺序是：

1. Django 原生样式
2. `nova_admin/theme.css`
3. `catalog/enterprise.css`
4. 仅紧凑预设启用时的 `catalog/enterprise-compact.css`

以上项目样式只在 `nova_admin_active` 时加载。项目 nonce helper 保留 `csp_nonce` 的转义，不依赖可移除的 Nova 模板标签。蓝色通过 Django/Nova 现有变量覆盖，包括链接、焦点、按钮、选中行；危险操作和成功/错误状态的语义颜色不更改。手动 light/dark 独立于系统配色；auto 默认浅色，只在 `prefers-color-scheme: dark` 中采用深色蓝色变量。

要在另一个宿主套用颜色，把项目 CSS 放入宿主静态目录，在宿主 `admin/base_site.html` 的 `extrastyle` 中置于 `block.super` 之后加载。示例浅色强调色 `#1d4ed8`，深色强调色 `#93c5fd`；修改整组变量可避免按钮、链接和选中状态色调不一致。

紧凑预设的实际内容可直接调整：

```css
body.nova-admin {
  --nova-cell-padding: 7px 12px;
  --nova-form-row-padding: 10px 12px;
  --nova-control-padding-block: 5px;
  --nova-control-padding-inline: 8px;
  --nova-control-min-height: 32px;
  --nova-action-padding: 8px 12px;
  --nova-section-padding: 16px 20px;
}
```

这些变量分别控制表格单元格、表单行、输入控件纵/横内边距、控件最小高度、操作区域和页面内容区域。触摸设备的最小目标尺寸由 Nova 核心单独保证；项目密度层不添加覆盖其触摸保护的选择器。更宽松的变量示例也在 `enterprise.css` 文件末尾，默认注释。

## 原生恢复和验证

选择 native 或关闭 `NOVA_ADMIN_ENABLED` 后，Nova/企业样式不加载；项目中文措辞和标点仍然生效。若要恢复 Django 原生中文措辞，移除项目 `LOCALE_PATHS`；若也要恢复原生标签标点，移除项目 `FORM_RENDERER` 和项目 admin 模板覆盖。此操作与权限/数据库无关。

`tests/test_project_localization.py` 使用临时测试数据库和无可用密码的合成测试用户，覆盖三种语言的真实页面、首页/应用列表/模型新增链接、占位符、只读标题、普通/只读/checkbox 标签、两种 inline、原生恢复、CSRF/权限、默认浅色及样式顺序。测试不创建演示登录账户。

官方参考：[Django 翻译及目录优先级](https://docs.djangoproject.com/en/5.2/topics/i18n/translation/#how-django-discovers-translations)、[表单 renderer](https://docs.djangoproject.com/en/5.2/ref/forms/renderers/)、[admin 模板覆盖](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/#overriding-admin-templates)。
