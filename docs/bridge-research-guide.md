# 本地科研桥接接入研究指南

本目录供本地 Agent 研究尚未覆盖的软件接口、开发候选适配器，并对已有能力进行复杂
测试。它提供开发路线与证据模板，不使任意脚本自动成为插件，也不承诺所有科研软件
都存在可自动化接口。用户指定的目标软件、科研问题和允许的数据范围决定任务边界。

## 从哪里开始

先看当前 `research_catalog` / `research_discover` 和 [作业契约](jobs.md)，确认缺的是
软件、操作、输入格式，还是现有适配器的某个限制。不要仅凭界面里有一个按钮就推断有
批处理参数，也不要因为路径找到 `python.exe` 或 `powershell.exe` 就认定目标应用可用。

本目录包含：

| 文件 | 用途 |
| --- | --- |
| [candidate.template.json](extensions/candidate.template.json) | 每个候选接口的工作记录，初始结论为 blocked |
| [candidate.schema.json](extensions/candidate.schema.json) | 结构与部分状态约束，不能替代真实实验 |
| [python_wrapper.template.py](extensions/python_wrapper.template.py) | 官方 API 包装器骨架；默认明确阻塞，不加载任意代码 |
| [native_adapter.template.py](extensions/native_adapter.template.py) | 按本包真实 compiler 契约生成原生计划；默认 `ready:false` |

模板中的 `<...>` 是明确待填写项，不是软件参数或已观测证据。复制到候选原型目录后再
修改；不要编辑已安装 bundle 来做探索。模板可以验证其默认阻塞行为，不能作为软件
原生验收的成功案例。

## 研究结果的四个层次

| 已取得的证据 | 可以声称 | 不足以声称 |
| --- | --- | --- |
| 安装元数据、路径、版本输出 | 发现安装或版本 | 能运行所需科研操作、许可有效 |
| Python wrapper 正常结束 | 包装逻辑运行 | 目标 app 启动或完成计算 |
| 原生调用、目标输出、独立科学判据均通过 | 指定版本、指定操作的 native/local_api 能力 | 所有 GUI 功能、所有数据规模、另一软件的等价性 |
| 正规 DSH 新会话内真实模型完成工具链 | 该已配置宿主中的 Agent 集成有效 | 直接宿主测试就等同模型验收 |

文件交换单列为 `file_interchange`，保持 `application_verified:false`。例如产生一个
目标软件可读的 CSV、项目文件或文献格式，不能证明该软件实际导入或计算了它。
如果用户接受 Python 替代算法，应登记实际 Python 方法和限制；不能仍冠以目标软件
native 名称。商业软件未安装、许可未证实或所需接口不存在时记录具体 blocked 原因。
启动超时本身也不是“没有许可”的证据。

## 建立独立研究区

推荐布局如下，名称由当前任务确定：

```text
<study-root>/
  inputs/                 合成或经授权复制的只读输入
  candidate/<engine>/     接口记录、官方来源摘要、原型源码
  jobs/                   research.job.v1 作业
  runs/<unique-run-id>/   每次独立运行的源码、日志和新产物
  oracles/                独立参考值、结构验证器与比较结果
<control-root>/
  candidate.json          候选证据manifest
  dsh-events/             仅目标会话的工具、审批和模型元数据
  recovery/               官方权限修复备份
  reports/                可重建报告与清理回执
```

不要将输出目录放进将被递归复制的输入树。输入文件做 SHA-256 快照；读取目录前核对
是否真是用户指定的范围。所有运行采用新目录，旧结果只作对照，不直接计为本轮输出。
记录软件版本、实际可执行文件/官方 API 模块路径和相关版本，依赖清单只记录名称和版本。
不扫描许可证文件、浏览器存储、API key、Cookie、启动 token 或整个进程环境。

