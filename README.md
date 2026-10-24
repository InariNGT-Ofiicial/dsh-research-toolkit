# DSH 科研软件桥接插件

**科研软件太难用？让大肥鱼帮你调度。**

用自然语言告诉 DSH 你想研究什么、有哪些数据、需要什么结果，让 Agent 调用本机科研软件，把分析、绘图和报告串起来。

插件负责发现软件、编译原生作业、执行任务和保存验收证据。你可以查看生成的脚本、软件退出状态、输出文件与校验结果，继续复查和修改研究过程。

## 快速安装

从 [Releases](https://github.com/InariNGT-Ofiicial/dsh-research-toolkit/releases) 下载 `dsh-research-toolkit-0.3.0.tgz`，或使用仓库 `dist/` 中的同一份包，在 DSH 插件管理器中导入并启用。

使用 DSH Desktop 随附命令行也可以安装：

```powershell
dsh plugin --profile desktop add "C:\Downloads\dsh-research-toolkit-0.3.0.tgz"
```

运行环境：Windows、Node.js 24+、DSH 0.2.1-rc.2；Python 及对应科研软件需单独安装。插件配置项为 `pythonPath`、`workspaceRoot`、`maxTimeoutSeconds`。软件位置可通过 `research_discover` 检查；详情见 [安装与配置](docs/dsh-plugin.md)。

## 在 DSH 中这样开始

> 先检查本机有哪些可用科研软件。用 MATLAB 比较三组质量、刚度和阻尼条件，输出模态频率、位移随时间的曲线和能量平衡图；保留脚本和数据，核对结果，再给我一段能放进组会汇报的说明。

Agent 将研究目标整理为明确作业，调用以下五个工具：

| 工具 | 用途 |
|---|---|
| `research_catalog` | 查看支持的软件与操作 |
| `research_discover` | 发现本机可用程序 |
| `research_compile` | 生成原生脚本和运行计划 |
| `research_run` | 调用软件并保存输出 |
| `research_acceptance_report` | 读取执行与产物核验记录 |

作业格式见 [作业契约](docs/jobs.md)，可直接使用 [MATLAB 复杂任务示例](scenarios/chain_dynamics/jobs) 和 [统计学示例](scenarios/statistics)。

## 软件范围

目录目前包含 **29 个软件入口**。按接口类型分为 20 个原生入口、1 个本地 API 入口和 8 个文件交换入口（含 RStudio 工程）；是否可执行取决于实际安装、授权和任务所需依赖。

| 场景 | 主要软件与路线 |
|---|---|
| 统计分析 | R、Scientific Python、jamovi 的 jmv 后端、SPSS；Stata / SAS 原生接口待有环境后验收 |
| 数值计算 | MATLAB、GNU Octave、Julia |
| 绘图与图像 | ImageJ、Inkscape、Graphviz；Origin 接口待有环境后验收 |
| 论文与复现 | Jupyter、Pandoc、Quarto、XeLaTeX / MiKTeX、Git |
| 文档与文献 | LibreOffice、Microsoft Office、Zotero 本地 API |
| 文件与工程交换 | JabRef、EndNote、NVivo、MAXQDA、ATLAS.ti、Prism、JASP、RStudio |

文件交换表示生成或校验对应格式，并不代表接管软件 GUI 或覆盖其全部功能。商业软件需要使用者自行安装并持有有效授权。

免费工具的官方项目页、获取地址与许可说明见 [18 项软件获取清单](docs/software-downloads.json)。科研软件二进制需单独获取。

## 验收情况

早期综合研究任务使用 144 名模拟受试者、4 次随访，共 576 行数据，对统计分析、文档链、图像测量和文献接口进行了逐项验证。

0.3.0 新增 MATLAB `chain_dynamics`，在 MATLAB R2026a 上验证 12、48、96 自由度质量—弹簧—阻尼链，每种规模重复两次，通过独立 SciPy 数值核验。后续在已安装的 DSH 中，由实际 Agent 调用安装版：9 次运行，8 次成功、1 次预期超时，包含关闭绘图和超时后恢复。

已有验收记录还包括 Python 63 项回归、最终解包源码 21 项链动力学与负面对照、14 项原生宿主测试和 3 项技能工具测试。见 [发布与验收说明](docs/RELEASE-0.3.0.zh-CN.md)。这些结论适用于记录中的操作和本机环境。

## 桥接新软件

内置 `research-bridge-lab` 技能和 [陌生科研软件桥接研究指南](docs/bridge-research-guide.md)，支持 Agent 调查 CLI / API / 文件协议，编写独立候选适配器，设计复杂任务与失败对照，通过验收后再并入目录。

## 开发与许可

```powershell
python -B -m unittest discover -s tests -p "test_*.py" -v
python scripts/package_plugin.py --output ./build
```

部分测试需要 [可选科研与测试依赖](requirements-acceptance.txt) 或实际 DSH 宿主。源码使用 [MIT License](LICENSE)；第三方软件按各自许可提供，参见 [第三方说明](THIRD_PARTY_NOTICES.md)。插件不包含商业软件、授权文件、个人数据或配音模型。

欢迎用你自己的研究问题试用，也欢迎通过 Issue 提交新的科研软件、任务样例和适配结果。
