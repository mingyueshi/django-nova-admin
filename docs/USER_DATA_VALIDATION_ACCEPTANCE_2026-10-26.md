# 预览用户数据校验与转义：独立验收

日期：2026-10-26（Asia/Shanghai）。对应 [诊断复核第一项](DIAGNOSIS_2026-10-26_REVIEW.md)。结论：**本项本地修复和独立验收通过，产品候选尚未提交。**

实施：原会话 `01a166ed-0e0f-7253-a9aa-e2d6800617d8`。统筹、源码复核及独立验证：当前会话 `01a167ba-833e-7b52-97c7-cac94af2642b`。范围仅限静态预览用户数据，不涉及真实 Django 用户、认证、权限或数据库。

## 候选与 Git 边界

- 产品基线：`c6e3484d33144bff58222e31fdb901e17a1ec0df`。
- 当前本地 `main`：`df4849458a0a71ef8de9b65da02f2a524d0788af`。该提交只新增上一轮诊断复核文档；实施会话在恢复上下文后误执行了历史提交指令，已向用户说明。本轮保留该提交，不改写历史。
- 本地 `origin/main` 跟踪引用仍为 `c6e3484`。本轮未推送，未触发线上 CI；产品修复为工作区中的六文件候选，暂存区为空。
- 已独立逐文件核对基线：除以下五个已跟踪文件外，其余原有文件内容不变；另新增用户数据测试文件。锁文件、版本、Django 代码和工作流均未改动。本文为统筹新增验收记录。

| 冻结候选文件 | SHA-256 |
| --- | --- |
| `dist/js/app.js` | `76debd1d511b3ab15f6202008a9944890dc27c0c027436197594e9994291eea0` |
| `dist/js/scenarios.js` | `8ff062e88fa7210a6b21c1fe3215ae56b0e6ec99fa360d4928dc882fc2c868c4` |
| `package.json` | `c86c35a7d7be2fbfb319ccc1c49156e1c36837a53f9688efac7b8a5d3e28c7a8` |
| `scripts/ci_support.py` | `f654a6926a78bd31c6f2674351029b6cb5c0527eb67b378d63c1832c6fa14c02` |
| `scripts/tests/test_ci_support.py` | `dd5ec23d4baa6ef63100d7465ea804c9d3f84f9175a1062ac030a3f6da60a1a0` |
| `tests/users-data.cjs` | `73cb277c6ce67503b14f2b187d383ebecb6673d539aa1b0c7189243c21cbe299` |

## 修复行为

1. 用户存储读取与新增、编辑共用字段规则：姓名符合现有表单长度、邮箱格式和唯一性规则；角色、状态、团队使用现有选项；编号为唯一正安全整数。加入日期必须是有效的 `YYYY-MM-DD` 日历日期，年份 0001–9999；编辑保留日期，新建沿用当前 UTC 日期。
2. 畸形记录沿用原有整组回退策略。**读取时不覆盖、删除或修补原始 `nova-users`**；合法空数组保持为空。
3. 列表、移动卡片、概览、详情与时间线、组件资料、头像文字和密度表格均转义展示。姓名中的标签字符可保存、编辑，按原始文本显示。
4. 空列表组件页显示“暂无成员”和添加入口。伪造选项、编号溢出会阻止保存并保留表单；存储失败时保留草稿和原记录。CSV 的原始字面内容、引号处理和公式前缀保护继续生效。

## 实际验证