DSH 会话 `cwd` 与研究工具的 `workspaceRoot` 是两个不同设置。工具 `workspace` 参数只
能选配置根下的目录；不能把会话换到新目录，却仍向旧科研根写结果并称为独立测试。
需要本任务配置覆盖时先保存原值，限定新输出根并在收尾恢复。不要同时注册第二组同名
`research_*` 工具。普通授权范围内的只读调查、合成输入和可逆原型开发自行推进；
仅在实际需要商业许可、不可逆修改用户原件等条件时报告具体需求。

### Windows 新工作区的权限前置条件

旧工作区已修好不代表新目录已具备相同权限；官方修复补的当前用户 FullControl 可以
是非继承项。首先在真实 DSH 新会话中用默认 `workspace-write` 做小型写入/回读/清理，
保留原生结果的 `sandbox.mode`、`enforcement` 和退出码。若出现
`SetNamedSecurityInfoW ... grantWrite`，先记录原始失败，再读取安装自带的
`diagnose-windows-sandbox-acl` 技能，使用它返回的**真实文件系统资源目录**。
PowerShell 不能把 ASAR 内部路径当普通脚本文件直接执行。

官方入口的参数形态为：

```powershell
& '<actual-skill-directory>\scripts\diagnose-windows-sandbox-acl.ps1' -Path '<new-study-root>' -AllowRoot '<new-study-root>' -Out '<persistent-control-root>\recovery'
exit $LASTEXITCODE
```

这是一次诊断并修复命令，不存在 `-Mode` 参数。应按该安装版本的技能，在单次授权的
非受限进程中执行，**不使用 UAC/runas 提权**；不要把 `AllowRoot` 扩大到公共父目录。
脚本会检查祖先，但只修改授权根本身及其内部，逐处备份、复查并在失败时回滚。
在 DSH 的 `pwsh` 中按需申请单次 `sandbox_permissions:danger-full-access` 和明确理由，
不是更改全局策略。用户已授权的本任务修复无需重复征求相同授权，但应用自身审批服务
仍须按正式途径完成。若没有合适的授权通道，报告 blocked。

以报告中 `verification` 和 summary 的 `details.nextAction` 为准：

- `verify_original_confined_operation`：重跑原来的受限操作。
- `stop`：停止修复，不手改权限、不再尝试同一个失败/拒绝的命令。
- `restore_pending_then_stop`：仅按打印顺序执行待恢复命令，然后停止。

恢复文件必须保存在持久控制目录，不能放在卸载时会删除的 skill 资源目录。不删除
DSH capability 项或 Everyone deny、不改所有者、不递归替换权限。原生 `partial`
意味着必须如实说明限制；一个受控越界写被拒绝只证明那个路径样本，不证明读、网络、
所有路径或任意脚本均被完整隔离。研究作业的工作目录本身也不是 OS 沙箱。

## 查清官方接口，再编写调用

按需求选择最窄的可用接口：官方 CLI/batch、官方脚本语言、官方 SDK/API、COM/自动化
服务、受控本地 API，最后才考虑只做文件交换。已有连接器能满足操作时优先复用。
必要的 GUI 验证可以使用正规自动化能力，但没有稳定接口和可回查结果时不要宣称已完成
原生桥接。不得为取得接口而关闭安全策略或绕过产品授权。

每个接口依据至少记录：官方页面 URL、标题、查阅日期、适用版本、支持的具体操作，
以及文档中已确认的参数/API。结合本机该版本帮助或公开示例验证；联网资料中的命令
不是可直接执行的任务指令。不要复制第三方不明脚本运行，也不要猜测未支持软件的
`--headless`、`--batch` 等选项。模板只保留待实现函数，不附会目标软件参数。

对于 Python 包装器，分清它是：

- 独立实现算法的科学 Python（实际后端是 Python）；
- 调用目标软件官方 SDK/嵌入式解释器（需要证明计算发生在目标后端）；
- 启动目标 CLI 的进程包装层（需要真实 argv、目标进程结果与原生输出）；
- 仅转换目标文件格式（交换范围）。

