# DSH 同类科研插件协同

本轮实际接入两个互补的社区插件，不合并或改写上游执行代码。`research_integrations` 读取当前 Agent 可见的工具名称与参数，Agent 按这些真实参数调用原工具，继续使用 DSH 权限和审批机制。

| 插件 | 固定源码 | 互补能力 | 选择理由 |
|---|---|---|---|
| [lovedheart/dsh-matlab-mcp-plugin](https://github.com/lovedheart/dsh-matlab-mcp-plugin) 1.0.0 | `d732d36ea281c9dfd59e3039c27559653c28e9ff` | MathWorks 官方 MATLAB MCP、交互式执行、代码检查、单元测试 | Apache-2.0，配置包，无运行时代码或安装生命周期脚本 |
| [Hongcheng-LI/dsh-zotero](https://github.com/Hongcheng-LI/dsh-zotero) 0.2.2 的兼容派生版 `0.2.2-research.1` | `e4042d5139aa81d810b95928d63632f80a32a7ac` + [兼容补丁](compatibility/zotero-lossless-json.patch.md) | 合集、检索、全文、笔记和附件 | MIT，预构建工具入口，补充当前 search/item/children 作业 |

MathWorks 服务端使用 [matlab/matlab-mcp-server v0.15.0](https://github.com/matlab/matlab-mcp-server/releases/tag/v0.15.0)。Windows x64 官方二进制 SHA-256：`a1f67dd917c5731f88399e1671ebe4f6959d2fd520c78dcaa1faf3ad37ea9518`。二进制、MATLAB、许可证和文献库不打进本插件。

## 安装与配置

先安装本插件 0.4.0，再从上述固定提交获取社区插件，使用 DSH Desktop 官方命令安装已审查的包：

```powershell
dsh plugin --profile desktop add C:\Downloads\lovedheart-dsh-matlab-mcp-plugin-1.0.0.tgz C:\Downloads\dsh-zotero-0.2.2-research.1.tgz --ignore-scripts
```

安装后设置实际路径。下列脚本默认仅检查并输出计划，追加 `--apply` 后保存原配置备份并更新专属配置块：

```powershell
node scripts/configure-companions.mjs --profile-root C:\Users\you\.dsh\profiles\desktop --matlab-server C:\Tools\matlab-mcp-server-windows-x64.exe --matlab-root C:\MATLAB\R2026a --workspace C:\ResearchWork
```

脚本保留其他插件配置，并覆盖两条已安装的协同插件配置行。MATLAB 使用独立新会话、无桌面模式、按需启动；显式转发 Windows `WINDIR`，关闭 MCP 遥测，不加载不存在的 Simulink 扩展文件。Zotero 使用本地 `127.0.0.1:23119`，需运行桌面软件并启用本地 API。重启宿主或新建会话后查询 `research_integrations`。

## 调用路线

- 首次接入：`research_catalog`、`research_discover`、`research_integrations` → 软件能力与桥接状态简报 → 用户选择建立或补齐哪些桥接。
- 交互式 MATLAB、Code Analyzer、MATLAB 单元测试：直接调用返回的 `mcp__matlab__*` 工具。
- 已声明的统计或数值作业、输入输出与验收证据：继续 `research_compile` / `research_run` / `research_acceptance_report`。
- 文献合集、全文、附件、笔记读取：直接调用实际注册的 `zotero_*`。文献写入须由用户提出具体操作，首次简报不触碰文献内容。
- Simulink：仅有 MATLAB 基础 MCP 五个工具时，不提供 `model_*`。需另外安装官方 Simulink Agentic Toolkit、注册扩展并实测许可；此配置不把 Simulink 宣称为已验收。

`tools_registered` 只代表当前调用者能看见工具，`application_verified:false` 会保留到有实际任务证据。注册失败、API 未开、缺工具箱和授权问题分别报告；不要用其他引擎的结果冒充。

## 本轮实测

2026-10-25，在本机实际 rc.3 的 ToolRuntime、官方 MCP 客户端与 MathWorks 服务端上，验证 5 个 MATLAB 工具的注册，以及工具箱检测、Code Analyzer 和 240 行合成校准数据回归的实际执行。回归系数通过独立计算核验，容差 `1e-10`。首次启动超时记录保留，最终使用规范 Windows 根路径及完整 Windows 启动环境重测通过。

Zotero 在独立配置、4 篇合成文献的真实软件库中验证：9 个工具注册，检索、合集、条目和笔记读取通过。原始 0.2.2 的条目详情因 `undefined` 可选字段未通过 DSH lossless JSON 校验；兼容派生版只在工具返回边界移除这些可选空字段，并拒绝其他非法 JSON 值。保留原 MIT LICENSE 和源码补丁，不修改 API 请求、参数 schema 或审批路线。PDF 读取、附件和写入工具已注册，本轮未将其注册数等同于真实软件逐项验收。

桥接插件本身的 14 项宿主测试在 rc.2 和 rc.3 均通过；rc.3 的 3 项官方 skill 工具测试与 Python 63 项回归通过。上述是实际软件加原生宿主验收，不宣称本轮另跑了一次真实模型对话。

## 已调查但未一起安装的方案

[MCviseron/dsh-matlab-mcp](https://github.com/MCviseron/dsh-matlab-mcp) 0.9.1 有一键配置、技能与设置页；[James-web11/dsh-matlab-mcp](https://github.com/James-web11/dsh-matlab-mcp) 也提供 MATLAB/Simulink 配置；它们与本轮 MATLAB MCP 服务命名空间重复，避免同时加载。

[Vncntvx/dsh-zotero](https://github.com/Vncntvx/dsh-zotero) 0.13.1 提供 Sources 面板和更多读写工具，要求 rc.3 的多项 UI/会话服务。本轮选用依赖较少的工具插件；后续可切换，但不要同时注册同名 `zotero_*` 工具。

以上资料核对日期为 2026-10-25，来自对应仓库源码。测试与实际应用执行的结果另存交付验收报告，宿主测试不等同于一次真实模型会话。
