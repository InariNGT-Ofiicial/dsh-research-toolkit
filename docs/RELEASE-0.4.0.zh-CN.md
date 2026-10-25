# 0.4.0：科研软件清单与协同插件接入

完整支持清单见 [29 项科研软件入口](supported-software.md)，逐项标明原生调用、本地 API、文件交换及验收范围。

新增 `research_integrations`：查询当前 Agent 可见的 MATLAB MCP、Zotero 工具和真实输入 schema。调用仍经过各自的 DSH 原生工具执行与权限管线。首次使用先检测环境并整理简报，再由用户选择建立哪些桥接。

本机实际安装：

- `dsh-research-toolkit` 0.4.0。
- `@lovedheart/dsh-matlab-mcp-plugin` 1.0.0，使用 MathWorks MCP Server v0.15.0。
- `dsh-zotero` 0.2.2-research.1，来自 Hongcheng-LI 的 MIT 源码及本轮原生 JSON 兼容补丁。补丁与原许可均保留。

## 验证

- Python：63 项回归通过。
- 原生 DSH 宿主：rc.2、rc.3 各 14 项通过。
- 官方 skill 工具：rc.2、rc.3 各 3 项通过。
- 协同发现测试：验证调用者作用域传递和注册状态不冒充执行，1 项通过。
- 实际 MATLAB R2026a：五个 MCP 工具注册；工具箱检测、静态代码检查、240 行合成校准数据回归执行通过，系数与独立计算差异小于 `1e-10`。
- 实际 Zotero：隔离配置与四篇合成文献，九个工具注册；检索、合集、条目详情、笔记读取通过。日常文献库未用于测试。

首次 MATLAB 启动超时及原版 Zotero 非 JSON 空字段失败保留在本地诊断记录中，最终规范 Windows 路径/启动环境和 JSON 兼容派生版复测通过。本轮为真实应用加原生宿主验证，没有声称另外完成一轮 LLM 对话验收。

## 使用

安装主插件后，按 [协同插件说明](integrations.md) 安装两份可选协同包并配置本机 MATLAB 路径。配置脚本默认预览，`--apply` 时保存原配置备份。若已有同名 MATLAB 服务或 Zotero 工具，先选择一个实现，避免重复注册。

Simulink `model_*` 扩展、Zotero PDF/附件与写入虽然有对应上游能力，但本轮不将工具注册等同于逐项真实软件验收。Stata、SAS、Origin 仍需要相应环境后的原生验收。
