# 上游模板漂移预警

Nova 采用同名模板继承。主题覆盖和 Django 原版必然有差异，因此不能把每个 diff 都当作回归，也不能把“无文本差异”当作兼容保证。

仓库根目录的 `scripts/template_drift.py` 同时输出两份 diff：

- `*.override.diff`：当前 Django 原版与 Nova／项目覆盖的差异，供人工审查改写范围
- `*.upstream.diff`：当前 Django 原版与已审查版本的差异；发现变更或继承链中丢失所用 block 时退出 1，要求审查

审查范围包括主题 base/index/login，以及 Demo 项目 base_site/actions/fieldset/tabular。`ci/template-baselines.json` 保存 5.2.17、6.0.8、6.1.1 原版模板，许可证见 `src/nova_admin/LICENSE-DJANGO.txt`。主题自有 `nova_*` block 不被误当作上游必需 block。版本专属的中文字段呈现片段仍须由集成回归覆盖。

在已安装目标 Django 的环境，从仓库根目录运行：

```bash
python scripts/template_drift.py --output /tmp/nova-drift-6.1.1
```

报告目录必须不存在，脚本不会覆盖旧证据或自动接受新版本。实际 diff 审查及回归通过后，维护者才可明确更新某个稳定版本基线：

```bash
python scripts/template_drift.py --record-reviewed --output /tmp/nova-reviewed-6.1.1
```

主线检查只读取官方源码，不把 main 加入包的支持区间：

```bash
git clone --depth 1 --branch main https://github.com/django/django.git /tmp/django-main
revision=$(git -C /tmp/django-main rev-parse HEAD)
python scripts/template_drift.py --django-root /tmp/django-main/django \
  --label "main@$revision" --output /tmp/nova-drift-main
```

`.github/workflows/upstream-drift.yml` 配置每周一 05:23 UTC 和手动运行，读取官方 Django main 的当次精确 SHA，保存 diff 与源码回归日志；出现变化会使独立预警任务失败，不伪装成已支持分支的失败。它不发布、不修改基线、不创建权限或秘密，也不自动扩大 `Django<6.2` 依赖边界。

当前没有 GitHub 远端，因此这个 cron 只是已准备的工作流，尚未持续运行。接入后须把工作流放在默认分支、启用 Actions，并由维护者查看 GitHub 通知。调度可能延迟，公开仓库长期无活动也可能被停用；不承诺即时响应未来 6.2。

2026-10-03 本地实际观察官方 main `7847227a3fecde4b2a169552b84c60c6286b6025`：7 种上游模板文本与6.1.1基线相同；Python3.14.8 的完整源码实验回归运行314项，产生54个错误、2个预期跳过。错误来自 Demo 中文字段模板明确限制5.2/6.0/6.1的版本闸门及对应测试映射。没有删除闸门、跳过失败或将其记为6.2兼容；后续需审查新分支模板并补项目片段、再做正式矩阵。文本漂移与运行兼容性检查的结果必须分别解读。

参考：[Django 模板覆盖](https://docs.djangoproject.com/en/dev/howto/overriding-templates/)、[Django 发布过程](https://docs.djangoproject.com/en/dev/internals/release-process/)、[GitHub schedule 限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
