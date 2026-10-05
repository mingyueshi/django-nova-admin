# Node 开发工具链兼容范围

核验日期：2026-10-03。此矩阵针对维护源码时的 npm 安装、格式检查与 JavaScript 回归测试。`dist/` 是无需构建的静态源码；查看演示、安装主题及运行 Django Admin 均不需要 Node 服务。

## 已测试的精确版本

实际平台：Linux x64。每一行使用 Node 官方二进制及其自带的 npm，在独立目录执行干净安装，不复用其它 Node 版本的 node_modules。

| Node | npm | 官方阶段（核验日） | 本项目定位 | npm ci / 格式 / 语法 | 前端交互 | 主题 JS |
|---|---|---|---|---|---:|---:|
| 22.23.3 | 10.9.9 | Maintenance LTS | 维护 LTS 边界 | 通过 | 540 | 97 |
| 24.21.0 | 11.19.0 | Active LTS | 推荐开发版本 | 通过 | 540 | 97 |
| 26.10.0 | 11.19.1 | Current | 当前分支已测，非长期承诺 | 通过 | 540 | 97 |

主题 JS 每轮包含导航57项（分别加载Django 5.2.17、6.0.8、6.1.1的官方nav_sidebar.js）、搜索增强8项、验证码刷新11项。全矩阵共1605项前端交互检查、228项主题JS检查。DOM检查不替代浏览器布局、真实服务端认证或真机验收。

Node 22/24的计划EOL分别为2027-04-30、2028-04-30。Node 26在核验日仍是Current，计划2026-10-28进入LTS、2029-04-30 EOL；将来阶段变更不自动等于重新验证。Node 18/20及已结束维护的奇数分支不列为默认维护推荐。

## 依赖边界保持不变

- `package.json`没有新增engines门槛；`package-lock.json`仍为版本3，内容与本轮开始前逐字节一致
- 固定jsdom 26.1.0要求Node >=18；固定Prettier 3.9.9已发布包要求Node >=14。锁中依赖的整体技术门槛为Node 18，这不表示对EOL版本继续提供维护承诺
- Prettier自身源码仓库的开发引擎要求，不应误认为用户运行已发布Prettier包的要求
- 每个npm ci启用engine-strict，使用官方npm registry和原有integrity锁值；安装后核对40个实际包版本及完整依赖树，无自动升级或npm audit fix
- 锁中无需要执行的preinstall/install/postinstall脚本；部分发布包保留prepare元数据，但从registry安装这些包不会执行它。测试安装仍使用`--ignore-scripts`；安装前后package.json和package-lock.json的SHA-256保持一致
- 测试继续显式使用`--experimental-vm-modules`；Node 26的vm.SourceTextModule仍属实验API。没有删除此标记、跳过相关断言或用语法通过冒充交互通过

原先Node 24.19.0的结果是历史单版本证据。本轮没有宣称整个22/24/26分支、全部未来补丁、Windows/macOS/ARM64、其它包管理器或其它npm版本都已经通过。

## 重现检查

从官方发行目录获取所需Node版本，并用同目录SHASUMS256.txt核对SHA-256。解压到独立目录；不要覆盖系统Node。推荐24.21.0。复制源码到新的验证目录，每个版本各一份，保留原锁文件，排除已有node_modules、数据库和环境文件。

在该验证目录中，为本次终端命令临时选择相应Node二进制及其自带npm；不要修改系统或其它项目配置。先确认实际版本：

```bash
node --version
npm --version
npm ci --engine-strict --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org
npm ls --all
npm test
```

`npm test`已经包含Prettier、源码语法及540项DOM检查。以下补充主题脚本测试，Django路径来自已安装的对应官方版本（参数使用自己的绝对路径）：

```bash
node django-theme/scripts/test-navigation.mjs \
  /path/to/django-5.2.17/django/contrib/admin/static/admin/js/nav_sidebar.js \
  /path/to/django-6.0.8/django/contrib/admin/static/admin/js/nav_sidebar.js \
  /path/to/django-6.1.1/django/contrib/admin/static/admin/js/nav_sidebar.js
node django-theme/scripts/test-enhancements.mjs
node django-theme/scripts/test-captcha.mjs
```

本项目没有Node静态打包器或`npm run build`步骤，因而没有虚构构建测试。真实Django只读样本的导出脚本使用Python；本轮相关脚本、主题运行资源与导出资源哈希保持不变，沿用已通过的[七组Python/Django验证](django-theme/COMPATIBILITY.md)，没有重复全矩阵。网站发布归档属于托管流程，不是Node运行时需求，也不是新增源码下载包。

## 官方运行时校验

| Node Linux x64压缩包 | SHA-256 |
|---|---|
| node-v22.23.3-linux-x64.tar.xz | df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de |
| node-v24.21.0-linux-x64.tar.xz | fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6 |
| node-v26.10.0-linux-x64.tar.xz | ca70e9e349de048b9522abb3adc05b3bd6f43c5ffd3ec57916c7da292f59f022 |

下载后的本地压缩包SHA与以下官方HTTPS清单逐一相符，再解压运行。此检查是官方HTTPS校验和验证，不宣称进行了独立GPG签名链验证。

- [官方版本/npm索引](https://nodejs.org/dist/index.json)
- [官方发布生命周期](https://raw.githubusercontent.com/nodejs/Release/main/schedule.json)
- [官方维护状态](https://nodejs.org/en/about/previous-releases)
- [22.23.3校验清单](https://nodejs.org/dist/v22.23.3/SHASUMS256.txt)
- [24.21.0校验清单](https://nodejs.org/dist/v24.21.0/SHASUMS256.txt)
- [26.10.0校验清单](https://nodejs.org/dist/v26.10.0/SHASUMS256.txt)
- [jsdom 26.1.0已发布元数据](https://registry.npmjs.org/jsdom/26.1.0)
- [Prettier 3.9.9已发布元数据](https://registry.npmjs.org/prettier/3.9.9)
- [Node 26.10.0的VM文档](https://github.com/nodejs/node/blob/v26.10.0/doc/api/vm.md)

0.6.0扩展轮保留相同三个精确Node/npm组合，新增5项项目扩展页检查，导航增加21项（每个Django脚本版本7项）；本轮结果以TEST_REPORT.md为准，不改变此前0.5.1记录。
