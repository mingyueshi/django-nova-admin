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

## 内建业务图标

`django-theme/src/nova_admin/icons.json` 是 Django 主题和静态预览共用的内建图标清单。保留仓库已有的简洁线性路径，新增业务图标为项目内手写线稿，按根目录 MIT 许可提供；没有引入第三方图标整库、字体、CDN 或运行时外部素材。`dist/js/icons-data.js` 由 `scripts/sync_icons.py` 从同一清单生成。这里的图标不包含 `dist/native-admin/` 下的 Django 原生素材，后者继续适用上述 Django 声明。
