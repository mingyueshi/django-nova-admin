# 主题包代码与素材来源

Nova 自有代码、模板、样式、文档与合成 Demo 按本目录的 [MIT 许可证](LICENSE) 提供。`nova_admin/templates/admin/login.html` 相关内容改编自 Django 原生模板；完整 BSD 3-Clause 许可证作为 `nova_admin/LICENSE-DJANGO.txt` 随 wheel 与 sdist 分发。

sdist 内 `demo/templates/project_admin/` 的版本对应字段集与内联片段来自 Django 5.2.17、6.0.8、6.1.1，保留同目录 `DJANGO_LICENSE.txt`。这些片段、Demo 模型与合成图片不进入运行 wheel。

Demo 的三个 WebP 图集是本地 AI 合成素材：头像为虚构成年人，商品没有品牌，新闻场景为虚构。它们不是私人照片、真实人物授权或真实商品背书，也不提供第三方权利的额外保证。图集按允许的本地 key 使用，没有外部图片请求。

Django 和可选 CAPTCHA、Pillow、Axes 等依赖分别安装，保留各自许可证；其代码、字体、解释器、数据库和系统音频工具不内嵌到本主题发行包。仓库静态预览另有 Django/Select2 资源与对应许可证，不属于 Python wheel，参见仓库根目录 `THIRD_PARTY_NOTICES.md`。
