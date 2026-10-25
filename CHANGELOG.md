# Changelog

## 0.4.0 — 2026-10-25

- 同步本地集成版，新增 `research_integrations`，按当前 Agent 可见范围返回 MATLAB MCP、Zotero 工具及真实参数 schema。
- 保留原有五个科研工具、两个内嵌技能、配置键和用户数据目录；协同插件继续使用各自的 DSH 执行及权限管线。
- 提供可选 MATLAB MCP、Zotero 兼容派生包、配置预览/备份脚本、29 项科研软件清单与第三方许可说明。
- 继续支持 DSH 0.2.1-rc.2 和 0.2.1-rc.3；Windows / Linux × 两版宿主的打包分发兼容 CI 通过。
- 正式包与本地安装版的 79 个文件逐字节一致。安装、验收范围及可选协同包见 [发布说明](docs/RELEASE-0.4.0.zh-CN.md)。

## 0.3.1 — 2026-10-25

- 保留 DSH rc.2 支持，补齐 rc.3 安装兼容声明及 DSH peer 范围。
- 新增 Windows / Linux × rc.2 / rc.3 官方宿主发行包回归，覆盖工具或技能的注册、执行、渲染和卸载。
- 业务工具、配置和已有用户设置不变；详见 docs/DSH_COMPATIBILITY.md。