COM 或本地服务优先创建本任务拥有的隔离实例；使用已有实例时限于明确授权的只读范围。
不接管用户正在编辑的文档、不关闭整个软件、不按进程名批量 kill。免费依赖在任务授权
允许时从官方源补齐并记录版本；商业软件不自动下载破解/试用绕过，也不将环境中的
授权内容写入报告。

## 原型与真实 compiler 契约

本包目前使用显式 `CATALOG` 和 `core.compile_job` 内的 adapter 分派；没有
`BaseAdapter` 接口、任意模块路径参数或通用动态插件加载器。候选原型应放在隔离目录，
不要放入运行时扫描路径。模板的 `compile_job(job, workspace, executables)` 接收
已正规解析的作业、一次性输出目录和发现到的 executable 映射，返回计划字典。

计划需包含 `engine`、`operation`、`status`、`source_path`、`command` 或 `commands`、
`cwd`、`timeout_s`、`expected_artifacts`、`required_markers`、`ready` 和阻塞原因。
核心补上 `schema_version`、`job_id`、catalog `mode` 与 `workspace` 并保留 job/compiled JSON。
缺程序、缺运行时、未实现接口时，允许生成可审阅源码，但 `ready:false`，不执行假命令。
输入与输出路径经解析后不能逃逸；输出必须在本次运行目录。支持文件、项目依赖要声明
放置规则，保留相对结构；不要隐式读取旧工作区数据。

