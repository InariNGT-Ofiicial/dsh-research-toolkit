# 科研工具插件 v0.4.0

0.4.0 正式版同步本地集成功能，继续支持 **DSH 0.2.1-rc.2 与 0.2.1-rc.3**。版本声明为 `>=0.2.1-rc.2 <0.3.0`，无需宿主版本豁免。

新增 `research_integrations`，查询当前 Agent 可见的 MATLAB MCP、Zotero 工具及真实参数。原有五个科研工具、两个内嵌技能和 `pythonPath`、`workspaceRoot`、`maxTimeoutSeconds` 配置保持兼容。可选协同包独立安装，调用继续经过其原生 DSH 工具及权限管线。

从 [v0.4.0 正式发行页](https://github.com/InariNGT-Ofiicial/dsh-research-toolkit/releases/tag/v0.4.0) 下载 `dsh-research-toolkit-0.4.0.tgz` 和 `SHA256SUMS.txt`，核验后安装到实际使用的同一 profile：

```powershell
dsh plugin --profile desktop add "C:\Downloads\dsh-research-toolkit-0.4.0.tgz"
```

刷新插件或重启 DSH 后，科研插件应显示 0.4.0 并处于运行中。科研软件、Python 环境、模型及许可证仍需单独准备，安装过程不携带本机配置、研究数据或文献库。

Windows / Linux × rc.2 / rc.3 的四组打包分发兼容 CI 通过。公开正式包的 79 个文件与本地集成版逐字节一致；详细功能与既有真实应用验收范围见 [0.4.0 发布说明](RELEASE-0.4.0.zh-CN.md)，双版本复现方法见 [宿主兼容说明](DSH_COMPATIBILITY.md)。

MATLAB、Zotero 可选协同包与配置方法见 [协同插件说明](integrations.md)。旧版兼容维护记录保留在 [CHANGELOG](../CHANGELOG.md) 和 [v0.3.1](https://github.com/InariNGT-Ofiicial/dsh-research-toolkit/releases/tag/v0.3.1)。
