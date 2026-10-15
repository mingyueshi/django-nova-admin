# Node 开发工具链兼容范围

核验日期：2026-10-15。Node 用于源码维护、npm 安装、格式及 JavaScript 回归；主题安装和 Django Admin 运行无需 Node 服务。`0.6.1` 本轮使用 macOS ARM64，历史 Linux x64 结果保留在 TEST_REPORT.md，不自动归入本次包。

## 本轮精确版本

| Node | npm | 矩阵定位 | 干净安装/格式/语法 | 前端 | 主题 JS |
|---|---|---|---|---:|---:|
| 22.23.3 | 10.9.9 | Maintenance LTS 边界 | 通过 | 622 | 121 |
| 24.21.0 | 11.19.0 | Active LTS，推荐开发版本 | 通过 | 622 | 121 |
| 26.10.0 | 11.19.1 | Current 已测版本 | 通过 | 622 | 121 |

每组独立源码副本、全新安装 40 个原锁定包，并核对实际 Node/npm 路径和全部依赖版本。主题 JS 是 Django 5.2.17/6.0.8/6.1.1 三份官方导航脚本的 78 项，加列表增强 32 项、验证码 11 项。三组合计 1,866 项前端和 363 项主题 JS；DOM 检查不替代真实浏览器布局或服务端认证。

2026-10-15 较早的 Node 22.23.1/npm10.9.8、26.5.0/npm11.17.0 及两版 Django 导航的 95 项结果只作历史补充，本轮没有用它们替代精确矩阵。最终源码身份与报告见 [发行验证](django-theme/RELEASE_VALIDATION.md)。

## 安装与支持边界

- `package.json` 不新增 engines 门槛，`package-lock.json` 保持原版本 3 和内容；不自动升级或执行 audit fix。
- jsdom 26.1.0 要求 Node >=18；锁中依赖技术门槛不代表继续维护 EOL 的 Node 18/20。
- 三组使用官方 Node 运行时及匹配 npm。新下载的压缩包先对官方 HTTPS `SHASUMS256.txt` 校验，再解压到任务专用目录；已有 Node24 核对实际二进制及 npm 版本，不覆盖系统设置。
- npm ci 启用 engine-strict、ignore-scripts，核对原锁中的 integrity 与全部 40 个安装版本；记录安装和依赖树。没有改 package.json 或 package-lock.json。
- 测试继续使用 `--experimental-vm-modules`，不删除实验标记或跳过断言。本项目无 `npm run build` 静态打包步骤。

Node 22/24 的计划 EOL 为 2027-04-30/2028-04-30；Node26 在核验日仍为 Current，计划 2026-10-28 进入 LTS、2029-04-30 EOL。维护阶段变化不等于重测；精确版本是回归基线，不是最新补丁推荐表。其它补丁、OS/CPU、包管理器/npm 版本不因同属一个分支就自动视为已测。

## 复现

每组在新的源码副本及日志目录执行，PATH 只为该命令选择目标 Node。先核对真实版本，再运行原入口：

```bash
node --version
npm --version
python scripts/ci_support.py sidebars \
  --wheelhouse /absolute/verified-django-wheels --output /absolute/new-sidebars
node scripts/ci_node.mjs --node 24.21.0 --npm 11.19.0 \
  --logs /absolute/new-node-logs --sidebars /absolute/new-sidebars
```

另外两组使用表中对应参数。runner 执行安装、依赖核对、npm test 和三套主题脚本；源码副本之间不复用 node_modules。最终清单必须记录实际版本、源码输入哈希、日志和退出码。

官方依据：[Node 版本/npm 索引](https://nodejs.org/dist/index.json)、[生命周期](https://raw.githubusercontent.com/nodejs/Release/main/schedule.json)、[22.23.3 校验清单](https://nodejs.org/dist/v22.23.3/SHASUMS256.txt)、[24.21.0 校验清单](https://nodejs.org/dist/v24.21.0/SHASUMS256.txt)、[26.10.0 校验清单](https://nodejs.org/dist/v26.10.0/SHASUMS256.txt)。