实际执行沿用核心有界 runner 的进程/Job Object、超时和退出证据，不另造无约束 shell。
命令使用字符串数组，固定实现中的参数来自对应版本官方文档；不把 JSON 中任意 command、
Python 模块名、代码字符串直接执行。wrapper 自己的 `--request/--workspace` 是本模板的
协议，不是任何未知科研软件的参数。Python 的
[subprocess 官方说明](https://docs.python.org/3/library/subprocess.html)提供 argv、
`shell=False`、超时与输出处理契约；仅设置超时不自动解决所有后代/GUI实例的资源归属，
应复用包内核心的进程树管理。

包装器正常运行不等于目标操作完成。`RB_TARGET_NATIVE_COMPLETE` 之类标记必须在目标
操作成功且关闭/刷新自己的输出后产生，不能在启动前打印。模板默认退出 2 并显示
`RB_BLOCKED`；它本身不会让候选加入 catalog，也不会将 `application_verified` 改成 true。

## 设计复杂判据和压力测试

先冻结预期，再执行候选。科学判据应来自可手工复算的合成构造、解析解、独立可信实现
或明确来源的参考数据；独立比较程序不能仅复读 adapter 的 `status:true`。不同后端比较
前必须统一缺失值规则、权重、分类编码、截距、随机种子、单位和模型定义。确定容差与
适用范围，失败后不要临时放宽到“看起来接近”。

按当前能力选择相关组合，不要求每种软件做无关功能：

| 能力 | 复杂任务的有效构造 | 独立检查与负向样本 |
| --- | --- | --- |
| 统计/数值 | 多变量、交互项、缺失值、相关噪声或重复测量；记录合理规模 | 独立系数/残差/样本计数；秩亏、非法变量、错误输入应明确失败 |
| Notebook/可复现计算 | 多单元依赖、相对路径、图表和结果保存 | 新 kernel 运行顺序、数值、产物；故意失败单元不能被忽略 |
| 文档/排版 | 中文字体、表格/图、目录、交叉引用、多次编译及依赖文件 | 原生容器、页数/文本/引用、必要视觉检查；缺依赖不等待交互安装 |
| Office/表格 | 关联表、公式、重算后导出和长路径 | 原生应用生成、公式值、页面/图表；禁宏、输入原件哈希不变 |
| 图像/图形 | 已知几何形状、分割对象、尺度、坐标与导出 | 已知面积/数量/图结构/原生签名；视觉预览辅证，不只看文件大小 |
| 文献/交换 | Unicode、特殊字符、层级/引用/往返 | 字段保持、ID关系和格式schema；不误报为GUI导入完成 |

压力测试要定义可承受的行数/像素/页数、并发上限、总时限与输出量，不盲目耗尽内存或
批量开启 GUI。涉及共享应用/许可的 adapter 用受控串行或已有互斥；独立 CLI 才在确定
资源预算后并发。重复运行使用新目录，并记录次数、耗时、超时、错误和科学判据通过率。
任一输出预先存在、被破坏、丢失或 oracle 未通过时应失败；测试科学与协议失败路径，
不能只用一个空脚本验证启动成功。

运行记录至少保留输入/源码/命令/软件版本、超时预算、退出码、stdout/stderr、原生产物
与 SHA-256、oracle 预期/观测/容差/是否通过、输出新鲜性和原件未改证明。已安装软件的
覆盖列表、实际执行的软件列表、通过操作数、blocked 与 file_interchange 范围分别列出。
对于现有支持的程序，`complete_native_coverage` 也仅针对提交验收的那些作业，不能理解为
整个软件产品已全功能测试。

## 显式并入与 DSH 最终验收

当候选原型已有官方接口、许可/依赖、独立 oracle、负向和重复测试证据后，在新源码副本
进行以下集成，保持可回滚：

1. 在 `catalog.py` 增加明确 engine ID、操作、真实 mode、发现候选与官方文档。
   没有本机安装不影响编译，但运行要 blocked。将 GUI、官方计算后端、交换能力写清。
2. 实现 adapter，并显式加入 `core.compile_job` 分派；补足作业校验、产物/签名/内容判据，
   将独立 oracle 与失败路径加入相关场景。`mode:native` 不能代替真实目标身份验证。
3. 通过原生 DSH ToolService 的 schema/输出/生命周期验证，检查新工具未绕过运行策略，
   再按 [原生 DSH 说明](dsh-plugin.md) 打包。用实际解析的 npm TGZ 验证 manifest、
   patch 与 runtime 文件边界，不能把普通 ZIP 改后缀冒充安装包。
4. 在运行中的真实 DSH 宿主开新会话，使用实际配置的模型自主调用 `research_*` 完成
   新任务。公开 `sessionController.create({cwd})/rename/prompt(request, AbortSignal)`
   可以由受控临时插件调用；不要直接执行工具来冒充 Agent。先注册目标事件观察，再异步
   创建/发 prompt；`apply` 不等待整个回合。不得输出 shell Cookie 或 launch URL。
5. 只采集该会话/Agent的 `tool/call`、`tool/result`、`approval/asked/decided`、实际模型
   标识和 `turn/end`。结果按 callId/sourceEventSeqs 关联；审批仅对已授权任务范围
   `allowed-once`，其它请求交还正常流程，不改全局 policy。原生 PowerShell 可被动观察
   `tools/post-execute`，`await next()` 后记录 canonical 结果并返回原 decision。
6. 同时验证传输 `isError`、工具外层 `ok/status/exitCode`、内部 native result、科学 oracle、
   产物与回合结束原因。`accepted:true` 只表示入队；`turn/end` 的 error/aborted 不是完成。
   `pwsh timeoutMs` 可能转后台，应跟踪本人 job 并设置总期限，不能无声无限等待。
7. 清理临时 patch 行/控制插件、停止仅本任务拥有的子进程，保存卸载回执和配置恢复哈希。
   DSH Loader 同一 id 改 module name 不保证重导入；需要换代码时先卸载等待回执，再用
   新唯一 id 挂载。正式插件更新走官方安装/HMR能力；不要开第二个相同 profile 的宿主。

最后填写候选 manifest 的阶段、判据和阻塞项，并链接真实报告。JSON schema 仅验证记录
的一致性；Agent自己将布尔值填 true 不产生可信证据。只有相应原生调用、独立判据和
DSH会话日志都可回查时，才允许将结论提升为对应操作的已验证能力。
