---
name: research-bridge-lab
description: "研究尚未覆盖的本机科研软件接口，构建隔离的桥接原型，以独立科学判据和真实 DSH Agent 验收后并入插件；也用于已有适配器的复杂压力测试。"
---

# Research bridge lab

把用户指定的软件和科研操作转成有证据的能力。普通已支持作业使用
`research-toolkit`；新增接口研究、修复覆盖缺口或设计复杂压力测试时使用本技能。

先读 [接入研究指南](../../docs/bridge-research-guide.md)。候选证据格式及
可复制的 Python wrapper / 原生 adapter 模板在 [extensions](../../docs/extensions/README.md)；它们是开发材料，
不会被运行时自动加载。清单中没有的软件不能通过任意 `engine` 值绕过验证。

## 工作约定

1. 调用 `research_catalog` 和 `research_discover`，核对软件、版本、当前操作与
   能力范围。发现可执行文件只证明文件存在。读取必要的本机公开说明、安装元数据、
   只读接口信息；联网时查目标厂商/项目的官方文档，记录适用版本和查阅日期。
   未确认的命令行选项或 API 保留为未实现项，不能按同类软件猜测。
2. 在用户授权的新研究目录内建立候选原型、合成输入和独立输出目录，另设控制目录。
   复制并填写 `candidate.template.json`；保留可执行文件、输入、生成源码、
   官方接口依据、原生命令及验收文件的路径和哈希，不保存凭据或推理内容。
3. 实现最窄的官方接口。常规只读研究和可逆的本任务开发自行推进；只有确实缺少
   许可、需要不可逆改动用户数据等具体缺口时报告所需条件。已有授权持续有效。
   商业许可/接口缺失如实记为 `blocked`，不以另一软件的结果冒充目标软件。
4. 先让原型真实调用目标程序，再用独立判据检查数值、结构和语义。增加与能力相关的
   非平凡输入、负向样本、重复运行和有界资源测试。Python 包装器能运行、生成了
   某个文件、退出码为零或出现标记，都不能单独证明目标软件原生执行。
5. 原型通过后，显式修改源码副本的 `catalog.py`、相应 adapter、`core.compile_job`
   分派与回归场景；不存在通用 `BaseAdapter` 或动态加载入口。遵循实际
   `compile_job(job, workspace, executables)` 契约，缺依赖时保持 `ready:false`。
6. 使用原生 DSH 宿主验证工具 schema 和生命周期，再让新 DSH 会话中的实际配置模型
   自主调用科研工具。记录目标会话的真实模型标识、`tool/call`、`tool/result`、
   原生结果和正常 `turn/end`，核对独立产物。完成后移除临时控制插件并恢复本次
   配置覆盖；保留报告与恢复材料。直接 `tools.execute` 只能做宿主测试，不能替代
   真实模型验收。

## 结论必须与证据同范围

- `native` / `local_api`：已证明目标程序或其官方计算后端执行了声明的操作；
  不自动证明 GUI 交互、完整产品或所有方法。
- `file_interchange`：只验证交换格式，`application_verified:false`。
- Python 科学栈替代实现：记录实际 Python 后端，不归入另一软件的原生覆盖。
- 超时、许可不明、接口不可用、科学判据失败，都保留为 blocked/failed，不能用空文件
  或陈旧产物补齐。压力测试的规模、次数、通过数和未测部分分别报告。

Windows 新目录的 `WRITE_OWNER` 不可由旧工作区推断。遇到 `grantWrite` 前置权限错误，
使用安装自带 `diagnose-windows-sandbox-acl` 技能，以**新 root 本身**为 `AllowRoot`、
持久控制目录为 `Out`，按官方单次修复/验证/回滚规则处理。正常回归仍用
`workspace-write`；`enforcement:partial` 与单个越界写样本不能扩写成完整隔离。
不要读取授权内容或凭据、终止非本任务拥有的进程、手改权限/删除 deny、扩大修复根目录。