| 执行方 / 层次 | 结果与范围 |
| --- | --- |
| 实施 / 修复前后回归 | 最终新增 62 项在保留的原产品源码上为 40 失败、22 通过；修复后 62 项通过。原始失败日志与退出码保留。 |
| 统筹 / 基线真实 Chrome | 复现团队/日期 HTML 元素注入、数字日期排序报错、空列表组件报错；经正常表单创建 `<b id=probe>甲</b>` 后，原组件页生成实际 HTML 元素。 |
| 统筹 / 最终全量前端 | 独立运行 `npm test`，20 套件、1,397 项全部通过，包含新增 62 项；格式、语法检查通过。测试前后六文件哈希一致并匹配实施冻结清单。 |
| 统筹 / CI 契约 | 独立运行 `python3.12 -m unittest discover -s scripts/tests -p test_ci_support.py -v`，62 项通过。新增套件接入完整性检查，缺套件、重复、失败、顺序、数量和来源校验保留。 |
| 统筹 / 最终 Chrome 存储及展示 | 9 个隔离场景通过：团队/日期标签、数字日期、无效日历、非法角色、null 记录、对象邮箱均安全回退且原存储不变；1440×1000 与 390×844 下合法标签姓名/邮箱按文本展示；空数组跨列表、概览、组件页可用。最终无未捕获页面异常。 |
| 统筹 / 正常表单与恢复 | 使用实际控件新增标签姓名，组件中编辑姓名、团队、角色、状态，刷新后全部保留且日期不变；筛选、排序、窄屏详情正常，无注入元素。 |
| 统筹 / 拒绝与失败路径 | Chrome 中伪造团队选项被拒绝，焦点定位错误字段，原存储不变；模拟存储写入失败后输入与原记录保留。 |
| 统筹 / 实际 CSV 下载 | 下载 `nova-demo-users.csv`，解析实际字节，确认含逗号及引号的 `="1,2"` 姓名正确引用并加公式保护前缀，其余字段保持原值。 |
| 统筹 / 截图目视 | 核对桌面文字展示、窄屏详情和空列表组件截图，内容可读、操作入口可见。截图在有限动画结束后采集，不是自动像素差分。 |
| 实施 / 主题 JS | 本轮实施会话执行 260 项通过；统筹核对执行记录和主题源码未变，未把它写成本会话独立重跑。 |

本地前端运行时：Node v24.21.0 / npm 11.19.0；浏览器：Chrome 155.0.8059.86。390×844 为本机浏览器窄视口，**不是 iPhone/Safari 或 VoiceOver 真机验收**。

## 证据位置与过程异常

统筹原始证据位于忽略目录 `.local/users-review-20261026/`：

- `baseline-browser.json`、`baseline-user-form-to-component.json`：原代码问题复现。
- `independent-final-test-receipt.json`、`independent-final-frontend.log`、`independent-final-ci-contract.log`：独立最终测试、输入哈希及退出码。
- `final-browser-storage-and-surfaces.json`、`final-browser-workflows.json`、`final-browser-csv.json`、`candidate-users.csv`：最终浏览器断言与真实下载。
- `final-scope-verification.json`：候选哈希、源码范围与基线比对。
- `document-commit-incident.json`：误提交文档的范围记录。

实施证据位于 `.local/users-data-20261026/`，包括 `HANDOFF.md`、`candidate-manifest.json`、`candidate.patch`、`before-fix-62.log` 与 `final-logs/`。这些本地忽略文件不是已上传的公开 CI 工件。

截图位于 `output/playwright/users-review-20261026/`：`literal-component-desktop.png`、`literal-detail-mobile.png`、`empty-component-mobile.png`。早期处于动画中的截图保留为 `*-during-animation.png`，不作为最终目视证据。

浏览器早期检查和补拍各出现一次定位等待超时，日志保留为 `candidate-browser.log`、`final-browser-screenshots.log`；未据此认定通过。增加诊断并在冻结候选上完成上述全套断言，补拍空列表使用当前页重新加载后成功。未将未经定位的超时归因为产品缺陷。实施中关于 JavaScript `$` 接受末尾换行的初始推测，经两项实际回归推翻；没有据此修改产品实现，过程记录保留。

## 未执行与下一项

本轮未重装依赖，未运行 Django Python 完整矩阵、线上 CI、真实移动设备/读屏器、人工音频听辨、发布或部署；历史结果不充当本候选验证。人工音频听辨继续按用户决定跳过。

本项完成后，建议按诊断复核顺序处理 README/CI/验收入口的过期状态摘要，保留历史 SHA 和证据。该下一项尚未实施。当前会话继续统筹和独立验证，原实施会话继续负责实现。

本轮使用的 127.0.0.1:4201/4202 测试服务与专用浏览器会话已关闭；清理后再次核对六文件哈希未变、暂存区为空。
